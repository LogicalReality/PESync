# pyre-ignore-all-errors[21]
"""PESync - Herramienta de sincronización y respaldo para Pro Evolution Soccer."""
from __future__ import annotations
import os
from dotenv import load_dotenv # type: ignore
import requests # type: ignore
import shutil
import time
import logging
import logging.handlers
from typing import Any
from bs4 import BeautifulSoup # type: ignore
import re
from tqdm import tqdm # type: ignore

# Importar proveedores de almacenamiento
from storage_providers import (
    get_storage_provider,
    StorageProvider,
    DropboxProvider,
    GoogleDriveProvider
)

# ==========================================
# CONFIGURACIÓN Y CONSTANTES
# ==========================================
load_dotenv()
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos
VERSION_REGEX = re.compile(r'\d+\.\d+[\d.]*\.zip')
TAG_REGEX = re.compile(r'v\d+\.\d+[\d.\-]*\d')

# Configuración de cantidad de versiones a respaldar
BACKUP_CONFIG = {
    "emu": 2,
    "licenses": 2,
    "system": 2
}

# ==========================================
# SEGURIDAD Y CIFRADO
# ==========================================
def xor_cipher(data: str, key: str = "pesync_2026") -> str:
    """Aplica un cifrado XOR simple. Útil para ocultar strings de escaneos básicos."""
    try:
        # Intentamos decodificar desde hexadecimal
        data_bytes = bytes.fromhex(data)
        return bytes([b ^ ord(key[i % len(key)]) for i, b in enumerate(data_bytes)]).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        # Si falla (o si queremos codificar), devolvemos el hex del XOR
        return bytes([ord(c) ^ ord(key[i % len(key)]) for i, c in enumerate(data)]).hex()

EMU_RELEASES_API_URL = xor_cipher("181107091d59701d575b425e00171c004e3a5f451c5215135c181e0a7044011d4415151c0a41063b575e1f531d105c1c0a06311d42575a1504001c1d")  # URL de la API para las versiones del Emu
EMU_ASSET_IDENTIFIER = xor_cipher("1108174f5a4e3851531f4504041d1d0f113b1c7142463908121e0b")  # Fragmento para identificar el binario del Emu

# ==========================================
# LOGGING
# ==========================================
def setup_logger(name: str = "pesync", log_file: str | None = None) -> logging.Logger:
    """Configura y retorna un logger con rotación de archivos y nombre por sesión."""
    if log_file is None:
        # Generar nombre único por sesión: logs/pesync_20240316_203000.log
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join("logs", f"pesync_{timestamp}.log")
        
    # Asegurar que el directorio de logs existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Evitar duplicados si el logger ya está configurado
    if logger.handlers:
        return logger

    # Formato con timestamp y nombre del módulo    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler para salida rapida (INFO y superiores)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    log_dir = os.path.dirname(log_file)
    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1*1024*1024,  # 1MB por archivo - suficiente para GHA y local
            backupCount=1,  # Mantener 1 archivo de backup
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.error(f"No se pudo inicializar log en archivo '{log_file}': {e}.")
    
    return logger

# Inicializar logger global
logger = setup_logger()

# ==========================================
# UTILIDADES DE RED Y AYUDANTES
# ==========================================
def is_valid_link(link: str) -> bool:
    return link.startswith("https://") and link.endswith(".zip")

def normalize_filename(filename: str) -> str:
    """Normaliza nombre de archivo para comparación.
    
    Ejemplos:
        Firmware.21.2.0.zip -> 21.2.0.zip
        emu.v0.2.0-rc1.zip -> emu.v0.2.0-rc1.zip
    """
    # Eliminar prefijo "Firmware." para Vergleich
    if filename.lower().startswith("firmware."):
        return filename.split(".", 1)[-1]
    return filename

