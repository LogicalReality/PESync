import pytest  # type: ignore
import hashlib
from unittest.mock import mock_open, patch
from src.utils.helpers import calculate_sha256 # type: ignore

def test_calculate_sha256():
    """Verifica el cálculo del hash SHA256."""
    content = b"PESync integrity test"
    
    expected_hash = hashlib.sha256(content).hexdigest()
    with patch("builtins.open", mock_open(read_data=content)):
        actual_hash = calculate_sha256("test.txt")
    
    assert actual_hash == expected_hash

def test_calculate_sha256_missing_file():
    """Verifica que retorne cadena vacía si el archivo no existe."""
    assert calculate_sha256("non_existent_file.zip") == ""

def test_sha256_consistency_large_file():
    """Verifica la consistencia con archivos que exceden el tamaño de bloque (64KB)."""
    # 100KB de datos aleatorios
    content = b"x" * (100 * 1024)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    with patch("builtins.open", mock_open(read_data=content)):
        actual_hash = calculate_sha256("large_test.bin")
    
    assert actual_hash == expected_hash
