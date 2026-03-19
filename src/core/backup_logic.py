# pyre-ignore-all-errors[21]
"""PESync - Herramienta de sincronización y respaldo para Pro Evolution Soccer."""
from __future__ import annotations
import os
import time
import shutil
import tempfile
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv # type: ignore
import re

# Importar proveedores de almacenamiento
from src.providers.storage_providers import ( # type: ignore
    get_storage_provider,
    StorageProvider
)

# Importar utilidades y red
from src.utils.helpers import ( # type: ignore
    logger,
    BACKUP_CONFIG,
    EMU_ASSET_IDENTIFIER,
    xor_cipher,
    normalize_filename,
    is_license_file,
    is_system_file,
    VERSION_REGEX,
    TAG_REGEX,
    create_shared_progress
)
from src.network.http_utils import ( # type: ignore
    get_emu_releases,
    get_latest_links,
    download_asset
)

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================
load_dotenv()

# ==========================================
# INTERACCIONES CON ALMACENAMIENTO (PROVEEDOR ABSTRACTO)
# ==========================================
def sync_to_storage(
    provider: StorageProvider,
    backed_up: set[str],
    all_items_to_download: list[tuple[str, str, str]],
    all_files_to_delete: list[str]
) -> bool:
    """
    Descarga en paralelo todos los archivos pendientes y los sube en batch.
    
    all_items_to_download: lista de (download_url, file_name, category_name)
    all_files_to_delete: lista de file_name a eliminar del almacenamiento
    """
    any_uploaded = False

    # 1. Descargar en paralelo y subir en lote
    if all_items_to_download:
        temp_dir = tempfile.mkdtemp(prefix="pesync_bulk_")
        downloaded_paths: list[str] = []

        try:
            logger.info(f"[SYNC] Descargando {len(all_items_to_download)} archivos en paralelo...")

            def _download(item: tuple[str, str, str], progress_bar: Any) -> str | None:
                download_url, file_name, category = item
                local_path = os.path.join(temp_dir, file_name)
                logger.info(f"[{category}] Descargando: {file_name}")
                if download_asset(download_url, local_path, progress_bar):
                    return local_path
                logger.error(f"[{category}] Fallo al descargar: {file_name}")
                return None

            with create_shared_progress() as progress:
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(_download, item, progress): item for item in all_items_to_download} # type: ignore
                    for future in as_completed(futures):
                        result = future.result()
                        if result:
                            downloaded_paths.append(result)

            logger.info(f"[SYNC] {len(downloaded_paths)}/{len(all_items_to_download)} archivos descargados correctamente.")

            # Subir todos en paralelo
            if downloaded_paths:
                if provider.upload_files(downloaded_paths):
                    for p in downloaded_paths:
                        backed_up.add(os.path.basename(p))
                    any_uploaded = True

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # 2. Limpiar archivos obsoletos en el almacenamiento
    for f in all_files_to_delete:
        if provider.delete_file(f):
            backed_up.discard(f)

    return any_uploaded


