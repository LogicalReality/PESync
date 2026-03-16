from __future__ import annotations
import os
import urllib.request
import shutil
import time
import base64
import logging
import logging.handlers
from typing import Any
from bs4 import BeautifulSoup # type: ignore
import dropbox # type: ignore
from dropbox.exceptions import ApiError # type: ignore
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo # type: ignore
import re
import json

# Constantes de configuración
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos
VERSION_REGEX = re.compile(r'\d+\.\d+[\d.]*\.zip')
TAG_REGEX = re.compile(r'v\d+\.\d+[\d.\-]*\d')

# Configuración del logger
def setup_logger(name: str = "pesync", log_file: str = "pesync.log") -> logging.Logger:
    """Configura y retorna un logger con rotación de archivos."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Evitar duplicados si el logger ya está configurado
    if logger.handlers:
        return logger
    
    # Validar y crear directorio del archivo de log si es necesario
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            # Si no se puede crear el directorio, usar solo console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            logger.addHandler(console_handler)
            logger.error(f"No se pudo crear el directorio de logs '{log_dir}': {e}. Usando solo consola.")
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
    
    # File handler con rotation (guarda todo DEBUG y superior)
    try:
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
        logger.error(f"No se pudo crear el archivo de log '{log_file}': {e}. Usando solo consola.")
    
    logger.addHandler(console_handler)
    
    return logger

# Inicializar logger global
logger = setup_logger()

def decode_base64(s):
    """Decodifica una cadena en base64 a UTF-8."""
    return base64.b64decode(s).decode('utf-8')

EMU_RELEASES_API_URL = decode_base64("aHR0cHM6Ly9naXQuZWRlbi1lbXUuZGV2L2FwaS92MS9yZXBvcy9lZGVuLWVtdS9lZGVuL3JlbGVhc2Vz")  # URL de la API para las versiones del Emu

EMU_ASSET_IDENTIFIER = decode_base64("YW1kNjQtZ2NjLXN0YW5kYXJkLkFwcEltYWdl")  # Fragmento para identificar el binario del Emu

# Configuración de cantidad de versiones a respaldar
BACKUP_CONFIG = {
    "emu": 2,
    "licenses": 2,
    "system": 2
}

def delete_from_dropbox(dbx, file_name):
    logger.info(f"Eliminando versión antigua: {file_name}...")
    try:
        dbx.files_delete_v2(f'/{file_name}')
        return True
    except Exception:
        logger.exception("Error al eliminar:")
        return False

def get_emu_releases(n: int = 2) -> list[dict[str, Any]]:
    req = urllib.request.Request(EMU_RELEASES_API_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                logger.warning("No se encontraron versiones.")
                return []
            return data[:n]
    except Exception:
        logger.exception("Error al obtener las versiones:")
        return []

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

def get_latest_links(url: str, limit: int = 2, max_retries: int = 3) -> list[str]:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')

            soup = BeautifulSoup(html, 'html.parser')
            links: list[str] = [str(a['href']) for a in soup.find_all('a', href=True) if is_valid_link(str(a['href']))]

            if not links:
                logger.critical("No se encontraron recursos válidos. ¡La estructura remota podría haber cambiado!")
                return []

            unique_links: list[str] = list(dict.fromkeys(links))
            return unique_links[:limit] # type: ignore[index]

        except Exception:
            logger.warning(f"Intento {attempt + 1} fallido:")
            if attempt < max_retries - 1:
                logger.info("Reintentando en 5 segundos...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Máximo de reintentos alcanzado.")
                return []
    return []  # Código inalcanzable - eliminado

def get_dropbox_client():
    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as e:
        logger.error(f"Error: La variable de entorno {e} no esta configurada.")
        return None

    try:
        return dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
    except Exception:
        logger.exception("Error al inicializar el cliente de almacenamiento:")
        return None

def get_dropbox_files(dbx) -> set[str]:
    """Returns the set of filenames currently in the Dropbox root folder."""
    try:
        result = dbx.files_list_folder("")
        files: set[str] = {entry.name for entry in result.entries}
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            files.update(entry.name for entry in result.entries)
        return files
    except Exception:
        logger.exception("Error al listar el almacenamiento remoto:")
        return set()

def upload_to_dropbox(dbx, file_path, file_name):
    """Sube un archivo a Dropbox con reintentos y limpieza automática."""
    logger.info(f"Subiendo a Dropbox: {file_name}...")
    try:
        file_size = os.path.getsize(file_path)
        with open(file_path, 'rb') as f:
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), f'/{file_name}', mode=WriteMode.overwrite)
            else:
                # Upload session para archivos grandes
                # Primer chunk
                chunk = f.read(CHUNK_SIZE)
                upload_session_start = dbx.files_upload_session_start(chunk)
                cursor = UploadSessionCursor(session_id=upload_session_start.session_id, offset=len(chunk))
                commit = CommitInfo(path=f'/{file_name}', mode=WriteMode.overwrite)

                #Chunks restantes
                while True:
                    remaining = file_size - cursor.offset
                    if remaining <= CHUNK_SIZE:
                        # Último chunk - finish session
                        chunk = f.read(remaining)
                        dbx.files_upload_session_finish(chunk, cursor, commit)
                        break
                    else:
                        # Chunk intermedio - append
                        chunk = f.read(CHUNK_SIZE)
                        dbx.files_upload_session_append_v2(chunk, cursor)
                        cursor.offset += len(chunk)

        logger.info("Archivo subido correctamente.")
        return True
    except ApiError:
        logger.exception("Error en la API de almacenamiento:")
        return False
    except Exception:
        logger.exception("Error inesperado al subir:")
        return False
    finally:
        # Limpiar archivo temporal
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except OSError:
                pass

def download_asset(url, file_name):
    logger.info(f"Descargando: {file_name}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQv")
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        logger.info("Descarga completada exitosamente.")
        return True
    except Exception:
        logger.exception("Error al descargar:")
        return False

def process_emu_backups(dbx, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de versiones del Emu."""
    logger.info("[EMU] Verificando versiones...")
    releases: list[dict[str, Any]] = get_emu_releases(n=BACKUP_CONFIG.get("emu", 2))
    any_uploaded = False

    # Identificar qué versiones ya están en el backup
    all_core_tags = [str(r.get("tag_name", "unknown")) for r in releases]
    core_in_backup_tags = []
    
    for tag in all_core_tags:
        if any(tag in f and EMU_ASSET_IDENTIFIER in f for f in backed_up):
            core_in_backup_tags.append(tag)
    
    logger.info(f"[EMU] En backup: {len(core_in_backup_tags)} de {len(all_core_tags)} - {core_in_backup_tags}")

    for _release in releases:
        latest_release: dict[str, Any] = _release
        release_tag: str = str(latest_release.get("tag_name", "unknown"))
        
        if release_tag in core_in_backup_tags:
            continue

        logger.info(f"[EMU] Procesando versión: {release_tag}")
        target_asset: dict[str, Any] | None = None
        for _asset in latest_release.get("assets", []):
            if not isinstance(_asset, dict): continue
            asset_name: str = str(_asset.get("name", ""))
            if EMU_ASSET_IDENTIFIER in asset_name and not asset_name.endswith(".zsync"):
                target_asset = _asset
                break

        if target_asset:
            assert target_asset is not None
            download_url: str = str(target_asset["browser_download_url"])
            file_name: str = str(target_asset["name"])
            if download_asset(download_url, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name)
                    any_uploaded = True
        else:
            logger.error(f"[EMU] Error: No se encontró el recurso para la versión {release_tag}")

    # Rotación Emu
    desired_emu_files = []
    for release in releases:
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if EMU_ASSET_IDENTIFIER in name and not name.endswith(".zsync"):
                desired_emu_files.append(name)
    
    for f in list(backed_up):
        if EMU_ASSET_IDENTIFIER in f and f not in desired_emu_files:
            if delete_from_dropbox(dbx, f):
                backed_up.remove(f)
    return any_uploaded

