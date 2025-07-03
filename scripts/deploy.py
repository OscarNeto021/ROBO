#!/usr/bin/env python3
"""
Deploy Script - Deployment automatizado do BTC Perpetual Elite Trader
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
import shutil

# Adicionar o diretório raiz ao path para permitir imports do pacote src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.logger import get_trading_logger

logger = get_trading_logger(__name__)

class SystemDeployer:
    """
    Deployer automatizado do sistema
    """
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.deployment_steps = []
        self.errors = []
        
    def run_deployment(self):
        """
        Executa deployment completo
        """
        print("🚀 BTC Perpetual Elite Trader - Deployment Automatizado")
        print("=" * 65)
        print()
        
        try:
            # Verificações pré-deployment
            if not self.pre_deployment_checks():
                print("❌ Verificações pré-deployment falharam!")
                return False
            
            # Instalação de dependências
            if not self.install_dependencies():
                print("❌ Instalação de dependências falhou!")
                return False
            
            # Configuração do ambiente
            if not self.setup_environment():
                print("❌ Configuração do ambiente falhou!")
                return False
            
            # Criação de diretórios
            if not self.create_directories():
                print("❌ Criação de diretórios falhou!")
                return False
            
            # Configuração inicial
            if not self.initial_configuration():
                print("❌ Configuração inicial falhou!")
                return False
            
            # Testes do sistema
            if not self.run_system_tests():
                print("❌ Testes do sistema falharam!")
                return False
            
            # Finalização
            self.finalize_deployment()
            
            print("✅ Deployment concluído com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante deployment: {e}")
            print(f"❌ Erro durante deployment: {e}")
            return False
    
    def pre_deployment_checks(self) -> bool:
        """
        Verificações pré-deployment
        
        Returns:
            bool: True se todas as verificações passaram
        """
        print("🔍 Executando Verificações Pré-Deployment...")
        print("-" * 45)
        
        checks_passed = 0
        total_checks = 5
        
        # Verificar Python
        try:
            python_version = sys.version_info
            if python_version.major >= 3 and python_version.minor >= 8:
                print(f"  ✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
                checks_passed += 1
            else:
                print(f"  ❌ Python {python_version.major}.{python_version.minor}.{python_version.micro} (Requer 3.8+)")
        except Exception as e:
            print(f"  ❌ Python: Erro - {e}")
        
        # Verificar pip
        try:
            result = subprocess.run(['pip', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ pip disponível")
                checks_passed += 1
            else:
                print("  ❌ pip não disponível")
        except Exception as e:
            print(f"  ❌ pip: Erro - {e}")
        
        # Verificar estrutura do projeto
        required_dirs = ['src', 'config', 'dashboard', 'scripts']
        structure_ok = True
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                print(f"  ✅ Diretório {dir_name}/")
            else:
                print(f"  ❌ Diretório {dir_name}/ não encontrado")
                structure_ok = False
        
        if structure_ok:
            checks_passed += 1
        
        # Verificar requirements.txt
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            print("  ✅ requirements.txt encontrado")
            checks_passed += 1
        else:
            print("  ❌ requirements.txt não encontrado")
        
        # Verificar espaço em disco
        try:
            disk_usage = shutil.disk_usage(self.project_root)
            free_gb = disk_usage.free / (1024**3)
            
            if free_gb >= 1.0:  # Pelo menos 1GB livre
                print(f"  ✅ Espaço em disco: {free_gb:.1f}GB livres")
                checks_passed += 1
            else:
                print(f"  ❌ Espaço em disco insuficiente: {free_gb:.1f}GB livres (mínimo 1GB)")
        except Exception as e:
            print(f"  ❌ Espaço em disco: Erro - {e}")
        
        success_rate = (checks_passed / total_checks) * 100
        print(f"\\n  📊 Verificações: {checks_passed}/{total_checks} ({success_rate:.1f}%)\\n")
        
        return checks_passed >= total_checks * 0.8  # 80% das verificações devem passar
    
    def install_dependencies(self) -> bool:
        """
        Instala dependências do projeto
        
        Returns:
            bool: True se instalação bem-sucedida
        """
        print("📦 Instalando Dependências...")
        print("-" * 30)
        
        try:
            requirements_file = self.project_root / "requirements.txt"
            
            if not requirements_file.exists():
                print("  ❌ requirements.txt não encontrado")
                return False
            
            print("  🔄 Instalando pacotes Python...")
            
            # Atualizar pip
            subprocess.run([
                sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'
            ], check=True, capture_output=True)
            
            # Instalar dependências
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("  ✅ Dependências instaladas com sucesso")
                
                # Verificar algumas dependências críticas
                critical_packages = ['pandas', 'numpy', 'flask', 'asyncio']
                
                for package in critical_packages:
                    try:
                        __import__(package)
                        print(f"    ✅ {package}")
                    except ImportError:
                        print(f"    ❌ {package} não disponível")
                        return False
                
                print()
                return True
            else:
                print(f"  ❌ Erro na instalação: {result.stderr}")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Erro na instalação: {e}")
            return False
        except Exception as e:
            print(f"  ❌ Erro inesperado: {e}")
            return False
    
    def setup_environment(self) -> bool:
        """
        Configura ambiente do sistema
        
        Returns:
            bool: True se configuração bem-sucedida
        """
        print("🔧 Configurando Ambiente...")
        print("-" * 25)
        
        try:
            # Criar arquivo .env se não existir
            env_file = self.project_root / ".env"
            
            if not env_file.exists():
                print("  📝 Criando arquivo .env...")
                
                env_content = """# BTC Perpetual Elite Trader - Environment Variables

