import pytest # type: ignore
from unittest.mock import MagicMock

@pytest.fixture
def mock_dropbox_client(mocker):
    """Fixture para simular el cliente de Dropbox."""
    mock_dbx = mocker.patch("dropbox.Dropbox", autospec=True)
    return mock_dbx.return_value

@pytest.fixture
def mock_google_drive_service(mocker):
    """Fixture para simular el servicio de Google Drive."""
    mock_service = MagicMock()
    mocker.patch("googleapiclient.discovery.build", return_value=mock_service)
    return mock_service
