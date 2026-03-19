"""
Módulo de comprobación de salud para PESync.
Proporciona funciones para verificar la conectividad con los proveedores de almacenamiento.
"""
import os
import sys
from typing import Optional
from src.providers.storage_providers import DropboxProvider, GoogleDriveProvider # type: ignore
from src.utils.helpers import logger # type: ignore
from dotenv import load_dotenv # type: ignore

def test_dropbox_connection(silent: bool = False) -> bool:
    """Prueba la conexión con Dropbox y muestra resultados."""
    # Recargar variables de entorno para asegurar que tenemos las más recientes
    load_dotenv(override=True)
    
    if not silent:
        print("\n" + "=" * 60)
        print("VERIFICACIÓN DE CONEXIÓN - DROPBOX")
        print("=" * 60)
    
    # 1. Verificar presencia de variables
    vars_to_check = ["DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"]
    missing = [v for v in vars_to_check if not os.getenv(v)]
    
    if missing:
        if not silent: print(f"[ERROR] Faltan variables en el entorno: {', '.join(missing)}")
        return False
    
    if not silent: print("[OK] Variables de entorno detectadas.")
    
    # 2. Intentar inicializar y conectar
    provider = DropboxProvider()
    if not provider.connect():
        if not silent: print("[ERROR] No se pudo inicializar el cliente. Revisa tus credenciales.")
        return False
        
    # 3. Prueba de llamada a la API
    try:
        dbx = provider.dbx
        if dbx:
            account = dbx.users_get_current_account()
            if not silent:
                print(f"[OK] CONEXIÓN EXITOSA!")
                print(f"   Cuenta: {account.name.display_name} ({account.email})")
            return True
    except Exception as e:
        if not silent: print(f"[ERROR] de API: {e}")
        return False
    return False

def test_google_drive_connection(silent: bool = False) -> bool:
    """Prueba la conexión con Google Drive y muestra resultados."""
    # Recargar variables de entorno para asegurar que tenemos las más recientes
    load_dotenv(override=True)
    
    if not silent:
        print("\n" + "=" * 60)
        print("VERIFICACIÓN DE CONEXIÓN - GOOGLE DRIVE")
        print("=" * 60)
    
    # 1. Verificar presencia de variables
    vars_to_check = ["GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET", "GOOGLE_DRIVE_REFRESH_TOKEN"]
    missing = [v for v in vars_to_check if not os.getenv(v)]
    
    if missing:
        if not silent: print(f"[ERROR] Faltan variables en el entorno: {', '.join(missing)}")
        return False
    
    if not silent: print("[OK] Variables de entorno detectadas.")
    
    # 2. Intentar conectar
    provider = GoogleDriveProvider()
    if not provider.connect():
        if not silent: print("[ERROR] Error al inicializar el cliente de Google Drive.")
        return False
        
    # 3. Prueba de llamada a la API
    try:
        service = provider.service
        if service:
            # Intentar listar un archivo para confirmar acceso
            results = service.files().list(
                q=f"'{provider.folder_id}' in parents and trashed=false",
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            
            if not silent:
                print(f"[OK] CONEXIÓN EXITOSA!")
                print(f"   Acceso confirmado a la carpeta (ID: {provider.folder_id})")
            return True
    except Exception as e:
        if not silent: print(f"[ERROR] de API: {e}")
        return False
    return False

def run_all_checks() -> bool:
    """Detecta el proveedor configurado y ejecuta la prueba correspondiente."""
    # Recargar variables de entorno por si acaso
    from dotenv import load_dotenv # type: ignore
    load_dotenv()
    
    provider_type = os.getenv("STORAGE_PROVIDER", "dropbox").lower()
    
    if provider_type == "googledrive":
        return test_google_drive_connection()
    else:
        return test_dropbox_connection()
