import os
import urllib.request
import shutil
import time
import base64
from typing import Any
from bs4 import BeautifulSoup # type: ignore
import dropbox # type: ignore
from dropbox.exceptions import ApiError # type: ignore
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo # type: ignore
import re
import json

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
    print(f"Eliminando versión antigua: {file_name}...")
    try:
        dbx.files_delete_v2(f'/{file_name}')
        return True
    except Exception as e:
        print(f"Error al eliminar: {e}")
        return False

def get_sys_releases(n: int = 2) -> list[dict[str, Any]]:
    print("Consultando versiones disponibles del Emu...")
    req = urllib.request.Request(EMU_RELEASES_API_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                print("No se encontraron versiones.")
                return []
            return data[:n]
    except Exception as e:
        print(f"Error al obtener las versiones: {e}")
        return []

def is_valid_link(link: str) -> bool:
    return link.startswith("https://") and link.endswith(".zip")

def get_latest_links(url: str, limit: int = 2, max_retries: int = 3) -> list[str]:
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')

            soup = BeautifulSoup(html, 'html.parser')
            links: list[str] = [str(a['href']) for a in soup.find_all('a', href=True) if is_valid_link(str(a['href']))]

            if not links:
                print("CRÍTICO: No se encontraron recursos válidos. ¡La estructura remota podría haber cambiado!")
                return []

            unique_links: list[str] = list(dict.fromkeys(links))
            return unique_links[:limit] # type: ignore[index]

        except Exception as e:
            print(f"Intento {attempt + 1} fallido: {e}")
            if attempt < max_retries - 1:
                print("Reintentando en 5 segundos...")
                time.sleep(5)
            else:
                print("Máximo de reintentos alcanzado.")
                return []
    return []

def get_dropbox_client():
    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as e:
        print(f"Error: La variable de entorno {e} no está configurada.")
        return None

    try:
        return dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
    except Exception as e:
        print(f"Error al inicializar el cliente de almacenamiento: {e}")
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
    except Exception as e:
        print(f"Error al listar el almacenamiento remoto: {e}")
        return set()

def upload_to_dropbox(dbx, file_path, file_name):
    print(f"Subiendo a Dropbox: {file_name}...")
    try:
        file_size = os.path.getsize(file_path)
        CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
        with open(file_path, 'rb') as f:
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), f'/{file_name}', mode=WriteMode.overwrite)
            else:
                upload_session_start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                cursor = UploadSessionCursor(session_id=upload_session_start.session_id, offset=f.tell()) # type: ignore
                commit = CommitInfo(path=f'/{file_name}', mode=WriteMode.overwrite) # type: ignore

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= CHUNK_SIZE:
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                    else:
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                        cursor.offset = f.tell()

        print("Archivo subido correctamente.")
        return True
    except ApiError as e:
        print(f"Error en la API de almacenamiento: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado al subir: {e}")
        return False

def download_asset(url, file_name):
    print(f"Descargando: {file_name}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQv")
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Descarga completada exitosamente.")
        return True
    except Exception as e:
        print(f"Error al descargar: {e}")
        return False