# Modo de operação
TRADING_MODE=demo

# Configurações de log
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log

# Configurações do dashboard
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=5000
DASHBOARD_DEBUG=False

# Configurações de segurança
SECRET_KEY=your-secret-key-here

# Configurações da Binance (configurar via setup.py)
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=True

# Configurações de trading
INITIAL_CAPITAL=200
MAX_POSITIONS=3
POSITION_SIZE_PCT=0.1

# Configurações de risco
MAX_DAILY_LOSS_PCT=0.05
MAX_DRAWDOWN_PCT=0.15
"""
                
                with open(env_file, 'w') as f:
                    f.write(env_content)
                
                print("  ✅ Arquivo .env criado")
            else:
                print("  ✅ Arquivo .env já existe")
            
            # Configurar variáveis de ambiente
            os.environ['PYTHONPATH'] = str(self.project_root)
            
            print("  ✅ Variáveis de ambiente configuradas")
            print()
            return True
            
        except Exception as e:
            print(f"  ❌ Erro na configuração do ambiente: {e}")
            return False
    
    def create_directories(self) -> bool:
        """
        Cria diretórios necessários
        
        Returns:
            bool: True se criação bem-sucedida
        """
        print("📁 Criando Diretórios...")
        print("-" * 22)
        
        try:
            directories = [
                'logs',
                'data/raw',
                'data/processed',
                'data/models',
                'reports',
                'backups',
                'temp'
            ]
            
            for dir_path in directories:
                full_path = self.project_root / dir_path
                full_path.mkdir(parents=True, exist_ok=True)
                print(f"  ✅ {dir_path}/")
            
            # Criar arquivos .gitkeep para manter diretórios vazios
            gitkeep_dirs = ['logs', 'data/raw', 'data/processed', 'reports', 'temp']
            
            for dir_path in gitkeep_dirs:
                gitkeep_file = self.project_root / dir_path / '.gitkeep'
                gitkeep_file.touch()
            
            print("  ✅ Arquivos .gitkeep criados")
            print()
            return True
            
        except Exception as e:
            print(f"  ❌ Erro na criação de diretórios: {e}")
            return False
    
    def initial_configuration(self) -> bool:
        """
        Configuração inicial do sistema
        
        Returns:
            bool: True se configuração bem-sucedida
        """
        print("⚙️ Configuração Inicial...")
        print("-" * 24)
        
        try:
            # Verificar se configuração já existe
            config_file = self.project_root / "config" / "config.yaml"
            
            if config_file.exists():
                print("  ✅ Configuração já existe")
            else:
                print("  📝 Criando configuração padrão...")
                
                # Criar configuração básica
                from src.core.configuration_manager import ConfigurationManager
                
                config_manager = ConfigurationManager()
                
                # Configuração padrão para $200
                default_config = {
                    'trading': {
                        'initial_capital': 200.0,
                        'max_positions': 3,
                        'position_size_pct': 0.1,
                        'min_position_size': 10.0
                    },
                    'risk_management': {
                        'max_daily_loss_pct': 0.05,
                        'max_drawdown_pct': 0.15,
                        'stop_loss_pct': 0.02,
                        'take_profit_pct': 0.04
                    },
                    'strategies': {
                        'funding_arbitrage': {
                            'enabled': True,
                            'allocation': 0.4,
                            'min_funding_rate': 0.01,
                            'holding_period_hours': 8
                        },
                        'market_making': {
                            'enabled': True,
                            'allocation': 0.3,
                            'spread_pct': 0.001,
                            'inventory_limit': 0.5
                        },
                        'statistical_arbitrage': {
                            'enabled': True,
                            'allocation': 0.3,
                            'lookback_period': 30,
                            'z_score_threshold': 2.0
                        }
                    },
                    'system': {
                        'demo_mode': True,
                        'log_level': 'INFO',
                        'update_interval_seconds': 60,
                        'max_api_calls_per_minute': 1000
                    }
                }
                
                config_manager.config = default_config
                
                if config_manager.save_configuration():
                    print("  ✅ Configuração padrão criada")
                else:
                    print("  ❌ Erro ao criar configuração padrão")
                    return False
            
            print("  ✅ Sistema configurado para capital de $200")
            print("  ✅ Modo demo ativado por padrão")
            print("  ✅ Estratégias otimizadas configuradas")
            print()
            return True
            
        except Exception as e:
            print(f"  ❌ Erro na configuração inicial: {e}")
            return False
    
    def run_system_tests(self) -> bool:
        """
        Executa testes básicos do sistema
        
        Returns:
            bool: True se testes passaram
        """
        print("🧪 Executando Testes Básicos...")
        print("-" * 32)
        
        try:
            # Teste de importação dos módulos principais
            print("  🔍 Testando importações...")
            
            modules_to_test = [
                'src.core.configuration_manager',
                'src.core.system_manager',
                'src.core.backtest_engine',
                'src.strategies.strategy_manager',
                'src.models.model_manager'
            ]
            
            import_success = 0
            
            for module_name in modules_to_test:
                try:
                    __import__(module_name)
                    module_display = module_name.split('.')[-1]
                    print(f"    ✅ {module_display}")
                    import_success += 1
                except ImportError as e:
                    module_display = module_name.split('.')[-1]
                    print(f"    ❌ {module_display}: {e}")
            
            if import_success < len(modules_to_test):
                print(f"  ❌ Importações: {import_success}/{len(modules_to_test)} bem-sucedidas")
                return False
            
            print(f"  ✅ Importações: {import_success}/{len(modules_to_test)} bem-sucedidas")
            
            # Teste de inicialização básica
            print("  🔧 Testando inicialização...")
            
            try:
                from src.core.configuration_manager import ConfigurationManager
                
                config_manager = ConfigurationManager()
                config_loaded = config_manager.load_configuration()
                
                if config_loaded:
                    print("    ✅ ConfigurationManager")
                else:
                    print("    ❌ ConfigurationManager")
                    return False
                
            except Exception as e:
                print(f"    ❌ ConfigurationManager: {e}")
                return False
            
            print("  ✅ Testes básicos concluídos")
            print()
            return True
            
        except Exception as e:
            print(f"  ❌ Erro nos testes: {e}")
            return False
    
    def finalize_deployment(self):
        """
        Finaliza o deployment
        """
        print("🎯 Finalizando Deployment...")
        print("-" * 27)
        
        # Criar scripts de conveniência
        self.create_convenience_scripts()
        
        # Mostrar instruções finais
        self.show_final_instructions()
    
    def create_convenience_scripts(self):
        """
        Cria scripts de conveniência
        """
        try:
            # Script para iniciar o sistema
            start_script = self.project_root / "start.py"
            
            start_content = """#!/usr/bin/env python3
