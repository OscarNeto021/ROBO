"""
Strategy Manager - Gerenciador de estratégias de trading
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_strategy import BaseStrategy
from .funding_arbitrage import FundingArbitrageStrategy
from .market_making import MarketMakingStrategy
from .statistical_arbitrage import StatisticalArbitrageStrategy
from .ml_ensemble import MLEnsembleStrategy
from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class StrategyManager:
    """
    Gerenciador de estratégias de trading
    
    Responsabilidades:
    - Inicializar e gerenciar estratégias
    - Coordenar execução de estratégias
    - Balancear alocação de capital
    - Monitorar performance
    - Gerenciar prioridades
    """
    
    def __init__(
        self, 
        config: Dict[str, Any], 
        market_data, 
        execution_engine, 
        risk_manager, 
        model_manager
    ):
        """
        Inicializa o gerenciador de estratégias
        
        Args:
            config: Configurações do sistema
            market_data: Gerenciador de dados de mercado
            execution_engine: Engine de execução
            risk_manager: Gerenciador de risco
            model_manager: Gerenciador de modelos ML
        """
        self.config = config
        self.market_data = market_data
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.model_manager = model_manager
        
        # Estratégias disponíveis
        self.available_strategies = {
            'funding_arbitrage': FundingArbitrageStrategy,
            'market_making': MarketMakingStrategy,
            'statistical_arbitrage': StatisticalArbitrageStrategy,
            'ml_ensemble': MLEnsembleStrategy
        }
        
        # Estratégias ativas
        self.active_strategies: Dict[str, BaseStrategy] = {}
        
        # Estado do gerenciador
        self.is_initialized = False
        self.is_running = False
        self.trading_paused = False
        
        # Métricas agregadas
        self.total_signals_generated = 0
        self.total_signals_executed = 0
        self.last_rebalance_time = datetime.now()
        
        logger.info("StrategyManager inicializado")
    
    async def initialize(self) -> bool:
        """
        Inicializa o gerenciador e todas as estratégias habilitadas
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🔧 Inicializando Strategy Manager...")
            
            # Obter estratégias habilitadas
            enabled_strategies = self._get_enabled_strategies()
            
            if not enabled_strategies:
                logger.warning("⚠️ Nenhuma estratégia habilitada!")
                return False
            
            # Inicializar cada estratégia
            for strategy_name in enabled_strategies:
                success = await self._initialize_strategy(strategy_name)
                if not success:
                    logger.error(f"❌ Falha ao inicializar estratégia: {strategy_name}")
                    return False
            
            # Validar alocações
            if not self._validate_allocations():
                logger.error("❌ Alocações de capital inválidas!")
                return False
            
            self.is_initialized = True
            logger.info(f"✅ Strategy Manager inicializado com {len(self.active_strategies)} estratégias")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização do Strategy Manager: {e}")
            return False
    
    async def run_cycle(self):
        """
        Executa um ciclo de todas as estratégias ativas
        """
        if not self.is_initialized or self.trading_paused:
            return
        
        try:
            # Executar estratégias por ordem de prioridade
            sorted_strategies = sorted(
                self.active_strategies.values(),
                key=lambda s: s.get_priority()
            )
            
            # Executar estratégias em paralelo (por grupo de prioridade)
            await self._execute_strategies_by_priority(sorted_strategies)
            
            # Rebalancear capital se necessário
            await self._check_rebalancing()
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo de estratégias: {e}")
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas de performance agregadas
        
        Returns:
            Dict: Métricas de performance
        """
        try:
            metrics = {
                'total_strategies': len(self.active_strategies),
                'active_strategies': len([s for s in self.active_strategies.values() if s.is_active()]),
                'total_signals_generated': self.total_signals_generated,
                'total_signals_executed': self.total_signals_executed,
                'signal_execution_rate': (
                    self.total_signals_executed / self.total_signals_generated 
                    if self.total_signals_generated > 0 else 0
                ),
                'strategies': {}
            }
            
            # Métricas por estratégia
            for name, strategy in self.active_strategies.items():
                strategy_metrics = await strategy.get_performance_metrics()
                metrics['strategies'][name] = strategy_metrics
            
            # Métricas agregadas
            total_pnl = sum([
                m.get('total_pnl', 0) 
                for m in metrics['strategies'].values()
            ])
            
            total_trades = sum([
                m.get('total_trades', 0) 
                for m in metrics['strategies'].values()
            ])
            
            metrics['aggregated'] = {
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter métricas: {e}")
            return {}
    
    async def stop_all_strategies(self):
        """
        Para todas as estratégias
        """
        try:
            logger.info("🛑 Parando todas as estratégias...")
            
            for strategy in self.active_strategies.values():
                await strategy.stop()
            
            self.is_running = False
            logger.info("✅ Todas as estratégias paradas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar estratégias: {e}")
    
    async def pause_trading(self):
        """
        Pausa trading de todas as estratégias
        """
        try:
            logger.info("⏸️ Pausando trading...")
            
            for strategy in self.active_strategies.values():
                await strategy.pause()
            
            self.trading_paused = True
            logger.info("✅ Trading pausado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao pausar trading: {e}")
    
    async def resume_trading(self):
        """
        Resume trading de todas as estratégias
        """
        try:
            logger.info("▶️ Resumindo trading...")
            
            for strategy in self.active_strategies.values():
                await strategy.resume()
            
            self.trading_paused = False
            logger.info("✅ Trading resumido")
            
        except Exception as e:
            logger.error(f"❌ Erro ao resumir trading: {e}")
    
    async def add_strategy(self, strategy_name: str) -> bool:
        """
        Adiciona nova estratégia
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            bool: True se adição bem-sucedida
        """
        try:
            if strategy_name in self.active_strategies:
                logger.warning(f"⚠️ Estratégia {strategy_name} já está ativa")
                return False
            
            success = await self._initialize_strategy(strategy_name)
            if success:
                logger.info(f"✅ Estratégia {strategy_name} adicionada")
                await self._rebalance_allocations()
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar estratégia {strategy_name}: {e}")
            return False
    
    async def remove_strategy(self, strategy_name: str) -> bool:
        """
        Remove estratégia
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            bool: True se remoção bem-sucedida
        """
        try:
            if strategy_name not in self.active_strategies:
                logger.warning(f"⚠️ Estratégia {strategy_name} não está ativa")
                return False
            
            strategy = self.active_strategies[strategy_name]
            await strategy.shutdown()
            
            del self.active_strategies[strategy_name]
            
            logger.info(f"✅ Estratégia {strategy_name} removida")
            await self._rebalance_allocations()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao remover estratégia {strategy_name}: {e}")
            return False
    
    async def shutdown(self):
        """
        Shutdown do gerenciador
        """
        try:
            logger.info("🛑 Finalizando Strategy Manager...")
            
            # Parar todas as estratégias
            await self.stop_all_strategies()
            
            # Shutdown individual
            for strategy in self.active_strategies.values():
                await strategy.shutdown()
            
            self.active_strategies.clear()
            self.is_initialized = False
            
            logger.info("✅ Strategy Manager finalizado")
            
        except Exception as e:
            logger.error(f"❌ Erro no shutdown: {e}")
    
    def _get_enabled_strategies(self) -> List[str]:
        """
        Obtém lista de estratégias habilitadas
        
        Returns:
            List[str]: Nomes das estratégias habilitadas
        """
        enabled = []
        strategies_config = self.config.get('strategies', {})
        
        for name, config in strategies_config.items():
            if config.get('enabled', False) and name in self.available_strategies:
                enabled.append(name)
        
        return enabled
    
    async def _initialize_strategy(self, strategy_name: str) -> bool:
        """
        Inicializa uma estratégia específica
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            if strategy_name not in self.available_strategies:
                logger.error(f"❌ Estratégia desconhecida: {strategy_name}")
                return False
            
            # Criar instância da estratégia
            strategy_class = self.available_strategies[strategy_name]
            strategy = strategy_class(
                self.config,
                self.market_data,
                self.execution_engine,
                self.risk_manager
            )
            
            # Adicionar model_manager se estratégia suportar
            if hasattr(strategy, 'set_model_manager'):
                strategy.set_model_manager(self.model_manager)
            
            # Inicializar estratégia
            if await strategy.initialize():
                # Iniciar estratégia
                if await strategy.start():
                    self.active_strategies[strategy_name] = strategy
                    logger.info(f"✅ Estratégia {strategy_name} inicializada")
                    return True
            
            logger.error(f"❌ Falha na inicialização de {strategy_name}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar {strategy_name}: {e}")
            return False
    
    def _validate_allocations(self) -> bool:
        """
        Valida alocações de capital
        
        Returns:
            bool: True se alocações válidas
        """
        try:
            total_allocation = sum([
                strategy.get_allocation() 
                for strategy in self.active_strategies.values()
            ])
            
            if total_allocation > 1.0:
                logger.error(f"❌ Alocação total excede 100%: {total_allocation:.1%}")
                return False
            
            if total_allocation < 0.5:
                logger.warning(f"⚠️ Alocação total baixa: {total_allocation:.1%}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao validar alocações: {e}")
            return False
    
    async def _execute_strategies_by_priority(self, strategies: List[BaseStrategy]):
        """
        Executa estratégias agrupadas por prioridade
        
        Args:
            strategies: Lista de estratégias ordenadas por prioridade
        """
        try:
            # Agrupar por prioridade
            priority_groups = {}
            for strategy in strategies:
                priority = strategy.get_priority()
                if priority not in priority_groups:
                    priority_groups[priority] = []
                priority_groups[priority].append(strategy)
            
            # Executar cada grupo de prioridade
            for priority in sorted(priority_groups.keys()):
                group = priority_groups[priority]
                
                # Executar estratégias do mesmo grupo em paralelo
                tasks = [strategy.run_cycle() for strategy in group if strategy.is_active()]
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Erro na execução por prioridade: {e}")
    
    async def _check_rebalancing(self):
        """
        Verifica se é necessário rebalancear capital
        """
        try:
            # Rebalancear a cada 24 horas
            time_since_rebalance = datetime.now() - self.last_rebalance_time
            
            if time_since_rebalance.total_seconds() > 24 * 3600:  # 24 horas
                await self._rebalance_allocations()
                self.last_rebalance_time = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar rebalanceamento: {e}")
    
    async def _rebalance_allocations(self):
        """
        Rebalanceia alocações de capital
        """
        try:
            logger.info("⚖️ Rebalanceando alocações de capital...")
            
            # Obter capital total atual
            account_info = await self.execution_engine.get_account_info()
            total_capital = account_info.get('balance', 0)
            
            # Recalcular capital alocado para cada estratégia
            for strategy in self.active_strategies.values():
                new_allocated_capital = total_capital * strategy.get_allocation()
                strategy.allocated_capital = new_allocated_capital
            
            logger.info("✅ Alocações rebalanceadas")
            
        except Exception as e:
            logger.error(f"❌ Erro no rebalanceamento: {e}")
    
    def get_strategy_status(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtém status de uma estratégia específica
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Optional[Dict]: Status da estratégia ou None
        """
        if strategy_name in self.active_strategies:
            return self.active_strategies[strategy_name].get_status()
        return None
    
    def get_all_strategies_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtém status de todas as estratégias
        
        Returns:
            Dict: Status de todas as estratégias
        """
        return {
            name: strategy.get_status()
            for name, strategy in self.active_strategies.items()
        }
    
    def is_strategy_active(self, strategy_name: str) -> bool:
        """
        Verifica se estratégia está ativa
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            bool: True se ativa
        """
        if strategy_name in self.active_strategies:
            return self.active_strategies[strategy_name].is_active()
        return False
    
    def get_active_strategy_count(self) -> int:
        """
        Retorna número de estratégias ativas
        
        Returns:
            int: Número de estratégias ativas
        """
        return len([s for s in self.active_strategies.values() if s.is_active()])
    
    def __str__(self) -> str:
        """
        Representação string do gerenciador
        """
        active_count = self.get_active_strategy_count()
        total_count = len(self.active_strategies)
        return f"StrategyManager(active={active_count}/{total_count}, paused={self.trading_paused})"