# ==========================================
# RECOPILACIÓN DE PENDIENTES (SOLO LECTURA, SIN DESCARGAS)
# ==========================================
def collect_emu_pending(backed_up: set[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Determina qué versiones del Emu faltan y cuáles son obsoletas. No descarga nada."""
    logger.info("[EMU] Verificando versiones...")
    releases: list[dict[str, Any]] = get_emu_releases(n=BACKUP_CONFIG.get("emu", 2))

    all_core_tags = [str(r.get("tag_name", "unknown")) for r in releases]
    core_in_backup_tags = [
        tag for tag in all_core_tags
        if any(tag in f and EMU_ASSET_IDENTIFIER in f for f in backed_up)
    ]
    logger.info(f"[EMU] En backup: {len(core_in_backup_tags)} de {len(all_core_tags)} - {core_in_backup_tags}")

    items_to_download: list[tuple[str, str, str]] = []
    for release in releases:
        release_tag: str = str(release.get("tag_name", "unknown"))
        if release_tag in core_in_backup_tags:
            continue

        logger.info(f"[EMU] Pendiente: {release_tag}")
        target_asset: dict[str, Any] | None = next(
            (
                asset for asset in release.get("assets", [])
                if isinstance(asset, dict)
                and EMU_ASSET_IDENTIFIER in str(asset.get("name", ""))
                and not str(asset.get("name", "")).endswith(".zsync")
            ),
            None,
        )
        if target_asset:
            download_url = str(target_asset.get("browser_download_url", ""))
            file_name = str(target_asset.get("name", ""))
            if download_url:
                items_to_download.append((download_url, file_name, "EMU"))
        else:
            logger.error(f"[EMU] No se encontró el asset para {release_tag}")

    desired_emu_files = {
        asset.get("name", "")
        for release in releases
        for asset in release.get("assets", [])
        if EMU_ASSET_IDENTIFIER in asset.get("name", "") and not asset.get("name", "").endswith(".zsync")
    }
    files_to_delete = [
        f for f in backed_up
        if EMU_ASSET_IDENTIFIER in f and f not in desired_emu_files
    ]

    return items_to_download, files_to_delete


def collect_generic_pending(
    backed_up: set[str],
    url: str,
    config_key: str,
    category_name: str,
    file_pattern: str,
    exclude_pattern: str | None = None
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Determina qué archivos genéricos (firmware/sistema) faltan. No descarga nada."""
    logger.info(f"[{category_name}] Verificando archivos...")
    links: list[str] = get_latest_links(url, limit=BACKUP_CONFIG.get(config_key, 2)) or []

    if not links:
        logger.warning(f"[{category_name}] ADVERTENCIA: No se pudieron obtener los archivos.")
        return [], []

    remote_norm = {normalize_filename(link.split("/")[-1]): link for link in links}
    local_norm = {
        normalize_filename(f): f for f in backed_up
        if file_pattern in f.lower() and (not exclude_pattern or exclude_pattern not in f.lower())
    }

    remote_keys = set(remote_norm.keys())
    local_keys = set(local_norm.keys())

    in_backup_norm = remote_keys & local_keys
    missing_norm = remote_keys - local_keys

    display = [re.sub(r'(?i)\.zip$', '', (VERSION_REGEX.findall(local_norm[nl]) or [local_norm[nl]])[0]) for nl in in_backup_norm]
    logger.info(f"[{category_name}] En backup: {len(in_backup_norm)} de {len(links)} - {display}")

    items_to_download: list[tuple[str, str, str]] = [
        (remote_norm[nl], remote_norm[nl].split("/")[-1], category_name)
        for nl in missing_norm
    ]
    files_to_delete = [
        raw_f for nl, raw_f in local_norm.items() if nl not in remote_keys
    ]

    return items_to_download, files_to_delete


# ==========================================
# PUNTO DE ENTRADA (ENTRYPOINT)
# ==========================================

def display_backup_summary(backed_up: set[str]):
    """Imprime un resumen formateado del estado actual del backup."""
    logger.info("="*40)
    logger.info("ESTADO ACTUAL DEL BACKUP".center(40))
    logger.info("="*40)

    final_emu = sorted(f for f in backed_up if EMU_ASSET_IDENTIFIER in f)
    emu_tags = [t for f in final_emu for t in TAG_REGEX.findall(f)]
    logger.info(f"  Emu        : {emu_tags if emu_tags else 'ninguno'}")

    final_keys = {normalize_filename(f) for f in backed_up if is_license_file(f)}
    keys_display = [re.sub(r'(?i)\.zip$', '', (VERSION_REGEX.findall(f) or [f])[0]) for f in sorted(final_keys)]
    logger.info(f"  Licencias  : {keys_display if keys_display else 'ninguna'}")

    final_sys = {normalize_filename(f) for f in backed_up if is_system_file(f)}
    sys_display = [re.sub(r'(?i)\.zip$', '', (VERSION_REGEX.findall(f) or [f])[0]) for f in sorted(final_sys)]
    logger.info(f"  Sistema    : {sys_display if sys_display else 'ninguno'}")
    logger.info("="*40)

def main():
    # Banner de inicio de sesión
    logger.info("="*60)
    logger.info("INICIANDO NUEVA SESION DE SINCRONIZACION".center(60))
    logger.info(f"Sesion: {time.strftime('%Y-%m-%d %H:%M:%S')}".center(60))
    logger.info("="*60)

    # Obtener proveedor de almacenamiento
    provider = get_storage_provider()
    if not provider:
        logger.critical("[CRÍTICO] Error: no se pudo obtener el proveedor de almacenamiento. Abortando...")
        return

    if not provider.connect():
        logger.critical("[CRÍTICO] Error: no se pudo conectar al almacenamiento. Abortando...")
        return

    provider_name = provider.get_provider_name()
    logger.info(f"[{provider_name}] Obteniendo estado del almacenamiento remoto...")
    backed_up: set[str] = provider.list_files()

    # ── Fase 1: Recopilar pendientes de TODAS las categorías ──────────────────
    logger.info("[SYNC] Fase 1: Verificando pendientes en todas las categorías...")
    emu_items, emu_delete = collect_emu_pending(backed_up)

    lic_items, lic_delete = collect_generic_pending(
        backed_up,
        xor_cipher("181107091d59701d404059140e16001d4d3157441d5314001d541e1130561d595309165e485d4c"),
        "licenses",
        "LICENCIAS",
        ".zip",
        "firmware"
    )

    sys_items, sys_delete = collect_generic_pending(
        backed_up,
        xor_cipher("181107091d59701d404059140e16001d4d3157441d5a1111160a1a4e2c45594655184815101c0e28534257455d13424041"),
        "system",
        "SISTEMA",
        "firmware"
    )

    all_items = emu_items + lic_items + sys_items
    all_deletes = emu_delete + lic_delete + sys_delete

    # ── Fase 2: Descargar todo en paralelo y subir en batch ───────────────────
    if all_items or all_deletes:
        logger.info(f"[SYNC] Fase 2: {len(all_items)} archivos pendientes de subir, {len(all_deletes)} a eliminar.")
        any_uploaded = sync_to_storage(provider, backed_up, all_items, all_deletes)
    else:
        any_uploaded = False

    if any_uploaded:
        logger.info("Actualizacion de archivos completada.")
    else:
        logger.info("No hay nuevas actualizaciones.")

    display_backup_summary(backed_up)

if __name__ == "__main__":
    main()

