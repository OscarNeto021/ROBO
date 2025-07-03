#!/usr/bin/env python3
"""
Setup Script - Configuração interativa do BTC Perpetual Elite Trader
"""

import os
import sys
import asyncio
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.configuration_manager import ConfigurationManager
from src.core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class SetupWizard:
    """
    Assistente de configuração interativo
    """
    
    def __init__(self):
        self.config_manager = ConfigurationManager()
        
    def run(self):
        """
        Executa o assistente de configuração
        """
        print("🚀 BTC Perpetual Elite Trader - Assistente de Configuração")
        print("=" * 60)
        print()
        
        try:
            # Carregar configuração existente
            self.config_manager.load_configuration()
            
            # Menu principal
            while True:
                choice = self.show_main_menu()
                
                if choice == '1':
                    self.setup_binance_api()
                elif choice == '2':
                    self.configure_trading_parameters()
                elif choice == '3':
                    self.configure_strategies()
                elif choice == '4':
                    self.configure_risk_management()
                elif choice == '5':
                    self.switch_mode()
                elif choice == '6':
                    self.show_current_configuration()
                elif choice == '7':
                    self.test_configuration()
                elif choice == '8':
                    print("✅ Configuração concluída!")
                    break
                else:
                    print("❌ Opção inválida!")
                
                input("\nPressione Enter para continuar...")
                
        except KeyboardInterrupt:
            print("\n\n🛑 Configuração cancelada pelo usuário")
        except Exception as e:
            print(f"\n❌ Erro durante configuração: {e}")
    
    def show_main_menu(self) -> str:
        """
        Mostra menu principal
        
        Returns:
            str: Opção escolhida
        """
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("🚀 BTC Perpetual Elite Trader - Menu de Configuração")
        print("=" * 60)
        
        # Status atual
        status = self.config_manager.get_configuration_status()
        mode = "🧪 Demo" if status['demo_mode'] else "🚀 Produção"
        binance_status = "✅ Configurada" if status['binance_configured'] else "❌ Não configurada"
        
        print(f"Modo atual: {mode}")
        print(f"API Binance: {binance_status}")
        print()
        
        print("Opções disponíveis:")
        print("1. 🔧 Configurar API da Binance")
        print("2. 💰 Configurar Parâmetros de Trading")
        print("3. 🎯 Configurar Estratégias")
        print("4. 🛡️  Configurar Gestão de Risco")
        print("5. 🔄 Alternar Modo (Demo/Produção)")
        print("6. 📋 Ver Configuração Atual")
        print("7. 🧪 Testar Configuração")
        print("8. ✅ Finalizar Configuração")
        print()
        
        return input("Escolha uma opção (1-8): ").strip()
    
    def setup_binance_api(self):
        """
        Configura API da Binance
        """
        print("\n🔧 Configuração da API da Binance")
        print("-" * 40)
        
        print("\nPara obter suas credenciais da API:")
        print("1. Acesse https://www.binance.com/en/my/settings/api-management")
        print("2. Crie uma nova API Key")
        print("3. Habilite 'Futures Trading'")
        print("4. Configure IP whitelist (recomendado)")
        print()
        
        # Verificar se já existe configuração
        current_config = self.config_manager.get_binance_config()
        if current_config and current_config.get('api_key'):
            print(f"✅ API já configurada (Testnet: {current_config.get('testnet', True)})")
            if input("Deseja reconfigurar? (s/N): ").lower() != 's':
                return
        
        # Solicitar credenciais
        print("\nInsira suas credenciais:")
        api_key = input("API Key: ").strip()
        
        if not api_key:
            print("❌ API Key é obrigatória!")
            return
        
        api_secret = input("API Secret: ").strip()
        
        if not api_secret:
            print("❌ API Secret é obrigatório!")
            return
        
        # Escolher modo
        print("\nEscolha o modo:")
        print("1. Testnet (Recomendado para testes)")
        print("2. Mainnet (Produção - USE COM CUIDADO!)")
        
        mode_choice = input("Modo (1-2): ").strip()
        testnet = mode_choice != '2'
        
        if not testnet:
            print("\n⚠️  ATENÇÃO: Você está configurando para PRODUÇÃO!")
            print("⚠️  Isso usará dinheiro real!")
            confirm = input("Tem certeza? Digite 'CONFIRMO' para continuar: ")
            
            if confirm != 'CONFIRMO':
                print("❌ Configuração cancelada")
                return
        
        # Configurar API
        print("\n🔄 Configurando API...")
        
        if self.config_manager.setup_binance_api(api_key, api_secret, testnet):
            mode_text = "Testnet" if testnet else "Mainnet"
            print(f"✅ API da Binance configurada com sucesso ({mode_text})")
        else:
            print("❌ Erro ao configurar API da Binance")
    
    def configure_trading_parameters(self):
        """
        Configura parâmetros de trading
        """
        print("\n💰 Configuração de Parâmetros de Trading")
        print("-" * 45)
        
        current_config = self.config_manager.get_trading_config()
        
        print(f"\nCapital inicial atual: ${current_config.get('initial_capital', 200)}")
        new_capital = input("Novo capital inicial ($200 recomendado): ").strip()
        
        if new_capital:
            try:
                capital = float(new_capital)
                if capital <= 0:
                    print("❌ Capital deve ser maior que zero!")
                    return
            except ValueError:
                print("❌ Valor inválido!")
                return
        else:
            capital = current_config.get('initial_capital', 200)
        
        print(f"\nMáximo de posições simultâneas atual: {current_config.get('max_positions', 3)}")
        new_positions = input("Novo máximo de posições (3 recomendado): ").strip()
        
        if new_positions:
            try:
                max_positions = int(new_positions)
                if max_positions <= 0:
                    print("❌ Número de posições deve ser maior que zero!")
                    return
            except ValueError:
                print("❌ Valor inválido!")
                return
        else:
            max_positions = current_config.get('max_positions', 3)
        
        print(f"\nTamanho da posição (% do capital) atual: {current_config.get('position_size_pct', 0.1)*100}%")
        new_size = input("Novo tamanho da posição (10% recomendado): ").strip()
        
        if new_size:
            try:
                position_size = float(new_size.replace('%', '')) / 100
                if position_size <= 0 or position_size > 1:
                    print("❌ Tamanho deve estar entre 0% e 100%!")
                    return
            except ValueError:
                print("❌ Valor inválido!")
                return
        else:
            position_size = current_config.get('position_size_pct', 0.1)
        
        # Atualizar configuração
        new_trading_config = current_config.copy()
        new_trading_config.update({
            'initial_capital': capital,
            'max_positions': max_positions,
            'position_size_pct': position_size
        })
        
        self.config_manager.config['trading'] = new_trading_config
        
        if self.config_manager.save_configuration():
            print("✅ Parâmetros de trading atualizados!")
        else:
            print("❌ Erro ao salvar configuração!")
    
    def configure_strategies(self):
        """
        Configura estratégias
        """
        print("\n🎯 Configuração de Estratégias")
        print("-" * 35)
        
        strategies_config = self.config_manager.get_strategies_config()
        
        strategies = [
            ('funding_arbitrage', 'Funding Rate Arbitrage', 'Estratégia de baixo risco baseada em funding rates'),
            ('market_making', 'Market Making', 'Fornece liquidez e captura spreads'),
            ('statistical_arbitrage', 'Statistical Arbitrage', 'Arbitragem estatística entre ativos'),
            ('ml_ensemble', 'ML Ensemble', 'Ensemble de modelos de machine learning')
        ]
        
        print("\nEstrategias disponíveis:")
        
        for i, (key, name, description) in enumerate(strategies, 1):
            current = strategies_config.get(key, {})
            enabled = "✅" if current.get('enabled', False) else "❌"
            allocation = current.get('allocation', 0) * 100
            
            print(f"{i}. {enabled} {name}")
            print(f"   {description}")
            print(f"   Alocação: {allocation:.1f}%")
            print()
        
        # Configurar cada estratégia
        for key, name, description in strategies:
            current = strategies_config.get(key, {})
            
            print(f"\n--- {name} ---")
            
            # Habilitar/desabilitar
            current_enabled = current.get('enabled', False)
            enable_choice = input(f"Habilitar estratégia? (s/N) [atual: {'Sim' if current_enabled else 'Não'}]: ").strip().lower()
            
            if enable_choice == 's':
                enabled = True
            elif enable_choice == 'n':
                enabled = False
            else:
                enabled = current_enabled
            
            # Alocação
            if enabled:
                current_allocation = current.get('allocation', 0) * 100
                allocation_input = input(f"Alocação de capital (%) [atual: {current_allocation:.1f}%]: ").strip()
                
                if allocation_input:
                    try:
                        allocation = float(allocation_input.replace('%', '')) / 100
                        if allocation < 0 or allocation > 1:
                            print("❌ Alocação deve estar entre 0% e 100%!")
                            allocation = current.get('allocation', 0)
                    except ValueError:
                        print("❌ Valor inválido!")
                        allocation = current.get('allocation', 0)
                else:
                    allocation = current.get('allocation', 0)
            else:
                allocation = 0
            
            # Atualizar configuração
            strategies_config[key] = current.copy()
            strategies_config[key].update({
                'enabled': enabled,
                'allocation': allocation
            })
        
        # Validar alocações
        total_allocation = sum(s.get('allocation', 0) for s in strategies_config.values())
        
        if total_allocation > 1.0:
            print(f"\n⚠️  Alocação total excede 100% ({total_allocation*100:.1f}%)")
            print("As alocações serão normalizadas automaticamente.")
            
            # Normalizar alocações
            for strategy in strategies_config.values():
                if strategy.get('allocation', 0) > 0:
                    strategy['allocation'] = strategy['allocation'] / total_allocation
        
        # Salvar configuração
        self.config_manager.config['strategies'] = strategies_config
        
        if self.config_manager.save_configuration():
            print("✅ Configuração de estratégias atualizada!")
        else:
            print("❌ Erro ao salvar configuração!")
    
    def configure_risk_management(self):
        """
        Configura gestão de risco
        """
        print("\n🛡️  Configuração de Gestão de Risco")
        print("-" * 40)
        
        current_config = self.config_manager.get_risk_config()
        
        # Perda máxima diária
        current_daily_loss = current_config.get('max_daily_loss_pct', 0.05) * 100
        print(f"\nPerda máxima diária atual: {current_daily_loss}%")
        new_daily_loss = input("Nova perda máxima diária (% - 5% recomendado): ").strip()
        
        if new_daily_loss:
            try:
                daily_loss = float(new_daily_loss.replace('%', '')) / 100
                if daily_loss <= 0 or daily_loss > 0.5:
                    print("❌ Perda deve estar entre 0% e 50%!")
                    daily_loss = current_config.get('max_daily_loss_pct', 0.05)
            except ValueError:
                print("❌ Valor inválido!")
                daily_loss = current_config.get('max_daily_loss_pct', 0.05)
        else:
            daily_loss = current_config.get('max_daily_loss_pct', 0.05)
        
        # Drawdown máximo
        current_drawdown = current_config.get('max_drawdown_pct', 0.15) * 100
        print(f"\nDrawdown máximo atual: {current_drawdown}%")
        new_drawdown = input("Novo drawdown máximo (% - 15% recomendado): ").strip()
        
        if new_drawdown:
            try:
                drawdown = float(new_drawdown.replace('%', '')) / 100
                if drawdown <= 0 or drawdown > 0.8:
                    print("❌ Drawdown deve estar entre 0% e 80%!")
                    drawdown = current_config.get('max_drawdown_pct', 0.15)
            except ValueError:
                print("❌ Valor inválido!")
                drawdown = current_config.get('max_drawdown_pct', 0.15)
        else:
            drawdown = current_config.get('max_drawdown_pct', 0.15)
        
        # Atualizar configuração
        new_risk_config = current_config.copy()
        new_risk_config.update({
            'max_daily_loss_pct': daily_loss,
            'max_drawdown_pct': drawdown
        })
        
        if self.config_manager.update_risk_config(new_risk_config):
            print("✅ Configuração de risco atualizada!")
        else:
            print("❌ Erro ao salvar configuração!")
    
    def switch_mode(self):
        """
        Alterna entre modo demo e produção
        """
        print("\n🔄 Alternar Modo de Operação")
        print("-" * 35)
        
        current_mode = "Demo" if self.config_manager.is_demo_mode else "Produção"
        print(f"Modo atual: {current_mode}")
        
        if self.config_manager.is_demo_mode:
            print("\n🚀 Alternar para modo PRODUÇÃO")
            print("⚠️  ATENÇÃO: Modo produção usa dinheiro real!")
            print("⚠️  Certifique-se de que:")
            print("   - Suas estratégias foram testadas")
            print("   - Você entende os riscos")
            print("   - Você tem credenciais de produção configuradas")
            
            confirm = input("\nDigite 'CONFIRMO' para alternar para produção: ")
            
            if confirm == 'CONFIRMO':
                if self.config_manager.switch_to_production_mode():
                    print("✅ Modo produção ativado!")
                else:
                    print("❌ Erro ao alternar para produção!")
            else:
                print("❌ Alteração cancelada")
        else:
            print("\n🧪 Alternar para modo DEMO")
            print("✅ Modo demo é seguro para testes")
            
            if input("Confirma alteração para demo? (s/N): ").lower() == 's':
                if self.config_manager.switch_to_demo_mode():
                    print("✅ Modo demo ativado!")
                else:
                    print("❌ Erro ao alternar para demo!")
    
    def show_current_configuration(self):
        """
        Mostra configuração atual
        """
        print("\n📋 Configuração Atual")
        print("-" * 25)
        
        # Status geral
        status = self.config_manager.get_configuration_status()
        mode = "🧪 Demo" if status['demo_mode'] else "🚀 Produção"
        
        print(f"\nModo: {mode}")
        print(f"Configuração carregada: {'✅' if status['config_loaded'] else '❌'}")
        print(f"API Binance: {'✅' if status['binance_configured'] else '❌'}")
        
        # Configuração de trading
        trading_config = self.config_manager.get_trading_config()
        print(f"\n💰 Trading:")
        print(f"   Capital inicial: ${trading_config.get('initial_capital', 0)}")
        print(f"   Máx. posições: {trading_config.get('max_positions', 0)}")
        print(f"   Tamanho posição: {trading_config.get('position_size_pct', 0)*100:.1f}%")
        
        # Estratégias
        strategies_config = self.config_manager.get_strategies_config()
        print(f"\n🎯 Estratégias:")
        
        for key, config in strategies_config.items():
            enabled = "✅" if config.get('enabled', False) else "❌"
            allocation = config.get('allocation', 0) * 100
            name = key.replace('_', ' ').title()
            print(f"   {enabled} {name}: {allocation:.1f}%")
        
        # Gestão de risco
        risk_config = self.config_manager.get_risk_config()
        print(f"\n🛡️  Gestão de Risco:")
        print(f"   Perda máx. diária: {risk_config.get('max_daily_loss_pct', 0)*100:.1f}%")
        print(f"   Drawdown máximo: {risk_config.get('max_drawdown_pct', 0)*100:.1f}%")
    
    def test_configuration(self):
        """
        Testa configuração
        """
        print("\n🧪 Teste de Configuração")
        print("-" * 30)
        
        print("🔄 Testando configuração...")
        
        # Testar carregamento
        if not self.config_manager.config_loaded:
            print("❌ Configuração não carregada!")
            return
        
        print("✅ Configuração carregada")
        
        # Testar API Binance
        binance_config = self.config_manager.get_binance_config()
        if binance_config and binance_config.get('api_key'):
            print("✅ API Binance configurada")
            
            # TODO: Implementar teste real da API
            print("⚠️  Teste de conectividade da API não implementado")
        else:
            print("❌ API Binance não configurada")
        
        # Validar estratégias
        strategies_config = self.config_manager.get_strategies_config()
        enabled_strategies = [k for k, v in strategies_config.items() if v.get('enabled', False)]
        
        if enabled_strategies:
            print(f"✅ {len(enabled_strategies)} estratégias habilitadas")
        else:
            print("⚠️  Nenhuma estratégia habilitada")
        
        # Validar alocações
        total_allocation = sum(s.get('allocation', 0) for s in strategies_config.values())
        
        if total_allocation > 0:
            print(f"✅ Alocação total: {total_allocation*100:.1f}%")
        else:
            print("⚠️  Nenhuma alocação de capital definida")
        
        print("\n✅ Teste de configuração concluído!")

def main():
    """
    Função principal
    """
    wizard = SetupWizard()
    wizard.run()

if __name__ == "__main__":
    main()

