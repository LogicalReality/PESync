import os
import sys
import json
import urllib.request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

EDEN_API = "https://git.eden-emu.dev/api/v1/repos/eden-emu/eden/releases"
VERSION_FILE = "version.txt"

# Target file substring
TARGET_FILE_SUBSTRING = "amd64-gcc-standard.AppImage"

# Load Secrets
try:
    GDRIVE_CREDENTIALS_JSON = json.loads(os.environ["GDRIVE_CREDENTIALS"])
    GDRIVE_FOLDER_ID = os.environ["GDRIVE_FOLDER_ID"]
except KeyError as e:
    print(f"Error: Missing environment variable {e}")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: GDRIVE_CREDENTIALS is not valid JSON")
    sys.exit(1)

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

def upload_to_drive(file_path, file_name):
    print(f"Uploading {file_name} to Google Drive...")
    credentials = service_account.Credentials.from_service_account_info(
        GDRIVE_CREDENTIALS_JSON, 
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    service = build('drive', 'v3', credentials=credentials)
    
    file_metadata = {
        'name': file_name,
        'parents': [GDRIVE_FOLDER_ID]
    }
    
    media = MediaFileUpload(file_path, resumable=True)
    
    try:
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True
        ).execute()
        print(f"Upload successful. File ID: {file.get('id')}")
    except Exception as e:
        print(f"Failed to upload to Google Drive: {e}")
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
    
    upload_to_drive(file_name, file_name)
    
    # Update version file on success
    with open(VERSION_FILE, "w") as f:
        f.write(release_tag)
    print(f"Updated local version to {release_tag}")

if __name__ == "__main__":
    main()
