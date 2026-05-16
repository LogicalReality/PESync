import pytest # type: ignore
import os
from unittest.mock import MagicMock, mock_open, patch
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


def _google_drive_provider(existing_files):
    provider = GoogleDriveProvider()
    provider.folder_id = "folder-1"
    provider.service = MagicMock()
    provider.credentials = MagicMock(token="token")
    provider.session = MagicMock()
    provider.service.files.return_value.list.return_value.execute.return_value = {
        "files": existing_files
    }

    response = MagicMock()
    response.headers = {"Location": "https://upload.example/session"}
    response.raise_for_status.return_value = None
    provider.session.post.return_value = response
    provider.session.patch.return_value = response
    provider.session.put.return_value.raise_for_status.return_value = None
    return provider


def test_google_drive_upload_creates_file_when_missing():
    provider = _google_drive_provider([])

    with (
        patch("src.providers.storage_providers.os.path.getsize", return_value=4),
        patch("src.providers.storage_providers.os.path.exists", return_value=False),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        assert provider.upload_file("local.bin", "remote.bin") is True

    provider.session.post.assert_called_once()
    provider.session.patch.assert_not_called()
    provider.service.files.return_value.delete.assert_not_called()


def test_google_drive_upload_updates_existing_file():
    provider = _google_drive_provider([{"id": "file-1", "name": "remote.bin"}])

    with (
        patch("src.providers.storage_providers.os.path.getsize", return_value=4),
        patch("src.providers.storage_providers.os.path.exists", return_value=False),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        assert provider.upload_file("local.bin", "remote.bin") is True

    provider.session.patch.assert_called_once()
    assert "/file-1?uploadType=resumable" in provider.session.patch.call_args.args[0]
    provider.session.post.assert_not_called()
    provider.service.files.return_value.delete.assert_not_called()


def test_google_drive_upload_cleans_duplicate_files_after_update():
    provider = _google_drive_provider([
        {"id": "file-1", "name": "remote.bin"},
        {"id": "file-2", "name": "remote.bin"},
        {"id": "file-3", "name": "remote.bin"},
    ])

    with (
        patch("src.providers.storage_providers.os.path.getsize", return_value=4),
        patch("src.providers.storage_providers.os.path.exists", return_value=False),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        assert provider.upload_file("local.bin", "remote.bin") is True

    provider.session.patch.assert_called_once()
    deleted_ids = [
        call.kwargs["fileId"]
        for call in provider.service.files.return_value.delete.call_args_list
    ]
    assert deleted_ids == ["file-2", "file-3"]
