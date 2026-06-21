# Módulo de proveedores de almacenamiento para PESync.
"""
Módulo de proveedores de almacenamiento para PESync.
Proporciona una abstracción para soportar múltiples servicios de nube (Dropbox, Google Drive, etc.)
"""
from __future__ import annotations
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, cast
import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import WriteMode, UploadSessionCursor, CommitInfo
import requests
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress
from src.utils.helpers import logger, create_shared_progress, retry_with_backoff

# Tamaño de chunk (fijado a 16MB para mayor estabilidad en conexiones variables)
CHUNK_SIZE: int = 16 * 1024 * 1024

# ==========================================
# INTERFAZ ABSTRACTA DE PROVEEDOR
# ==========================================
class StorageProvider(ABC):
    """Clase abstracta que define la interfaz para proveedores de almacenamiento."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Conecta al servicio de almacenamiento. Retorna True si la conexión fue exitosa."""
        return False
    
    @abstractmethod
    def list_files(self) -> set[str]:
        """Lista todos los archivos en el almacenamiento remoto."""
        return set()
    
    @abstractmethod
    def upload_file(self, local_path: str, remote_name: str, progress: Progress | None = None) -> bool:
        """Sube un archivo al almacenamiento remoto."""
        return False

    @abstractmethod
    def upload_files(self, file_paths: list[str]) -> set[str]:
        """Sube archivos en paralelo. Retorna el set de basenames subidos OK."""
        return set()
    
    @abstractmethod
    def delete_file(self, file_name: str) -> bool:
        """Elimina un archivo del almacenamiento remoto."""
        return False
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Retorna el nombre del proveedor."""
        return ""

    def _log_prefix(self) -> str:
        """Retorna el prefijo para los logs de este proveedor."""
        return f"[{self.get_provider_name().upper()}]"

    def _run_parallel_uploads(self, file_paths: list[str]) -> set[str]:
        """Sube archivos en paralelo vía self.upload_file.

        Retorna el set de basenames subidos correctamente. Aísla los errores por
        archivo para que el fallo de uno no aborte el lote ni descarte los que sí
        subieron.
        """
        if not file_paths:
            return set()

        logger.info(
            f"{self._log_prefix()} Iniciando subida paralela de {len(file_paths)} archivos..."
        )
        succeeded: set[str] = set()
        succeeded_lock = threading.Lock()

        def _upload_one(path: str, progress: Progress | None) -> None:
            name = os.path.basename(path)
            try:
                if self.upload_file(path, name, progress):
                    with succeeded_lock:
                        succeeded.add(name)
            except Exception:
                logger.exception(f"{self._log_prefix()} Fallo definitivo al subir: {name}")

        with create_shared_progress() as progress:
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(lambda p: _upload_one(p, progress), file_paths))
        return succeeded

# ==========================================
# PROVEEDOR DE DROPBOX
# ==========================================
class DropboxProvider(StorageProvider):
    """Implementación de StorageProvider para Dropbox."""
    
    def __init__(self) -> None:
        self.dbx: dropbox.Dropbox | None = None
    
    def connect(self) -> bool:
        """Inicializa el cliente de Dropbox."""
        try:
            app_key = os.environ["DROPBOX_APP_KEY"]
            app_secret = os.environ["DROPBOX_APP_SECRET"]
            refresh_token = os.environ["DROPBOX_REFRESH_TOKEN"]
        except KeyError as e:
            logger.error(f"Error: La variable de entorno {e} no está configurada.")
            return False
        
        try:
            self.dbx = dropbox.Dropbox(
                app_key=app_key,
                app_secret=app_secret,
                oauth2_refresh_token=refresh_token
            )
            # Verificar conexión
            self.dbx.users_get_current_account()
            logger.info(f"{self._log_prefix()} Cliente inicializado correctamente.")
            return True
        except Exception:
            logger.exception("Error al conectar a Dropbox:")
            return False
    
    @retry_with_backoff()
    def list_files(self) -> set[str]:
        """Lista archivos en Dropbox."""
        if not self.dbx:
            logger.error("Cliente de Dropbox no inicializado.")
            return set()
        
        try:
            result = self.dbx.files_list_folder("")
            files: set[str] = {entry.name for entry in result.entries}
            while result.has_more:
                result = self.dbx.files_list_folder_continue(result.cursor)
                files.update(entry.name for entry in result.entries)
            return files
        except Exception:
            logger.exception("Error al listar archivos en Dropbox:")
            return set()
    
    @retry_with_backoff()
    def upload_file(self, local_path: str, remote_name: str, progress: Progress | None = None) -> bool:
        """Sube un archivo a Dropbox con soporte para archivos grandes."""
        if not self.dbx:
            logger.error(f"{self._log_prefix()} Cliente de Dropbox no inicializado.")
            return False
        
        logger.info(f"{self._log_prefix()} Subiendo: {remote_name}...")
        # La limpieza del archivo local es responsabilidad del llamador
        # (sync_to_storage hace rmtree del temp_dir). Dejar que las excepciones
        # transitorias propaguen para que retry_with_backoff pueda reintentar.
        file_size = os.path.getsize(local_path)

        task_id = None
        if progress is not None:
            task_id = progress.add_task(description="Upload", filename=remote_name, total=float(file_size))

        with open(local_path, 'rb') as f:
            if file_size <= CHUNK_SIZE:
                self.dbx.files_upload(f.read(), f'/{remote_name}', mode=WriteMode.overwrite)
                if progress is not None and task_id is not None:
                    progress.update(task_id, advance=float(file_size))
            else:
                # Upload session para archivos grandes
                chunk = f.read(CHUNK_SIZE)
                upload_session_start = self.dbx.files_upload_session_start(chunk)
                cursor = UploadSessionCursor(
                    session_id=upload_session_start.session_id,
                    offset=len(chunk)
                )
                commit = CommitInfo(path=f'/{remote_name}', mode=WriteMode.overwrite)

                if progress is not None and task_id is not None:
                    progress.update(task_id, advance=float(len(chunk)))

                # Subir chunks restantes
                while True:
                    remaining = file_size - cursor.offset
                    if remaining <= CHUNK_SIZE:
                        final_chunk = f.read(remaining)
                        self.dbx.files_upload_session_finish(final_chunk, cursor, commit)
                        if progress is not None and task_id is not None:
                            progress.update(task_id, advance=float(len(final_chunk)))
                        break
                    else:
                        next_chunk = f.read(CHUNK_SIZE)
                        self.dbx.files_upload_session_append_v2(next_chunk, cursor)
                        cursor.offset += len(next_chunk)
                        if progress is not None and task_id is not None:
                            progress.update(task_id, advance=float(len(next_chunk)))

        logger.info(f"{self._log_prefix()} Archivo subido correctamente.")
        return True
    
    @retry_with_backoff()
    def delete_file(self, file_name: str) -> bool:
        """Elimina un archivo de Dropbox."""
        if not self.dbx:
            logger.error(f"{self._log_prefix()} Cliente de Dropbox no inicializado.")
            return False
        
        logger.info(f"{self._log_prefix()} Eliminando: {file_name}...")
        try:
            self.dbx.files_delete_v2(f'/{file_name}')
            return True
        except Exception:
            logger.exception("Error al eliminar archivo:")
            return False
    
    def upload_files(self, file_paths: list[str]) -> set[str]:
        """Sube archivos en paralelo a Dropbox. Retorna basenames subidos OK."""
        return self._run_parallel_uploads(file_paths)

    def get_provider_name(self) -> str:
        return "Dropbox"


# ==========================================
# PROVEEDOR DE GOOGLE DRIVE
# ==========================================
class GoogleDriveProvider(StorageProvider):
    """Implementación de StorageProvider para Google Drive."""
    
    def __init__(self) -> None:
        self.service: Any = None
        self.credentials: Any = None
        self.folder_id: str = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        if not self.folder_id:
            self.folder_id = "root"
        self.folder_name: str = os.environ.get("GOOGLE_DRIVE_FOLDER", "").strip()
        if not self.folder_name:
            self.folder_name = "PESync_Backup"
        self.session = requests.Session()
        # httplib2 (bajo self.service) NO es thread-safe: serializa su acceso
        # para evitar SSLError (DECRYPTION_FAILED_OR_BAD_RECORD_MAC) en uploads
        # paralelos. self.session (requests/urllib3) sí es thread-safe.
        self._service_lock = threading.Lock()
    
    def connect(self) -> bool:
        """Inicializa el cliente de Google Drive."""
        try:
            client_id = os.environ["GOOGLE_DRIVE_CLIENT_ID"]
            client_secret = os.environ["GOOGLE_DRIVE_CLIENT_SECRET"]
            refresh_token = os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"]
        except KeyError as e:
            logger.error(f"Error: La variable de entorno {e} no está configurada.")
            return False
        
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            self.credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token"
            )
            
            self.service = build('drive', 'v3', credentials=self.credentials)
            # Verificar conexión
            self.service.about().get(fields="user").execute()
            logger.info(f"{self._log_prefix()} Cliente inicializado correctamente.")
            
            # Resolver folder_id si es necesario
            if self.folder_name and self.folder_id == "root":
                self._resolve_folder_id()
                
            return True
        except Exception:
            logger.exception("Error al conectar a Google Drive:")
            return False
            
    def _resolve_folder_id(self) -> None:
        """Busca la carpeta por nombre o la crea si no existe."""
        if not self.service or not self.folder_name:
            return
            
        try:
            query = f"name='{self.folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            if files:
                self.folder_id = cast(str, files[0]['id'])
                logger.info(f"{self._log_prefix()} Carpeta encontrada: '{self.folder_name}' (ID: {self.folder_id})")
            else:
                logger.info(f"{self._log_prefix()} Creando carpeta: '{self.folder_name}'")
                file_metadata = {'name': self.folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
                folder = self.service.files().create(body=file_metadata, fields='id').execute()
                self.folder_id = cast(str, folder.get('id'))
                logger.info(f"{self._log_prefix()} Carpeta creada (ID: {self.folder_id})")
        except Exception:
            logger.exception(f"Error al resolver carpeta '{self.folder_name}':")
            self.folder_id = "root"
    
    @retry_with_backoff()
    def list_files(self) -> set[str]:
        """Lista archivos en la carpeta de Google Drive."""
        if not self.service:
            return set()
        
        try:
            query = f"'{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query, pageSize=1000, fields="files(name)").execute()
            items = results.get('files', [])
            return {str(item['name']) for item in items}
        except Exception:
            logger.exception("Error al listar archivos en Google Drive:")
            return set()

    def _find_files_by_name(self, file_name: str) -> list[dict[str, str]]:
        """Busca archivos no eliminados con nombre exacto en la carpeta configurada."""
        if not self.service:
            return []

        escaped_name = file_name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name='{escaped_name}' and "
            f"'{self.folder_id}' in parents and "
            "trashed=false"
        )
        with self._service_lock:
            results = self.service.files().list(
                q=query,
                pageSize=100,
                fields="files(id, name)",
            ).execute()
        return [
            {"id": str(item["id"]), "name": str(item["name"])}
            for item in results.get("files", [])
            if "id" in item and "name" in item
        ]

    def _delete_files_by_id(self, files: list[dict[str, str]]) -> None:
        """Elimina duplicados por ID sin interrumpir una subida exitosa."""
        if not self.service:
            return

        for file_info in files:
            try:
                with self._service_lock:
                    self.service.files().delete(fileId=file_info["id"]).execute()
                logger.info(
                    f"{self._log_prefix()} Duplicado eliminado: {file_info['name']}"
                )
            except Exception:
                logger.exception(
                    f"Error al eliminar duplicado en Google Drive: {file_info}"
                )
    
    @retry_with_backoff()
    def upload_file(self, local_path: str, remote_name: str, progress: Progress | None = None) -> bool:
        """Sube un archivo a Google Drive usando carga resumible e idempotente."""
        if not self.service:
            return False
        
        logger.info(f"{self._log_prefix()} Subiendo: {remote_name}...")
        # La limpieza del archivo local es responsabilidad del llamador
        # (sync_to_storage hace rmtree del temp_dir). Dejar que las excepciones
        # transitorias propaguen para que retry_with_backoff pueda reintentar.
        from google.auth.transport.requests import Request
        self.credentials.refresh(Request())
        access_token = self.credentials.token

        file_size = os.path.getsize(local_path)
        task_id = None
        if progress is not None:
            task_id = progress.add_task(description="Upload", filename=remote_name, total=float(file_size))

        existing_files = self._find_files_by_name(remote_name)
        file_to_update = existing_files[0] if existing_files else None
        duplicate_files = existing_files[1:]

        # Iniciar sesión de carga resumible
        if file_to_update:
            init_url = (
                "https://www.googleapis.com/upload/drive/v3/files/"
                f"{file_to_update['id']}?uploadType=resumable"
            )
            metadata = {"name": remote_name}
            start_upload = self.session.patch
        else:
            init_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
            metadata = {"name": remote_name, "parents": [self.folder_id]}
            start_upload = self.session.post

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/octet-stream",
            "X-Upload-Content-Length": str(file_size)
        }

        response = start_upload(init_url, headers=headers, json=metadata, timeout=30)
        response.raise_for_status()
        upload_url = response.headers.get("Location")

        if not upload_url:
            return False

        with open(local_path, "rb") as f:
            offset = 0
            while offset < file_size:
                chunk_data = f.read(CHUNK_SIZE)
                if not chunk_data: break

                chunk_len = len(chunk_data)
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Range": f"bytes {offset}-{offset + chunk_len - 1}/{file_size}",
                    "Content-Length": str(chunk_len)
                }

                self.session.put(upload_url, headers=headers, data=chunk_data, timeout=300).raise_for_status()
                offset += chunk_len
                if progress is not None and task_id is not None:
                    progress.update(task_id, advance=float(chunk_len))

        if duplicate_files:
            self._delete_files_by_id(duplicate_files)

        logger.info(f"{self._log_prefix()} Archivo subido correctamente.")
        return True
    
    @retry_with_backoff()
    def delete_file(self, file_name: str) -> bool:
        """Elimina un archivo de Google Drive."""
        if not self.service:
            return False
        
        try:
            query = f"name='{file_name}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query, pageSize=1, fields="files(id)").execute()
            files = results.get('files', [])
            if not files: return False
            
            self.service.files().delete(fileId=files[0]['id']).execute()
            logger.info(f"{self._log_prefix()} Archivo eliminado: {file_name}")
            return True
        except Exception:
            logger.exception("Error al eliminar en Google Drive:")
            return False
    
    def upload_files(self, file_paths: list[str]) -> set[str]:
        """Sube archivos en paralelo a Google Drive. Retorna basenames subidos OK."""
        return self._run_parallel_uploads(file_paths)

    def get_provider_name(self) -> str:
        return "Google Drive"


# ==========================================
# FÁBRICA DE PROVEEDORES
# ==========================================
def get_storage_provider() -> StorageProvider | None:
    """Retorna el proveedor de almacenamiento configurado."""
    provider = os.environ.get("STORAGE_PROVIDER", "dropbox").lower()
    if provider == "googledrive": return GoogleDriveProvider()
    return DropboxProvider()
