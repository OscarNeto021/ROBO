#!/usr/bin/env python3
"""
BTC Perpetual Elite Trader - Sistema Principal
Sistema de trading algorítmico avançado para Bitcoin perpétuo na Binance

Desenvolvido com base em pesquisa extensiva dos melhores traders e robôs do mundo.
Otimizado para capital inicial de $200 mensais com estratégias de elite.
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Dict, Any
import yaml
import argparse
from datetime import datetime

# Adicionar o diretório raiz ao path para permitir imports do pacote src
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.system_manager import SystemManager
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logging
from src.api.dashboard_server import DashboardServer

# Configuração de logging
logger = logging.getLogger(__name__)

class BTCPerpetualEliteTrader:
    """
    Sistema principal do BTC Perpetual Elite Trader
    
    Orquestra todos os componentes do sistema:
    - Estratégias de trading avançadas
    - Machine learning ensemble
    - Gestão de risco multidimensional
    - Dashboard em tempo real
    - APIs da Binance
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Inicializa o sistema principal
        
        Args:
            config_path: Caminho para arquivo de configuração
        """
        self.config_path = config_path
        self.config_manager = None
        self.system_manager = None
        self.dashboard_server = None
        self.running = False
        
        # Setup signal handlers para shutdown graceful
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    async def initialize(self) -> bool:
        """
        Inicializa todos os componentes do sistema
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            logger.info("🚀 Inicializando BTC Perpetual Elite Trader...")
            
            # 1. Carregar configurações
            logger.info("📋 Carregando configurações...")
            self.config_manager = ConfigManager(self.config_path)
            config = self.config_manager.get_config()
            
            # 2. Validar configurações críticas
            if not self._validate_config(config):
                logger.error("❌ Configurações inválidas!")
                return False
            
            # 3. Inicializar sistema principal
            logger.info("🔧 Inicializando sistema principal...")
            self.system_manager = SystemManager(config)
            
            if not await self.system_manager.initialize():
                logger.error("❌ Falha na inicialização do sistema!")
                return False
            
            # 4. Inicializar dashboard
            if config.get('monitoring', {}).get('dashboard_enabled', True):
                logger.info("📊 Inicializando dashboard...")
                port = config.get('monitoring', {}).get('dashboard_port', 8080)
                self.dashboard_server = DashboardServer(
                    self.system_manager, 
                    port=port
                )
                await self.dashboard_server.start()
            
            # 5. Verificar conectividade
            logger.info("🌐 Verificando conectividade...")
            if not await self.system_manager.test_connectivity():
                logger.warning("⚠️ Problemas de conectividade detectados!")
            
            logger.info("✅ Sistema inicializado com sucesso!")
            self._print_startup_summary(config)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {e}")
            return False
    
    async def run(self):
        """
        Loop principal do sistema
        """
        if not await self.initialize():
            logger.error("❌ Falha na inicialização. Encerrando...")
            return
        
        self.running = True
        logger.info("🎯 Sistema em execução! Pressione Ctrl+C para parar.")
        
        try:
            # Loop principal
            while self.running:
                # O SystemManager gerencia todas as operações
                await self.system_manager.run_cycle()
                
                # Pequena pausa para evitar uso excessivo de CPU
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Interrupção do usuário detectada...")
        except Exception as e:
            logger.error(f"❌ Erro no loop principal: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """
        Shutdown graceful do sistema
        """
        logger.info("🛑 Iniciando shutdown do sistema...")
        self.running = False
        
        try:
            # Parar dashboard
            if self.dashboard_server:
                logger.info("📊 Parando dashboard...")
                await self.dashboard_server.stop()
            
            # Parar sistema principal
            if self.system_manager:
                logger.info("🔧 Parando sistema principal...")
                await self.system_manager.shutdown()
            
            logger.info("✅ Shutdown concluído com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro durante shutdown: {e}")
    
    def _signal_handler(self, signum, frame):
        """
        Handler para sinais do sistema
        """
        logger.info(f"🛑 Sinal {signum} recebido. Iniciando shutdown...")
        self.running = False
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Valida configurações críticas
        
        Args:
            config: Configurações carregadas
            
        Returns:
            bool: True se configurações válidas
        """
        required_sections = [
            'exchange', 'capital', 'risk_management', 
            'strategies', 'data', 'execution'
        ]
        
        for section in required_sections:
            if section not in config:
                logger.error(f"❌ Seção obrigatória '{section}' não encontrada!")
                return False
        
        # Validar configurações da exchange
        exchange_config = config['exchange']
        if not exchange_config.get('api_key') or not exchange_config.get('api_secret'):
            logger.error("❌ API keys da Binance não configuradas!")
            logger.info("💡 Configure suas chaves em config/config.yaml")
            return False
        
        # Validar capital inicial
        capital = config['capital'].get('initial_balance', 0)
        if capital <= 0:
            logger.error("❌ Capital inicial deve ser maior que zero!")
            return False
        
        return True
    
    def _print_startup_summary(self, config: Dict[str, Any]):
        """
        Imprime resumo da inicialização
        """
        print("\n" + "="*60)
        print("🚀 BTC PERPETUAL ELITE TRADER")
        print("="*60)
        
        # Informações básicas
        capital = config['capital']['initial_balance']
        testnet = config['exchange']['testnet']
        
        print(f"💰 Capital Inicial: ${capital:,.2f}")
        print(f"🌐 Modo: {'TESTNET' if testnet else 'MAINNET'}")
        print(f"📊 Dashboard: http://localhost:{config.get('monitoring', {}).get('dashboard_port', 8080)}")
        
        # Estratégias ativas
        print("\n📈 Estratégias Ativas:")
        strategies = config.get('strategies', {})
        for name, strategy in strategies.items():
            if strategy.get('enabled', False):
                allocation = strategy.get('allocation', 0) * 100
                print(f"  • {name.replace('_', ' ').title()}: {allocation:.1f}%")
        
        # Configurações de risco
        risk = config.get('risk_management', {})
        print(f"\n⚖️ Gestão de Risco:")
        print(f"  • Risco Máximo: {risk.get('max_portfolio_risk', 0)*100:.1f}%")
        print(f"  • Drawdown Máximo: {risk.get('max_drawdown', 0)*100:.1f}%")
        print(f"  • Perda Diária Máxima: {risk.get('max_daily_loss', 0)*100:.1f}%")
        
        print("\n" + "="*60)
        print("✅ Sistema pronto para trading!")
        print("="*60 + "\n")

def main():
    """
    Função principal
    """
    parser = argparse.ArgumentParser(
        description="BTC Perpetual Elite Trader - Sistema de Trading Algorítmico Avançado"
    )
    
    parser.add_argument(
        "--config", 
        default="config/config.yaml",
        help="Caminho para arquivo de configuração"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de logging"
    )
    
    parser.add_argument(
        "--paper-trading",
        action="store_true",
        help="Executar em modo paper trading"
    )
    
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Executar backtesting ao invés de trading ao vivo"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    # Verificar se arquivo de configuração existe
    if not os.path.exists(args.config):
        logger.error(f"❌ Arquivo de configuração não encontrado: {args.config}")
        logger.info("💡 Copie config/config.example.yaml para config/config.yaml")
        sys.exit(1)
    
    # Criar e executar sistema
    trader = BTCPerpetualEliteTrader(args.config)
    
    try:
        # Executar sistema
        asyncio.run(trader.run())
    except KeyboardInterrupt:
        logger.info("🛑 Sistema interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

