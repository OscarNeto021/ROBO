"""
Backtest Engine - Sistema de backtesting e otimização para capital específico
"""

import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json

from .logger import get_trading_logger

logger = get_trading_logger(__name__)

class BacktestEngine:
    """
    Engine de backtesting e otimização
    
    Funcionalidades:
    - Backtesting de estratégias individuais
    - Backtesting de portfolio
    - Otimização de parâmetros
    - Análise de performance
    - Otimização para capital específico ($200)
    - Geração de relatórios
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o engine de backtesting
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        self.backtest_config = config.get('backtesting', {})
        
        # Configurações específicas para $200
        self.target_capital = 200.0
        self.min_position_size = 10.0  # Mínimo $10 por posição
        self.max_leverage = 10  # Máximo 10x leverage
        
        # Dados históricos
        self.historical_data: Optional[pd.DataFrame] = None
        self.price_data: Dict[str, pd.DataFrame] = {}
        
        # Resultados de backtests
        self.backtest_results: Dict[str, Any] = {}
        self.optimization_results: Dict[str, Any] = {}
        
        # Métricas de performance
        self.performance_metrics: Dict[str, float] = {}
        
        # Configurações de otimização
        self.optimization_params = {
            'funding_arbitrage': {
                'min_funding_rate': [0.005, 0.01, 0.015, 0.02],
                'position_size_pct': [0.05, 0.1, 0.15, 0.2],
                'holding_period_hours': [8, 12, 16, 24]
            },
            'market_making': {
                'spread_pct': [0.0005, 0.001, 0.0015, 0.002],
                'position_size_pct': [0.05, 0.1, 0.15, 0.2],
                'inventory_limit': [0.3, 0.5, 0.7, 1.0]
            },
            'statistical_arbitrage': {
                'lookback_period': [20, 30, 40, 50],
                'z_score_threshold': [1.5, 2.0, 2.5, 3.0],
                'position_size_pct': [0.05, 0.1, 0.15, 0.2]
            }
        }
        
        logger.info("BacktestEngine inicializado")
    
    async def initialize(self) -> bool:
        """
        Inicializa o engine de backtesting
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🔧 Inicializando Backtest Engine...")
            
            # Carregar dados históricos
            if not await self._load_historical_data():
                logger.error("❌ Falha ao carregar dados históricos")
                return False
            
            # Preparar dados para backtesting
            if not await self._prepare_backtest_data():
                logger.error("❌ Falha ao preparar dados de backtesting")
                return False
            
            logger.info("✅ Backtest Engine inicializado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização do Backtest Engine: {e}")
            return False
    
    async def run_strategy_backtest(
        self, 
        strategy_name: str, 
        strategy_params: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Executa backtest de uma estratégia específica
        
        Args:
            strategy_name: Nome da estratégia
            strategy_params: Parâmetros da estratégia
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Dict: Resultados do backtest
        """
        try:
            logger.info(f"🎯 Executando backtest: {strategy_name}")
            
            # Filtrar dados para o período
            data = self._filter_data_by_period(start_date, end_date)
            
            if data is None or len(data) == 0:
                logger.error("❌ Dados insuficientes para backtest")
                return {}
            
            # Executar backtest específico da estratégia
            if strategy_name == 'funding_arbitrage':
                results = await self._backtest_funding_arbitrage(data, strategy_params)
            elif strategy_name == 'market_making':
                results = await self._backtest_market_making(data, strategy_params)
            elif strategy_name == 'statistical_arbitrage':
                results = await self._backtest_statistical_arbitrage(data, strategy_params)
            else:
                logger.error(f"❌ Estratégia desconhecida: {strategy_name}")
                return {}
            
            # Calcular métricas de performance
            performance_metrics = self._calculate_performance_metrics(results)
            
            # Compilar resultados
            backtest_result = {
                'strategy_name': strategy_name,
                'strategy_params': strategy_params,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'initial_capital': self.target_capital,
                'trades': results.get('trades', []),
                'equity_curve': results.get('equity_curve', []),
                'performance_metrics': performance_metrics,
                'backtest_completed_at': datetime.now().isoformat()
            }
            
            # Salvar resultados
            self.backtest_results[f"{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"] = backtest_result
            
            logger.info(f"✅ Backtest concluído: {strategy_name}")
            logger.info(f"   Total Return: {performance_metrics.get('total_return', 0):.2%}")
            logger.info(f"   Sharpe Ratio: {performance_metrics.get('sharpe_ratio', 0):.2f}")
            logger.info(f"   Max Drawdown: {performance_metrics.get('max_drawdown', 0):.2%}")
            
            return backtest_result
            
        except Exception as e:
            logger.error(f"❌ Erro no backtest de {strategy_name}: {e}")
            return {}
    
    async def optimize_strategy_for_capital(
        self, 
        strategy_name: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Otimiza estratégia para capital de $200
        
        Args:
            strategy_name: Nome da estratégia
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Dict: Resultados da otimização
        """
        try:
            logger.info(f"⚡ Otimizando estratégia para $200: {strategy_name}")
            
            if strategy_name not in self.optimization_params:
                logger.error(f"❌ Parâmetros de otimização não definidos para {strategy_name}")
                return {}
            
            params_to_test = self.optimization_params[strategy_name]
            best_result = None
            best_score = -float('inf')
            all_results = []
            
            # Gerar combinações de parâmetros
            param_combinations = self._generate_param_combinations(params_to_test)
            
            logger.info(f"🔄 Testando {len(param_combinations)} combinações de parâmetros...")
            
            for i, params in enumerate(param_combinations):
                try:
                    # Executar backtest com estes parâmetros
                    result = await self.run_strategy_backtest(
                        strategy_name, 
                        params, 
                        start_date, 
                        end_date
                    )
                    
                    if result and result.get('performance_metrics'):
                        # Calcular score de otimização (focado em capital de $200)
                        score = self._calculate_optimization_score(result['performance_metrics'])
                        
                        result['optimization_score'] = score
                        all_results.append(result)
                        
                        # Verificar se é o melhor resultado
                        if score > best_score:
                            best_score = score
                            best_result = result
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"   Progresso: {i + 1}/{len(param_combinations)} ({(i + 1)/len(param_combinations)*100:.1f}%)")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro no teste de parâmetros {params}: {e}")
                    continue
            
            if best_result:
                optimization_result = {
                    'strategy_name': strategy_name,
                    'target_capital': self.target_capital,
                    'optimization_period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    },
                    'best_params': best_result['strategy_params'],
                    'best_performance': best_result['performance_metrics'],
                    'best_score': best_score,
                    'total_combinations_tested': len(param_combinations),
                    'successful_tests': len(all_results),
                    'all_results': all_results[:50],  # Manter apenas top 50
                    'optimization_completed_at': datetime.now().isoformat()
                }
                
                # Salvar resultados de otimização
                self.optimization_results[f"{strategy_name}_optimization"] = optimization_result
                
                logger.info(f"✅ Otimização concluída: {strategy_name}")
                logger.info(f"   Melhor Score: {best_score:.4f}")
                logger.info(f"   Melhor Return: {best_result['performance_metrics'].get('total_return', 0):.2%}")
                logger.info(f"   Melhor Sharpe: {best_result['performance_metrics'].get('sharpe_ratio', 0):.2f}")
                
                return optimization_result
            else:
                logger.error(f"❌ Nenhum resultado válido na otimização de {strategy_name}")
                return {}
            
        except Exception as e:
            logger.error(f"❌ Erro na otimização de {strategy_name}: {e}")
            return {}
    
    async def run_portfolio_backtest(
        self,
        strategies_config: Dict[str, Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Executa backtest de portfolio com múltiplas estratégias
        
        Args:
            strategies_config: Configuração das estratégias
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Dict: Resultados do backtest de portfolio
        """
        try:
            logger.info("📊 Executando backtest de portfolio...")
            
            # Executar backtest individual de cada estratégia
            strategy_results = {}
            
            for strategy_name, config in strategies_config.items():
                if config.get('enabled', False):
                    result = await self.run_strategy_backtest(
                        strategy_name,
                        config,
                        start_date,
                        end_date
                    )
                    
                    if result:
                        strategy_results[strategy_name] = result
            
            if not strategy_results:
                logger.error("❌ Nenhuma estratégia válida para portfolio")
                return {}
            
            # Combinar resultados em portfolio
            portfolio_result = await self._combine_strategies_into_portfolio(
                strategy_results,
                strategies_config
            )
            
            logger.info("✅ Backtest de portfolio concluído")
            return portfolio_result
            
        except Exception as e:
            logger.error(f"❌ Erro no backtest de portfolio: {e}")
            return {}
    
    async def generate_optimization_report(self, strategy_name: str) -> str:
        """
        Gera relatório de otimização
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            str: Caminho do relatório gerado
        """
        try:
            logger.info(f"📋 Gerando relatório de otimização: {strategy_name}")
            
            optimization_key = f"{strategy_name}_optimization"
            
            if optimization_key not in self.optimization_results:
                logger.error(f"❌ Resultados de otimização não encontrados para {strategy_name}")
                return ""
            
            results = self.optimization_results[optimization_key]
            
            # Criar relatório
            report_content = self._create_optimization_report_content(results)
            
            # Salvar relatório
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            
            report_file = reports_dir / f"{strategy_name}_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            # Gerar gráficos
            await self._generate_optimization_charts(results, reports_dir)
            
            logger.info(f"✅ Relatório gerado: {report_file}")
            return str(report_file)
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar relatório: {e}")
            return ""
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo das otimizações
        
        Returns:
            Dict: Resumo das otimizações
        """
        summary = {
            'target_capital': self.target_capital,
            'optimizations_completed': len(self.optimization_results),
            'strategies': {}
        }
        
        for key, results in self.optimization_results.items():
            strategy_name = results['strategy_name']
            
            summary['strategies'][strategy_name] = {
                'best_return': results['best_performance'].get('total_return', 0),
                'best_sharpe': results['best_performance'].get('sharpe_ratio', 0),
                'best_score': results['best_score'],
                'combinations_tested': results['total_combinations_tested'],
                'optimization_date': results['optimization_completed_at']
            }
        
        return summary
    
    async def _load_historical_data(self) -> bool:
        """
        Carrega dados históricos
        
        Returns:
            bool: True se carregamento bem-sucedido
        """
        try:
            # Por enquanto, criar dados simulados
            # Em produção, carregar dados reais da Binance
            
            logger.info("📊 Carregando dados históricos...")
            
            # Simular dados de 1 ano
            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now()
            
            dates = pd.date_range(start_date, end_date, freq='1H')
            
            # Simular preços do Bitcoin
            np.random.seed(42)  # Para reprodutibilidade
            
            initial_price = 45000
            returns = np.random.normal(0, 0.02, len(dates))  # 2% volatilidade horária
            prices = [initial_price]
            
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                prices.append(new_price)
            
            # Simular funding rates
            funding_rates = np.random.normal(0.01, 0.005, len(dates))  # 1% média, 0.5% desvio
            
            # Criar DataFrame
            self.historical_data = pd.DataFrame({
                'timestamp': dates,
                'price': prices,
                'funding_rate': funding_rates,
                'volume': np.random.uniform(1000, 10000, len(dates)),
                'spread': np.random.uniform(0.0005, 0.002, len(dates))
            })
            
            self.historical_data.set_index('timestamp', inplace=True)
            
            logger.info(f"✅ Dados históricos carregados: {len(self.historical_data)} registros")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar dados históricos: {e}")
            return False
    
    async def _prepare_backtest_data(self) -> bool:
        """
        Prepara dados para backtesting
        
        Returns:
            bool: True se preparação bem-sucedida
        """
        try:
            if self.historical_data is None:
                return False
            
            # Adicionar indicadores técnicos
            self.historical_data['sma_20'] = self.historical_data['price'].rolling(20).mean()
            self.historical_data['sma_50'] = self.historical_data['price'].rolling(50).mean()
            self.historical_data['volatility'] = self.historical_data['price'].pct_change().rolling(24).std()
            
            # Remover NaN
            self.historical_data.dropna(inplace=True)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar dados: {e}")
            return False
    
    def _filter_data_by_period(self, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Filtra dados por período
        
        Args:
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Optional[pd.DataFrame]: Dados filtrados
        """
        try:
            if self.historical_data is None:
                return None
            
            mask = (self.historical_data.index >= start_date) & (self.historical_data.index <= end_date)
            return self.historical_data.loc[mask].copy()
            
        except Exception as e:
            logger.error(f"❌ Erro ao filtrar dados: {e}")
            return None
    
    async def _backtest_funding_arbitrage(
        self, 
        data: pd.DataFrame, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa backtest da estratégia Funding Arbitrage
        
        Args:
            data: Dados históricos
            params: Parâmetros da estratégia
            
        Returns:
            Dict: Resultados do backtest
        """
        try:
            min_funding_rate = params.get('min_funding_rate', 0.01)
            position_size_pct = params.get('position_size_pct', 0.1)
            holding_period_hours = params.get('holding_period_hours', 8)
            
            trades = []
            equity_curve = []
            current_capital = self.target_capital
            position = None
            
            for i, (timestamp, row) in enumerate(data.iterrows()):
                # Verificar se deve abrir posição
                if position is None and row['funding_rate'] >= min_funding_rate:
                    position_size = current_capital * position_size_pct
                    
                    if position_size >= self.min_position_size:
                        position = {
                            'entry_time': timestamp,
                            'entry_price': row['price'],
                            'size': position_size,
                            'funding_rate': row['funding_rate'],
                            'expected_exit_time': timestamp + timedelta(hours=holding_period_hours)
                        }
                
                # Verificar se deve fechar posição
                elif position is not None:
                    should_close = (
                        timestamp >= position['expected_exit_time'] or
                        row['funding_rate'] < min_funding_rate * 0.5  # Stop loss
                    )
                    
                    if should_close:
                        # Calcular PnL
                        funding_pnl = position['size'] * position['funding_rate'] * (
                            (timestamp - position['entry_time']).total_seconds() / 3600 / 8
                        )  # Funding é pago a cada 8 horas
                        
                        price_pnl = position['size'] * (row['price'] - position['entry_price']) / position['entry_price']
                        total_pnl = funding_pnl - abs(price_pnl)  # Hedged position
                        
                        current_capital += total_pnl
                        
                        trade = {
                            'entry_time': position['entry_time'],
                            'exit_time': timestamp,
                            'entry_price': position['entry_price'],
                            'exit_price': row['price'],
                            'size': position['size'],
                            'funding_pnl': funding_pnl,
                            'price_pnl': price_pnl,
                            'total_pnl': total_pnl,
                            'return_pct': total_pnl / position['size']
                        }
                        
                        trades.append(trade)
                        position = None
                
                # Registrar equity
                equity_curve.append({
                    'timestamp': timestamp,
                    'equity': current_capital
                })
            
            return {
                'trades': trades,
                'equity_curve': equity_curve,
                'final_capital': current_capital
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no backtest de funding arbitrage: {e}")
            return {}
    
    async def _backtest_market_making(
        self, 
        data: pd.DataFrame, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa backtest da estratégia Market Making
        
        Args:
            data: Dados históricos
            params: Parâmetros da estratégia
            
        Returns:
            Dict: Resultados do backtest
        """
        try:
            spread_pct = params.get('spread_pct', 0.001)
            position_size_pct = params.get('position_size_pct', 0.1)
            inventory_limit = params.get('inventory_limit', 0.5)
            
            trades = []
            equity_curve = []
            current_capital = self.target_capital
            inventory = 0  # Posição líquida
            
            for i, (timestamp, row) in enumerate(data.iterrows()):
                position_size = current_capital * position_size_pct
                
                if position_size >= self.min_position_size:
                    # Simular market making
                    bid_price = row['price'] * (1 - spread_pct / 2)
                    ask_price = row['price'] * (1 + spread_pct / 2)
                    
                    # Simular execução baseada na volatilidade
                    volatility = row.get('volatility', 0.02)
                    execution_prob = min(volatility * 10, 0.8)  # Maior volatilidade = mais execuções
                    
                    if np.random.random() < execution_prob:
                        # Decidir lado da execução baseado no inventory
                        if inventory > inventory_limit * current_capital:
                            # Muito comprado, vender
                            side = 'sell'
                            price = bid_price
                            inventory -= position_size
                        elif inventory < -inventory_limit * current_capital:
                            # Muito vendido, comprar
                            side = 'buy'
                            price = ask_price
                            inventory += position_size
                        else:
                            # Inventory neutro, escolher aleatoriamente
                            side = 'buy' if np.random.random() < 0.5 else 'sell'
                            price = ask_price if side == 'buy' else bid_price
                            inventory += position_size if side == 'buy' else -position_size
                        
                        # Calcular PnL do spread
                        spread_pnl = position_size * spread_pct / 2
                        current_capital += spread_pnl
                        
                        trade = {
                            'timestamp': timestamp,
                            'side': side,
                            'price': price,
                            'size': position_size,
                            'spread_pnl': spread_pnl,
                            'inventory': inventory
                        }
                        
                        trades.append(trade)
                
                # Registrar equity
                equity_curve.append({
                    'timestamp': timestamp,
                    'equity': current_capital + inventory * row['price'] / row['price']  # Mark-to-market
                })
            
            return {
                'trades': trades,
                'equity_curve': equity_curve,
                'final_capital': current_capital,
                'final_inventory': inventory
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no backtest de market making: {e}")
            return {}
    
    async def _backtest_statistical_arbitrage(
        self, 
        data: pd.DataFrame, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executa backtest da estratégia Statistical Arbitrage
        
        Args:
            data: Dados históricos
            params: Parâmetros da estratégia
            
        Returns:
            Dict: Resultados do backtest
        """
        try:
            lookback_period = params.get('lookback_period', 30)
            z_score_threshold = params.get('z_score_threshold', 2.0)
            position_size_pct = params.get('position_size_pct', 0.1)
            
            trades = []
            equity_curve = []
            current_capital = self.target_capital
            position = None
            
            # Calcular z-score da relação preço/SMA
            data['price_sma_ratio'] = data['price'] / data['sma_20']
            data['ratio_mean'] = data['price_sma_ratio'].rolling(lookback_period).mean()
            data['ratio_std'] = data['price_sma_ratio'].rolling(lookback_period).std()
            data['z_score'] = (data['price_sma_ratio'] - data['ratio_mean']) / data['ratio_std']
            
            for i, (timestamp, row) in enumerate(data.iterrows()):
                if pd.isna(row['z_score']):
                    continue
                
                position_size = current_capital * position_size_pct
                
                # Verificar sinais de entrada
                if position is None and abs(row['z_score']) > z_score_threshold:
                    if position_size >= self.min_position_size:
                        side = 'short' if row['z_score'] > 0 else 'long'  # Mean reversion
                        
                        position = {
                            'entry_time': timestamp,
                            'entry_price': row['price'],
                            'side': side,
                            'size': position_size,
                            'entry_z_score': row['z_score']
                        }
                
                # Verificar sinais de saída
                elif position is not None:
                    should_close = (
                        abs(row['z_score']) < 0.5 or  # Reversão à média
                        (position['side'] == 'long' and row['z_score'] > z_score_threshold) or  # Stop loss
                        (position['side'] == 'short' and row['z_score'] < -z_score_threshold)
                    )
                    
                    if should_close:
                        # Calcular PnL
                        if position['side'] == 'long':
                            pnl = position['size'] * (row['price'] - position['entry_price']) / position['entry_price']
                        else:
                            pnl = position['size'] * (position['entry_price'] - row['price']) / position['entry_price']
                        
                        current_capital += pnl
                        
                        trade = {
                            'entry_time': position['entry_time'],
                            'exit_time': timestamp,
                            'side': position['side'],
                            'entry_price': position['entry_price'],
                            'exit_price': row['price'],
                            'size': position['size'],
                            'pnl': pnl,
                            'return_pct': pnl / position['size'],
                            'entry_z_score': position['entry_z_score'],
                            'exit_z_score': row['z_score']
                        }
                        
                        trades.append(trade)
                        position = None
                
                # Registrar equity
                equity_curve.append({
                    'timestamp': timestamp,
                    'equity': current_capital
                })
            
            return {
                'trades': trades,
                'equity_curve': equity_curve,
                'final_capital': current_capital
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no backtest de statistical arbitrage: {e}")
            return {}
    
    def _calculate_performance_metrics(self, backtest_results: Dict[str, Any]) -> Dict[str, float]:
        """
        Calcula métricas de performance
        
        Args:
            backtest_results: Resultados do backtest
            
        Returns:
            Dict: Métricas de performance
        """
        try:
            trades = backtest_results.get('trades', [])
            equity_curve = backtest_results.get('equity_curve', [])
            final_capital = backtest_results.get('final_capital', self.target_capital)
            
            if not trades or not equity_curve:
                return {}
            
            # Retorno total
            total_return = (final_capital - self.target_capital) / self.target_capital
            
            # Número de trades
            total_trades = len(trades)
            
            # Win rate
            winning_trades = [t for t in trades if t.get('pnl', t.get('total_pnl', 0)) > 0]
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            # PnL médio
            pnls = [t.get('pnl', t.get('total_pnl', 0)) for t in trades]
            avg_pnl = np.mean(pnls) if pnls else 0
            
            # Sharpe ratio
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
                returns.append(ret)
            
            if returns:
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(24 * 365) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Maximum drawdown
            equity_values = [e['equity'] for e in equity_curve]
            peak = equity_values[0]
            max_drawdown = 0
            
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Profit factor
            gross_profit = sum([p for p in pnls if p > 0])
            gross_loss = abs(sum([p for p in pnls if p < 0]))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            return {
                'total_return': total_return,
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'profit_factor': profit_factor,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'final_capital': final_capital
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular métricas: {e}")
            return {}
    
    def _calculate_optimization_score(self, metrics: Dict[str, float]) -> float:
        """
        Calcula score de otimização (focado em capital de $200)
        
        Args:
            metrics: Métricas de performance
            
        Returns:
            float: Score de otimização
        """
        try:
            # Pesos para diferentes métricas (otimizado para capital pequeno)
            weights = {
                'total_return': 0.3,      # Retorno é importante
                'sharpe_ratio': 0.25,     # Risco-ajustado é crucial
                'win_rate': 0.2,          # Consistência é importante para capital pequeno
                'max_drawdown': -0.15,    # Penalizar drawdowns altos
                'profit_factor': 0.1      # Eficiência dos trades
            }
            
            # Normalizar métricas
            normalized_metrics = {
                'total_return': min(metrics.get('total_return', 0), 2.0),  # Cap em 200%
                'sharpe_ratio': min(metrics.get('sharpe_ratio', 0) / 3.0, 1.0),  # Normalizar por 3.0
                'win_rate': metrics.get('win_rate', 0),
                'max_drawdown': metrics.get('max_drawdown', 1.0),  # Já é percentual
                'profit_factor': min(metrics.get('profit_factor', 1.0) / 5.0, 1.0)  # Normalizar por 5.0
            }
            
            # Calcular score ponderado
            score = sum(
                normalized_metrics.get(metric, 0) * weight
                for metric, weight in weights.items()
            )
            
            # Bonus para estratégias adequadas a capital pequeno
            if metrics.get('total_trades', 0) > 10:  # Atividade suficiente
                score += 0.1
            
            if metrics.get('max_drawdown', 1.0) < 0.1:  # Baixo drawdown
                score += 0.1
            
            return max(score, 0)  # Não permitir scores negativos
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular score de otimização: {e}")
            return 0
    
    def _generate_param_combinations(self, params_dict: Dict[str, List]) -> List[Dict[str, Any]]:
        """
        Gera combinações de parâmetros
        
        Args:
            params_dict: Dicionário com listas de valores para cada parâmetro
            
        Returns:
            List: Lista de combinações de parâmetros
        """
        try:
            import itertools
            
            keys = list(params_dict.keys())
            values = list(params_dict.values())
            
            combinations = []
            for combination in itertools.product(*values):
                param_dict = dict(zip(keys, combination))
                combinations.append(param_dict)
            
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar combinações: {e}")
            return []
    
    async def _combine_strategies_into_portfolio(
        self,
        strategy_results: Dict[str, Dict[str, Any]],
        strategies_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Combina resultados de estratégias em portfolio
        
        Args:
            strategy_results: Resultados individuais das estratégias
            strategies_config: Configuração das estratégias
            
        Returns:
            Dict: Resultados do portfolio
        """
        try:
            # Implementar combinação de estratégias
            # Por enquanto, retornar resultado simples
            
            total_return = 0
            total_trades = 0
            combined_metrics = {}
            
            for strategy_name, results in strategy_results.items():
                allocation = strategies_config[strategy_name].get('allocation', 0)
                metrics = results.get('performance_metrics', {})
                
                total_return += metrics.get('total_return', 0) * allocation
                total_trades += metrics.get('total_trades', 0)
            
            combined_metrics = {
                'total_return': total_return,
                'total_trades': total_trades,
                'strategies_count': len(strategy_results)
            }
            
            return {
                'portfolio_type': 'multi_strategy',
                'strategies_results': strategy_results,
                'combined_metrics': combined_metrics,
                'target_capital': self.target_capital
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao combinar estratégias: {e}")
            return {}
    
    def _create_optimization_report_content(self, results: Dict[str, Any]) -> str:
        """
        Cria conteúdo do relatório de otimização
        
        Args:
            results: Resultados da otimização
            
        Returns:
            str: Conteúdo do relatório
        """
        try:
            strategy_name = results['strategy_name']
            best_params = results['best_params']
            best_performance = results['best_performance']
            
            report = f"""# Relatório de Otimização - {strategy_name.title()}

## Resumo Executivo

**Capital Alvo:** ${results['target_capital']}
**Período de Otimização:** {results['optimization_period']['start_date']} a {results['optimization_period']['end_date']}
**Combinações Testadas:** {results['total_combinations_tested']}
**Testes Bem-sucedidos:** {results['successful_tests']}

## Melhores Parâmetros Encontrados

"""
            
            for param, value in best_params.items():
                report += f"- **{param}:** {value}\n"
            
            report += f"""
## Performance dos Melhores Parâmetros

- **Retorno Total:** {best_performance.get('total_return', 0):.2%}
- **Sharpe Ratio:** {best_performance.get('sharpe_ratio', 0):.2f}
- **Win Rate:** {best_performance.get('win_rate', 0):.2%}
- **Maximum Drawdown:** {best_performance.get('max_drawdown', 0):.2%}
- **Profit Factor:** {best_performance.get('profit_factor', 0):.2f}
- **Total de Trades:** {best_performance.get('total_trades', 0)}
- **PnL Médio:** ${best_performance.get('avg_pnl', 0):.2f}

## Score de Otimização

**Score Final:** {results['best_score']:.4f}

O score de otimização é calculado considerando múltiplas métricas ponderadas, 
com foco especial em estratégias adequadas para capital de $200.

## Recomendações

1. **Implementação:** Os parâmetros otimizados podem ser implementados diretamente no sistema
2. **Monitoramento:** Acompanhar performance em tempo real para validar resultados
3. **Reotimização:** Considerar nova otimização a cada 30-60 dias
4. **Gestão de Risco:** Manter stops e limites de drawdown configurados

## Observações

- Resultados baseados em dados históricos
- Performance passada não garante resultados futuros
- Considerar custos de transação na implementação real
- Testar em ambiente demo antes da produção

---
*Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}*
"""
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar relatório: {e}")
            return ""
    
    async def _generate_optimization_charts(self, results: Dict[str, Any], output_dir: Path):
        """
        Gera gráficos de otimização
        
        Args:
            results: Resultados da otimização
            output_dir: Diretório de saída
        """
        try:
            # Implementar geração de gráficos
            # Por enquanto, apenas log
            logger.info("📊 Gráficos de otimização serão implementados")
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar gráficos: {e}")

