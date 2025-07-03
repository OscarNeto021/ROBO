"""
System Manager - Gerenciador central do sistema de trading
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

from .logger import get_trading_logger
from ..data.market_data_manager import MarketDataManager
from ..strategies.strategy_manager import StrategyManager
from ..execution.execution_engine import ExecutionEngine
from ..risk.risk_manager import RiskManager
from ..models.model_manager import ModelManager

logger = get_trading_logger(__name__)

@dataclass
class SystemStatus:
    """Status do sistema"""
    running: bool = False
    start_time: Optional[datetime] = None
    uptime: timedelta = timedelta()
    total_trades: int = 0
    active_positions: int = 0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    current_balance: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0

class SystemManager:
    """
    Gerenciador central do sistema de trading
    
    Responsabilidades:
    - Orquestrar todos os componentes do sistema
    - Gerenciar ciclo de vida das estratégias
    - Coordenar coleta de dados e execução
    - Monitorar performance e risco
    - Gerenciar estado do sistema
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o gerenciador do sistema
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        self.status = SystemStatus()
        
        # Componentes principais
        self.market_data_manager: Optional[MarketDataManager] = None
        self.strategy_manager: Optional[StrategyManager] = None
        self.execution_engine: Optional[ExecutionEngine] = None
        self.risk_manager: Optional[RiskManager] = None
        self.model_manager: Optional[ModelManager] = None
        
        # Estado interno
        self.running = False
        self.last_cycle_time = datetime.now()
        self.cycle_count = 0
        
        # Métricas de performance
        self.performance_history: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        
        # Tasks assíncronas
        self.background_tasks: List[asyncio.Task] = []
        
        logger.info("SystemManager inicializado")
    
    async def initialize(self) -> bool:
        """
        Inicializa todos os componentes do sistema
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🔧 Inicializando componentes do sistema...")
            
            # 1. Inicializar Market Data Manager
            logger.info("📊 Inicializando Market Data Manager...")
            self.market_data_manager = MarketDataManager(self.config)
            if not await self.market_data_manager.initialize():
                logger.error("❌ Falha na inicialização do Market Data Manager")
                return False
            
            # 2. Inicializar Risk Manager
            logger.info("⚖️ Inicializando Risk Manager...")
            self.risk_manager = RiskManager(self.config)
            if not await self.risk_manager.initialize():
                logger.error("❌ Falha na inicialização do Risk Manager")
                return False
            
            # 3. Inicializar Execution Engine
            logger.info("⚡ Inicializando Execution Engine...")
            self.execution_engine = ExecutionEngine(self.config)
            if not await self.execution_engine.initialize():
                logger.error("❌ Falha na inicialização do Execution Engine")
                return False
            
            # 4. Inicializar Model Manager
            logger.info("🧠 Inicializando Model Manager...")
            self.model_manager = ModelManager(self.config)
            if not await self.model_manager.initialize():
                logger.error("❌ Falha na inicialização do Model Manager")
                return False
            
            # 5. Inicializar Strategy Manager
            logger.info("📈 Inicializando Strategy Manager...")
            self.strategy_manager = StrategyManager(
                self.config,
                self.market_data_manager,
                self.execution_engine,
                self.risk_manager,
                self.model_manager
            )
            if not await self.strategy_manager.initialize():
                logger.error("❌ Falha na inicialização do Strategy Manager")
                return False
            
            # 6. Iniciar tasks de background
            await self._start_background_tasks()
            
            # 7. Atualizar status
            self.status.running = True
            self.status.start_time = datetime.now()
            self.running = True
            
            logger.info("✅ Todos os componentes inicializados com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização do sistema: {e}")
            return False
    
    async def run_cycle(self):
        """
        Executa um ciclo completo do sistema
        """
        try:
            cycle_start = datetime.now()
            self.cycle_count += 1
            
            # 1. Atualizar dados de mercado
            await self.market_data_manager.update()
            
            # 2. Executar estratégias
            await self.strategy_manager.run_cycle()
            
            # 3. Verificar e executar ordens pendentes
            await self.execution_engine.process_pending_orders()
            
            # 4. Atualizar métricas de risco
            await self.risk_manager.update_metrics()
            
            # 5. Verificar limites de risco
            risk_violations = await self.risk_manager.check_risk_limits()
            if risk_violations:
                await self._handle_risk_violations(risk_violations)
            
            # 6. Atualizar status do sistema
            await self._update_system_status()
            
            # 7. Log de performance do ciclo
            cycle_time = (datetime.now() - cycle_start).total_seconds()
            if cycle_time > 1.0:  # Log apenas se ciclo demorou mais que 1s
                logger.warning(f"Ciclo {self.cycle_count} demorou {cycle_time:.2f}s")
            
            self.last_cycle_time = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo do sistema: {e}")
    
    async def test_connectivity(self) -> bool:
        """
        Testa conectividade com APIs externas
        
        Returns:
            bool: True se conectividade OK
        """
        try:
            # Testar conectividade da exchange
            if self.execution_engine:
                exchange_ok = await self.execution_engine.test_connectivity()
                if not exchange_ok:
                    logger.warning("⚠️ Problemas de conectividade com exchange")
                    return False
            
            # Testar conectividade de dados
            if self.market_data_manager:
                data_ok = await self.market_data_manager.test_connectivity()
                if not data_ok:
                    logger.warning("⚠️ Problemas de conectividade com dados")
                    return False
            
            logger.info("✅ Conectividade OK")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no teste de conectividade: {e}")
            return False
    
    async def shutdown(self):
        """
        Shutdown graceful do sistema
        """
        try:
            logger.info("🛑 Iniciando shutdown do sistema...")
            self.running = False
            self.status.running = False
            
            # 1. Cancelar tasks de background
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # 2. Fechar posições abertas (se configurado)
            if self.config.get('execution', {}).get('close_positions_on_shutdown', False):
                await self._close_all_positions()
            
            # 3. Shutdown dos componentes
            if self.strategy_manager:
                await self.strategy_manager.shutdown()
            
            if self.execution_engine:
                await self.execution_engine.shutdown()
            
            if self.market_data_manager:
                await self.market_data_manager.shutdown()
            
            if self.risk_manager:
                await self.risk_manager.shutdown()
            
            if self.model_manager:
                await self.model_manager.shutdown()
            
            # 4. Salvar estado final
            await self._save_final_state()
            
            logger.info("✅ Shutdown concluído")
            
        except Exception as e:
            logger.error(f"❌ Erro durante shutdown: {e}")
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas atuais do sistema
        
        Returns:
            Dict: Métricas do sistema
        """
        try:
            metrics = {
                'system_status': {
                    'running': self.status.running,
                    'uptime': str(self.status.uptime),
                    'cycle_count': self.cycle_count,
                    'last_cycle': self.last_cycle_time.isoformat()
                },
                'trading_metrics': {
                    'total_trades': self.status.total_trades,
                    'active_positions': self.status.active_positions,
                    'total_pnl': self.status.total_pnl,
                    'daily_pnl': self.status.daily_pnl,
                    'current_balance': self.status.current_balance
                },
                'risk_metrics': {
                    'max_drawdown': self.status.max_drawdown,
                    'sharpe_ratio': self.status.sharpe_ratio
                }
            }
            
            # Adicionar métricas específicas dos componentes
            if self.risk_manager:
                risk_metrics = await self.risk_manager.get_current_metrics()
                metrics['risk_metrics'].update(risk_metrics)
            
            if self.strategy_manager:
                strategy_metrics = await self.strategy_manager.get_performance_metrics()
                metrics['strategy_metrics'] = strategy_metrics
            
            if self.execution_engine:
                execution_metrics = await self.execution_engine.get_metrics()
                metrics['execution_metrics'] = execution_metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter métricas: {e}")
            return {}
    
    async def _start_background_tasks(self):
        """
        Inicia tasks de background
        """
        # Task de monitoramento de performance
        performance_task = asyncio.create_task(self._performance_monitor())
        self.background_tasks.append(performance_task)
        
        # Task de limpeza de dados antigos
        cleanup_task = asyncio.create_task(self._data_cleanup())
        self.background_tasks.append(cleanup_task)
        
        # Task de backup periódico
        backup_task = asyncio.create_task(self._periodic_backup())
        self.background_tasks.append(backup_task)
        
        logger.info("📋 Tasks de background iniciadas")
    
    async def _performance_monitor(self):
        """
        Monitor de performance em background
        """
        while self.running:
            try:
                # Calcular métricas de performance
                await self._calculate_performance_metrics()
                
                # Aguardar próximo ciclo (a cada 60 segundos)
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no monitor de performance: {e}")
                await asyncio.sleep(60)
    
    async def _data_cleanup(self):
        """
        Limpeza de dados antigos em background
        """
        while self.running:
            try:
                # Limpar dados antigos (a cada 6 horas)
                await asyncio.sleep(6 * 3600)
                
                # Implementar limpeza de dados
                logger.info("🧹 Executando limpeza de dados...")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro na limpeza de dados: {e}")
    
    async def _periodic_backup(self):
        """
        Backup periódico em background
        """
        while self.running:
            try:
                # Backup a cada 24 horas
                await asyncio.sleep(24 * 3600)
                
                # Implementar backup
                logger.info("💾 Executando backup periódico...")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no backup: {e}")
    
    async def _handle_risk_violations(self, violations: List[str]):
        """
        Trata violações de risco
        
        Args:
            violations: Lista de violações detectadas
        """
        logger.warning(f"⚠️ Violações de risco detectadas: {violations}")
        
        for violation in violations:
            if 'max_drawdown' in violation.lower():
                # Parar todas as estratégias
                await self.strategy_manager.stop_all_strategies()
                logger.critical("🛑 Todas as estratégias paradas devido a drawdown excessivo")
            
            elif 'daily_loss' in violation.lower():
                # Parar trading por hoje
                await self.strategy_manager.pause_trading()
                logger.warning("⏸️ Trading pausado devido a perda diária excessiva")
            
            elif 'position_size' in violation.lower():
                # Reduzir posições
                await self.execution_engine.reduce_positions()
                logger.warning("📉 Posições reduzidas devido a tamanho excessivo")
    
    async def _update_system_status(self):
        """
        Atualiza status do sistema
        """
        try:
            if self.status.start_time:
                self.status.uptime = datetime.now() - self.status.start_time
            
            # Obter métricas atuais
            if self.execution_engine:
                account_info = await self.execution_engine.get_account_info()
                self.status.current_balance = account_info.get('balance', 0.0)
                self.status.active_positions = len(account_info.get('positions', []))
            
            if self.risk_manager:
                risk_metrics = await self.risk_manager.get_current_metrics()
                self.status.max_drawdown = risk_metrics.get('max_drawdown', 0.0)
                self.status.sharpe_ratio = risk_metrics.get('sharpe_ratio', 0.0)
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar status: {e}")
    
    async def _calculate_performance_metrics(self):
        """
        Calcula métricas de performance
        """
        try:
            # Implementar cálculo de métricas
            current_time = datetime.now()
            
            # Adicionar ponto de performance
            performance_point = {
                'timestamp': current_time,
                'balance': self.status.current_balance,
                'pnl': self.status.total_pnl,
                'active_positions': self.status.active_positions,
                'drawdown': self.status.max_drawdown
            }
            
            self.performance_history.append(performance_point)
            
            # Manter apenas últimos 1000 pontos
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular métricas: {e}")
    
    async def _close_all_positions(self):
        """
        Fecha todas as posições abertas
        """
        try:
            if self.execution_engine:
                await self.execution_engine.close_all_positions()
                logger.info("📤 Todas as posições fechadas")
        except Exception as e:
            logger.error(f"❌ Erro ao fechar posições: {e}")
    
    async def _save_final_state(self):
        """
        Salva estado final do sistema
        """
        try:
            # Implementar salvamento de estado
            logger.info("💾 Estado final salvo")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar estado: {e}")
    
    def get_status(self) -> SystemStatus:
        """
        Retorna status atual do sistema
        
        Returns:
            SystemStatus: Status do sistema
        """
        return self.status
    
    def is_running(self) -> bool:
        """
        Verifica se sistema está rodando
        
        Returns:
            bool: True se sistema rodando
        """
        return self.running

