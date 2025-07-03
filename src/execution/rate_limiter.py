"""
Rate Limiter - Sistema inteligente de limitação de taxa para APIs da Binance

Este módulo implementa um sistema avançado de limitação de taxa para evitar
banimentos da API da Binance, gerenciando automaticamente os limites de
requisições e adaptando-se dinamicamente às mudanças nos limites da API.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import requests

from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class IntelligentRateLimiter:
    """
    Rate Limiter inteligente para APIs da Binance
    
    Características:
    - Gerenciamento de múltiplos endpoints com diferentes limites
    - Adaptação dinâmica aos limites da API
    - Cache de informações de exchange
    - Janela deslizante para controle preciso de limites
    - Modo de emergência para situações de alta carga
    """
    
    # Constantes para limites da Binance
    DEFAULT_WEIGHT_LIMIT = 1200  # Limite padrão para IP por minuto
    DEFAULT_ORDER_LIMIT = 50     # Limite padrão de ordens por 10 segundos
    EXCHANGE_INFO_CACHE_FILE = "exchange_info_cache.json"
    EXCHANGE_INFO_CACHE_TTL = 12 * 60 * 60  # 12 horas em segundos
    
    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 safety_factor: float = 0.9,
                 emergency_threshold: float = 0.95):
        """
        Inicializa o Rate Limiter
        
        Args:
            cache_dir: Diretório para cache de informações da exchange
            safety_factor: Fator de segurança para limites (0.0-1.0)
            emergency_threshold: Limite para ativar modo de emergência (0.0-1.0)
        """
        self.safety_factor = max(0.1, min(safety_factor, 0.99))
        self.emergency_threshold = max(0.5, min(emergency_threshold, 0.99))
        self.emergency_mode = False
        
        # Configurar diretório de cache
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(os.path.expanduser("~")) / ".btc_perpetual_elite" / "cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / self.EXCHANGE_INFO_CACHE_FILE
        
        # Inicializar limites
        self.weight_limit = self.DEFAULT_WEIGHT_LIMIT
        self.order_limit = self.DEFAULT_ORDER_LIMIT
        
        # Janelas deslizantes para controle de limites
        self.weight_window: List[Tuple[float, int]] = []  # (timestamp, weight)
        self.order_window: List[float] = []  # timestamps
        
        # Locks para thread-safety
        self.weight_lock = threading.Lock()
        self.order_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        
        # Carregar informações da exchange
        self._load_exchange_info()
        
        logger.info(f"IntelligentRateLimiter inicializado (safety={self.safety_factor:.2f}, "
                   f"emergency={self.emergency_threshold:.2f})")
    
    def check_and_wait(self, endpoint: str, weight: int = 1) -> float:
        """
        Verifica se uma requisição pode ser feita e espera se necessário
        
        Args:
            endpoint: Endpoint da API
            weight: Peso da requisição
            
        Returns:
            float: Tempo de espera em segundos (0 se não esperou)
        """
        # Verificar se é uma operação de ordem
        is_order = 'order' in endpoint.lower()
        
        # Calcular tempo de espera
        wait_time = 0.0
        
        if is_order:
            with self.order_lock:
                wait_time = self._check_order_limit()
        
        with self.weight_lock:
            weight_wait = self._check_weight_limit(weight)
            wait_time = max(wait_time, weight_wait)
        
        # Esperar se necessário
        if wait_time > 0:
            if wait_time > 5:  # Log apenas esperas significativas
                logger.warning(f"Rate limit: esperando {wait_time:.2f}s para endpoint {endpoint} (weight={weight})")
            time.sleep(wait_time)
        
        # Registrar uso
        self._register_usage(endpoint, weight, is_order)
        
        return wait_time
    
    def _check_weight_limit(self, weight: int) -> float:
        """
        Verifica o limite de peso e calcula tempo de espera
        
        Args:
            weight: Peso da requisição
            
        Returns:
            float: Tempo de espera em segundos
        """
        now = time.time()
        minute_ago = now - 60
        
        # Limpar janela deslizante
        self.weight_window = [(ts, w) for ts, w in self.weight_window if ts > minute_ago]
        
        # Calcular peso atual na janela
        current_weight = sum(w for _, w in self.weight_window)
        
        # Calcular limite efetivo com fator de segurança
        effective_limit = int(self.weight_limit * self.safety_factor)
        
        # Verificar modo de emergência
        if current_weight > self.weight_limit * self.emergency_threshold:
            if not self.emergency_mode:
                logger.warning(f"Ativando modo de emergência! Uso atual: {current_weight}/{self.weight_limit}")
                self.emergency_mode = True
        elif self.emergency_mode and current_weight < self.weight_limit * 0.7:
            logger.info(f"Desativando modo de emergência. Uso atual: {current_weight}/{self.weight_limit}")
            self.emergency_mode = False
        
        # Aplicar modo de emergência
        if self.emergency_mode:
            effective_limit = int(effective_limit * 0.7)  # Reduzir ainda mais em emergência
        
        # Verificar se excede o limite
        if current_weight + weight > effective_limit:
            # Calcular tempo até que haja espaço suficiente
            if not self.weight_window:
                return 0.0
            
            # Ordenar por timestamp
            sorted_window = sorted(self.weight_window, key=lambda x: x[0])
            
            # Calcular quanto peso precisa ser liberado
            needed_weight = current_weight + weight - effective_limit
            freed_weight = 0
            
            for ts, w in sorted_window:
                freed_weight += w
                if freed_weight >= needed_weight:
                    # Calcular tempo até este timestamp + 60s
                    wait_time = (ts + 60) - now
                    return max(0.0, wait_time)
            
            # Se chegou aqui, precisa esperar um minuto completo
            return 60.0
        
        return 0.0
    
    def _check_order_limit(self) -> float:
        """
        Verifica o limite de ordens e calcula tempo de espera
        
        Returns:
            float: Tempo de espera em segundos
        """
        now = time.time()
        ten_seconds_ago = now - 10
        
        # Limpar janela deslizante
        self.order_window = [ts for ts in self.order_window if ts > ten_seconds_ago]
        
        # Calcular número atual de ordens na janela
        current_orders = len(self.order_window)
        
        # Calcular limite efetivo com fator de segurança
        effective_limit = int(self.order_limit * self.safety_factor)
        
        # Verificar se excede o limite
        if current_orders + 1 > effective_limit:
            # Calcular tempo até que haja espaço suficiente
            if not self.order_window:
                return 0.0
            
            # Ordenar por timestamp
            sorted_window = sorted(self.order_window)
            
            # Calcular quantas ordens precisam ser liberadas
            needed_slots = current_orders + 1 - effective_limit
            
            if needed_slots <= len(sorted_window):
                # Calcular tempo até este timestamp + 10s
                wait_time = (sorted_window[needed_slots - 1] + 10) - now
                return max(0.0, wait_time)
            
            # Se chegou aqui, precisa esperar 10 segundos completos
            return 10.0
        
        return 0.0
    
    def _register_usage(self, endpoint: str, weight: int, is_order: bool) -> None:
        """
        Registra o uso de um endpoint
        
        Args:
            endpoint: Endpoint da API
            weight: Peso da requisição
            is_order: Se é uma operação de ordem
        """
        now = time.time()
        
        with self.weight_lock:
            self.weight_window.append((now, weight))
        
        if is_order:
            with self.order_lock:
                self.order_window.append(now)
    
    def update_limits(self, weight_limit: Optional[int] = None, order_limit: Optional[int] = None) -> None:
        """
        Atualiza os limites da API
        
        Args:
            weight_limit: Novo limite de peso
            order_limit: Novo limite de ordens
        """
        with self.weight_lock:
            if weight_limit is not None:
                old_limit = self.weight_limit
                self.weight_limit = weight_limit
                logger.info(f"Limite de peso atualizado: {old_limit} -> {weight_limit}")
        
        with self.order_lock:
            if order_limit is not None:
                old_limit = self.order_limit
                self.order_limit = order_limit
                logger.info(f"Limite de ordens atualizado: {old_limit} -> {order_limit}")
    
    def _load_exchange_info(self) -> None:
        """
        Carrega informações da exchange do cache ou da API
        """
        with self.cache_lock:
            # Verificar se o cache existe e é válido
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    # Verificar validade do cache
                    cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01T00:00:00'))
                    if (datetime.now() - cache_time).total_seconds() < self.EXCHANGE_INFO_CACHE_TTL:
                        # Cache válido
                        self.weight_limit = cache_data.get('weight_limit', self.DEFAULT_WEIGHT_LIMIT)
                        self.order_limit = cache_data.get('order_limit', self.DEFAULT_ORDER_LIMIT)
                        logger.info(f"Informações da exchange carregadas do cache (weight={self.weight_limit}, "
                                   f"order={self.order_limit})")
                        return
                except Exception as e:
                    logger.warning(f"Erro ao carregar cache: {e}")
            
            # Cache inválido ou inexistente, tentar atualizar
            self._update_exchange_info()
    
    def _update_exchange_info(self) -> None:
        """
        Atualiza informações da exchange da API
        """
        try:
            # Tentar obter informações da API da Binance
            response = requests.get('https://api.binance.com/api/v3/exchangeInfo', timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extrair limites
                rate_limits = data.get('rateLimits', [])
                
                for limit in rate_limits:
                    limit_type = limit.get('rateLimitType')
                    interval = limit.get('interval')
                    
                    if limit_type == 'REQUEST_WEIGHT' and interval == 'MINUTE':
                        self.weight_limit = limit.get('limit', self.DEFAULT_WEIGHT_LIMIT)
                    
                    if limit_type == 'ORDERS' and interval == 'SECOND' and limit.get('intervalNum') == 10:
                        self.order_limit = limit.get('limit', self.DEFAULT_ORDER_LIMIT)
                
                # Salvar no cache
                cache_data = {
                    'timestamp': datetime.now().isoformat(),
                    'weight_limit': self.weight_limit,
                    'order_limit': self.order_limit
                }
                
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                logger.info(f"Informações da exchange atualizadas (weight={self.weight_limit}, "
                           f"order={self.order_limit})")
            else:
                logger.warning(f"Erro ao obter informações da exchange: {response.status_code}")
        except Exception as e:
            logger.error(f"Erro ao atualizar informações da exchange: {e}")
    
    def force_update_exchange_info(self) -> bool:
        """
        Força atualização das informações da exchange
        
        Returns:
            bool: True se atualização bem-sucedida
        """
        try:
            with self.cache_lock:
                self._update_exchange_info()
            return True
        except Exception as e:
            logger.error(f"Erro ao forçar atualização de informações: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtém status atual do rate limiter
        
        Returns:
            Dict: Status atual
        """
        with self.weight_lock, self.order_lock:
            now = time.time()
            minute_ago = now - 60
            ten_seconds_ago = now - 10
            
            # Limpar janelas
            weight_window = [(ts, w) for ts, w in self.weight_window if ts > minute_ago]
            order_window = [ts for ts in self.order_window if ts > ten_seconds_ago]
            
            current_weight = sum(w for _, w in weight_window)
            current_orders = len(order_window)
            
            return {
                'weight_limit': self.weight_limit,
                'order_limit': self.order_limit,
                'current_weight': current_weight,
                'current_orders': current_orders,
                'weight_usage_pct': current_weight / self.weight_limit if self.weight_limit else 0,
                'order_usage_pct': current_orders / self.order_limit if self.order_limit else 0,
                'emergency_mode': self.emergency_mode,
                'safety_factor': self.safety_factor,
                'cache_age_hours': self._get_cache_age_hours()
            }
    
    def _get_cache_age_hours(self) -> float:
        """
        Calcula idade do cache em horas
        
        Returns:
            float: Idade do cache em horas
        """
        if not self.cache_file.exists():
            return float('inf')
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01T00:00:00'))
            age_seconds = (datetime.now() - cache_time).total_seconds()
            return age_seconds / 3600
        except Exception:
            return float('inf')

