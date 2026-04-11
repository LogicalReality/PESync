import pytest  # type: ignore
import os
import hashlib
from src.utils.helpers import calculate_sha256 # type: ignore

def test_calculate_sha256(tmp_path):
    """Verifica el cálculo del hash SHA256."""
    content = b"PESync integrity test"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(content)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    actual_hash = calculate_sha256(str(test_file))
    
    assert actual_hash == expected_hash

def test_calculate_sha256_missing_file():
    """Verifica que retorne cadena vacía si el archivo no existe."""
    assert calculate_sha256("non_existent_file.zip") == ""

def test_sha256_consistency_large_file(tmp_path):
    """Verifica la consistencia con archivos que exceden el tamaño de bloque (64KB)."""
    # 100KB de datos aleatorios
    content = os.urandom(100 * 1024)
    test_file = tmp_path / "large_test.bin"
    test_file.write_bytes(content)
    
    expected_hash = hashlib.sha256(content).hexdigest()
    actual_hash = calculate_sha256(str(test_file))
    
    assert actual_hash == expected_hash
