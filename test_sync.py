import os
import logging
from dotenv import load_dotenv # type: ignore
import dropbox # type: ignore
from main import get_dropbox_client, setup_logger # type: ignore

# Configurar logger para el test
logger = setup_logger("pesync_test")

def test_connection():
    """
    Realiza una prueba de conexión básica a Dropbox y verifica 
    que las variables de entorno estén cargadas correctamente.
    """
    print("=" * 60)
    print("PRUEBA DE CONEXION LOCAL - PESync")
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
        print(f"[OK] CONEXION EXITOSA!")
        print(f"   Cuenta: {account.name.display_name} ({account.email})")
        
        # 4. Listar archivos (opcional)
        print("\nVerificando acceso a archivos...")
        result = dbx.files_list_folder("")
        print(f"[OK] Acceso concedido. Se encontraron {len(result.entries)} elementos en la raiz.")
        
        print("\n" + "=" * 60)
        print("TODO LISTO: Puedes ejecutar 'python main.py' con confianza.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"[ERROR] de API: {e}")
        return False

if __name__ == "__main__":
    test_connection()
