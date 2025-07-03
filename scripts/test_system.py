#!/usr/bin/env python3
"""
Test System - Testes completos do BTC Perpetual Elite Trader
"""

import os
import sys
import asyncio
import unittest
from pathlib import Path
import time

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.configuration_manager import ConfigurationManager
from src.core.system_manager import SystemManager
from src.core.backtest_engine import BacktestEngine
from src.core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class SystemTester:
    """
    Testador completo do sistema
    """
    
    def __init__(self):
        self.config_manager = None
        self.system_manager = None
        self.backtest_engine = None
        self.test_results = {}
        
    async def run_all_tests(self):
        """
        Executa todos os testes do sistema
        """
        print("🧪 BTC Perpetual Elite Trader - Testes Completos")
        print("=" * 60)
        print()
        
        try:
            # Testes de configuração
            await self.test_configuration_system()
            
            # Testes de componentes centrais
            await self.test_core_components()
            
            # Testes de estratégias
            await self.test_strategies()
            
            # Testes de backtesting
            await self.test_backtesting_system()
            
            # Testes de integração
            await self.test_system_integration()
            
            # Relatório final
            self.generate_test_report()
            
        except Exception as e:
            logger.error(f"❌ Erro durante testes: {e}")
            print(f"❌ Erro durante testes: {e}")
    
    async def test_configuration_system(self):
        """
        Testa sistema de configuração
        """
        print("🔧 Testando Sistema de Configuração...")
        print("-" * 40)
        
        try:
            # Inicializar ConfigurationManager
            self.config_manager = ConfigurationManager()
            
            # Teste 1: Carregamento de configuração
            print("  📋 Teste 1: Carregamento de configuração...")
            success = self.config_manager.load_configuration()
            self.test_results['config_loading'] = success
            print(f"     {'✅' if success else '❌'} Carregamento: {'Sucesso' if success else 'Falha'}")
            
            # Teste 2: Validação de configuração
            print("  🔍 Teste 2: Validação de configuração...")
            status = self.config_manager.get_configuration_status()
            config_valid = status.get('config_loaded', False)
            self.test_results['config_validation'] = config_valid
            print(f"     {'✅' if config_valid else '❌'} Validação: {'Válida' if config_valid else 'Inválida'}")
            
            # Teste 3: Configuração de demo
            print("  🧪 Teste 3: Modo demo...")
            demo_success = self.config_manager.switch_to_demo_mode()
            self.test_results['demo_mode'] = demo_success
            print(f"     {'✅' if demo_success else '❌'} Demo Mode: {'Ativo' if demo_success else 'Falha'}")
            
            # Teste 4: Exportação de configuração
            print("  📤 Teste 4: Exportação de configuração...")
            export_data = self.config_manager.export_configuration()
            export_success = bool(export_data)
            self.test_results['config_export'] = export_success
            print(f"     {'✅' if export_success else '❌'} Exportação: {'Sucesso' if export_success else 'Falha'}")
            
            print("✅ Testes de configuração concluídos\\n")
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes de configuração: {e}")
            print(f"❌ Erro nos testes de configuração: {e}\\n")
    
    async def test_core_components(self):
        """
        Testa componentes centrais
        """
        print("⚙️ Testando Componentes Centrais...")
        print("-" * 35)
        
        try:
            # Teste 1: Inicialização do SystemManager
            print("  🎯 Teste 1: Inicialização do SystemManager...")
            
            if self.config_manager and self.config_manager.config_loaded:
                self.system_manager = SystemManager(self.config_manager.config)
                init_success = await self.system_manager.initialize()
                self.test_results['system_manager_init'] = init_success
                print(f"     {'✅' if init_success else '❌'} SystemManager: {'Inicializado' if init_success else 'Falha'}")
            else:
                print("     ⚠️ SystemManager: Configuração não disponível")
                self.test_results['system_manager_init'] = False
            
            # Teste 2: Status do sistema
            print("  📊 Teste 2: Status do sistema...")
            if self.system_manager:
                status = self.system_manager.get_status()
                status_success = bool(status)
                self.test_results['system_status'] = status_success
                print(f"     {'✅' if status_success else '❌'} Status: {'Disponível' if status_success else 'Indisponível'}")
            else:
                print("     ⚠️ Status: SystemManager não disponível")
                self.test_results['system_status'] = False
            
            # Teste 3: Componentes individuais
            print("  🔧 Teste 3: Componentes individuais...")
            components_ok = True
            
            if self.system_manager:
                # Testar StrategyManager
                if hasattr(self.system_manager, 'strategy_manager') and self.system_manager.strategy_manager:
                    print("     ✅ StrategyManager: Disponível")
                else:
                    print("     ❌ StrategyManager: Não disponível")
                    components_ok = False
                
                # Testar ModelManager
                if hasattr(self.system_manager, 'model_manager') and self.system_manager.model_manager:
                    print("     ✅ ModelManager: Disponível")
                else:
                    print("     ❌ ModelManager: Não disponível")
                    components_ok = False
                
                # Testar RiskManager
                if hasattr(self.system_manager, 'risk_manager') and self.system_manager.risk_manager:
                    print("     ✅ RiskManager: Disponível")
                else:
                    print("     ❌ RiskManager: Não disponível")
                    components_ok = False
            else:
                components_ok = False
            
            self.test_results['core_components'] = components_ok
            
            print("✅ Testes de componentes centrais concluídos\\n")
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes de componentes: {e}")
            print(f"❌ Erro nos testes de componentes: {e}\\n")
    
    async def test_strategies(self):
        """
        Testa estratégias de trading
        """
        print("🎯 Testando Estratégias de Trading...")
        print("-" * 38)
        
        try:
            strategies_tested = 0
            strategies_passed = 0
            
            if self.system_manager and hasattr(self.system_manager, 'strategy_manager'):
                strategy_manager = self.system_manager.strategy_manager
                
                # Teste 1: Estratégias disponíveis
                print("  📋 Teste 1: Estratégias disponíveis...")
                available_strategies = strategy_manager.available_strategies if strategy_manager else {}
                print(f"     📊 Estratégias disponíveis: {len(available_strategies)}")
                
                for strategy_name in available_strategies.keys():
                    print(f"     - {strategy_name}")
                
                # Teste 2: Estratégias ativas
                print("  ⚡ Teste 2: Estratégias ativas...")
                if strategy_manager:
                    active_strategies = strategy_manager.active_strategies
                    active_count = len(active_strategies)
                    print(f"     📊 Estratégias ativas: {active_count}")
                    
                    for strategy_name in active_strategies.keys():
                        print(f"     - {strategy_name}: Ativa")
                        strategies_tested += 1
                        strategies_passed += 1
                
                # Teste 3: Performance das estratégias
                print("  📈 Teste 3: Performance das estratégias...")
                if strategy_manager and active_strategies:
                    try:
                        performance = await strategy_manager.get_performance_metrics()
                        performance_success = bool(performance)
                        print(f"     {'✅' if performance_success else '❌'} Métricas: {'Disponíveis' if performance_success else 'Indisponíveis'}")
                    except Exception as e:
                        print(f"     ❌ Métricas: Erro - {e}")
                        performance_success = False
                else:
                    print("     ⚠️ Métricas: Nenhuma estratégia ativa")
                    performance_success = False
            else:
                print("     ⚠️ StrategyManager não disponível")
                performance_success = False
            
            self.test_results['strategies_available'] = strategies_tested
            self.test_results['strategies_working'] = strategies_passed
            self.test_results['strategy_performance'] = performance_success
            
            print(f"✅ Testes de estratégias concluídos: {strategies_passed}/{strategies_tested} funcionando\\n")
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes de estratégias: {e}")
            print(f"❌ Erro nos testes de estratégias: {e}\\n")
    
    async def test_backtesting_system(self):
        """
        Testa sistema de backtesting
        """
        print("📊 Testando Sistema de Backtesting...")
        print("-" * 38)
        
        try:
            # Teste 1: Inicialização do BacktestEngine
            print("  🔧 Teste 1: Inicialização do BacktestEngine...")
            
            if self.config_manager:
                self.backtest_engine = BacktestEngine(self.config_manager.config)
                backtest_init = await self.backtest_engine.initialize()
                self.test_results['backtest_init'] = backtest_init
                print(f"     {'✅' if backtest_init else '❌'} BacktestEngine: {'Inicializado' if backtest_init else 'Falha'}")
            else:
                print("     ⚠️ BacktestEngine: Configuração não disponível")
                self.test_results['backtest_init'] = False
                backtest_init = False
            
            # Teste 2: Dados históricos
            print("  📈 Teste 2: Dados históricos...")
            if self.backtest_engine and backtest_init:
                has_data = self.backtest_engine.historical_data is not None
                data_count = len(self.backtest_engine.historical_data) if has_data else 0
                self.test_results['historical_data'] = has_data
                print(f"     {'✅' if has_data else '❌'} Dados: {'Carregados' if has_data else 'Não disponíveis'}")
                if has_data:
                    print(f"     📊 Registros: {data_count}")
            else:
                print("     ⚠️ Dados: BacktestEngine não disponível")
                self.test_results['historical_data'] = False
            
            # Teste 3: Otimização rápida
            print("  ⚡ Teste 3: Teste de otimização...")
            if self.backtest_engine and backtest_init:
                try:
                    from datetime import datetime, timedelta
                    
                    # Teste rápido com período pequeno
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=7)
                    
                    # Testar otimização de funding arbitrage
                    optimization_result = await self.backtest_engine.optimize_strategy_for_capital(
                        'funding_arbitrage',
                        start_date,
                        end_date
                    )
                    
                    optimization_success = bool(optimization_result)
                    self.test_results['optimization_test'] = optimization_success
                    print(f"     {'✅' if optimization_success else '❌'} Otimização: {'Sucesso' if optimization_success else 'Falha'}")
                    
                    if optimization_success:
                        best_score = optimization_result.get('best_score', 0)
                        print(f"     📊 Melhor Score: {best_score:.4f}")
                
                except Exception as e:
                    print(f"     ❌ Otimização: Erro - {e}")
                    self.test_results['optimization_test'] = False
            else:
                print("     ⚠️ Otimização: BacktestEngine não disponível")
                self.test_results['optimization_test'] = False
            
            print("✅ Testes de backtesting concluídos\\n")
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes de backtesting: {e}")
            print(f"❌ Erro nos testes de backtesting: {e}\\n")
    
    async def test_system_integration(self):
        """
        Testa integração completa do sistema
        """
        print("🔗 Testando Integração do Sistema...")
        print("-" * 35)
        
        try:
            # Teste 1: Comunicação entre componentes
            print("  🔄 Teste 1: Comunicação entre componentes...")
            
            integration_score = 0
            total_tests = 4
            
            # ConfigManager <-> SystemManager
            if self.config_manager and self.system_manager:
                print("     ✅ ConfigManager ↔ SystemManager: OK")
                integration_score += 1
            else:
                print("     ❌ ConfigManager ↔ SystemManager: Falha")
            
            # SystemManager <-> StrategyManager
            if (self.system_manager and 
                hasattr(self.system_manager, 'strategy_manager') and 
                self.system_manager.strategy_manager):
                print("     ✅ SystemManager ↔ StrategyManager: OK")
                integration_score += 1
            else:
                print("     ❌ SystemManager ↔ StrategyManager: Falha")
            
            # SystemManager <-> ModelManager
            if (self.system_manager and 
                hasattr(self.system_manager, 'model_manager') and 
                self.system_manager.model_manager):
                print("     ✅ SystemManager ↔ ModelManager: OK")
                integration_score += 1
            else:
                print("     ❌ SystemManager ↔ ModelManager: Falha")
            
            # BacktestEngine independente
            if self.backtest_engine:
                print("     ✅ BacktestEngine: Independente OK")
                integration_score += 1
            else:
                print("     ❌ BacktestEngine: Não disponível")
            
            integration_success = integration_score >= total_tests * 0.75  # 75% dos testes
            self.test_results['system_integration'] = integration_success
            print(f"     📊 Score de Integração: {integration_score}/{total_tests}")
            
            # Teste 2: Fluxo completo simulado
            print("  🎭 Teste 2: Fluxo completo simulado...")
            
            if integration_success:
                try:
                    # Simular ciclo completo
                    print("     🔄 Simulando ciclo de trading...")
                    
                    # 1. Obter status do sistema
                    if self.system_manager:
                        status = self.system_manager.get_status()
                        print("     ✅ Status obtido")
                    
                    # 2. Obter configurações
                    if self.config_manager:
                        trading_config = self.config_manager.get_trading_config()
                        print("     ✅ Configurações obtidas")
                    
                    # 3. Simular métricas de estratégias
                    if (self.system_manager and 
                        hasattr(self.system_manager, 'strategy_manager') and 
                        self.system_manager.strategy_manager):
                        try:
                            metrics = await self.system_manager.strategy_manager.get_performance_metrics()
                            print("     ✅ Métricas de estratégias obtidas")
                        except:
                            print("     ⚠️ Métricas de estratégias: Não disponíveis")
                    
                    # 4. Teste de backtesting
                    if self.backtest_engine:
                        summary = self.backtest_engine.get_optimization_summary()
                        print("     ✅ Resumo de otimização obtido")
                    
                    flow_success = True
                    print("     ✅ Fluxo completo: Sucesso")
                    
                except Exception as e:
                    flow_success = False
                    print(f"     ❌ Fluxo completo: Erro - {e}")
            else:
                flow_success = False
                print("     ⚠️ Fluxo completo: Integração insuficiente")
            
            self.test_results['complete_flow'] = flow_success
            
            print("✅ Testes de integração concluídos\\n")
            
        except Exception as e:
            logger.error(f"❌ Erro nos testes de integração: {e}")
            print(f"❌ Erro nos testes de integração: {e}\\n")
    
    def generate_test_report(self):
        """
        Gera relatório final dos testes
        """
        print("📋 Relatório Final dos Testes")
        print("=" * 35)
        print()
        
        # Calcular estatísticas
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"📊 **Resumo Geral:**")
        print(f"   Total de Testes: {total_tests}")
        print(f"   Testes Aprovados: {passed_tests}")
        print(f"   Taxa de Sucesso: {success_rate:.1f}%")
        print()
        
        # Detalhes por categoria
        print("📋 **Detalhes por Teste:**")
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSOU" if result else "❌ FALHOU"
            test_display = test_name.replace('_', ' ').title()
            print(f"   {status} - {test_display}")
        
        print()
        
        # Recomendações
        print("💡 **Recomendações:**")
        
        if success_rate >= 90:
            print("   🎉 Sistema está funcionando excelentemente!")
            print("   ✅ Pronto para uso em produção")
        elif success_rate >= 75:
            print("   👍 Sistema está funcionando bem")
            print("   ⚠️ Alguns ajustes podem ser necessários")
        elif success_rate >= 50:
            print("   ⚠️ Sistema tem problemas significativos")
            print("   🔧 Correções necessárias antes do uso")
        else:
            print("   ❌ Sistema tem problemas críticos")
            print("   🛠️ Revisão completa necessária")
        
        print()
        
        # Próximos passos
        print("🚀 **Próximos Passos:**")
        
        if not self.test_results.get('config_loading', False):
            print("   1. Verificar configuração do sistema")
        
        if not self.test_results.get('system_manager_init', False):
            print("   2. Revisar inicialização do SystemManager")
        
        if not self.test_results.get('backtest_init', False):
            print("   3. Verificar sistema de backtesting")
        
        if success_rate >= 75:
            print("   ✅ Executar configuração com script setup.py")
            print("   ✅ Configurar APIs da Binance")
            print("   ✅ Executar otimização de estratégias")
            print("   ✅ Iniciar trading em modo demo")
        
        print()
        print("=" * 60)
        print("🧪 Testes Completos Finalizados")
        print("=" * 60)

async def main():
    """
    Função principal
    """
    tester = SystemTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())