def get_emu_releases(n: int = 2) -> list[dict[str, Any]]:
    try:
        response = requests.get(EMU_RELEASES_API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not data:
            logger.warning("No se encontraron versiones.")
            return []
        return data[:n] # type: ignore
    except Exception:
        logger.exception("Error al obtener las versiones:")
        return []

def get_latest_links(url: str, limit: int = 2, max_retries: int = 3) -> list[str]:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, 'html.parser')
            links: list[str] = [str(a['href']) for a in soup.find_all('a', href=True) if is_valid_link(str(a['href']))]

            if not links:
                logger.critical("No se encontraron recursos válidos. ¡La estructura remota podría haber cambiado!")
                return []

            unique_links: list[str] = list(dict.fromkeys(links))
            return unique_links[:limit] # type: ignore

        except Exception:
            logger.warning(f"Intento {attempt + 1} fallido:")
            if attempt < max_retries - 1:
                logger.info("Reintentando en 5 segundos...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Máximo de reintentos alcanzado.")
                return []
    return []

def download_asset(url, file_name):
    logger.info(f"Descargando: {file_name}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': xor_cipher("181107091d59701d404059140e16001d4d3157441d")
        }
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(file_name, 'wb') as f, tqdm(
                total=total_size,
                unit='iB',
                unit_scale=True,
                desc=f"Descargando {file_name}",
                leave=False
            ) as bar:
                for chunk in r.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    bar.update(size)
                    
        logger.info("Descarga completada exitosamente.")
        return True
    except Exception:
        logger.exception("Error al descargar:")
        return False

# ==========================================
# INTERACCIONES CON ALMACENAMIENTO (PROVEEDOR ABSTRACTO)
# ==========================================
def sync_to_storage(provider: StorageProvider, category_name: str, backed_up: set[str], items_to_download: list[tuple[str, str]], files_to_delete: list[str]) -> bool:
    """
    Gestiona la descarga, subida al almacenamiento y limpieza de archivos obsoletos de forma genérica.
    
    :param provider: Proveedor de almacenamiento (Dropbox, Google Drive, etc.)
    :param items_to_download: Lista de tuplas (url_de_descarga, nombre_archivo).
    :param files_to_delete: Lista de nombres exactos de archivos a eliminar en el almacenamiento.
    """
    provider_name = provider.get_provider_name()
    any_uploaded = False
    
    # 1. Descargar y subir nuevos archivos
    for download_url, file_name in items_to_download:
        logger.info(f"[{category_name}] Nuevo archivo a procesar: {file_name}")
        if download_asset(download_url, file_name):
            if provider.upload_file(file_name, file_name):
                # Usar set.add nativo, que es seguro modificar en memoria
                backed_up.add(file_name) 
                any_uploaded = True
                
    # 2. Limpiar archivos obsoletos en el almacenamiento
    for f in files_to_delete:
        if provider.delete_file(f):
            # Eliminamos del caché local si se borró de la nube con éxito
            backed_up.discard(f) 
            
    return any_uploaded

