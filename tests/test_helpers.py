from src.utils.helpers import normalize_filename, is_license_file # type: ignore

def test_normalize_filename():
    """Verifica que la normalización de nombres elimine el prefijo 'firmware.'."""
    assert normalize_filename("Firmware.21.2.0.zip") == "21.2.0.zip"
    assert normalize_filename("emu.v0.2.0-rc1.zip") == "emu.v0.2.0-rc1.zip"

def test_is_license_file():
    """Verifica la detección de archivos de licencia."""
    assert is_license_file("licencia_21.2.zip") is True
    assert is_license_file("archivo_random.pdf") is False
