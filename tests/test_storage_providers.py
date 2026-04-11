import pytest # type: ignore
import os
from src.providers.storage_providers import DropboxProvider, GoogleDriveProvider # type: ignore

def test_dropbox_provider_name():
    provider = DropboxProvider()
    assert provider.get_provider_name() == "Dropbox"

def test_google_drive_provider_name():
    provider = GoogleDriveProvider()
    assert provider.get_provider_name() == "Google Drive"

def test_dropbox_connect_fail(mocker):
    """Verifica que connect() falle si faltan variables de entorno."""
    mocker.patch.dict(os.environ, {}, clear=True)
    provider = DropboxProvider()
    assert provider.connect() is False

def test_google_drive_connect_fail(mocker):
    """Verifica que connect() falle si faltan variables de entorno."""
    mocker.patch.dict(os.environ, {}, clear=True)
    provider = GoogleDriveProvider()
    assert provider.connect() is False
