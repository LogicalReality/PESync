import os
import sys
import json
import urllib.request
import re
import time
from bs4 import BeautifulSoup
import dropbox # type: ignore
from dropbox.exceptions import ApiError # type: ignore
from dropbox.files import WriteMode # type: ignore

EDEN_API = "https://git.eden-emu.dev/api/v1/repos/eden-emu/eden/releases"
STATE_FILE = "state.json"
VERSION_FILE_OLD = "version.txt"

# Target file substring (AppImage para Linux GCC)
TARGET_FILE_SUBSTRING = "amd64-gcc-standard.AppImage"

def get_latest_eden_release():
    print("Fetching latest Eden release...")
    req = urllib.request.Request(EDEN_API, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                print("No releases found.")
                return None
            return data[0] # First item is the latest release
    except Exception as e:
        print(f"Failed to fetch releases: {e}")
        return None

def get_latest_links(url, max_retries=3):
    print(f"Fetching links from {url}...")
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8')
            
            # Usar BeautifulSoup para mayor robustez en lugar de regex
            soup = BeautifulSoup(html, 'html.parser')
            links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')]
            
            # VALIDACIÓN (Spec)
            if not links:
                print(f"CRITICAL: No .zip links found at {url}. The website structure might have changed!")
                return []
            
            unique_links = []
            for l in links:
                if l not in unique_links:
                    unique_links.append(l)
            return unique_links[:2] # type: ignore
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"Max retries reached. Could not fetch from {url}.")
                return []

def upload_to_dropbox(file_path, file_name):
    print(f"Uploading {file_name} to Dropbox...")
    
    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
    except KeyError as e:
        print(f"Warning: Environment secret {e} is not configured.")
        print("Skipping Dropbox upload (dry-run mode).")
        return True # Return true so the script continues downloading/storing state locally
        
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

        print("Upload to Dropbox successful!")
        return True
    except ApiError as e:
        print(f"Failed to upload to Dropbox API: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error uploading to Dropbox: {e}")
        return False

def load_state():
    state = {"eden_version": "", "prod_keys": [], "firmwares": []}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state.update(json.load(f))
    elif os.path.exists(VERSION_FILE_OLD):
        with open(VERSION_FILE_OLD, "r") as f:
            state["eden_version"] = f.read().strip()
    return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def download_file(url, file_name):
    print(f"Downloading {file_name} from {url}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://prodkeys.net/'
        })
        with urllib.request.urlopen(req) as response, open(file_name, 'wb') as out_file:
            import shutil
            shutil.copyfileobj(response, out_file)
        print("Download completed successfully.")
        return True
    except Exception as e:
        print(f"Failed to download file: {e}")
        return False

def main():
    state = load_state()
    state_changed = False
    
    # 1. Process Eden
    latest_release = get_latest_eden_release()
    if latest_release:
        release_tag = latest_release.get("tag_name", "unknown")
        if state["eden_version"] != release_tag:
            print(f"New Eden version found: {release_tag}")
            target_asset = None
            for asset in latest_release.get("assets", []):
                if TARGET_FILE_SUBSTRING in asset.get("name", "") and not asset.get("name").endswith(".zsync"):
                    target_asset = asset
                    break
                    
            if target_asset:
                download_url = target_asset["browser_download_url"] # type: ignore
                file_name = target_asset["name"] # type: ignore
                if download_file(download_url, file_name):
                    if upload_to_dropbox(file_name, file_name):
                        state["eden_version"] = release_tag
                        state_changed = True
            else:
                print(f"Error: Could not find target asset for Eden release {release_tag}")
        else:
            print(f"Eden version {release_tag} is already up to date.")
            
    # 2. Process Prod Keys
    keys_links = get_latest_links("https://prodkeys.net/eden-prod-keys-13/")
    if keys_links:
        # We only download the ones we don't already have
        new_keys = [link for link in keys_links if link not in state.get("prod_keys", [])] # type: ignore
        for link in new_keys:
            file_name = link.split("/")[-1] # type: ignore
            if download_file(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    if "prod_keys" not in state:
                        state["prod_keys"] = []
                    state["prod_keys"].append(link) # type: ignore
                    state_changed = True
        
        # Keep only the latest 2 in state
        all_keys = state.get("prod_keys", [])
        if len(all_keys) > 2:
            # The links we just retrieved are the latest, so we intersect them.
            # But the state also just appended the new keys. It's safer to keep the new_keys in order.
            # However `keys_links` are the true latest 2.
            # So anything in `state["prod_keys"]` that is also in `keys_links` should be kept.
            state["prod_keys"] = [k for k in keys_links if k in state["prod_keys"]] # type: ignore
            state_changed = True
            
    # 3. Process Firmwares
    firmware_links = get_latest_links("https://prodkeys.net/latest-switch-firmwares-v19/")
    if firmware_links:
        new_firmwares = [link for link in firmware_links if link not in state.get("firmwares", [])] # type: ignore
        for link in new_firmwares:
            file_name = link.split("/")[-1] # type: ignore
            if download_file(link, file_name):
                if upload_to_dropbox(file_name, file_name):
                    if "firmwares" not in state:
                        state["firmwares"] = []
                    state["firmwares"].append(link) # type: ignore
                    state_changed = True
                    
        all_firmwares = state.get("firmwares", [])
        if len(all_firmwares) > 2:
            state["firmwares"] = [f for f in firmware_links if f in state["firmwares"]] # type: ignore
            state_changed = True

    if state_changed:
        save_state(state)
        print("State updated locally. (state.json)")
    else:
        print("No new updates found.")

if __name__ == "__main__":
    main()