def process_emu_backups(dbx, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de versiones del Emu."""
    print("[EMU] Verificando versiones...")
    releases: list[dict[str, Any]] = get_sys_releases(n=BACKUP_CONFIG.get("emu", 2))
    any_uploaded = False

    # Identificar qué versiones ya están en el backup
    all_core_tags = [str(r.get("tag_name", "unknown")) for r in releases]
    core_in_backup_tags = []
    
    for tag in all_core_tags:
        if any(tag in f and EMU_ASSET_IDENTIFIER in f for f in backed_up):
            core_in_backup_tags.append(tag)
    
    print(f"[EMU] En backup: {len(core_in_backup_tags)} de {len(all_core_tags)} — {core_in_backup_tags}")

    for _release in releases:
        latest_release: dict[str, Any] = dict(_release)
        release_tag: str = str(latest_release.get("tag_name", "unknown"))
        
        if release_tag in core_in_backup_tags:
            continue

        print(f"[EMU] Procesando versión: {release_tag}")
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
            print(f"[EMU] Error: No se encontró el recurso para la versión {release_tag}")

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
    print("[LICENCIAS] Verificando licencias...")
    any_uploaded = False
    keys_links: list[str] = get_latest_links(decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvZWRlbi1wcm9kLWtleXMtMTMv"), limit=BACKUP_CONFIG.get("licenses", 2)) or []
    
    if keys_links:
        keys_in_backup = [link.split("/")[-1] for link in keys_links if link.split("/")[-1] in backed_up]
        keys_missing  = [link for link in keys_links if link.split("/")[-1] not in backed_up]
        keys_display  = [(re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in keys_in_backup]
        print(f"[LICENCIAS] En backup: {len(keys_in_backup)} de {len(keys_links)} — {keys_display}")
        
        for link in keys_missing:
            file_name = link.split("/")[-1]
            print(f"[LICENCIAS] Nueva licencia encontrada: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name)
                    any_uploaded = True
        
        # Rotación Licencias
        desired_keys_files = [link.split("/")[-1] for link in keys_links]
        for f in list(backed_up):
            if f.endswith(".zip") and re.search(r'\d+\.\d+', f) and "firmware" not in f.lower():
                if f not in desired_keys_files:
                    if delete_from_dropbox(dbx, f):
                        backed_up.remove(f)
    else:
        print("[LICENCIAS] ADVERTENCIA: No se pudieron obtener las licencias.")
    return any_uploaded

def process_system_backups(dbx, backed_up: set[str]) -> bool:
    """Procesa el respaldo y rotación de actualizaciones de sistema."""
    print("[SISTEMA] Verificando actualizaciones...")
    any_uploaded = False
    sys_links: list[str] = get_latest_links(decode_base64("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvbGF0ZXN0LXN3aXRjaC1maXJtd2FyZXMtdjE5Lw=="), limit=BACKUP_CONFIG.get("system", 2)) or []
    
    if sys_links:
        sys_in_backup  = [link.split("/")[-1] for link in sys_links if link.split("/")[-1] in backed_up]
        sys_missing    = [link for link in sys_links if link.split("/")[-1] not in backed_up]
        sys_display    = [(re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in sys_in_backup]
        print(f"[SISTEMA] En backup: {len(sys_in_backup)} de {len(sys_links)} — {sys_display}")
        
        for link in sys_missing:
            file_name = link.split("/")[-1]
            print(f"[SISTEMA] Nueva actualización encontrada: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name)
                    any_uploaded = True
        
        # Rotación Sistema
        desired_sys_files = [link.split("/")[-1] for link in sys_links]
        for f in list(backed_up):
            if f.endswith(".zip") and ("firmware" in f.lower() or "v19" in f.lower()):
                if f not in desired_sys_files:
                    if delete_from_dropbox(dbx, f):
                        backed_up.remove(f)
    else:
        print("[SISTEMA] ADVERTENCIA: No se pudieron obtener las actualizaciones del sistema.")
    return any_uploaded

def main():
    dbx = get_dropbox_client()
    if not dbx:
        print("[CRÍTICO] Error: no se pudo conectar al almacenamiento. Abortando.")
        return

    print("[DROPBOX] Obteniendo estado del almacenamiento remoto...")
    backed_up: set[str] = get_dropbox_files(dbx)
    
    # Procesar secciones
    any_uploaded = any([
        process_emu_backups(dbx, backed_up),
        process_license_backups(dbx, backed_up),
        process_system_backups(dbx, backed_up)
    ])

    if any_uploaded:
        print("[SISTEMA] Sincronización completada.")
    else:
        print("[SISTEMA] No se encontraron nuevas actualizaciones.")

    # Resumen final
    print("\n" + "="*40)
    print("ESTADO FINAL DEL BACKUP".center(40))
    print("="*40)
    
    final_emu = sorted(f for f in backed_up if EMU_ASSET_IDENTIFIER in f)
    emu_tags = [t for f in final_emu for t in re.findall(r'v\d+\.\d+[\d.\-\w]*', f)]
    print(f"  Emu        : {emu_tags if emu_tags else 'ninguno'}")

    final_keys = [f for f in backed_up if f.endswith(".zip") and re.search(r'\d+\.\d+', f) and "firmware" not in f.lower()]
    keys_display = [(re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in final_keys]
    print(f"  Licencias  : {keys_display if keys_display else 'ninguna'}")

    final_sys = [f for f in backed_up if f.endswith(".zip") and ("firmware" in f.lower() or "v19" in f.lower())]
    sys_display = [(re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in final_sys]
    print(f"  Sistema    : {sys_display if sys_display else 'ninguno'}")
    print("="*40)

if __name__ == "__main__":
    main()
