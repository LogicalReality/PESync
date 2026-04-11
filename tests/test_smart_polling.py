import pytest
from src.network.http_utils import get_latest_links, get_emu_releases
from src.core.backup_logic import collect_emu_pending, collect_generic_pending
from unittest.mock import MagicMock, patch

def test_get_latest_links_signature():
    """Verifica que get_latest_links retorne la tupla de 3 elementos."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><a href="https://example.com/test.zip"></a></html>'
        mock_response.headers = {'ETag': '123'}
        mock_get.return_value = mock_response
        
        links, headers, status = get_latest_links("http://example.com")
        assert isinstance(links, list)
        assert isinstance(headers, dict)
        assert status == 200
        assert headers['ETag'] == '123'

def test_get_latest_links_304():
    """Verifica el manejo de HTTP 304 en get_latest_links."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response
        
        links, headers, status = get_latest_links("http://example.com")
        assert links == []
        assert headers == {}
        assert status == 304

def test_collect_emu_pending_304():
    """Verifica que collect_emu_pending maneje el status 304 sin pedir list_files."""
    provider = MagicMock()
    # Si llama a list_files, el test fallará si no lo mockeamos (o podemos verificar que no se llamó)
    with patch('src.core.backup_logic.get_emu_releases') as mock_get:
        mock_get.return_value = ([], {}, 304)
        
        items, deletes, headers, changed, backed_up = collect_emu_pending(provider, headers={'If-None-Match': 'abc'})
        
        assert items == []
        assert deletes == []
        assert changed is False
        provider.list_files.assert_not_called()

def test_collect_generic_lazy_loading():
    """Verifica que collect_generic_pending pida list_files solo si hay un 200."""
    provider = MagicMock()
    provider.list_files.return_value = set()
    
    with patch('src.core.backup_logic.get_latest_links') as mock_get:
        mock_get.return_value = (['http://ex.com/v1.zip'], {'ETag': 'xyz'}, 200)
        
        # Caso 1: 200 OK -> Debe llamar a list_files porque backed_up es None
        items, deletes, headers, changed, backed_up = collect_generic_pending(
            provider, "url", "key", "CAT", ".zip", backed_up=None
        )
        
        assert changed is True
        provider.list_files.assert_called_once()
        assert headers['ETag'] == 'xyz'
def test_get_latest_links_fingerprint():
    """Verifica que el fingerprinting funcione para emular 304."""
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><a href="https://example.com/test.zip"></a></html>'
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_get.return_value = mock_response
        
        # Primera vez - Obtiene fingerprint
        links, headers, status = get_latest_links("http://example.com")
        fp = headers.get('X-PESync-Fingerprint')
        assert fp is not None
        assert status == 200
        
        # Segunda vez - Con el mismo fingerprint, debe dar 304
        links2, headers2, status2 = get_latest_links("http://example.com", headers={'X-PESync-Fingerprint': fp})
        assert status2 == 304
        assert links2 == []
