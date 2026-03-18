# pyre-ignore-all-errors[21]
import os
import logging
from dotenv import load_dotenv # type: ignore
from main import setup_logger # type: ignore
from storage_providers import get_storage_provider, DropboxProvider, GoogleDriveProvider

# Configurar logger para el test
logger = setup_logger("pesync_test")

def test_dropbox():
    """Prueba la conexión con Dropbox."""
    import dropbox # type: ignore
    from main import get_dropbox_client # type: ignore
    
    print("=" * 60)
    print("PRUEBA DE CONEXIÓN - DROPBOX")
    print("=" * 60)
    
    # Cargar variables desde .env
    load_dotenv()
    
    # 1. Verificar presencia de variables
    vars_to_check = ["DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"]
    missing = [v for v in vars_to_check if not os.getenv(v)]
    
    if missing:
        print(f"[ERROR] Faltan las siguientes variables en tu .env: {', '.join(missing)}")
        return False
    
    print("[OK] Variables de entorno detectadas correctamente.")
    
    # 2. Intentar inicializar cliente
    print("\nConectando con Dropbox...")
    dbx = get_dropbox_client()
    
    if not dbx:
        print("[ERROR] No se pudo inicializar el cliente de Dropbox. Revisa tus credenciales.")
        return False
    
    # 3. Prueba de llamada a la API
    try:
        account = dbx.users_get_current_account()
        print(f"[OK] CONEXIÓN EXITOSA!")
        print(f"   Cuenta: {account.name.display_name} ({account.email})")
        
        # 4. Listar archivos (opcional)
        print("\nVerificando acceso a archivos...")
        result = dbx.files_list_folder("")
        print(f"[OK] Acceso concedido. Se encontraron {len(result.entries)} elementos en la raíz.")
        
        print("\n" + "=" * 60)
        print("DROPBOX: TODO LISTO")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"[ERROR] de API: {e}")
        return False


def test_google_drive():
    """Prueba la conexión con Google Drive."""
    print("=" * 60)
    print("PRUEBA DE CONEXIÓN - GOOGLE DRIVE")
    print("=" * 60)
    
    # Cargar variables desde .env
    load_dotenv()
    
    # 1. Verificar presencia de variables
    vars_to_check = ["GOOGLE_DRIVE_CLIENT_ID", "GOOGLE_DRIVE_CLIENT_SECRET", "GOOGLE_DRIVE_REFRESH_TOKEN"]
    missing = [v for v in vars_to_check if not os.getenv(v)]
    
    if missing:
        print(f"[ERROR] Faltan las siguientes variables en tu .env: {', '.join(missing)}")
        return False
    
    print("[OK] Variables de entorno detectadas correctamente.")
    
    # 2. Intentar inicializar cliente
    print("\nConectando con Google Drive...")
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        print("[ERROR] No se encontró la librería google-api-python-client.")
        print("Instálala con: pip install google-api-python-client google-auth-httplib2")
        return False
    
    try:
        client_id = os.environ["GOOGLE_DRIVE_CLIENT_ID"]
        client_secret = os.environ["GOOGLE_DRIVE_CLIENT_SECRET"]
        refresh_token = os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"]
        
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        service = build('drive', 'v3', credentials=credentials)
        
        # 3. Prueba de llamada a la API
        print("\nVerificando acceso a archivos...")
        results = service.files().list(
            q="'root' in parents and trashed=false",
            pageSize=10,
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        print(f"[OK] CONEXIÓN EXITOSA!")
        print(f"   Acceso concedido. Se encontraron {len(files)} elementos en la raíz.")
        
        print("\n" + "=" * 60)
        print("GOOGLE DRIVE: TODO LISTO")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"[ERROR] de API: {e}")
        return False


def test_connection():
    """
    Realiza una prueba de conexión básica al almacenamiento configurado
    y verifica que las variables de entorno estén cargadas correctamente.
    """
    print("=" * 60)
    print("PRUEBA DE CONEXIÓN LOCAL - PESync")
    print("=" * 60)
    
    # Cargar variables desde .env
    load_dotenv()
    
    # Detectar qué proveedor está configurado
    provider_type = os.getenv("STORAGE_PROVIDER", "dropbox").lower()
    
    print(f"\nProveedor detectado: {provider_type}")
    
    if provider_type == "googledrive":
        return test_google_drive()
    else:
        # Por defecto, probar Dropbox
        return test_dropbox()


if __name__ == "__main__":
    if test_connection():
        print("\n[OK] Puedes ejecutar 'python main.py' con confianza.")
    else:
        print("\n[ERROR] Hay errores de configuración. Por favor, revisa los mensajes anteriores.")
