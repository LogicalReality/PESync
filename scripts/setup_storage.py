# pyre-ignore-all-errors[21]
import requests
import webbrowser

def main():
    print("=" * 60)
    print("Bienvenido al Asistente de Configuración de Almacenamiento")
    print("=" * 60)
    print("\nSelecciona el proveedor de almacenamiento que deseas configurar:")
    print("1. Dropbox")
    print("2. Google Drive")
    print("-" * 60)
    
    choice = input("Ingresa tu opción (1 o 2): ").strip()
    
    if choice == "1":
        setup_dropbox()
    elif choice == "2":
        setup_google_drive()
    else:
        print("Opción no válida. Por favor, ejecuta nuevamente el script.")
        input("\nPresiona ENTER para cerrar esta ventana...")
        return

def setup_dropbox():
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN DE DROPBOX")
    print("=" * 60)
    print("\nPara automatizar la subida, necesitamos crear un Token de Acceso Persistente (Refresh Token).")
    print("Sigue estos sencillos pasos:\n")
    print("1. Ve a https://www.dropbox.com/developers/apps")
    print("2. Haz clic en 'Create app'.")
    print("3. Selecciona 'Scoped access' y 'App folder' (o 'Full Dropbox'). Ponle un nombre a tu app.")
    print("4. Ve a la pestaña 'Permissions' de tu nueva App, marca 'files.content.write' y dale a 'Submit' abajo.")
    print("5. Vuelve a la pestaña 'Settings' y copia el 'App key' y el 'App secret'.")
    print("-" * 60)
    
    app_key = input("Pega aquí tu 'App key': ").strip()
    app_secret = input("Pega aquí tu 'App secret': ").strip()
    
    if not app_key or not app_secret:
        print("Error: Necesitas ingresar ambos valores.")
        return

    # Construir la URL de autorización
    auth_url = f"https://www.dropbox.com/oauth2/authorize?client_id={app_key}&response_type=code&token_access_type=offline"
    
    print("\n" + "-" * 60)
    print("Paso 6: Ahora debes autorizar a tu propia App para que acceda a tu Dropbox.")
    print("Se abrirá una ventana en tu navegador web. Inicia sesión, dale a 'Permitir',")
    print("y copia el 'Access Code' (Código de acceso corporativo) que te dará la página.")
    print(f"(Si el navegador no se abre automáticamente, entra aquí: {auth_url} )")
    print("-" * 60)
    
    # Intentar abrir el navegador automáticamente
    try:
        webbrowser.open_new(auth_url)
    except Exception:
        pass
        
    auth_code = input("\nPega aquí tu 'Access Code': ").strip()
    
    if not auth_code:
        print("Error: Necesitas el código de acceso.")
        return
        
    print("\nObteniendo el Refresh Token...")
    
    # Hacer la petición para cambiar el code por un refresh_token
    response = requests.post("https://api.dropbox.com/oauth2/token", data={
        "code": auth_code,
        "grant_type": "authorization_code",
    }, auth=(app_key, app_secret))
    
    if response.status_code == 200:
        data = response.json()
        refresh_token = data.get("refresh_token")
        
        print("\n" + "=" * 60)
        print("¡ÉXITO! Aquí están los 3 Secretos que debes guardar:")
        print("Si usas GitHub Actions, ve a Settings > Secrets and variables > Actions")
        print("Si usas local, se guardarán en el archivo .env\n")
        
        print(f"1) Nombre: DROPBOX_APP_KEY")
        print(f"   Valor:  {app_key}\n")
        
        print(f"2) Nombre: DROPBOX_APP_SECRET")
        print(f"   Valor:  {app_secret}\n")
        
        print(f"3) Nombre: DROPBOX_REFRESH_TOKEN")
        print(f"   Valor:  {refresh_token}\n")
        
        print(f"4) Nombre: STORAGE_PROVIDER")
        print(f"   Valor:  dropbox\n")
        
        print("=" * 60)
        
        # Intentar escribir automáticamente en .env
        try:
            with open(".env", "w", encoding="utf-8") as env_file:
                env_file.write(f"DROPBOX_APP_KEY={app_key}\n")
                env_file.write(f"DROPBOX_APP_SECRET={app_secret}\n")
                env_file.write(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
                env_file.write(f"STORAGE_PROVIDER=dropbox\n")
            print("✅ El archivo .env ha sido actualizado automáticamente.")
        except Exception as e:
            print(f"⚠️ No se pudo escribir el archivo .env: {e}")
            print("Por favor, copia los valores manualmente.")
            
        print("\n¡Listo! Ya puedes ejecutar 'python main.py'.")
    else:
        print(f"\nError al obtener el token. Código: {response.status_code}")
        print(response.text)
    
    input("\nPresiona ENTER para cerrar esta ventana...")

def setup_google_drive():
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN DE GOOGLE DRIVE")
    print("=" * 60)
    print("\nPara automatizar la subida a Google Drive, necesitamos credenciales OAuth 2.0.")
    print("Sigue estos pasos:\n")
    print("1. Ve a https://console.cloud.google.com/")
    print("2. Crea un nuevo proyecto (o usa uno existente)")
    print("3. En el menú, ve a 'APIs y servicios' > 'Biblioteca'")
    print("4. Busca 'Google Drive API' y habilítala")
    print("5. Ve a 'APIs y servicios' > 'Credenciales'")
    print("6. Haz clic en 'Crear credenciales' > 'ID de cliente OAuth'")
    print("7. Selecciona 'Aplicación de escritorio' como tipo de aplicación")
    print("8. Descarga el archivo JSON de credenciales")
    print("9. Copia el 'client_id' y 'client_secret' del archivo JSON")
    print("-" * 60)
    
    client_id = input("Pega aquí tu 'client_id': ").strip()
    client_secret = input("Pega aquí tu 'client_secret': ").strip()
    
    if not client_id or not client_secret:
        print("Error: Necesitas ingresar ambos valores.")
        return

    print("\n" + "-" * 60)
    print("Ahora necesitas obtener un refresh_token.")
    print("Para hacerlo, ejecuta este código en Python (necesitas instalar google-auth):")
    print("-" * 60)
    
    print("""
# Código para obtener refresh_token (ejecuta esto en Python):
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Descarga el archivo JSON de credenciales desde Google Cloud Console
# y ponlo como 'credentials.json'
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
credentials = flow.run_local_server(port=0)

print(f"Refresh token: {credentials.refresh_token}")
""")
    
    refresh_token = input("\nPega aquí tu 'refresh_token': ").strip()
    
    if not refresh_token:
        print("Error: Necesitas el refresh_token.")
        return
        
    print("\n" + "=" * 60)
    print("¡ÉXITO! Aquí están los secretos que debes guardar:")
    print("Si usas GitHub Actions, ve a Settings > Secrets and variables > Actions")
    print("Si usas local, se guardarán en el archivo .env\n")
    
    print(f"1) Nombre: GOOGLE_DRIVE_CLIENT_ID")
    print(f"   Valor:  {client_id}\n")
    
    print(f"2) Nombre: GOOGLE_DRIVE_CLIENT_SECRET")
    print(f"   Valor:  {client_secret}\n")
    
    print(f"3) Nombre: GOOGLE_DRIVE_REFRESH_TOKEN")
    print(f"   Valor:  {refresh_token}\n")
    
    print(f"4) Nombre: STORAGE_PROVIDER")
    print(f"   Valor:  googledrive\n")
    
    print("=" * 60)
    
    # Intentar escribir automáticamente en .env
    try:
        with open(".env", "w", encoding="utf-8") as env_file:
            env_file.write(f"GOOGLE_DRIVE_CLIENT_ID={client_id}\n")
            env_file.write(f"GOOGLE_DRIVE_CLIENT_SECRET={client_secret}\n")
            env_file.write(f"GOOGLE_DRIVE_REFRESH_TOKEN={refresh_token}\n")
            env_file.write(f"STORAGE_PROVIDER=googledrive\n")
        print("✅ El archivo .env ha sido actualizado automáticamente.")
    except Exception as e:
        print(f"⚠️ No se pudo escribir el archivo .env: {e}")
        print("Por favor, copia los valores manualmente.")
        
    print("\n¡Listo! Ya puedes ejecutar 'python main.py'.")
    input("\nPresiona ENTER para cerrar esta ventana...")

if __name__ == "__main__":
    main()
