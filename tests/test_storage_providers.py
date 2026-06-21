import pytest # type: ignore
import os
import threading
import time
import requests
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


# ── Fix 1: el acceso al cliente httplib2 (self.service) debe serializarse ──────
def test_google_drive_service_access_is_serialized_across_threads():
    """Dos uploads en paralelo no deben usar self.service concurrentemente.

    Reproduce el SSLError (DECRYPTION_FAILED_OR_BAD_RECORD_MAC) causado por
    httplib2 no thread-safe. Con el lock, las llamadas a service se serializan.
    """
    provider = _google_drive_provider([])
    state = {"active": 0, "breached": False}
    guard = threading.Lock()

    def execute_side_effect(*args, **kwargs):
        with guard:
            state["active"] += 1
            if state["active"] > 1:
                state["breached"] = True
        time.sleep(0.02)
        with guard:
            state["active"] -= 1
        return {"files": []}

    provider.service.files.return_value.list.return_value.execute.side_effect = (
        execute_side_effect
    )

    with (
        patch("src.providers.storage_providers.os.path.getsize", return_value=4),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        result = provider.upload_files(["/tmp/a.bin", "/tmp/b.bin"])

    assert state["breached"] is False
    assert result == {"a.bin", "b.bin"}


# ── Fix 2: errores transitorios deben reintentarse, no tragarse ───────────────
def test_google_drive_upload_retries_on_transient_error(mocker):
    provider = _google_drive_provider([])
    mocker.patch("src.utils.helpers.time.sleep", return_value=None)
    calls = {"n": 0}

    def flaky(_name):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ConnectionError("transient")
        return []

    mocker.patch.object(provider, "_find_files_by_name", side_effect=flaky)

    with (
        patch("src.providers.storage_providers.os.path.getsize", return_value=4),
        patch("builtins.open", mock_open(read_data=b"data")),
    ):
        assert provider.upload_file("/tmp/a.bin", "a.bin") is True

    assert calls["n"] == 2


# ── Fix 3: upload_files retorna el set de basenames subidos OK (parcial) ───────
def test_google_drive_upload_files_returns_succeeded_basenames(mocker):
    provider = GoogleDriveProvider()

    def fake_upload(_local_path, remote_name, progress=None):
        if remote_name == "bad.bin":
            raise RuntimeError("boom")
        return True

    mocker.patch.object(provider, "upload_file", side_effect=fake_upload)
    result = provider.upload_files(["/tmp/good.bin", "/tmp/bad.bin"])
    assert result == {"good.bin"}


def test_google_drive_upload_files_empty_returns_empty_set():
    assert GoogleDriveProvider().upload_files([]) == set()


def test_dropbox_upload_files_returns_succeeded_basenames(mocker):
    provider = DropboxProvider()
    mocker.patch.object(
        provider, "upload_file", side_effect=lambda p, n, prog=None: n != "bad.bin"
    )
    result = provider.upload_files(["/tmp/good.bin", "/tmp/bad.bin"])
    assert result == {"good.bin"}


def test_dropbox_upload_files_empty_returns_empty_set():
    assert DropboxProvider().upload_files([]) == set()
