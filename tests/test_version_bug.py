import pytest
from unittest.mock import patch, MagicMock
from src.core.backup_logic import collect_emu_pending
from src.utils.helpers import EMU_ASSET_IDENTIFIER

def test_version_substring_bug():
    """
    REPRODUCCIÓN DEL BUG:
    Si tenemos v0.2.0-rc2 en el backup, el bot NO debe creer que ya tiene v0.2.0.
    """
    # 1. Simulamos que en el storage YA TENEMOS la versión RC2
    # El nombre del archivo contiene 'v0.2.0' como substring de 'v0.2.0-rc2'
    filename_rc2 = f"emu-{EMU_ASSET_IDENTIFIER}-v0.2.0-rc2.zip"
    backed_up = {filename_rc2}
    
    # 2. Simulamos que GitHub nos devuelve la versión estable v0.2.0 y la RC2
    mock_releases = [
        {
            "tag_name": "v0.2.0",
            "assets": [{"name": f"emu-{EMU_ASSET_IDENTIFIER}-v0.2.0.zip", "browser_download_url": "http://ex.com/stable"}]
        },
        {
            "tag_name": "v0.2.0-rc2",
            "assets": [{"name": filename_rc2, "browser_download_url": "http://ex.com/rc2"}]
        }
    ]
    
    with patch('src.core.backup_logic.get_emu_releases') as mock_get:
        mock_get.return_value = mock_releases
        
        # Ejecutamos la lógica de detección
        items_to_download, files_to_delete = collect_emu_pending(backed_up)
        
        # EXPECTATIVA: v0.2.0 DEBERÍA estar en la lista para descargar
        tags_a_descargar = [item[1] for item in items_to_download]
        
        # Este assert VA A FALLAR con el código actual porque el bot cree que v0.2.0 ya está (por el substring)
        assert any("v0.2.0.zip" in f and "-rc2" not in f for f in tags_a_descargar), \
            f"El bot ignoró la versión estable v0.2.0 porque encontró {filename_rc2}"