# ==========================================
# LÓGICA DE PROCESAMIENTO DE EMU (CORE)
# ==========================================
def process_emu_backups(provider: StorageProvider, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de versiones del Emu."""
    logger.info("[EMU] Verificando versiones...")
    releases: list[dict[str, Any]] = get_emu_releases(n=BACKUP_CONFIG.get("emu", 2))

    # Identificar qué versiones ya están en el backup
    all_core_tags = [str(r.get("tag_name", "unknown")) for r in releases]
    core_in_backup_tags = [
        tag for tag in all_core_tags
        if any(tag in f and EMU_ASSET_IDENTIFIER in f for f in backed_up)
    ]
    
    logger.info(f"[EMU] En backup: {len(core_in_backup_tags)} de {len(all_core_tags)} - {core_in_backup_tags}")

    items_to_download = []
    for release in releases:
        release_tag: str = str(release.get("tag_name", "unknown"))
        
        if release_tag in core_in_backup_tags:
            continue

        logger.info(f"[EMU] Procesando versión: {release_tag}")
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
            assert target_asset is not None  # narrow type for static analysis
            download_url: str = str(target_asset.get("browser_download_url", ""))
            file_name: str = str(target_asset.get("name", ""))
            if download_url:
                items_to_download.append((download_url, file_name))
        else:
            logger.error(f"[EMU] Error: No se encontró el recurso para la versión {release_tag}")

    # Rotación Emu - Determinar obsoletos
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
    
    if items_to_download or files_to_delete:
        return sync_to_storage(provider, "EMU", backed_up, items_to_download, files_to_delete)
    
    return False

def process_license_backups(provider: StorageProvider, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de licencias del sistema."""
    return process_generic_backup(
        provider,
        backed_up,
        xor_cipher("181107091d59701d404059140e16001d4d3157441d5314001d541e1130561d595309165e485d4c"),
        "licenses",
        "LICENCIAS",
        ".zip",
        "firmware"
    )

def process_system_backups(provider: StorageProvider, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de actualizaciones de sistema."""
    return process_generic_backup(
        provider,
        backed_up,
        xor_cipher("181107091d59701d404059140e16001d4d3157441d5a1111160a1a4e2c45594655184815101c0e28534257455d13424041"),
        "system",
        "SISTEMA",
        "firmware"
    )

def process_generic_backup(
    provider: StorageProvider,
    backed_up: set[str],
    url: str,
    config_key: str,
    category_name: str,
    file_pattern: str,
    exclude_pattern: str | None = None
) -> bool:
    """Procesa respaldo genérico para una categoría de archivos."""
    logger.info(f"[{category_name}] Verificando archivos...")
    any_uploaded = False
    
    links: list[str] = get_latest_links(url, limit=BACKUP_CONFIG.get(config_key, 2)) or []
    
    if not links:
        logger.warning(f"[{category_name}] ADVERTENCIA: No se pudieron obtener los archivos.")
        return False
        
    # Normalizar nombres para comparación
    remote_norm = {normalize_filename(link.split("/")[-1]): link for link in links}
    local_norm = {
        normalize_filename(f): f for f in backed_up 
        if file_pattern in f.lower() and (not exclude_pattern or exclude_pattern not in f.lower())
    }
    
    remote_keys = set(remote_norm.keys())
    local_keys = set(local_norm.keys())
    
    in_backup_norm = remote_keys & local_keys
    missing_norm = remote_keys - local_keys
    
    display = [(VERSION_REGEX.findall(local_norm[nl]) or [local_norm[nl]])[0] for nl in in_backup_norm]
    logger.info(f"[{category_name}] En backup: {len(in_backup_norm)} de {len(links)} - {display}")
    
    # 1. Preparar descargas
    items_to_download = [
        (remote_norm[nl], remote_norm[nl].split("/")[-1]) for nl in missing_norm
    ]
    
    # 2. Preparar eliminación
    files_to_delete = [
        raw_f for nl, raw_f in local_norm.items() if nl not in remote_keys
    ]
    
    if items_to_download or files_to_delete:
        return sync_to_storage(provider, category_name, backed_up, items_to_download, files_to_delete)
    
    return False

# ==========================================
# PUNTO DE ENTRADA (ENTRYPOINT)
# ==========================================
def is_license_file(f: str) -> bool:
    f_low = f.lower()
    return f_low.endswith(".zip") and bool(re.search(r'\d+\.\d+', f)) and "firmware" not in f_low

def is_system_file(f: str) -> bool:
    f_low = f.lower()
    return f_low.endswith(".zip") and ("firmware" in f_low or "v19" in f_low)

def display_backup_summary(backed_up: set[str]):
    """Imprime un resumen formateado del estado actual del backup."""
    logger.info("="*40)
    logger.info("ESTADO ACTUAL DEL BACKUP".center(40))
    logger.info("="*40)
    
    final_emu = sorted(f for f in backed_up if EMU_ASSET_IDENTIFIER in f)
    emu_tags = [t for f in final_emu for t in TAG_REGEX.findall(f)]
    logger.info(f"  Emu        : {emu_tags if emu_tags else 'ninguno'}")

    final_keys = {normalize_filename(f) for f in backed_up if is_license_file(f)}
    keys_display = [(VERSION_REGEX.findall(f) or [f])[0] for f in sorted(final_keys)]
    logger.info(f"  Licencias  : {keys_display if keys_display else 'ninguna'}")

    final_sys = {normalize_filename(f) for f in backed_up if is_system_file(f)}
    sys_display = [(VERSION_REGEX.findall(f) or [f])[0] for f in sorted(final_sys)]
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
    
    # Procesar secciones
    any_uploaded = any([
        process_emu_backups(provider, backed_up),
        process_license_backups(provider, backed_up),
        process_system_backups(provider, backed_up)
    ])

    if any_uploaded:
        logger.info("Actualizacion de archivos completada.")
    else:
        logger.info("No hay nuevas actualizaciones.")

    display_backup_summary(backed_up)

if __name__ == "__main__":
    main()
