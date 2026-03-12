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

def d(s):
    return base64.b64decode(s).decode('utf-8')

B_URL = d("aHR0cHM6Ly9naXQuZWRlbi1lbXUuZGV2L2FwaS92MS9yZXBvcy9lZGVuLWVtdS9lZGVuL3JlbGVhc2Vz")  # emulator releases endpoint

TARGET_FILE_SUBSTRING = d("YW1kNjQtZ2NjLXN0YW5kYXJkLkFwcEltYWdl")  # target asset identifier

def get_sys_releases(n: int = 2):
    print("Consultando versiones disponibles del emu...")
    req = urllib.request.Request(B_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            import json
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

def get_latest_links(url, max_retries=3):
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
            return unique_links[:2] # type: ignore[index]

        except Exception as e:
            print(f"Intento {attempt + 1} fallido: {e}")
            if attempt < max_retries - 1:
                print("Reintentando en 5 segundos...")
                time.sleep(5)
            else:
                print("Máximo de reintentos alcanzado.")
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
            'Referer': d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQv")
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Descarga completada exitosamente.")
        return True
    except Exception as e:
        print(f"Error al descargar: {e}")
        return False

def main():
    dbx = get_dropbox_client()
    if not dbx:
        print("Error crítico: no se pudo conectar al almacenamiento. Abortando.")
        return

    print("Obteniendo estado del almacenamiento remoto...")
    backed_up: set[str] = get_dropbox_files(dbx)
    any_uploaded = False

    # 1. Procesar Core Environment
    import re as _re
    releases: list[dict[str, Any]] = get_sys_releases(n=2)
    all_core_in_backup = sorted(f for f in backed_up if TARGET_FILE_SUBSTRING in f)
    backed_up_tags = [t for f in all_core_in_backup for t in _re.findall(r'v\d+\.\d+[\d.\-\w]*', f)]

    if all_core_in_backup:
        print(f"emu en backup: {backed_up_tags}")
    else:
        print("No hay versiones del emu en backup aún.")

    for _release in releases:
        latest_release: dict[str, Any] = dict(_release)
        release_tag: str = str(latest_release.get("tag_name", "unknown"))
        core_in_backup = [f for f in backed_up if release_tag in f and TARGET_FILE_SUBSTRING in f]

        if core_in_backup:
            continue  # ya respaldado, pasar al siguiente

        print(f"Procesando versión del emu: {release_tag}")
        target_asset: dict[str, Any] | None = None
        for _asset in latest_release.get("assets", []):
            if not isinstance(_asset, dict):
                continue
            asset: dict[str, Any] = _asset
            asset_name: str = str(asset.get("name", ""))
            if TARGET_FILE_SUBSTRING in asset_name and not asset_name.endswith(".zsync"):
                target_asset = asset
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
            print(f"Error: No se encontró el recurso para la versión {release_tag}")


    # 2. Procesar Licencias
    print("Verificando licencias del sistema...")
    keys_links: list[str] = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvZWRlbi1wcm9kLWtleXMtMTMv")) or []
    if keys_links:
        keys_in_backup = [link.split("/")[-1] for link in keys_links if link.split("/")[-1] in backed_up]
        keys_missing  = [link for link in keys_links if link.split("/")[-1] not in backed_up]
        keys_display  = [(_re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in keys_in_backup]
        print(f"Licencias en backup: {len(keys_in_backup)} de {len(keys_links)} — {keys_display}")
        for link in keys_missing:
            link = str(link)
            file_name = link.split("/")[-1]
            print(f"Nueva licencia encontrada: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name)
                    any_uploaded = True
    else:
        print("ADVERTENCIA: No se pudieron obtener las licencias.")

    # 3. Procesar Actualizaciones de Sistema
    print("Verificando actualizaciones del sistema...")
    sys_links: list[str] = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvbGF0ZXN0LXN3aXRjaC1maXJtd2FyZXMtdjE5Lw==")) or []
    if sys_links:
        sys_in_backup  = [link.split("/")[-1] for link in sys_links if link.split("/")[-1] in backed_up]
        sys_missing    = [link for link in sys_links if link.split("/")[-1] not in backed_up]
        sys_display    = [(_re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in sys_in_backup]
        print(f"Actualizaciones en backup: {len(sys_in_backup)} de {len(sys_links)} — {sys_display}")
        for link in sys_missing:
            link = str(link)
            file_name = link.split("/")[-1]
            print(f"Nueva actualización encontrada: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(dbx, file_name, file_name):
                    backed_up.add(file_name)
                    any_uploaded = True
    else:
        print("ADVERTENCIA: No se pudieron obtener las actualizaciones del sistema.")

    if any_uploaded:
        print("Sincronización completada.")
    else:
        print("No se encontraron nuevas actualizaciones.")

    # Resumen final del estado en Dropbox
    print("\n--- Estado del almacenamiento remoto ---")
    final_core = sorted(f for f in backed_up if TARGET_FILE_SUBSTRING in f)
    final_core_tags = [t for f in final_core for t in _re.findall(r'v\d+\.\d+[\d.\-\w]*', f)]
    print(f"  emu : {final_core_tags if final_core_tags else 'ninguno'}")

    final_keys = [link.split("/")[-1] for link in (keys_links if keys_links else []) if link.split("/")[-1] in backed_up]
    final_keys_display = [(_re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in final_keys]
    print(f"  Licencias  : {final_keys_display if final_keys_display else 'ninguna'}")

    final_sys = [link.split("/")[-1] for link in (sys_links if sys_links else []) if link.split("/")[-1] in backed_up]
    final_sys_display = [(_re.findall(r'\d+\.\d+[\d.]*\.zip', f) or [f])[0] for f in final_sys]
    print(f"  Sistema    : {final_sys_display if final_sys_display else 'ninguno'}")
    print("----------------------------------------")

if __name__ == "__main__":
    main()
