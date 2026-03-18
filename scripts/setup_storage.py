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
        
        # Intentar escribir automáticamente en .env en la RAÍZ del proyecto
        try:
            import os
            env_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), '.env')
            with open(env_path, "w", encoding="utf-8") as env_file:
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
    print("8. Descarga el archivo JSON de credenciales y guárdalo en tu equipo")
    print("-" * 60)
    
    import json
    import os
    import glob
    
    json_path = ""
    downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    possible_files = []
    for path in [downloads_path, project_root]:
        if os.path.exists(path):
            possible_files.extend(glob.glob(os.path.join(path, "client_secret_*.json")))
            possible_files.extend(glob.glob(os.path.join(path, "credentials*.json")))
            
    possible_files = list(set(possible_files))
    
    if possible_files:
        print("\nHemos detectado los siguientes archivos de credenciales:")
        for i, file in enumerate(possible_files):
            print(f"[{i+1}] {file}")
        print(f"[{len(possible_files)+1}] Ingresar ruta manualmente")
        
        choice = input(f"\nSelecciona una opción (1-{len(possible_files)+1}): ").strip()
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(possible_files):
                json_path = possible_files[choice_idx]
        except ValueError:
            pass
            
    if not json_path:
        json_path = input("\nIngresa la ruta al archivo JSON descargado (ej. credentials.json): ").strip()
        
    # Remover comillas por si el usuario arrastró el archivo a la terminal
    json_path = json_path.strip("\"'")
    
    if not json_path or not os.path.exists(json_path):
        print(f"Error: El archivo '{json_path}' no existe o la ruta es inválida.")
        return
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            cred_data = json.load(f)
            
        if "installed" in cred_data:
            client_id = cred_data["installed"]["client_id"]
            client_secret = cred_data["installed"]["client_secret"]
        elif "web" in cred_data:
            client_id = cred_data["web"]["client_id"]
            client_secret = cred_data["web"]["client_secret"]
        else:
            print("Error: El formato del archivo JSON no contiene 'client_id' de forma reconocida.")
            return
            
    except Exception as e:
        print(f"Error leyendo el archivo JSON: {e}")
        return

    print("\n" + "-" * 60)
    print("Iniciando flujo de autorización...")
    print("Se abrirá una ventana en tu navegador web. Inicia sesión y autoriza a la aplicación.")
    print("-" * 60)
    
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except ImportError:
        print("Error: Faltan dependencias para Google Drive.")
        print("Por favor, instala los paquetes necesarios ejecutando:")
        print("pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return

    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    try:
        # Usar directamente el archivo JSON proporiconado por el usuario
        flow = InstalledAppFlow.from_client_secrets_file(json_path, SCOPES)
        credentials = flow.run_local_server(port=0)
        refresh_token = credentials.refresh_token
        
        if not refresh_token:
             print("\nAdvertencia: No se recibió un refresh token nuevo.")
             print("Si ya habías autorizado esta app antes, Google podría no enviar uno nuevo.")
             print("Solución: Ve a tu cuenta de Google > Seguridad > Apps con acceso, revoca el acceso y vuelve a intentarlo.")
             return
             
    except Exception as e:
        print(f"\nError durante la autorización: {e}")
        return
        
    print("\n" + "-" * 60)
    print("Opcional: Nombre de la carpeta de respaldo.")
    folder_name = input("Ingresa el nombre de la carpeta (presiona ENTER para usar 'PESync_Backup'): ").strip()
    if not folder_name:
        folder_name = "PESync_Backup"
        
    print(f"\nResolviendo u obteniendo ID para la carpeta: '{folder_name}'...")
    try:
        from googleapiclient.discovery import build # type: ignore
        service = build('drive', 'v3', credentials=credentials)
        
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if files:
            folder_id = files[0]['id']
            print(f"Carpeta existente encontrada. ID: {folder_id}")
        else:
            print("Carpeta no encontrada. Creándola...")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            print(f"Carpeta creada. ID: {folder_id}")
            
    except Exception as e:
        print(f"Error al resolver la carpeta en Drive: {e}")
        print("Continuaremos con la configuración base, pero podría fallar en ejecución.")
        folder_id = ""
        
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
    
    print(f"4) Nombre: GOOGLE_DRIVE_FOLDER_ID")
    print(f"   Valor:  {folder_id}\n")
    
    print(f"5) Nombre: STORAGE_PROVIDER")
    print(f"   Valor:  googledrive\n")
    
    print("-" * 60)
    print("Copia y pega este bloque en tu archivo .github/workflows/sync.yml bajo 'env:':")
    print("env:")
    print("  STORAGE_PROVIDER: ${{ secrets.STORAGE_PROVIDER }}")
    print("  GOOGLE_DRIVE_CLIENT_ID: ${{ secrets.GOOGLE_DRIVE_CLIENT_ID }}")
    print("  GOOGLE_DRIVE_CLIENT_SECRET: ${{ secrets.GOOGLE_DRIVE_CLIENT_SECRET }}")
    print("  GOOGLE_DRIVE_REFRESH_TOKEN: ${{ secrets.GOOGLE_DRIVE_REFRESH_TOKEN }}")
    print("  GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}")
    print("=" * 60)
    
    # Intentar escribir automáticamente en .env en la RAÍZ del proyecto
    try:
        env_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), '.env')
        with open(env_path, "w", encoding="utf-8") as env_file:
            env_file.write(f"GOOGLE_DRIVE_CLIENT_ID={client_id}\n")
            env_file.write(f"GOOGLE_DRIVE_CLIENT_SECRET={client_secret}\n")
            env_file.write(f"GOOGLE_DRIVE_REFRESH_TOKEN={refresh_token}\n")
            env_file.write(f"GOOGLE_DRIVE_FOLDER_ID={folder_id}\n")
            env_file.write(f"STORAGE_PROVIDER=googledrive\n")
        print("✅ El archivo .env ha sido actualizado automáticamente.")
    except Exception as e:
        print(f"⚠️ No se pudo escribir el archivo .env: {e}")
        print("Por favor, copia los valores manualmente.")
        
    print("\n¡Listo! Ya puedes ejecutar 'python main.py'.")
    input("\nPresiona ENTER para cerrar esta ventana...")

if __name__ == "__main__":
    main()
