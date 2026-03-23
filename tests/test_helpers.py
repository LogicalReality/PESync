import unittest
from src.utils.helpers import normalize_filename, is_license_file # type: ignore

class TestHelpers(unittest.TestCase):
    def test_normalize_filename(self):
        """Verifica que la normalización de nombres elimine el prefijo 'firmware.'."""
        self.assertEqual(normalize_filename("Firmware.21.2.0.zip"), "21.2.0.zip")
        self.assertEqual(normalize_filename("emu.v0.2.0-rc1.zip"), "emu.v0.2.0-rc1.zip")

    def test_is_license_file(self):
        """Verifica la detección de archivos de licencia."""
        self.assertTrue(is_license_file("licencia_21.2.zip"))
        self.assertFalse(is_license_file("archivo_random.pdf"))

if __name__ == '__main__':
    unittest.main()
