import pytest
from src.network.http_utils import get_latest_links, get_emu_releases
from src.core.backup_logic import collect_emu_pending, collect_generic_pending
from unittest.mock import MagicMock, patch

def test_get_latest_links_signature():
    """Verifica que get_latest_links retorne la lista de links."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><a href="https://example.com/test.zip"></a></html>'
        mock_get.return_value = mock_response
        
        links = get_latest_links("https://example.com")
        assert isinstance(links, list)
        assert len(links) == 1
        assert links[0] == "https://example.com/test.zip"

def test_collect_emu_pending_basic():
    """Verifica el flujo básico de collect_emu_pending."""
    backed_up = set()
    with patch('src.core.backup_logic.get_emu_releases') as mock_get:
        mock_get.return_value = [
            {"tag_name": "v1.0.0", "assets": [{"name": "Emu-steamdeck-gcc-standard.AppImage-v1.0.0.zip", "browser_download_url": "http://ex.com/1"}]}
        ]
        
        items, deletes = collect_emu_pending(backed_up)
        
        assert len(items) == 1
        assert "v1.0.0" in items[0][1]
        assert deletes == []

def test_collect_generic_basic():
    """Verifica el flujo básico de collect_generic_pending."""
    backed_up = set()
    with patch('src.core.backup_logic.get_latest_links') as mock_get:
        mock_get.return_value = ["https://example.com/firmware.zip"]
        
        items, deletes = collect_generic_pending(
            backed_up, "https://example.com", "system", "SISTEMA", "firmware"
        )
        
        assert len(items) == 1
        assert items[0][1] == "firmware.zip"
        assert deletes == []
