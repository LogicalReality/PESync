# pyre-ignore-all-errors[21]
from __future__ import annotations
import os
import requests # type: ignore
import time
from typing import Any
from bs4 import BeautifulSoup # type: ignore
from rich.progress import Progress

# Importar herramientas locales
from src.utils.helpers import (  # pyre-ignore[21]
    logger,
    MAX_RETRIES,
    RETRY_DELAY,
    EMU_RELEASES_API_URL,
    xor_cipher
)

def is_valid_link(link: str) -> bool:
    return link.startswith("https://") and link.endswith(".zip")

def get_emu_releases(n: int = 2) -> list[dict[str, Any]]:
    try:
        response = requests.get(EMU_RELEASES_API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not data:
            logger.warning("No se encontraron versiones.")
            return []
        return data[:n] # type: ignore
    except Exception:
        logger.exception("Error al obtener las versiones:")
        return []

def get_latest_links(url: str, limit: int = 2, max_retries: int = MAX_RETRIES) -> list[str]:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, 'html.parser')
            links: list[str] = [str(a['href']) for a in soup.find_all('a', href=True) if is_valid_link(str(a['href']))]

            if not links:
                logger.critical("No se encontraron recursos válidos. ¡La estructura remota podría haber cambiado!")
                return []

            unique_links: list[str] = list(dict.fromkeys(links))
            return unique_links[:limit] # type: ignore

        except Exception:
            logger.warning(f"Intento {attempt + 1} fallido:")
            if attempt < max_retries - 1:
                logger.info("Reintentando en 5 segundos...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Máximo de reintentos alcanzado.")
                return []
    return []

def download_asset(url: str, file_name: str, progress: Progress | None = None) -> bool:
    logger.info(f"Descargando: {file_name}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': xor_cipher("181107091d59701d404059140e16001d4d3157441d")
        }
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            
            total_size = int(r.headers.get('content-length', 0))
            task_id = None
            if progress is not None:
                task_id = progress.add_task(description="Download", filename=os.path.basename(file_name), total=total_size)
            
            with open(file_name, 'wb') as f:
                # Usar chunk de 1MB
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        if progress is not None and task_id is not None:
                            progress.update(task_id, advance=len(chunk))
                    
        logger.info(f"Descarga completada exitosamente: {file_name}")
        return True
    except Exception:
        logger.exception(f"Error al descargar {file_name}:")
        return False

