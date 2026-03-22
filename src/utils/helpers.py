from __future__ import annotations
import os
import time
import logging
import logging.handlers
import re
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)  # type: ignore


def create_shared_progress() -> Progress:
    """Crea una barra de progreso estilo pip para usar con administradores de contexto."""
    return Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        transient=True,
    )


# ==========================================
# CONSTANTES GLOBALES
# ==========================================
from src.config import config # type: ignore

VERSION_REGEX = re.compile(r"(\d+\.\d+[\d.]*)\.zip", re.IGNORECASE)
TAG_REGEX = re.compile(r"v\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?")

MAX_RETRIES = config.max_retries
RETRY_DELAY = config.retry_delay
BACKUP_CONFIG = {
    "emu": config.backup_count,
    "licenses": config.backup_count,
    "system": config.backup_count,
}
EMU_ASSET_IDENTIFIER = config.emu_asset_identifier


# ==========================================
# TELEGRAM NOTIFICATIONS
# ==========================================
TELEGRAM_CONFIG_DOC = """
# Configuración de Notificaciones Telegram (opcional)
# TELEGRAM_BOT_TOKEN: Token del bot de Telegram (obtenido via @BotFather)
# TELEGRAM_CHAT_ID: Tu ID de chat (obtenido via @userinfobot)
# TELEGRAM_NOTIFICATIONS: "true" para habilitar, "false" para deshabilitar
"""


# ==========================================
# LOGGING
# ==========================================
def setup_logger(name: str = "pesync", log_file: str | None = None) -> logging.Logger:
    """Configura y retorna un logger con rotación de archivos y nombre por sesión."""
    if log_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join("logs", f"pesync_{timestamp}.log")

    # Asegurar que el directorio de logs existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evitar duplicados si el logger ya está configurado
    if logger.handlers:
        return logger

    # Formato con timestamp y nombre del módulo
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler para salida rapida (INFO y superiores)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_dir = os.path.dirname(log_file)
    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Eliminar logs antiguos si hay más de 5
        log_files = [
            os.path.join(log_dir, f)
            for f in os.listdir(log_dir)
            if f.startswith("pesync_") and f.endswith(".log")
        ]
        log_files.sort(key=os.path.getmtime)
        while len(log_files) >= 5:  # Dejar espacio para el nuevo
            oldest_log = log_files.pop(0)
            try:
                os.remove(oldest_log)
            except OSError:
                pass

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1 * 1024 * 1024,  # 1MB por archivo - suficiente para GHA y local
            backupCount=1,  # Mantener 1 archivo de backup por sesion
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.error(f"No se pudo inicializar log en archivo '{log_file}': {e}.")

    return logger


# Inicializar logger global para uso en utilidades
logger = setup_logger()


# ==========================================
# AYUDANTES (HELPERS)
# ==========================================
def normalize_filename(filename: str) -> str:
    """Normaliza nombre de archivo para comparación.

    Ejemplos:
        Firmware.21.2.0.zip -> 21.2.0.zip
        emu.v0.2.0-rc1.zip -> emu.v0.2.0-rc1.zip
    """
    if filename.lower().startswith("firmware."):
        return filename.split(".", 1)[-1]
    return filename


def is_license_file(f: str) -> bool:
    f_low = f.lower()
    return (
        f_low.endswith(".zip")
        and bool(re.search(r"\d+\.\d+", f))
        and "firmware" not in f_low
    )


def is_system_file(f: str) -> bool:
    f_low = f.lower()
    return f_low.endswith(".zip") and ("firmware" in f_low or "v19" in f_low)


def wait_for_exit(timeout: int = 15):
    """
    Espera a que el usuario presione Enter para salir.
    Si se presiona cualquier otra tecla durante el timeout, se cancela el cierre automático
    para todos los sistemas operativos (Windows y Unix-like).
    """
    import sys
    import time

    if sys.platform == "win32":
        import msvcrt

        start_time = time.time()
        while time.time() - start_time < timeout:
            remaining = int(timeout - (time.time() - start_time))
            print(
                f"\rPresiona Enter para salir o cualquier otra tecla para cancelar temporizador ({remaining}s)...   ",
                end="",
                flush=True,
            )
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                if char in ("\r", "\n"):
                    print()
                    return
                else:
                    print("\n[Temporizador cancelado]")
                    input("Presiona Enter para salir...")
                    return
            time.sleep(0.1)
        print("\n¡Tiempo agotado! Cerrando...")
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            start_time = time.time()
            while time.time() - start_time < timeout:
                remaining = int(timeout - (time.time() - start_time))
                print(
                    f"\rPresiona Enter para salir o cualquier otra tecla para cancelar temporizador ({remaining}s)...   ",
                    end="",
                    flush=True,
                )
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    char = sys.stdin.read(1)
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    if char in ("\r", "\n"):
                        print()
                        return
                    else:
                        print("\n\n[Temporizador cancelado]")
                        input("Presiona Enter para salir...")
                        return

            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("\n¡Tiempo agotado! Cerrando...")
            return
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
