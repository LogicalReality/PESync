"""PESync - Centralized configuration management."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import yaml

CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"


def xor_cipher(data: str, key: str = "pesync_2026") -> str:
    """Decodes XOR-ciphered hex string or encodes plain text to hex."""
    try:
        data_bytes = bytes.fromhex(data)
        return bytes(
            b ^ ord(key[i % len(key)]) for i, b in enumerate(data_bytes)
        ).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return bytes(ord(c) ^ ord(key[i % len(key)]) for i, c in enumerate(data)).hex()


def _load_yaml() -> dict[str, Any]:
    """Load configuration from config.yaml."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _decode_url(encoded: str) -> str:
    """Decode a single XOR-ciphered URL from config."""
    return xor_cipher(encoded)


class Config:
    """Singleton configuration class that loads and exposes typed config values."""

    _instance: Config | None = None
    _data: dict[str, Any]

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """Load configuration from YAML file."""
        self._data = _load_yaml()

    @property
    def emu_releases_api_url(self) -> str:
        return _decode_url(self._data["sources"]["emu_releases_api"])

    @property
    def emu_asset_identifier(self) -> str:
        return _decode_url(self._data["sources"]["emu_asset_id"])

    @property
    def licenses_url(self) -> str:
        return _decode_url(self._data["sources"]["licenses"])

    @property
    def system_url(self) -> str:
        return _decode_url(self._data["sources"]["system"])

    @property
    def referer_url(self) -> str:
        return _decode_url(self._data["sources"]["referer"])

    @property
    def backup_count(self) -> int:
        return int(self._data["sync"]["backup_count"])

    @property
    def parallel_workers(self) -> int:
        return int(self._data["sync"]["parallel_workers"])

    @property
    def max_retries(self) -> int:
        return int(self._data["sync"]["max_retries"])

    @property
    def retry_delay(self) -> int:
        return int(self._data["sync"]["retry_delay"])

    @property
    def chunk_size_mb(self) -> int:
        return int(self._data["sync"]["chunk_size_mb"])

    @property
    def chunk_size_bytes(self) -> int:
        return self.chunk_size_mb * 1024 * 1024

    @property
    def default_provider(self) -> str:
        return self._data["providers"]["default"]

    @property
    def google_drive_folder(self) -> str:
        return self._data["providers"]["google_drive_folder"]


config = Config()
