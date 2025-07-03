"""
Testes para o sistema de retry com back-off exponencial
"""

import pytest
from unittest.mock import patch, MagicMock, call
import requests
from tenacity import RetryError

from src.execution.retry_utils import (
    retry_with_backoff,
    safe_order,
    safe_cancel_order,
    safe_fetch_balance,
    safe_fetch_ticker,
    safe_fetch_ohlcv,
    safe_fetch_funding_rate,
    robust_order_placement
)

class TestRetryUtils:
    """Testes para o sistema de retry com back-off exponencial"""
    
    def test_retry_with_backoff_success(self):
        """Teste de retry_with_backoff com sucesso"""
        # Função de teste que retorna um valor
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return "success"
        
        # Deve retornar o valor sem retry
        assert test_func() == "success"
    
    def test_retry_with_backoff_retry_success(self):
        """Teste de retry_with_backoff com retry e sucesso"""
        # Mock para contar chamadas
        mock_func = MagicMock()
        mock_func.side_effect = [ConnectionError("Erro de conexão"), "success"]
        
        # Função de teste que usa o mock
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_func()
        
        # Deve fazer retry e retornar o valor
        assert test_func() == "success"
        assert mock_func.call_count == 2
    
    def test_retry_with_backoff_max_attempts(self):
        """Teste de retry_with_backoff com máximo de tentativas"""
        # Mock que sempre falha
        mock_func = MagicMock()
        mock_func.side_effect = ConnectionError("Erro de conexão")
        
        # Função de teste que usa o mock
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_func()
        
        # Deve fazer retry e falhar
        with pytest.raises(ConnectionError):
            test_func()
        
        assert mock_func.call_count == 3
    
    def test_retry_with_backoff_custom_exceptions(self):
        """Teste de retry_with_backoff com exceções personalizadas"""
        # Mock que falha com exceção personalizada
        mock_func = MagicMock()
        mock_func.side_effect = [ValueError("Erro de valor"), "success"]
        
        # Função de teste que usa o mock
        @retry_with_backoff(max_attempts=3, exception_types=ValueError)
        def test_func():
            return mock_func()
        
        # Deve fazer retry e retornar o valor
        assert test_func() == "success"
        assert mock_func.call_count == 2
    
    def test_safe_order_ccxt(self):
        """Teste de safe_order com cliente ccxt"""
        # Mock de cliente ccxt
        client = MagicMock()
        client.create_order.return_value = {"id": "123"}
        
        # Chamar função
        result = safe_order(client, symbol="BTC/USDT", type="limit", side="buy", amount=1, price=50000)
        
        # Verificar resultado
        assert result == {"id": "123"}
        client.create_order.assert_called_once_with(
            symbol="BTC/USDT", type="limit", side="buy", amount=1, price=50000
        )
    
    def test_safe_order_binance(self):
        """Teste de safe_order com cliente python-binance"""
        # Mock de cliente python-binance
        client = MagicMock()
        client.create_order = None
        client.new_order.return_value = {"orderId": "123"}
        
        # Chamar função
        result = safe_order(client, symbol="BTCUSDT", side="BUY", type="LIMIT", quantity=1, price=50000)
        
        # Verificar resultado
        assert result == {"orderId": "123"}
        client.new_order.assert_called_once_with(
            symbol="BTCUSDT", side="BUY", type="LIMIT", quantity=1, price=50000
        )
    
    def test_safe_order_retry(self):
        """Teste de safe_order com retry"""
        # Mock de cliente que falha e depois sucede
        client = MagicMock()
        client.create_order.side_effect = [ConnectionError("Erro de conexão"), {"id": "123"}]
        
        # Chamar função
        result = safe_order(client, symbol="BTC/USDT", type="limit", side="buy", amount=1, price=50000)
        
        # Verificar resultado
        assert result == {"id": "123"}
        assert client.create_order.call_count == 2
    
    def test_safe_cancel_order(self):
        """Teste de safe_cancel_order"""
        # Mock de cliente
        client = MagicMock()
        client.cancel_order.return_value = {"id": "123", "status": "canceled"}
        
        # Chamar função
        result = safe_cancel_order(client, symbol="BTC/USDT", order_id="123")
        
        # Verificar resultado
        assert result == {"id": "123", "status": "canceled"}
        client.cancel_order.assert_called_once_with(symbol="BTC/USDT", order_id="123")
    
    def test_safe_fetch_balance(self):
        """Teste de safe_fetch_balance"""
        # Mock de cliente
        client = MagicMock()
        client.fetch_balance.return_value = {"BTC": {"free": 1.0, "used": 0.5, "total": 1.5}}
        
        # Chamar função
        result = safe_fetch_balance(client)
        
        # Verificar resultado
        assert result == {"BTC": {"free": 1.0, "used": 0.5, "total": 1.5}}
        client.fetch_balance.assert_called_once_with()
    
    def test_safe_fetch_ticker(self):
        """Teste de safe_fetch_ticker"""
        # Mock de cliente
        client = MagicMock()
        client.fetch_ticker.return_value = {"symbol": "BTC/USDT", "last": 50000}
        
        # Chamar função
        result = safe_fetch_ticker(client, symbol="BTC/USDT")
        
        # Verificar resultado
        assert result == {"symbol": "BTC/USDT", "last": 50000}
        client.fetch_ticker.assert_called_once_with("BTC/USDT")
    
    def test_safe_fetch_ohlcv(self):
        """Teste de safe_fetch_ohlcv"""
        # Mock de cliente
        client = MagicMock()
        client.fetch_ohlcv.return_value = [[1625097600000, 35000, 36000, 34000, 35500, 100]]
        
        # Chamar função
        result = safe_fetch_ohlcv(client, symbol="BTC/USDT", timeframe="1h")
        
        # Verificar resultado
        assert result == [[1625097600000, 35000, 36000, 34000, 35500, 100]]
        client.fetch_ohlcv.assert_called_once_with("BTC/USDT", "1h")
    
    def test_safe_fetch_funding_rate(self):
        """Teste de safe_fetch_funding_rate"""
        # Mock de cliente
        client = MagicMock()
        client.fetch_funding_rate.return_value = {"symbol": "BTC/USDT", "fundingRate": 0.0001}
        
        # Chamar função
        result = safe_fetch_funding_rate(client, symbol="BTC/USDT")
        
        # Verificar resultado
        assert result == {"symbol": "BTC/USDT", "fundingRate": 0.0001}
        client.fetch_funding_rate.assert_called_once_with("BTC/USDT")
    
    def test_robust_order_placement(self):
        """Teste de robust_order_placement"""
        # Mock de cliente
        client = MagicMock()
        client.create_order.return_value = {"id": "123"}
        
        # Mock de rate limiter
        rate_limiter = MagicMock()
        
        # Chamar função
        result = robust_order_placement(
            client,
            {"symbol": "BTC/USDT", "type": "limit", "side": "buy", "amount": 1, "price": 50000},
            rate_limiter=rate_limiter
        )
        
        # Verificar resultado
        assert result == {"id": "123"}
        rate_limiter.check_and_wait.assert_called_once_with("order", 1)
        client.create_order.assert_called_once_with(
            symbol="BTC/USDT", type="limit", side="buy", amount=1, price=50000
        )
    
    def test_robust_order_placement_no_rate_limiter(self):
        """Teste de robust_order_placement sem rate limiter"""
        # Mock de cliente
        client = MagicMock()
        client.create_order.return_value = {"id": "123"}
        
        # Chamar função
        result = robust_order_placement(
            client,
            {"symbol": "BTC/USDT", "type": "limit", "side": "buy", "amount": 1, "price": 50000}
        )
        
        # Verificar resultado
        assert result == {"id": "123"}
        client.create_order.assert_called_once_with(
            symbol="BTC/USDT", type="limit", side="buy", amount=1, price=50000
        )