def process_license_backups(dbx, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de licencias del sistema."""
    return process_generic_backup(
        dbx,
        backed_up,
        decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvZWRlbi1wcm9kLWtleXMtMTMv"),
        "licenses",
        "LICENCIAS",
        ".zip",
        "firmware"
    )

def process_system_backups(dbx, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de actualizaciones de sistema."""
    return process_generic_backup(
        dbx,
        backed_up,
        decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvbGF0ZXN0LXN3aXRjaC1maXJtd2FyZXMtdjE5Lw=="),
        "system",
        "SISTEMA",
        "firmware"
    )

def process_generic_backup(
    dbx,
    backed_up: set[str],
    url: str,
    config_key: str,
    category_name: str,
    file_pattern: str,
    exclude_pattern: str | None = None
) -> bool:
    """Procesa respaldo genérico para una categoría de archivos.
    
    Args:
        dbx: Cliente de Dropbox
        backed_up: Set de archivos ya respaldados
        url: URL remota para obtener archivos
        config_key: Clave en BACKUP_CONFIG para límite de versiones
        category_name: Nombre para logs (ej: "LICENCIAS")
        file_pattern: Pattern para identificar archivos de esta categoría
    """
    logger.info(f"[{category_name}] Verificando archivos...")
    any_uploaded = False
    
    links: list[str] = get_latest_links(url, limit=BACKUP_CONFIG.get(config_key, 2)) or []
    
    if links:
        # Normalizar nombres para comparación
        # remote_norm: mapeo de normalized_name -> raw_url_link
        remote_norm = {normalize_filename(link.split("/")[-1]): link for link in links}
        # local_norm: mapeo de normalized_name -> raw_dropbox_filename
        local_norm = {
            normalize_filename(f): f for f in backed_up 
            if file_pattern in f.lower() and (not exclude_pattern or exclude_pattern not in f.lower())
        }
        
        in_backup_norm = [nl for nl in remote_norm if nl in local_norm]
        missing_norm = [nl for nl in remote_norm if nl not in local_norm]
        
        display = [(VERSION_REGEX.findall(local_norm[nl]) or [local_norm[nl]])[0] for nl in in_backup_norm]
        logger.info(f"[{category_name}] En backup: {len(in_backup_norm)} de {len(links)} - {display}")
        
        for nl in missing_norm:
            link = remote_norm[nl]
            file_name = link.split("/")[-1]
            logger.info(f"[{category_name}] Nuevo archivo encontrado: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name) # Guardar nombre original
                    any_uploaded = True
        
        # Rotación de backups
        desired_norm = set(remote_norm.keys())
        for nl, raw_f in local_norm.items():
            if nl not in desired_norm:
                if delete_from_dropbox(dbx, raw_f):
                    backed_up.remove(raw_f)
    else:
        logger.warning(f"[{category_name}] ADVERTENCIA: No se pudieron obtener los archivos.")
    
    return any_uploaded

def main():
    dbx = get_dropbox_client()
    if not dbx:
        logger.critical("[CRÍTICO] Error: no se pudo conectar al almacenamiento. Abortando...")
        return

    logger.info("[DROPBOX] Obteniendo estado del almacenamiento remoto...")
    backed_up: set[str] = get_dropbox_files(dbx)
    
    # Procesar secciones
    any_uploaded = any([
        process_emu_backups(dbx, backed_up),
        process_license_backups(dbx, backed_up),
        process_system_backups(dbx, backed_up)
    ])

    if any_uploaded:
        logger.info("[SISTEMA] Actualizacion de archivos completada.")
    else:
        logger.info("[SISTEMA] No hay nuevas actualizaciones.")

    # Resumen final
    logger.info("="*40)
    logger.info("ESTADO ACTUAL DEL BACKUP".center(40))
    logger.info("="*40)
    
    final_emu = sorted(f for f in backed_up if EMU_ASSET_IDENTIFIER in f)
    emu_tags = [t for f in final_emu for t in TAG_REGEX.findall(f)]
    logger.info(f"  Emu        : {emu_tags if emu_tags else 'ninguno'}")

    final_keys = {normalize_filename(f) for f in backed_up if f.lower().endswith(".zip") and re.search(r'\d+\.\d+', f) and "firmware" not in f.lower()}
    keys_display = [(VERSION_REGEX.findall(f) or [f])[0] for f in sorted(final_keys)]
    logger.info(f"  Licencias  : {keys_display if keys_display else 'ninguna'}")

    final_sys = {normalize_filename(f) for f in backed_up if f.lower().endswith(".zip") and ("firmware" in f.lower() or "v19" in f.lower())}
    sys_display = [(VERSION_REGEX.findall(f) or [f])[0] for f in sorted(final_sys)]
    logger.info(f"  Sistema    : {sys_display if sys_display else 'ninguno'}")
    logger.info("="*40)

if __name__ == "__main__":
    main()
