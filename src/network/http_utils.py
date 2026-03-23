from __future__ import annotations
import os
import requests  # type: ignore
import time
from typing import Any, cast
from bs4 import BeautifulSoup  # type: ignore
from rich.progress import Progress  # type: ignore

# Importar herramientas locales
from src.utils.helpers import (
    logger,
    MAX_RETRIES,
    RETRY_DELAY,
    retry_with_backoff,
    calculate_sha256,
) # type: ignore
from src.config import config # type: ignore


def is_valid_link(link: str) -> bool:
    return link.startswith("https://") and link.endswith(".zip")


@retry_with_backoff()
def get_emu_releases(n: int = 2) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            config.emu_releases_api_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            logger.warning("No se encontraron versiones.")
            return []
        # Usar cast para evitar que Pyre se confunda con el slice
        return cast(list[Any], data[:n])
    except Exception:
        logger.exception("Error al obtener las versiones:")
        return []


@retry_with_backoff()
def get_latest_links(url: str, limit: int = 2) -> list[str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    response.raise_for_status()
    html = response.text

    soup = BeautifulSoup(html, "lxml")
    links: list[str] = [
        str(a["href"])
        for a in soup.find_all("a", href=True)
        if is_valid_link(str(a["href"]))
    ]

    if not links:
        logger.critical(
            "No se encontraron recursos válidos. ¡La estructura remota podría haber cambiado!"
        )
        return []

    unique_links: list[str] = list(dict.fromkeys(links))
    return cast(list[str], unique_links[:limit])


@retry_with_backoff()
def download_asset(url: str, file_name: str, progress: Progress | None = None) -> str | None:
    """Descarga un activo y retorna su hash SHA256 en caso de éxito."""
    logger.info(f"Descargando: {file_name}...")
    try:
        response = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0", "Referer": config.referer_url}, stream=True, timeout=30
        )
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        task_id = None
        if progress:
            task_id = progress.add_task(
                "download", filename=os.path.basename(file_name), total=total_size
            )

        with open(file_name, "wb") as f:
            for data in response.iter_content(chunk_size=1024 * 1024):
                f.write(data)
                if progress and task_id:
                    progress.update(task_id, advance=len(data))
        
        # Calcular y retornar el hash del archivo descargado
        file_hash = calculate_sha256(file_name)
        if file_hash:
            logger.info(f"✓ Descarga verificada [{os.path.basename(file_name)}]: {file_hash[:8]}...")
            return file_hash
        
        return None

    except Exception as e:
        logger.error(f"Error descargando {file_name}: {e}")
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except OSError:
                pass
        raise e
