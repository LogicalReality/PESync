import pytest # type: ignore
import time
from unittest.mock import MagicMock
from src.utils.helpers import retry_with_backoff # type: ignore

def test_retry_with_backoff_success():
    """Verifica que una función que tiene éxito no se reintente."""
    mock_func = MagicMock(return_value="success")
    
    @retry_with_backoff(max_retries=3, initial_delay=0.01)
    def decorated_func():
        return mock_func()
    
    result = decorated_func()
    assert result == "success"
    assert mock_func.call_count == 1

def test_retry_with_backoff_eventual_success(mocker):
    """Verifica que reintente y tenga éxito eventualmente."""
    # Simulamos que falla 2 veces y tiene éxito a la 3ra
    mock_func = mocker.Mock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])
    
    # Mockeamos time.sleep para que el test sea rápido
    mocker.patch("time.sleep")
    
    @retry_with_backoff(max_retries=5, initial_delay=0.01, exceptions=(ValueError,))
    def decorated_func():
        return mock_func()
    
    result = decorated_func()
    assert result == "Success"
    assert mock_func.call_count == 3

def test_retry_with_backoff_max_reached(mocker):
    """Verifica que lance la excepción al agotar reintentos."""
    mock_func = mocker.Mock(side_effect=ValueError("Permanent Fail"))
    mocker.patch("time.sleep")
    
    @retry_with_backoff(max_retries=2, initial_delay=0.01, exceptions=(ValueError,))
    def decorated_func():
        return mock_func()
    
    with pytest.raises(ValueError, match="Permanent Fail"):
        decorated_func()
    
    # Intento inicial (1) + 2 reintentos = 3 llamadas en total
    assert mock_func.call_count == 3
