import os
import sys
import json
import urllib.request
import re
import time
import base64
from bs4 import BeautifulSoup # type: ignore
import dropbox # type: ignore
from dropbox.exceptions import ApiError # type: ignore
from dropbox.files import WriteMode # type: ignore

def d(s):
    return base64.b64decode(s).decode('utf-8')

# URLs ofuscadas
B_URL = d("aHR0cHM6Ly9naXQuZWRlbi1lbXUuZGV2L2FwaS92MS9yZXBvcy9lZGVuLWVtdS9lZGVuL3JlbGVhc2Vz")
STATE_FILE = "state.json"
VERSION_FILE_OLD = "version.txt"

# Nombre de archivo objetivo (E-Core Component)
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
            return data[0] # El primer elemento es la última versión
    except Exception as e:
        print(f"Error al obtener las versiones: {e}")
        return None

def is_valid_link(link: str) -> bool:
    """
    SPEC (Contract): Verifica que el payload cumpla con el formato esperado.
    Evita que procesemos datos basura si la página web cambia su estructura.
    """
    return link.startswith("https://") and link.endswith(".zip")

def get_latest_links(url, max_retries=3):
    print(f"Obteniendo enlaces desde {url}...")
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')
            
            # Usar BeautifulSoup para mayor robustez en lugar de regex
            soup = BeautifulSoup(html, 'html.parser')
            
            # Buscamos y validamos contra nuestra SPEC
            links = [a['href'] for a in soup.find_all('a', href=True) if is_valid_link(a['href'])]
            
            # VALIDACIÓN: ¿Los datos lucen correctos?
            if not links:
                print(f"CRÍTICO: No se encontraron enlaces .zip válidos en {url}. ¡La estructura del sitio podría haber cambiado!")
                return []
            
            unique_links = []
            for l in links:
                if l not in unique_links:
                    unique_links.append(l)
            return unique_links[:2] # type: ignore
            
        except Exception as e:
            print(f"Intento {attempt + 1} fallido para {url}: {e}")
            if attempt < max_retries - 1:
                print("Reintentando en 5 segundos...")
                time.sleep(5)
            else:
                print(f"Máximo de reintentos alcanzado. No se pudo obtener de {url}.")
                return []

def upload_to_dropbox(file_path, file_name):
    print(f"Subiendo {file_name} a Dropbox...")
    
    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as e:
        print(f"Advertencia: El secreto de entorno {e} no está configurado.")
        print("Tratando de continuar sin subir a Dropbox (dry-run mode).")
        return True # Retorna true para que el script continúe descargando/guardando el estado localmente
        
    try:
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
        
        file_size = os.path.getsize(file_path)
        CHUNK_SIZE = 4 * 1024 * 1024 # 4MB
        
        with open(file_path, 'rb') as f:
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), f'/{file_name}', mode=WriteMode.overwrite)
            else:
                upload_session_start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start.session_id, offset=f.tell())
                commit = dropbox.files.CommitInfo(path=f'/{file_name}', mode=WriteMode.overwrite)
                
                while f.tell() < file_size:
                    if (file_size - f.tell()) <= CHUNK_SIZE:
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                    else:
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                        cursor.offset = f.tell()

        print("¡Subida a Dropbox exitosa!")
        return True
    except ApiError as e:
        print(f"Error al subir mediante la API de Dropbox: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado subiendo a Dropbox: {e}")
        return False

def load_state():
    state = {"core_v": "", "prod_keys": [], "sys_comps": []}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state.update(json.load(f))
    elif os.path.exists(VERSION_FILE_OLD):
        with open(VERSION_FILE_OLD, "r") as f:
            state["core_v"] = f.read().strip()
    return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def download_asset(url, file_name):
    print(f"Sincronizando {file_name}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://prodkeys.net/'
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            import shutil
            shutil.copyfileobj(response, out_file)
        print("Descarga completada exitosamente.")
        return True
    except Exception as e:
        print(f"Error al descargar el archivo: {e}")
        return False

def main():
    state = load_state()
    state_changed = False
    
    # 1. Procesar Core Environment
    latest_release = get_latest_sys_version()
    if latest_release:
        release_tag = latest_release.get("tag_name", "unknown")
        if state["core_v"] != release_tag:
            print(f"Nueva actualización detectada: {release_tag}")
            target_asset = None
            for asset in latest_release.get("assets", []):
                if TARGET_FILE_SUBSTRING in asset.get("name", "") and not asset.get("name").endswith(".zsync"):
                    target_asset = asset
                    break
                    
            if target_asset:
                download_url = target_asset["browser_download_url"] # type: ignore
                file_name = target_asset["name"] # type: ignore
                if download_asset(download_url, file_name):
                    if upload_to_dropbox(file_name, file_name):
                        state["core_v"] = release_tag
                        state_changed = True
            else:
                print(f"Error: No se encontró el recurso objetivo para la actualización {release_tag}")
        else:
            print(f"El componente {release_tag} ya está actualizado.")
            
    # 2. Procesar Assets de Metadata
    keys_links = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvZWRlbi1wcm9kLWtleXMtMTMv"))
    if keys_links:
        # Solo descargamos los que no tenemos todavía
        new_keys = [link for link in keys_links if link not in state.get("prod_keys", [])] # type: ignore
        for link in new_keys:
            file_name = link.split("/")[-1] # type: ignore
            if download_asset(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    if "prod_keys" not in state:
                        state["prod_keys"] = []
                    state["prod_keys"].append(link) # type: ignore
                    state_changed = True
        
        # Mantener solo los últimos 2 en el estado
        all_keys = state.get("prod_keys", [])
        if len(all_keys) > 2:
            state["prod_keys"] = [k for k in keys_links if k in state["prod_keys"]] # type: ignore
            state_changed = True
            
    # 3. Procesar Componentes de Sistema
    sys_links = get_latest_links(d("aHR0cHM6Ly9wcm9ka2V5cy5uZXQvbGF0ZXN0LXN3aXRjaC1maXJtd2FyZXMtdjE5Lw=="))
    if sys_links:
        new_sys = [link for link in sys_links if link not in state.get("sys_comps", [])] # type: ignore
        for link in new_sys:
            file_name = link.split("/")[-1] # type: ignore
            if download_asset(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    if "sys_comps" not in state:
                        state["sys_comps"] = []
                    state["sys_comps"].append(link) # type: ignore
                    state_changed = True
                    
        all_sys = state.get("sys_comps", [])
        if len(all_sys) > 2:
            state["sys_comps"] = [f for f in sys_links if f in state["sys_comps"]] # type: ignore
            state_changed = True

    if state_changed:
        save_state(state)
        print("Estado actualizado localmente. (state.json)")
    else:
        print("No se encontraron nuevas actualizaciones.")

if __name__ == "__main__":
    main()
