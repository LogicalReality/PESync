import os
import json
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
R_URL = d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQv")  # base reference
STATE_FILE = "state.json"

TARGET_FILE_SUBSTRING = "amd64-gcc-standard.AppImage"

def get_latest_sys_version():
    print("Sincronizando componente...")
    req = urllib.request.Request(B_URL, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                print("No se encontraron versiones.")
                return None
            return data[0]
    except Exception as e:
        print(f"Error al obtener las versiones: {e}")
        return None

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

def upload_to_dropbox(file_path, file_name):
    print(f"Subiendo {file_name}...")

    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as e:
        print(f"Advertencia: La variable de entorno {e} no está configurada.")
        return False

    try:
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )

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

        print("¡Subida exitosa!")
        return True
    except ApiError as e:
        print(f"Error en la API de almacenamiento: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado al subir: {e}")
        return False

def load_state() -> dict[str, Any]:
    state: dict[str, Any] = {"core_v": "", "prod_keys": [], "sys_comps": []}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state.update(json.load(f))
    return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def download_asset(url, file_name):
    print(f"Sincronizando {file_name}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQv")
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print("Descarga completada.")
        return True
    except Exception as e:
        print(f"Error al descargar: {e}")
        return False

def main():
    state = load_state()
    state_changed = False

    # 1. Procesar Core Environment
    latest_release: dict[str, Any] | None = get_latest_sys_version()
    if latest_release:
        release_tag: str = str(latest_release.get("tag_name", "unknown"))
        if state["core_v"] != release_tag:
            print(f"Nueva actualización detectada: {release_tag}")
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
                    if upload_to_dropbox(file_name, file_name):
                        state["core_v"] = release_tag
                        state_changed = True
            else:
                print(f"Error: No se encontró el recurso para la actualización {release_tag}")
        else:
            print(f"El componente {release_tag} ya está actualizado.")

    # 2. Procesar Assets de Metadata
    print("Verificando metadata keys...")
    keys_links: list[str] = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvZWRlbi1wcm9kLWtleXMtMTMv")) or []
    if keys_links:
        prod_keys: list[str] = list(state.get("prod_keys", []))
        new_keys = [link for link in keys_links if link not in prod_keys]
        if not new_keys:
            print("Las metadata keys ya están actualizadas.")
        for link in new_keys:
            link = str(link)
            file_name = link.split("/")[-1]
            print(f"Nueva key encontrada: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    prod_keys.append(str(link))
                    state["prod_keys"] = prod_keys
                    state_changed = True

        if len(prod_keys) > 2:
            state["prod_keys"] = [k for k in keys_links if k in prod_keys]
            state_changed = True
    else:
        print("ADVERTENCIA: No se pudieron obtener los links de metadata keys.")

    # 3. Procesar Componentes de Sistema
    print("Verificando firmware del sistema...")
    sys_links: list[str] = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvbGF0ZXN0LXN3aXRjaC1maXJtd2FyZXMtdjE5Lw==")) or []
    if sys_links:
        sys_comps: list[str] = list(state.get("sys_comps", []))
        new_sys = [link for link in sys_links if link not in sys_comps]
        if not new_sys:
            print("El firmware del sistema ya está actualizado.")
        for link in new_sys:
            link = str(link)
            file_name = link.split("/")[-1]
            print(f"Nuevo firmware encontrado: {file_name}")
            if download_asset(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    sys_comps.append(str(link))
                    state["sys_comps"] = sys_comps
                    state_changed = True

        if len(sys_comps) > 2:
            state["sys_comps"] = [f for f in sys_links if f in sys_comps]
            state_changed = True
    else:
        print("ADVERTENCIA: No se pudieron obtener los links de firmware.")

    if state_changed:
        save_state(state)
        print("Estado actualizado.")
    else:
        print("No se encontraron nuevas actualizaciones.")

if __name__ == "__main__":
    main()
