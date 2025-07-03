"""
Testes para o Rate-Limiter
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from src.execution.rate_limiter import IntelligentRateLimiter

class TestRateLimiter:
    """Testes para o IntelligentRateLimiter"""
    
    def test_init(self):
        """Teste de inicialização"""
        limiter = IntelligentRateLimiter(safety_factor=0.8, emergency_threshold=0.9)
        assert limiter.safety_factor == 0.8
        assert limiter.emergency_threshold == 0.9
        assert limiter.emergency_mode is False
        assert limiter.weight_limit == limiter.DEFAULT_WEIGHT_LIMIT
        assert limiter.order_limit == limiter.DEFAULT_ORDER_LIMIT
    
    def test_check_and_wait_no_wait(self):
        """Teste de check_and_wait sem espera"""
        limiter = IntelligentRateLimiter()
        
        # Primeiro request não deve esperar
        wait_time = limiter.check_and_wait('test_endpoint', 1)
        assert wait_time == 0.0
        
        # Verificar se o uso foi registrado
        assert len(limiter.weight_window) == 1
        assert limiter.weight_window[0][1] == 1  # weight
    
    def test_check_and_wait_order(self):
        """Teste de check_and_wait para ordens"""
        limiter = IntelligentRateLimiter()
        
        # Primeiro request de ordem não deve esperar
        wait_time = limiter.check_and_wait('order', 1)
        assert wait_time == 0.0
        
        # Verificar se o uso foi registrado
        assert len(limiter.weight_window) == 1
        assert len(limiter.order_window) == 1
    
    @patch('time.sleep')
    def test_check_and_wait_with_wait(self, mock_sleep):
        """Teste de check_and_wait com espera"""
        limiter = IntelligentRateLimiter(safety_factor=0.5)  # Limite efetivo = 600
        
        # Simular janela cheia
        now = time.time()
        with limiter.weight_lock:
            limiter.weight_window = [(now, 500)]
        
        # Próximo request deve esperar
        limiter.check_and_wait('test_endpoint', 200)
        
        # Verificar se sleep foi chamado
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')
    def test_check_and_wait_order_with_wait(self, mock_sleep):
        """Teste de check_and_wait para ordens com espera"""
        limiter = IntelligentRateLimiter(safety_factor=0.5)  # Limite efetivo = 25
        
        # Simular janela cheia
        now = time.time()
        with limiter.order_lock:
            limiter.order_window = [now] * 25
        
        # Próximo request deve esperar
        limiter.check_and_wait('order', 1)
        
        # Verificar se sleep foi chamado
        mock_sleep.assert_called_once()
    
    def test_emergency_mode(self):
        """Teste de modo de emergência"""
        limiter = IntelligentRateLimiter(emergency_threshold=0.8)
        
        # Simular uso alto
        now = time.time()
        with limiter.weight_lock:
            limiter.weight_window = [(now, int(limiter.weight_limit * 0.85))]
        
        # Deve ativar modo de emergência
        limiter.check_and_wait('test_endpoint', 1)
        assert limiter.emergency_mode is True
        
        # Simular uso baixo
        with limiter.weight_lock:
            limiter.weight_window = [(now, int(limiter.weight_limit * 0.6))]
        
        # Deve desativar modo de emergência
        limiter.check_and_wait('test_endpoint', 1)
        assert limiter.emergency_mode is False
    
    def test_update_limits(self):
        """Teste de atualização de limites"""
        limiter = IntelligentRateLimiter()
        
        # Atualizar limites
        limiter.update_limits(weight_limit=2000, order_limit=100)
        
        assert limiter.weight_limit == 2000
        assert limiter.order_limit == 100
    
    @patch('requests.get')
    def test_update_exchange_info(self, mock_get):
        """Teste de atualização de informações da exchange"""
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'rateLimits': [
                {
                    'rateLimitType': 'REQUEST_WEIGHT',
                    'interval': 'MINUTE',
                    'limit': 2000
                },
                {
                    'rateLimitType': 'ORDERS',
                    'interval': 'SECOND',
                    'intervalNum': 10,
                    'limit': 100
                }
            ]
        }
        mock_get.return_value = mock_response
        
        limiter = IntelligentRateLimiter()
        limiter._update_exchange_info()
        
        assert limiter.weight_limit == 2000
        assert limiter.order_limit == 100
    
    def test_get_status(self):
        """Teste de obtenção de status"""
        limiter = IntelligentRateLimiter()
        
        # Simular uso
        now = time.time()
        with limiter.weight_lock:
            limiter.weight_window = [(now, 100)]
        with limiter.order_lock:
            limiter.order_window = [now, now]
        
        status = limiter.get_status()
        
        assert status['weight_limit'] == limiter.weight_limit
        assert status['order_limit'] == limiter.order_limit
        assert status['current_weight'] == 100
        assert status['current_orders'] == 2
        assert status['emergency_mode'] is False
    
    def test_thread_safety(self):
        """Teste de thread-safety"""
        limiter = IntelligentRateLimiter()
        
        # Função para thread
        def worker():
            for _ in range(10):
                limiter.check_and_wait('test_endpoint', 1)
        
        # Criar e iniciar threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Aguardar threads
        for t in threads:
            t.join()
        
        # Verificar se o uso foi registrado corretamente
        with limiter.weight_lock:
            assert len(limiter.weight_window) == 50  # 5 threads * 10 calls

