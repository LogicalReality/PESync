import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_refresh_token():
    credentials_file = 'credentials.json'
    
    if not os.path.exists(credentials_file):
        print(f"ERROR: No se encontró el archivo '{credentials_file}' en el directorio actual.")
        print(f"Directorio actual: {os.getcwd()}")
        print("\nPor favor, descarga el archivo JSON de credenciales de Google Console,")
        print(f"renómbralo a '{credentials_file}' y colócalo en esta carpeta.")
        input("\nPresiona Enter para salir...")
        return

    try:
        print("Iniciando el proceso de autenticación...")
        print("Se abrirá una ventana en tu navegador predeterminado.")
        
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        credentials = flow.run_local_server(port=8080)

        print("\n" + "="*50)
        print("¡AUTENTICACIÓN EXITOSA!")
        print("="*50)
        print(f"\nREFRESH_TOKEN: {credentials.refresh_token}")
        print("\nCopia este token y guárdalo de forma segura.")
        print("="*50)
        
    except Exception as e:
        print(f"\nOcurrió un error inesperado: {e}")
    
    input("\nPresiona Enter para cerrar esta ventana...")

if __name__ == "__main__":
    get_refresh_token()