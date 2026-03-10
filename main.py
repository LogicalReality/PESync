import os
import sys
import json
import urllib.request
import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import WriteMode

EDEN_API = "https://git.eden-emu.dev/api/v1/repos/eden-emu/eden/releases"
VERSION_FILE = "version.txt"

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
                sys.exit(1)
            return data[0] # First item is the latest release
    except Exception as e:
        print(f"Failed to fetch releases: {e}")
        sys.exit(1)

def upload_to_dropbox(file_path, file_name):
    print(f"Uploading {file_name} to Dropbox...")
    
    try:
        app_key = os.environ["DROPBOX_APP_KEY"]
        app_secret = os.environ["DROPBOX_APP_SECRET"]
        refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
        
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
    except KeyError as e:
        print(f"Error: El secreto de entorno {e} no está configurado.")
        sys.exit(1)
    except ApiError as e:
        print(f"Failed to upload to Dropbox API: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error uploading to Dropbox: {e}")
        sys.exit(1)

def main():
    latest_release = get_latest_eden_release()
    release_tag = latest_release.get("tag_name", "unknown")
    
    # Check if we already processed this version
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            last_version = f.read().strip()
            if last_version == release_tag:
                print(f"Version {release_tag} is already up to date. Nothing to do.")
                sys.exit(0)

    print(f"New version found: {release_tag}")
    
    # Find the target asset
    target_asset = None
    for asset in latest_release.get("assets", []):
        if TARGET_FILE_SUBSTRING in asset.get("name", "") and not asset.get("name").endswith(".zsync"):
            target_asset = asset
            break
            
    if not target_asset:
        print(f"Error: Could not find an asset containing '{TARGET_FILE_SUBSTRING}' in release {release_tag}")
        sys.exit(1)
        
    download_url = target_asset["browser_download_url"]
    file_name = target_asset["name"]
    
    print(f"Downloading {file_name} from {download_url}...")
    try:
        urllib.request.urlretrieve(download_url, file_name)
    except Exception as e:
        print(f"Failed to download file: {e}")
        sys.exit(1)
        
    print("Download completed successfully.")
    
    upload_to_dropbox(file_name, file_name)
    
    # Update version file on success
    with open(VERSION_FILE, "w") as f:
        f.write(release_tag)
    print(f"Updated local version to {release_tag}")

if __name__ == "__main__":
    main()
