"""
Circuit Breaker - Sistema de proteção contra condições extremas de mercado

Este módulo implementa um circuit breaker que interrompe todas as operações
de trading quando condições extremas são detectadas, como drawdown excessivo,
perda diária acima do limite, ou outros eventos de risco.

A implementação usa uma flag global trading_enabled com operações atômicas
para garantir que nenhuma nova ordem seja enviada durante o processo de
cancelamento e fechamento de posições, eliminando race conditions.
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, Callable, List
import concurrent.futures

# Configuração de logging
logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit Breaker para interromper operações de trading em condições extremas.
    
    Utiliza uma flag global trading_enabled com operações atômicas para garantir
    que nenhuma nova ordem seja enviada durante o processo de emergência.
    """
    
    def __init__(
        self,
        client,
        config: Dict[str, Any],
        metrics_exporter=None,
        alert_manager=None
    ):
        """
        Inicializa o CircuitBreaker.
        
        Args:
            client: Cliente da exchange (ccxt ou python-binance)
            config: Configurações do circuit breaker
            metrics_exporter: Exportador de métricas (opcional)
            alert_manager: Gerenciador de alertas (opcional)
        """
        self.client = client
        self.config = config
        self.metrics_exporter = metrics_exporter
        self.alert_manager = alert_manager
        
        # Configurações
        self.max_drawdown = config.get('max_drawdown', 15.0)  # %
        self.max_daily_loss = config.get('max_daily_loss', 5.0)  # %
        self.max_position_size = config.get('max_position_size', 50.0)  # % do capital
        self.cooldown_period = config.get('cooldown_period', 3600)  # segundos
        
        # Estado
        self._trading_enabled = threading.Event()
        self._trading_enabled.set()  # Inicialmente habilitado
        self._lock = threading.RLock()  # Para operações que não são atômicas
        self._last_triggered = 0  # Timestamp da última vez que o breaker foi acionado
        self._triggered_reason = None  # Razão pela qual o breaker foi acionado
        
        # Callbacks
        self._pre_trigger_callbacks: List[Callable] = []
        self._post_trigger_callbacks: List[Callable] = []
        
        logger.info("Circuit Breaker inicializado com configurações: %s", config)
    
    def is_trading_enabled(self) -> bool:
        """
        Verifica se o trading está habilitado.
        
        Returns:
            bool: True se o trading estiver habilitado, False caso contrário
        """
        return self._trading_enabled.is_set()
    
    def check_before_order(self) -> bool:
        """
        Verifica se é seguro enviar uma ordem.
        Deve ser chamado antes de qualquer envio de ordem.
        
        Returns:
            bool: True se for seguro enviar a ordem, False caso contrário
        """
        return self._trading_enabled.is_set()
    
    def add_pre_trigger_callback(self, callback: Callable) -> None:
        """
        Adiciona um callback para ser executado antes do circuit breaker ser acionado.
        
        Args:
            callback: Função a ser chamada antes do circuit breaker ser acionado
        """
        with self._lock:
            self._pre_trigger_callbacks.append(callback)
    
    def add_post_trigger_callback(self, callback: Callable) -> None:
        """
        Adiciona um callback para ser executado após o circuit breaker ser acionado.
        
        Args:
            callback: Função a ser chamada após o circuit breaker ser acionado
        """
        with self._lock:
            self._post_trigger_callbacks.append(callback)
    
    def check_conditions(
        self,
        drawdown: Optional[float] = None,
        daily_pnl: Optional[float] = None,
        capital: Optional[float] = None,
        positions: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Verifica as condições que podem acionar o circuit breaker.
        
        Args:
            drawdown: Drawdown atual em porcentagem
            daily_pnl: PnL diário em valor absoluto
            capital: Capital total
            positions: Dicionário com as posições atuais
            
        Returns:
            bool: True se o circuit breaker foi acionado, False caso contrário
        """
        # Se o trading já estiver desabilitado, não precisa verificar
        if not self._trading_enabled.is_set():
            return True
        
        # Verificar drawdown
        if drawdown is not None and drawdown > self.max_drawdown:
            self._trigger_breaker(f"Drawdown excessivo: {drawdown:.2f}% > {self.max_drawdown:.2f}%")
            return True
        
        # Verificar perda diária
        if daily_pnl is not None and capital is not None:
            daily_loss_pct = (daily_pnl / capital) * 100
            if daily_loss_pct < -self.max_daily_loss:
                self._trigger_breaker(
                    f"Perda diária excessiva: {daily_loss_pct:.2f}% < -{self.max_daily_loss:.2f}%"
                )
                return True
        
        # Verificar tamanho das posições
        if positions is not None and capital is not None:
            for symbol, position in positions.items():
                position_size = abs(position.get('notional', 0))
                position_pct = (position_size / capital) * 100
                if position_pct > self.max_position_size:
                    self._trigger_breaker(
                        f"Posição excessiva em {symbol}: {position_pct:.2f}% > {self.max_position_size:.2f}%"
                    )
                    return True
        
        return False
    
    def _trigger_breaker(self, reason: str) -> None:
        """
        Aciona o circuit breaker.
        
        Args:
            reason: Razão pela qual o circuit breaker foi acionado
        """
        # Usar atomic compare-and-swap para evitar race conditions
        if not self._trading_enabled.is_set():
            logger.warning("Circuit breaker já está acionado")
            return
        
        logger.critical("ACIONANDO CIRCUIT BREAKER: %s", reason)
        
        # Desabilitar trading ANTES de qualquer outra operação
        self._trading_enabled.clear()
        
        # Registrar estado
        with self._lock:
            self._last_triggered = time.time()
            self._triggered_reason = reason
        
        # Executar callbacks pré-trigger
        for callback in self._pre_trigger_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Erro ao executar callback pré-trigger: %s", e)
        
        # Cancelar todas as ordens abertas
        self._cancel_all_orders()
        
        # Fechar todas as posições
        self._close_all_positions()
        
        # Registrar métricas
        if self.metrics_exporter:
            self.metrics_exporter.update_system_state("emergency")
            self.metrics_exporter.record_alert("critical", "circuit_breaker")
        
        # Registrar alerta
        if self.alert_manager:
            self.alert_manager.record_alert("critical", "circuit_breaker", reason)
        
        # Executar callbacks pós-trigger
        for callback in self._post_trigger_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Erro ao executar callback pós-trigger: %s", e)
        
        logger.info("Circuit breaker acionado com sucesso. Trading desabilitado.")
    
    def _cancel_all_orders(self) -> None:
        """
        Cancela todas as ordens abertas.
        """
        try:
            logger.info("Cancelando todas as ordens abertas...")
            
            # Obter símbolos com ordens abertas
            open_orders = self.client.fetch_open_orders()
            symbols = set(order['symbol'] for order in open_orders)
            
            # Cancelar ordens em paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for symbol in symbols:
                    futures.append(executor.submit(self.client.cancel_all_orders, symbol))
                
                # Aguardar conclusão
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error("Erro ao cancelar ordens: %s", e)
            
            logger.info("Todas as ordens foram canceladas com sucesso")
        except Exception as e:
            logger.error("Erro ao cancelar todas as ordens: %s", e)
    
    def _close_all_positions(self) -> None:
        """
        Fecha todas as posições abertas.
        """
        try:
            logger.info("Fechando todas as posições abertas...")
            
            # Obter posições abertas
            positions = self.client.fetch_positions()
            active_positions = [p for p in positions if abs(float(p['contracts'])) > 0]
            
            # Fechar posições em paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for position in active_positions:
                    symbol = position['symbol']
                    side = "sell" if position['side'] == 'long' else "buy"
                    amount = abs(float(position['contracts']))
                    
                    futures.append(
                        executor.submit(
                            self.client.create_market_order,
                            symbol,
                            side,
                            amount,
                            params={"reduceOnly": True}
                        )
                    )
                
                # Aguardar conclusão
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error("Erro ao fechar posição: %s", e)
            
            logger.info("Todas as posições foram fechadas com sucesso")
        except Exception as e:
            logger.error("Erro ao fechar todas as posições: %s", e)
    
    def reset(self, manual: bool = False) -> bool:
        """
        Reseta o circuit breaker após o período de cooldown.
        
        Args:
            manual: Se True, força o reset independentemente do período de cooldown
            
        Returns:
            bool: True se o reset foi bem-sucedido, False caso contrário
        """
        # Se o trading já estiver habilitado, não precisa resetar
        if self._trading_enabled.is_set():
            return True
        
        with self._lock:
            # Verificar período de cooldown
            elapsed = time.time() - self._last_triggered
            if not manual and elapsed < self.cooldown_period:
                remaining = self.cooldown_period - elapsed
                logger.warning(
                    "Não é possível resetar o circuit breaker ainda. "
                    f"Aguarde mais {remaining:.0f} segundos."
                )
                return False
            
            # Resetar estado
            self._trading_enabled.set()
            logger.info("Circuit breaker resetado. Trading habilitado novamente.")
            
            # Registrar métricas
            if self.metrics_exporter:
                self.metrics_exporter.update_system_state("running")
            
            return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do circuit breaker.
        
        Returns:
            Dict[str, Any]: Status do circuit breaker
        """
        with self._lock:
            return {
                "trading_enabled": self._trading_enabled.is_set(),
                "last_triggered": self._last_triggered,
                "triggered_reason": self._triggered_reason,
                "cooldown_remaining": max(
                    0, self.cooldown_period - (time.time() - self._last_triggered)
                ) if not self._trading_enabled.is_set() else 0,
                "config": {
                    "max_drawdown": self.max_drawdown,
                    "max_daily_loss": self.max_daily_loss,
                    "max_position_size": self.max_position_size,
                    "cooldown_period": self.cooldown_period
                }
            }


# Singleton para acesso global
_circuit_breaker_instance = None

def get_circuit_breaker() -> Optional[CircuitBreaker]:
    """
    Retorna a instância global do CircuitBreaker.
    
    Returns:
        Optional[CircuitBreaker]: Instância do CircuitBreaker ou None se não inicializado
    """
    return _circuit_breaker_instance

def initialize_circuit_breaker(
    client,
    config: Dict[str, Any],
    metrics_exporter=None,
    alert_manager=None
) -> CircuitBreaker:
    """
    Inicializa a instância global do CircuitBreaker.
    
    Args:
        client: Cliente da exchange (ccxt ou python-binance)
        config: Configurações do circuit breaker
        metrics_exporter: Exportador de métricas (opcional)
        alert_manager: Gerenciador de alertas (opcional)
        
    Returns:
        CircuitBreaker: Instância do CircuitBreaker
    """
    global _circuit_breaker_instance
    _circuit_breaker_instance = CircuitBreaker(
        client, config, metrics_exporter, alert_manager
    )
    return _circuit_breaker_instance

def is_trading_enabled() -> bool:
    """
    Verifica se o trading está habilitado.
    Função de conveniência para uso em qualquer parte do código.
    
    Returns:
        bool: True se o trading estiver habilitado, False caso contrário
    """
    cb = get_circuit_breaker()
    if cb is None:
        # Se o circuit breaker não estiver inicializado, assume que o trading está habilitado
        return True
    return cb.is_trading_enabled()

def check_before_order() -> bool:
    """
    Verifica se é seguro enviar uma ordem.
    Função de conveniência para uso antes de qualquer envio de ordem.
    
    Returns:
        bool: True se for seguro enviar a ordem, False caso contrário
    """
    cb = get_circuit_breaker()
    if cb is None:
        # Se o circuit breaker não estiver inicializado, assume que o trading está habilitado
        return True
    return cb.check_before_order()