\"\"\"
Start Script - Inicia o BTC Perpetual Elite Trader
\"\"\"

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import main

if __name__ == "__main__":
    main()
"""
            
            with open(start_script, 'w') as f:
                f.write(start_content)
            
            # Tornar executável
            start_script.chmod(0o755)
            
            print("  ✅ Script start.py criado")
            
            # Script para configuração
            setup_script = self.project_root / "setup.py"
            
            if not setup_script.exists():
                setup_content = """#!/usr/bin/env python3
\"\"\"
Setup Script - Configuração do BTC Perpetual Elite Trader
\"\"\"

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.setup import main

if __name__ == "__main__":
    main()
"""
                
                with open(setup_script, 'w') as f:
                    f.write(setup_content)
                
                setup_script.chmod(0o755)
                
                print("  ✅ Script setup.py criado")
            
            # Script para testes
            test_script = self.project_root / "test.py"
            
            test_content = """#!/usr/bin/env python3
\"\"\"
Test Script - Testa o BTC Perpetual Elite Trader
\"\"\"

import sys
import asyncio
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.test_system import main

if __name__ == "__main__":
    asyncio.run(main())
"""
            
            with open(test_script, 'w') as f:
                f.write(test_content)
            
            test_script.chmod(0o755)
            
            print("  ✅ Script test.py criado")
            
        except Exception as e:
            print(f"  ⚠️ Erro ao criar scripts: {e}")
    
    def show_final_instructions(self):
        """
        Mostra instruções finais
        """
        print()
        print("🎉 DEPLOYMENT CONCLUÍDO COM SUCESSO!")
        print("=" * 50)
        print()
        print("📋 **PRÓXIMOS PASSOS:**")
        print()
        print("1. **Configurar o Sistema:**")
        print("   python setup.py")
        print("   (Configure suas APIs da Binance e parâmetros)")
        print()
        print("2. **Testar o Sistema:**")
        print("   python test.py")
        print("   (Execute testes completos)")
        print()
        print("3. **Iniciar o Trading:**")
        print("   python start.py")
        print("   (Inicia o sistema de trading)")
        print()
        print("4. **Acessar Dashboard:**")
        print("   http://localhost:5000")
        print("   (Interface web de monitoramento)")
        print()
        print("🔧 **COMANDOS ÚTEIS:**")
        print()
        print("- Configuração rápida: python scripts/setup.py")
        print("- Testes completos: python scripts/test_system.py")
        print("- Otimização: python scripts/optimize.py")
        print("- Logs: tail -f logs/trading.log")
        print()
        print("💡 **DICAS IMPORTANTES:**")
        print()
        print("✅ Sempre teste em modo DEMO primeiro")
        print("✅ Configure alertas de risco adequados")
        print("✅ Monitore performance diariamente")
        print("✅ Faça backups regulares da configuração")
        print("✅ Mantenha o sistema atualizado")
        print()
        print("📚 **DOCUMENTAÇÃO:**")
        print("   README.md - Guia completo")
        print("   docs/ - Documentação técnica")
        print()
        print("🚀 **BOA SORTE COM SEU TRADING!**")
        print("=" * 50)

def main():
    """
    Função principal
    """
    deployer = SystemDeployer()
    success = deployer.run_deployment()
    
    if success:
        print("\\n✅ Sistema pronto para uso!")
        sys.exit(0)
    else:
        print("\\n❌ Deployment falhou!")
        sys.exit(1)

if __name__ == "__main__":
    main()

