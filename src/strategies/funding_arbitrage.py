"""
Funding Rate Arbitrage Strategy
Estratégia de arbitragem de funding rate - uma das mais lucrativas e de baixo risco

Esta estratégia explora as diferenças de funding rates entre exchanges ou entre
spot e futures para gerar retornos consistentes com risco direcional mínimo.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

from .base_strategy import BaseStrategy
from ..core.logger import get_trading_logger

logger = get_trading_logger(__name__)

@dataclass
class FundingOpportunity:
    """Oportunidade de arbitragem de funding"""
    symbol: str
    funding_rate: float
    annualized_rate: float
    next_funding_time: datetime
    time_to_funding: timedelta
    confidence_score: float
    expected_profit: float
    required_capital: float

@dataclass
class ArbitragePosition:
    """Posição de arbitragem ativa"""
    id: str
    symbol: str
    spot_position: Dict[str, Any]
    futures_position: Dict[str, Any]
    entry_time: datetime
    expected_funding: float
    realized_funding: float
    status: str  # 'active', 'closing', 'closed'

class FundingArbitrageStrategy(BaseStrategy):
    """
    Estratégia de Arbitragem de Funding Rate
    
    Características:
    - Baixo risco (delta-neutral)
    - Retornos consistentes
    - Sharpe ratio alto (>3.0)
    - Adequada para capital pequeno
    
    Funcionamento:
    1. Monitora funding rates em tempo real
    2. Identifica oportunidades lucrativas
    3. Executa posições delta-neutral
    4. Coleta funding payments
    5. Fecha posições após funding
    """
    
    def __init__(self, config: Dict[str, Any], market_data, execution_engine, risk_manager):
        """
        Inicializa estratégia de funding arbitrage
        
        Args:
            config: Configurações da estratégia
            market_data: Gerenciador de dados de mercado
            execution_engine: Engine de execução
            risk_manager: Gerenciador de risco
        """
        super().__init__("funding_arbitrage", config, market_data, execution_engine, risk_manager)
        
        # Configurações específicas
        self.strategy_config = config.get('strategies', {}).get('funding_arbitrage', {})
        self.min_funding_rate = self.strategy_config.get('min_funding_rate', 0.005)  # 0.5%
        self.max_position_size = self.strategy_config.get('max_position_size', 0.8)
        self.holding_period_hours = self.strategy_config.get('holding_period_hours', 8)
        self.max_spread = self.strategy_config.get('max_spread', 0.001)  # 0.1%
        self.min_liquidity = self.strategy_config.get('min_liquidity', 100000)  # $100k
        
        # Estado interno
        self.active_positions: Dict[str, ArbitragePosition] = {}
        self.funding_history: List[Dict[str, Any]] = []
        self.opportunities_history: List[FundingOpportunity] = []
        
        # Métricas
        self.total_funding_collected = 0.0
        self.successful_arbitrages = 0
        self.failed_arbitrages = 0
        
        logger.strategy("Funding Arbitrage Strategy inicializada", strategy=self.name)
    
    async def initialize(self) -> bool:
        """
        Inicializa a estratégia
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🔄 Inicializando Funding Arbitrage Strategy...")
            
            # Verificar se exchange suporta funding rates
            if not await self._check_funding_support():
                logger.error("❌ Exchange não suporta funding rates")
                return False
            
            # Carregar histórico de funding rates
            await self._load_funding_history()
            
            # Configurar monitoramento de funding
            await self._setup_funding_monitoring()
            
            self.is_initialized = True
            logger.info("✅ Funding Arbitrage Strategy inicializada")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {e}")
            return False
    
    async def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Gera sinais de trading baseados em funding rates
        
        Returns:
            List[Dict]: Lista de sinais gerados
        """
        signals = []
        
        try:
            # Obter funding rates atuais
            funding_data = await self._get_current_funding_rates()
            
            # Analisar oportunidades
            opportunities = await self._analyze_funding_opportunities(funding_data)
            
            # Gerar sinais para oportunidades válidas
            for opportunity in opportunities:
                if await self._validate_opportunity(opportunity):
                    signal = await self._create_arbitrage_signal(opportunity)
                    if signal:
                        signals.append(signal)
            
            # Log de oportunidades encontradas
            if opportunities:
                logger.strategy(
                    f"Encontradas {len(opportunities)} oportunidades de funding",
                    strategy=self.name,
                    opportunities=len(opportunities),
                    valid_signals=len(signals)
                )
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar sinais: {e}")
            return []
    
    async def execute_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Executa sinal de arbitragem
        
        Args:
            signal: Sinal a ser executado
            
        Returns:
            bool: True se execução bem-sucedida
        """
        try:
            opportunity = signal['opportunity']
            
            logger.strategy(
                f"Executando arbitragem de funding para {opportunity.symbol}",
                strategy=self.name,
                symbol=opportunity.symbol,
                funding_rate=opportunity.funding_rate,
                expected_profit=opportunity.expected_profit
            )
            
            # Calcular tamanhos de posição
            position_sizes = await self._calculate_position_sizes(opportunity)
            
            # Executar posições simultaneamente
            arbitrage_position = await self._execute_arbitrage_positions(
                opportunity, position_sizes
            )
            
            if arbitrage_position:
                # Registrar posição ativa
                self.active_positions[arbitrage_position.id] = arbitrage_position
                
                # Agendar fechamento da posição
                await self._schedule_position_close(arbitrage_position)
                
                logger.strategy(
                    f"Arbitragem executada com sucesso",
                    strategy=self.name,
                    position_id=arbitrage_position.id,
                    symbol=opportunity.symbol
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar sinal: {e}")
            return False
    
    async def update_positions(self):
        """
        Atualiza posições ativas
        """
        try:
            for position_id, position in list(self.active_positions.items()):
                # Verificar se é hora de fechar posição
                if await self._should_close_position(position):
                    await self._close_arbitrage_position(position)
                
                # Atualizar métricas da posição
                await self._update_position_metrics(position)
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar posições: {e}")
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Retorna métricas de performance da estratégia
        
        Returns:
            Dict: Métricas de performance
        """
        try:
            total_arbitrages = self.successful_arbitrages + self.failed_arbitrages
            success_rate = (
                self.successful_arbitrages / total_arbitrages 
                if total_arbitrages > 0 else 0
            )
            
            # Calcular ROI anualizado
            if self.funding_history:
                daily_funding = np.mean([f['funding_collected'] for f in self.funding_history[-30:]])
                annualized_roi = daily_funding * 365 / self.allocated_capital if self.allocated_capital > 0 else 0
            else:
                annualized_roi = 0
            
            return {
                'strategy_name': self.name,
                'total_funding_collected': self.total_funding_collected,
                'successful_arbitrages': self.successful_arbitrages,
                'failed_arbitrages': self.failed_arbitrages,
                'success_rate': success_rate,
                'active_positions': len(self.active_positions),
                'annualized_roi': annualized_roi,
                'avg_funding_rate': np.mean([o.funding_rate for o in self.opportunities_history[-100:]]) if self.opportunities_history else 0,
                'total_opportunities': len(self.opportunities_history)
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular métricas: {e}")
            return {}
    
    async def _check_funding_support(self) -> bool:
        """
        Verifica se exchange suporta funding rates
        """
        try:
            # Tentar obter funding rate atual
            funding_info = await self.execution_engine.get_funding_rate('BTCUSDT')
            return funding_info is not None
        except:
            return False
    
    async def _load_funding_history(self):
        """
        Carrega histórico de funding rates
        """
        try:
            # Implementar carregamento de histórico
            logger.info("📊 Carregando histórico de funding rates...")
            
            # Por enquanto, criar histórico vazio
            self.funding_history = []
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar histórico: {e}")
    
    async def _setup_funding_monitoring(self):
        """
        Configura monitoramento de funding rates
        """
        try:
            # Configurar WebSocket para funding rates
            await self.market_data.subscribe_funding_rates(['BTCUSDT'])
            logger.info("📡 Monitoramento de funding rates configurado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar monitoramento: {e}")
    
    async def _get_current_funding_rates(self) -> Dict[str, Any]:
        """
        Obtém funding rates atuais
        """
        try:
            symbols = ['BTCUSDT']  # Expandir para mais símbolos conforme necessário
            funding_data = {}
            
            for symbol in symbols:
                funding_info = await self.execution_engine.get_funding_rate(symbol)
                if funding_info:
                    funding_data[symbol] = funding_info
            
            return funding_data
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter funding rates: {e}")
            return {}
    
    async def _analyze_funding_opportunities(self, funding_data: Dict[str, Any]) -> List[FundingOpportunity]:
        """
        Analisa oportunidades de arbitragem
        
        Args:
            funding_data: Dados de funding rates
            
        Returns:
            List[FundingOpportunity]: Oportunidades identificadas
        """
        opportunities = []
        
        try:
            for symbol, funding_info in funding_data.items():
                funding_rate = funding_info.get('fundingRate', 0)
                next_funding_time = funding_info.get('nextFundingTime')
                
                # Calcular taxa anualizada (3 payments por dia)
                annualized_rate = funding_rate * 3 * 365
                
                # Verificar se atende critério mínimo
                if abs(annualized_rate) >= self.min_funding_rate:
                    # Calcular tempo até próximo funding
                    if next_funding_time:
                        time_to_funding = next_funding_time - datetime.now()
                    else:
                        time_to_funding = timedelta(hours=8)  # Padrão 8h
                    
                    # Calcular score de confiança
                    confidence_score = await self._calculate_confidence_score(
                        symbol, funding_rate, time_to_funding
                    )
                    
                    # Estimar lucro esperado
                    expected_profit = await self._estimate_expected_profit(
                        symbol, funding_rate, self.allocated_capital
                    )
                    
                    opportunity = FundingOpportunity(
                        symbol=symbol,
                        funding_rate=funding_rate,
                        annualized_rate=annualized_rate,
                        next_funding_time=next_funding_time,
                        time_to_funding=time_to_funding,
                        confidence_score=confidence_score,
                        expected_profit=expected_profit,
                        required_capital=self.allocated_capital * self.max_position_size
                    )
                    
                    opportunities.append(opportunity)
            
            # Ordenar por lucro esperado
            opportunities.sort(key=lambda x: x.expected_profit, reverse=True)
            
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar oportunidades: {e}")
            return []
    
    async def _validate_opportunity(self, opportunity: FundingOpportunity) -> bool:
        """
        Valida se oportunidade é executável
        
        Args:
            opportunity: Oportunidade a ser validada
            
        Returns:
            bool: True se oportunidade válida
        """
        try:
            # Verificar se já temos posição ativa para este símbolo
            for position in self.active_positions.values():
                if position.symbol == opportunity.symbol and position.status == 'active':
                    return False
            
            # Verificar liquidez
            orderbook = await self.market_data.get_orderbook(opportunity.symbol)
            if not orderbook:
                return False
            
            bid_liquidity = sum([level['quantity'] for level in orderbook['bids'][:5]])
            ask_liquidity = sum([level['quantity'] for level in orderbook['asks'][:5]])
            
            if min(bid_liquidity, ask_liquidity) < self.min_liquidity:
                return False
            
            # Verificar spread spot-futures
            spot_price = await self.market_data.get_spot_price(opportunity.symbol.replace('USDT', '/USDT'))
            futures_price = await self.market_data.get_futures_price(opportunity.symbol)
            
            if spot_price and futures_price:
                spread = abs(futures_price - spot_price) / spot_price
                if spread > self.max_spread:
                    return False
            
            # Verificar tempo até funding (mínimo 1 hora)
            if opportunity.time_to_funding < timedelta(hours=1):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao validar oportunidade: {e}")
            return False
    
    async def _create_arbitrage_signal(self, opportunity: FundingOpportunity) -> Optional[Dict[str, Any]]:
        """
        Cria sinal de arbitragem
        
        Args:
            opportunity: Oportunidade identificada
            
        Returns:
            Optional[Dict]: Sinal criado ou None
        """
        try:
            signal = {
                'strategy': self.name,
                'type': 'funding_arbitrage',
                'symbol': opportunity.symbol,
                'opportunity': opportunity,
                'timestamp': datetime.now(),
                'confidence': opportunity.confidence_score,
                'expected_return': opportunity.expected_profit,
                'risk_level': 'low',  # Funding arbitrage é baixo risco
                'time_horizon': opportunity.time_to_funding
            }
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar sinal: {e}")
            return None
    
    async def _calculate_position_sizes(self, opportunity: FundingOpportunity) -> Dict[str, float]:
        """
        Calcula tamanhos de posição para arbitragem
        
        Args:
            opportunity: Oportunidade de arbitragem
            
        Returns:
            Dict: Tamanhos de posição
        """
        try:
            # Capital disponível para esta arbitragem
            available_capital = self.allocated_capital * self.max_position_size
            
            # Obter preços atuais
            spot_price = await self.market_data.get_spot_price(opportunity.symbol.replace('USDT', '/USDT'))
            futures_price = await self.market_data.get_futures_price(opportunity.symbol)
            
            if not spot_price or not futures_price:
                raise ValueError("Não foi possível obter preços")
            
            # Calcular quantidade baseada no capital disponível
            # Usar preço médio para cálculo
            avg_price = (spot_price + futures_price) / 2
            quantity = available_capital / avg_price
            
            # Ajustar para tamanho mínimo de ordem
            min_order_size = await self.execution_engine.get_min_order_size(opportunity.symbol)
            quantity = max(quantity, min_order_size)
            
            return {
                'spot_quantity': quantity,
                'futures_quantity': quantity,
                'spot_price': spot_price,
                'futures_price': futures_price
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular tamanhos de posição: {e}")
            return {}
    
    async def _execute_arbitrage_positions(
        self, 
        opportunity: FundingOpportunity, 
        position_sizes: Dict[str, float]
    ) -> Optional[ArbitragePosition]:
        """
        Executa posições de arbitragem
        
        Args:
            opportunity: Oportunidade de arbitragem
            position_sizes: Tamanhos de posição
            
        Returns:
            Optional[ArbitragePosition]: Posição criada ou None
        """
        try:
            position_id = f"funding_arb_{opportunity.symbol}_{int(datetime.now().timestamp())}"
            
            # Determinar direção baseada no funding rate
            if opportunity.funding_rate > 0:
                # Funding positivo: long spot, short futures
                spot_side = 'buy'
                futures_side = 'sell'
            else:
                # Funding negativo: short spot, long futures
                spot_side = 'sell'
                futures_side = 'buy'
            
            # Executar ordens simultaneamente
            spot_order = await self.execution_engine.place_order(
                symbol=opportunity.symbol.replace('USDT', '/USDT'),
                side=spot_side,
                order_type='market',
                quantity=position_sizes['spot_quantity'],
                market_type='spot'
            )
            
            futures_order = await self.execution_engine.place_order(
                symbol=opportunity.symbol,
                side=futures_side,
                order_type='market',
                quantity=position_sizes['futures_quantity'],
                market_type='futures'
            )
            
            if spot_order and futures_order:
                # Criar posição de arbitragem
                arbitrage_position = ArbitragePosition(
                    id=position_id,
                    symbol=opportunity.symbol,
                    spot_position={
                        'order_id': spot_order['id'],
                        'side': spot_side,
                        'quantity': position_sizes['spot_quantity'],
                        'price': position_sizes['spot_price']
                    },
                    futures_position={
                        'order_id': futures_order['id'],
                        'side': futures_side,
                        'quantity': position_sizes['futures_quantity'],
                        'price': position_sizes['futures_price']
                    },
                    entry_time=datetime.now(),
                    expected_funding=opportunity.expected_profit,
                    realized_funding=0.0,
                    status='active'
                )
                
                return arbitrage_position
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar posições: {e}")
            return None
    
    async def _schedule_position_close(self, position: ArbitragePosition):
        """
        Agenda fechamento da posição
        
        Args:
            position: Posição a ser fechada
        """
        try:
            # Calcular tempo até próximo funding
            next_funding = await self.execution_engine.get_next_funding_time(position.symbol)
            
            if next_funding:
                # Agendar fechamento após funding
                close_time = next_funding + timedelta(minutes=5)  # 5 min após funding
                delay = (close_time - datetime.now()).total_seconds()
                
                if delay > 0:
                    # Criar task para fechamento
                    asyncio.create_task(self._delayed_position_close(position, delay))
            
        except Exception as e:
            logger.error(f"❌ Erro ao agendar fechamento: {e}")
    
    async def _delayed_position_close(self, position: ArbitragePosition, delay: float):
        """
        Fecha posição após delay
        
        Args:
            position: Posição a ser fechada
            delay: Delay em segundos
        """
        try:
            await asyncio.sleep(delay)
            await self._close_arbitrage_position(position)
            
        except Exception as e:
            logger.error(f"❌ Erro no fechamento agendado: {e}")
    
    async def _close_arbitrage_position(self, position: ArbitragePosition):
        """
        Fecha posição de arbitragem
        
        Args:
            position: Posição a ser fechada
        """
        try:
            logger.strategy(
                f"Fechando posição de arbitragem",
                strategy=self.name,
                position_id=position.id,
                symbol=position.symbol
            )
            
            # Fechar posição spot
            spot_close_order = await self.execution_engine.close_position(
                symbol=position.symbol.replace('USDT', '/USDT'),
                market_type='spot'
            )
            
            # Fechar posição futures
            futures_close_order = await self.execution_engine.close_position(
                symbol=position.symbol,
                market_type='futures'
            )
            
            if spot_close_order and futures_close_order:
                # Calcular funding realizado
                realized_funding = await self._calculate_realized_funding(position)
                position.realized_funding = realized_funding
                position.status = 'closed'
                
                # Atualizar métricas
                self.total_funding_collected += realized_funding
                if realized_funding > 0:
                    self.successful_arbitrages += 1
                else:
                    self.failed_arbitrages += 1
                
                # Remover da lista de posições ativas
                if position.id in self.active_positions:
                    del self.active_positions[position.id]
                
                logger.strategy(
                    f"Posição fechada com sucesso",
                    strategy=self.name,
                    position_id=position.id,
                    realized_funding=realized_funding
                )
            
        except Exception as e:
            logger.error(f"❌ Erro ao fechar posição: {e}")
    
    async def _should_close_position(self, position: ArbitragePosition) -> bool:
        """
        Verifica se posição deve ser fechada
        
        Args:
            position: Posição a ser verificada
            
        Returns:
            bool: True se deve fechar
        """
        try:
            # Verificar tempo de holding
            holding_time = datetime.now() - position.entry_time
            if holding_time > timedelta(hours=self.holding_period_hours):
                return True
            
            # Verificar se funding já foi coletado
            next_funding = await self.execution_engine.get_next_funding_time(position.symbol)
            if next_funding and datetime.now() > next_funding:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar fechamento: {e}")
            return False
    
    async def _update_position_metrics(self, position: ArbitragePosition):
        """
        Atualiza métricas da posição
        
        Args:
            position: Posição a ser atualizada
        """
        try:
            # Calcular PnL atual
            current_pnl = await self._calculate_position_pnl(position)
            
            # Atualizar métricas (implementar conforme necessário)
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar métricas: {e}")
    
    async def _calculate_confidence_score(
        self, 
        symbol: str, 
        funding_rate: float, 
        time_to_funding: timedelta
    ) -> float:
        """
        Calcula score de confiança para oportunidade
        
        Args:
            symbol: Símbolo do ativo
            funding_rate: Taxa de funding
            time_to_funding: Tempo até próximo funding
            
        Returns:
            float: Score de confiança (0-1)
        """
        try:
            score = 0.5  # Base score
            
            # Ajustar baseado na magnitude do funding rate
            if abs(funding_rate) > 0.01:  # 1%
                score += 0.3
            elif abs(funding_rate) > 0.005:  # 0.5%
                score += 0.2
            
            # Ajustar baseado no tempo até funding
            hours_to_funding = time_to_funding.total_seconds() / 3600
            if 2 <= hours_to_funding <= 6:  # Tempo ideal
                score += 0.2
            elif hours_to_funding < 1:  # Muito pouco tempo
                score -= 0.3
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular confiança: {e}")
            return 0.5
    
    async def _estimate_expected_profit(
        self, 
        symbol: str, 
        funding_rate: float, 
        capital: float
    ) -> float:
        """
        Estima lucro esperado da arbitragem
        
        Args:
            symbol: Símbolo do ativo
            funding_rate: Taxa de funding
            capital: Capital disponível
            
        Returns:
            float: Lucro esperado em USD
        """
        try:
            # Lucro = funding_rate * capital * max_position_size
            expected_profit = abs(funding_rate) * capital * self.max_position_size
            
            # Descontar custos estimados (comissões, slippage)
            estimated_costs = capital * self.max_position_size * 0.0008  # 0.08% custos
            
            return max(expected_profit - estimated_costs, 0.0)
            
        except Exception as e:
            logger.error(f"❌ Erro ao estimar lucro: {e}")
            return 0.0
    
    async def _calculate_realized_funding(self, position: ArbitragePosition) -> float:
        """
        Calcula funding realizado da posição
        
        Args:
            position: Posição de arbitragem
            
        Returns:
            float: Funding realizado
        """
        try:
            # Obter histórico de funding payments
            funding_payments = await self.execution_engine.get_funding_payments(
                position.symbol,
                start_time=position.entry_time
            )
            
            total_funding = sum([payment['amount'] for payment in funding_payments])
            return total_funding
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular funding realizado: {e}")
            return 0.0
    
    async def _calculate_position_pnl(self, position: ArbitragePosition) -> float:
        """
        Calcula PnL atual da posição
        
        Args:
            position: Posição de arbitragem
            
        Returns:
            float: PnL atual
        """
        try:
            # Implementar cálculo de PnL
            # Por enquanto retornar 0
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular PnL: {e}")
            return 0.0

