"""
Base Strategy - Classe base para todas as estratégias de trading
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

@dataclass
class StrategyMetrics:
    """Métricas de performance de uma estratégia"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration: timedelta = timedelta()
    last_trade_time: Optional[datetime] = None

class BaseStrategy(ABC):
    """
    Classe base abstrata para todas as estratégias de trading
    
    Define interface comum e funcionalidades básicas que todas as
    estratégias devem implementar ou podem utilizar.
    """
    
    def __init__(
        self, 
        name: str, 
        config: Dict[str, Any], 
        market_data, 
        execution_engine, 
        risk_manager
    ):
        """
        Inicializa estratégia base
        
        Args:
            name: Nome da estratégia
            config: Configurações da estratégia
            market_data: Gerenciador de dados de mercado
            execution_engine: Engine de execução
            risk_manager: Gerenciador de risco
        """
        self.name = name
        self.config = config
        self.market_data = market_data
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        
        # Estado da estratégia
        self.is_enabled = False
        self.is_initialized = False
        self.is_running = False
        
        # Configurações básicas
        self.allocation = config.get('strategies', {}).get(name, {}).get('allocation', 0.1)
        self.priority = config.get('strategies', {}).get(name, {}).get('priority', 5)
        
        # Capital alocado
        total_capital = config.get('capital', {}).get('initial_balance', 1000)
        self.allocated_capital = total_capital * self.allocation
        
        # Métricas
        self.metrics = StrategyMetrics()
        self.trade_history: List[Dict[str, Any]] = []
        self.signal_history: List[Dict[str, Any]] = []
        
        # Controle de tempo
        self.last_signal_time = datetime.min
        self.last_execution_time = datetime.min
        
        logger.strategy(f"Estratégia {name} inicializada", strategy=name)
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Inicializa a estratégia
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        pass
    
    @abstractmethod
    async def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Gera sinais de trading
        
        Returns:
            List[Dict]: Lista de sinais gerados
        """
        pass
    
    @abstractmethod
    async def execute_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Executa um sinal de trading
        
        Args:
            signal: Sinal a ser executado
            
        Returns:
            bool: True se execução bem-sucedida
        """
        pass
    
    @abstractmethod
    async def update_positions(self):
        """
        Atualiza posições ativas da estratégia
        """
        pass
    
    @abstractmethod
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Retorna métricas de performance da estratégia
        
        Returns:
            Dict: Métricas de performance
        """
        pass
    
    async def start(self) -> bool:
        """
        Inicia a estratégia
        
        Returns:
            bool: True se início bem-sucedido
        """
        try:
            if not self.is_initialized:
                if not await self.initialize():
                    logger.error(f"❌ Falha na inicialização da estratégia {self.name}")
                    return False
            
            self.is_enabled = True
            self.is_running = True
            
            logger.strategy(f"Estratégia iniciada", strategy=self.name)
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar estratégia {self.name}: {e}")
            return False
    
    async def stop(self):
        """
        Para a estratégia
        """
        try:
            self.is_enabled = False
            self.is_running = False
            
            # Fechar posições abertas se configurado
            if self.config.get('strategies', {}).get(self.name, {}).get('close_on_stop', False):
                await self._close_all_positions()
            
            logger.strategy(f"Estratégia parada", strategy=self.name)
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar estratégia {self.name}: {e}")
    
    async def pause(self):
        """
        Pausa a estratégia temporariamente
        """
        self.is_running = False
        logger.strategy(f"Estratégia pausada", strategy=self.name)
    
    async def resume(self):
        """
        Resume a estratégia
        """
        if self.is_enabled:
            self.is_running = True
            logger.strategy(f"Estratégia resumida", strategy=self.name)
    
    async def run_cycle(self):
        """
        Executa um ciclo completo da estratégia
        """
        if not self.is_enabled or not self.is_running:
            return
        
        try:
            # 1. Gerar sinais
            signals = await self.generate_signals()
            
            # 2. Filtrar sinais válidos
            valid_signals = await self._filter_signals(signals)
            
            # 3. Executar sinais
            for signal in valid_signals:
                if await self._should_execute_signal(signal):
                    success = await self.execute_signal(signal)
                    await self._record_signal_execution(signal, success)
            
            # 4. Atualizar posições
            await self.update_positions()
            
            # 5. Atualizar métricas
            await self._update_metrics()
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo da estratégia {self.name}: {e}")
    
    async def _filter_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra sinais baseado em critérios de qualidade
        
        Args:
            signals: Sinais gerados
            
        Returns:
            List[Dict]: Sinais válidos
        """
        valid_signals = []
        
        for signal in signals:
            # Verificar confiança mínima
            min_confidence = self.config.get('strategies', {}).get(self.name, {}).get('min_confidence', 0.6)
            if signal.get('confidence', 0) < min_confidence:
                continue
            
            # Verificar se não é muito frequente
            if await self._is_signal_too_frequent(signal):
                continue
            
            # Verificar limites de risco
            if not await self.risk_manager.validate_signal(signal, self.name):
                continue
            
            valid_signals.append(signal)
        
        return valid_signals
    
    async def _should_execute_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Verifica se sinal deve ser executado
        
        Args:
            signal: Sinal a ser verificado
            
        Returns:
            bool: True se deve executar
        """
        try:
            # Verificar se estratégia está ativa
            if not self.is_running:
                return False
            
            # Verificar capital disponível
            if self.allocated_capital <= 0:
                return False
            
            # Verificar limites de posição
            max_positions = self.config.get('strategies', {}).get(self.name, {}).get('max_positions', 5)
            current_positions = await self._get_active_positions_count()
            if current_positions >= max_positions:
                return False
            
            # Verificar horário de trading
            if not await self._is_trading_hours():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar execução de sinal: {e}")
            return False
    
    async def _is_signal_too_frequent(self, signal: Dict[str, Any]) -> bool:
        """
        Verifica se sinal é muito frequente
        
        Args:
            signal: Sinal a ser verificado
            
        Returns:
            bool: True se muito frequente
        """
        try:
            min_interval = self.config.get('strategies', {}).get(self.name, {}).get('min_signal_interval', 300)  # 5 min
            
            time_since_last = (datetime.now() - self.last_signal_time).total_seconds()
            return time_since_last < min_interval
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar frequência: {e}")
            return False
    
    async def _is_trading_hours(self) -> bool:
        """
        Verifica se está em horário de trading
        
        Returns:
            bool: True se em horário de trading
        """
        # Crypto trading é 24/7, mas pode ter restrições específicas
        trading_hours = self.config.get('strategies', {}).get(self.name, {}).get('trading_hours')
        
        if not trading_hours:
            return True  # Sem restrições
        
        # Implementar lógica de horário se necessário
        return True
    
    async def _get_active_positions_count(self) -> int:
        """
        Obtém número de posições ativas
        
        Returns:
            int: Número de posições ativas
        """
        try:
            positions = await self.execution_engine.get_positions(strategy=self.name)
            return len([p for p in positions if p.get('status') == 'active'])
        except:
            return 0
    
    async def _record_signal_execution(self, signal: Dict[str, Any], success: bool):
        """
        Registra execução de sinal
        
        Args:
            signal: Sinal executado
            success: Se execução foi bem-sucedida
        """
        try:
            execution_record = {
                'timestamp': datetime.now(),
                'signal': signal,
                'success': success,
                'strategy': self.name
            }
            
            self.signal_history.append(execution_record)
            
            # Manter apenas últimos 1000 registros
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]
            
            self.last_signal_time = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar execução: {e}")
    
    async def _update_metrics(self):
        """
        Atualiza métricas da estratégia
        """
        try:
            # Obter trades recentes
            recent_trades = await self.execution_engine.get_trades(strategy=self.name)
            
            if recent_trades:
                # Atualizar métricas básicas
                self.metrics.total_trades = len(recent_trades)
                self.metrics.winning_trades = len([t for t in recent_trades if t.get('pnl', 0) > 0])
                self.metrics.losing_trades = len([t for t in recent_trades if t.get('pnl', 0) < 0])
                self.metrics.total_pnl = sum([t.get('pnl', 0) for t in recent_trades])
                
                # Calcular win rate
                if self.metrics.total_trades > 0:
                    self.metrics.win_rate = self.metrics.winning_trades / self.metrics.total_trades
                
                # Calcular profit factor
                gross_profit = sum([t.get('pnl', 0) for t in recent_trades if t.get('pnl', 0) > 0])
                gross_loss = abs(sum([t.get('pnl', 0) for t in recent_trades if t.get('pnl', 0) < 0]))
                
                if gross_loss > 0:
                    self.metrics.profit_factor = gross_profit / gross_loss
                
                # Última trade
                if recent_trades:
                    last_trade = max(recent_trades, key=lambda x: x.get('timestamp', datetime.min))
                    self.metrics.last_trade_time = last_trade.get('timestamp')
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar métricas: {e}")
    
    async def _close_all_positions(self):
        """
        Fecha todas as posições da estratégia
        """
        try:
            positions = await self.execution_engine.get_positions(strategy=self.name)
            
            for position in positions:
                if position.get('status') == 'active':
                    await self.execution_engine.close_position(position['id'])
            
            logger.strategy(f"Todas as posições fechadas", strategy=self.name)
            
        except Exception as e:
            logger.error(f"❌ Erro ao fechar posições: {e}")
    
    def get_allocation(self) -> float:
        """
        Retorna alocação de capital da estratégia
        
        Returns:
            float: Percentual de alocação (0-1)
        """
        return self.allocation
    
    def get_allocated_capital(self) -> float:
        """
        Retorna capital alocado em USD
        
        Returns:
            float: Capital alocado
        """
        return self.allocated_capital
    
    def get_priority(self) -> int:
        """
        Retorna prioridade da estratégia
        
        Returns:
            int: Prioridade (menor número = maior prioridade)
        """
        return self.priority
    
    def is_active(self) -> bool:
        """
        Verifica se estratégia está ativa
        
        Returns:
            bool: True se ativa
        """
        return self.is_enabled and self.is_running
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status atual da estratégia
        
        Returns:
            Dict: Status da estratégia
        """
        return {
            'name': self.name,
            'enabled': self.is_enabled,
            'running': self.is_running,
            'initialized': self.is_initialized,
            'allocation': self.allocation,
            'allocated_capital': self.allocated_capital,
            'priority': self.priority,
            'last_signal_time': self.last_signal_time,
            'metrics': {
                'total_trades': self.metrics.total_trades,
                'win_rate': self.metrics.win_rate,
                'total_pnl': self.metrics.total_pnl,
                'profit_factor': self.metrics.profit_factor
            }
        }
    
    async def shutdown(self):
        """
        Shutdown da estratégia
        """
        try:
            await self.stop()
            logger.strategy(f"Estratégia finalizada", strategy=self.name)
            
        except Exception as e:
            logger.error(f"❌ Erro no shutdown da estratégia {self.name}: {e}")
    
    def __str__(self) -> str:
        """
        Representação string da estratégia
        """
        return f"Strategy({self.name}, allocation={self.allocation:.1%}, active={self.is_active()})"

