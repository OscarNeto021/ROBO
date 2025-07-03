"""
Configuration Manager - Gerenciador avançado de configurações
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from cryptography.fernet import Fernet
import base64

from .logger import get_trading_logger

logger = get_trading_logger(__name__)

class ConfigurationManager:
    """
    Gerenciador avançado de configurações
    
    Funcionalidades:
    - Configuração de APIs (Binance, etc.)
    - Alternância entre demo/produção
    - Criptografia de credenciais
    - Validação de configurações
    - Backup e restore
    - Interface web para configuração
    """
    
    def __init__(self, config_dir: str = "config"):
        """
        Inicializa o gerenciador de configurações
        
        Args:
            config_dir: Diretório de configurações
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Arquivos de configuração
        self.main_config_file = self.config_dir / "config.yaml"
        self.credentials_file = self.config_dir / "credentials.enc"
        self.backup_dir = self.config_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Configurações carregadas
        self.config: Dict[str, Any] = {}
        self.credentials: Dict[str, Any] = {}
        
        # Chave de criptografia
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Estado
        self.is_demo_mode = True
        self.config_loaded = False
        
        logger.info("ConfigurationManager inicializado")
    
    def load_configuration(self) -> bool:
        """
        Carrega todas as configurações
        
        Returns:
            bool: True se carregamento bem-sucedido
        """
        try:
            logger.info("📁 Carregando configurações...")
            
            # Carregar configuração principal
            if not self._load_main_config():
                logger.error("❌ Falha ao carregar configuração principal")
                return False
            
            # Carregar credenciais
            if not self._load_credentials():
                logger.warning("⚠️ Credenciais não encontradas - usando configuração padrão")
                self._create_default_credentials()
            
            # Validar configurações
            if not self._validate_configuration():
                logger.error("❌ Configuração inválida")
                return False
            
            # Determinar modo (demo/produção)
            self.is_demo_mode = self.config.get('environment', {}).get('demo_mode', True)
            
            self.config_loaded = True
            logger.info(f"✅ Configurações carregadas - Modo: {'Demo' if self.is_demo_mode else 'Produção'}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar configurações: {e}")
            return False
    
    def save_configuration(self) -> bool:
        """
        Salva todas as configurações
        
        Returns:
            bool: True se salvamento bem-sucedido
        """
        try:
            logger.info("💾 Salvando configurações...")
            
            # Criar backup antes de salvar
            self._create_backup()
            
            # Salvar configuração principal
            if not self._save_main_config():
                logger.error("❌ Falha ao salvar configuração principal")
                return False
            
            # Salvar credenciais
            if not self._save_credentials():
                logger.error("❌ Falha ao salvar credenciais")
                return False
            
            logger.info("✅ Configurações salvas")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar configurações: {e}")
            return False
    
    def setup_binance_api(
        self, 
        api_key: str, 
        api_secret: str, 
        testnet: bool = True
    ) -> bool:
        """
        Configura API da Binance
        
        Args:
            api_key: Chave da API
            api_secret: Secret da API
            testnet: Se deve usar testnet
            
        Returns:
            bool: True se configuração bem-sucedida
        """
        try:
            logger.info("🔧 Configurando API da Binance...")
            
            # Validar credenciais
            if not self._validate_binance_credentials(api_key, api_secret, testnet):
                logger.error("❌ Credenciais da Binance inválidas")
                return False
            
            # Salvar credenciais
            if 'binance' not in self.credentials:
                self.credentials['binance'] = {}
            
            self.credentials['binance'].update({
                'api_key': api_key,
                'api_secret': api_secret,
                'testnet': testnet,
                'configured_at': datetime.now().isoformat()
            })
            
            # Atualizar configuração
            if 'exchanges' not in self.config:
                self.config['exchanges'] = {}
            
            self.config['exchanges']['binance'] = {
                'enabled': True,
                'testnet': testnet,
                'base_url': 'https://testnet.binancefuture.com' if testnet else 'https://fapi.binance.com'
            }
            
            # Salvar configurações
            if self.save_configuration():
                logger.info("✅ API da Binance configurada")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar API da Binance: {e}")
            return False
    
    def switch_to_demo_mode(self) -> bool:
        """
        Alterna para modo demo
        
        Returns:
            bool: True se alteração bem-sucedida
        """
        try:
            logger.info("🧪 Alternando para modo demo...")
            
            self.is_demo_mode = True
            
            # Atualizar configuração
            if 'environment' not in self.config:
                self.config['environment'] = {}
            
            self.config['environment']['demo_mode'] = True
            
            # Configurar URLs de testnet
            if 'exchanges' in self.config and 'binance' in self.config['exchanges']:
                self.config['exchanges']['binance']['testnet'] = True
                self.config['exchanges']['binance']['base_url'] = 'https://testnet.binancefuture.com'
            
            # Salvar configuração
            if self.save_configuration():
                logger.info("✅ Modo demo ativado")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao alternar para modo demo: {e}")
            return False
    
    def switch_to_production_mode(self) -> bool:
        """
        Alterna para modo produção
        
        Returns:
            bool: True se alteração bem-sucedida
        """
        try:
            logger.info("🚀 Alternando para modo produção...")
            
            # Verificar se credenciais de produção estão configuradas
            if not self._has_production_credentials():
                logger.error("❌ Credenciais de produção não configuradas")
                return False
            
            self.is_demo_mode = False
            
            # Atualizar configuração
            if 'environment' not in self.config:
                self.config['environment'] = {}
            
            self.config['environment']['demo_mode'] = False
            
            # Configurar URLs de produção
            if 'exchanges' in self.config and 'binance' in self.config['exchanges']:
                self.config['exchanges']['binance']['testnet'] = False
                self.config['exchanges']['binance']['base_url'] = 'https://fapi.binance.com'
            
            # Salvar configuração
            if self.save_configuration():
                logger.info("✅ Modo produção ativado")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao alternar para modo produção: {e}")
            return False
    
    def get_binance_config(self) -> Optional[Dict[str, Any]]:
        """
        Obtém configuração da Binance
        
        Returns:
            Optional[Dict]: Configuração da Binance
        """
        try:
            if 'binance' not in self.credentials:
                return None
            
            binance_creds = self.credentials['binance']
            binance_config = self.config.get('exchanges', {}).get('binance', {})
            
            return {
                'api_key': binance_creds.get('api_key'),
                'api_secret': binance_creds.get('api_secret'),
                'testnet': self.is_demo_mode or binance_creds.get('testnet', True),
                'base_url': binance_config.get('base_url'),
                'enabled': binance_config.get('enabled', False)
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter configuração da Binance: {e}")
            return None
    
    def get_trading_config(self) -> Dict[str, Any]:
        """
        Obtém configuração de trading
        
        Returns:
            Dict: Configuração de trading
        """
        return self.config.get('trading', {})
    
    def get_strategies_config(self) -> Dict[str, Any]:
        """
        Obtém configuração das estratégias
        
        Returns:
            Dict: Configuração das estratégias
        """
        return self.config.get('strategies', {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """
        Obtém configuração de risco
        
        Returns:
            Dict: Configuração de risco
        """
        return self.config.get('risk_management', {})
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Atualiza configuração de uma estratégia
        
        Args:
            strategy_name: Nome da estratégia
            config: Nova configuração
            
        Returns:
            bool: True se atualização bem-sucedida
        """
        try:
            if 'strategies' not in self.config:
                self.config['strategies'] = {}
            
            self.config['strategies'][strategy_name] = config
            
            return self.save_configuration()
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar configuração da estratégia {strategy_name}: {e}")
            return False
    
    def update_risk_config(self, config: Dict[str, Any]) -> bool:
        """
        Atualiza configuração de risco
        
        Args:
            config: Nova configuração de risco
            
        Returns:
            bool: True se atualização bem-sucedida
        """
        try:
            self.config['risk_management'] = config
            return self.save_configuration()
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar configuração de risco: {e}")
            return False
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """
        Obtém status da configuração
        
        Returns:
            Dict: Status da configuração
        """
        return {
            'config_loaded': self.config_loaded,
            'demo_mode': self.is_demo_mode,
            'binance_configured': 'binance' in self.credentials,
            'has_production_credentials': self._has_production_credentials(),
            'last_backup': self._get_last_backup_time(),
            'config_file_exists': self.main_config_file.exists(),
            'credentials_file_exists': self.credentials_file.exists()
        }
    
    def export_configuration(self, include_credentials: bool = False) -> Dict[str, Any]:
        """
        Exporta configuração
        
        Args:
            include_credentials: Se deve incluir credenciais
            
        Returns:
            Dict: Configuração exportada
        """
        export_data = {
            'config': self.config.copy(),
            'exported_at': datetime.now().isoformat(),
            'demo_mode': self.is_demo_mode
        }
        
        if include_credentials:
            # Remover dados sensíveis
            safe_credentials = {}
            for key, value in self.credentials.items():
                if isinstance(value, dict):
                    safe_credentials[key] = {
                        k: v if k not in ['api_secret'] else '***HIDDEN***'
                        for k, v in value.items()
                    }
                else:
                    safe_credentials[key] = value
            
            export_data['credentials'] = safe_credentials
        
        return export_data
    
    def import_configuration(self, config_data: Dict[str, Any]) -> bool:
        """
        Importa configuração
        
        Args:
            config_data: Dados de configuração
            
        Returns:
            bool: True se importação bem-sucedida
        """
        try:
            logger.info("📥 Importando configuração...")
            
            # Validar dados
            if 'config' not in config_data:
                logger.error("❌ Dados de configuração inválidos")
                return False
            
            # Criar backup antes de importar
            self._create_backup()
            
            # Importar configuração
            self.config = config_data['config']
            
            # Importar credenciais se disponíveis
            if 'credentials' in config_data:
                self.credentials = config_data['credentials']
            
            # Salvar configuração
            if self.save_configuration():
                logger.info("✅ Configuração importada")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao importar configuração: {e}")
            return False
    
    def _load_main_config(self) -> bool:
        """
        Carrega configuração principal
        
        Returns:
            bool: True se carregamento bem-sucedido
        """
        try:
            if not self.main_config_file.exists():
                logger.info("📄 Criando configuração padrão...")
                self._create_default_config()
                return True
            
            with open(self.main_config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar configuração principal: {e}")
            return False
    
    def _save_main_config(self) -> bool:
        """
        Salva configuração principal
        
        Returns:
            bool: True se salvamento bem-sucedido
        """
        try:
            with open(self.main_config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar configuração principal: {e}")
            return False
    
    def _load_credentials(self) -> bool:
        """
        Carrega credenciais criptografadas
        
        Returns:
            bool: True se carregamento bem-sucedido
        """
        try:
            if not self.credentials_file.exists():
                return False
            
            with open(self.credentials_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            self.credentials = json.loads(decrypted_data.decode('utf-8'))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar credenciais: {e}")
            return False
    
    def _save_credentials(self) -> bool:
        """
        Salva credenciais criptografadas
        
        Returns:
            bool: True se salvamento bem-sucedido
        """
        try:
            credentials_json = json.dumps(self.credentials)
            encrypted_data = self.cipher.encrypt(credentials_json.encode('utf-8'))
            
            with open(self.credentials_file, 'wb') as f:
                f.write(encrypted_data)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar credenciais: {e}")
            return False
    
    def _get_or_create_encryption_key(self) -> bytes:
        """
        Obtém ou cria chave de criptografia
        
        Returns:
            bytes: Chave de criptografia
        """
        key_file = self.config_dir / ".encryption_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Tornar arquivo somente leitura
            os.chmod(key_file, 0o600)
            
            return key
    
    def _create_default_config(self):
        """
        Cria configuração padrão
        """
        self.config = {
            'environment': {
                'demo_mode': True,
                'log_level': 'INFO',
                'data_path': 'data/',
                'models_path': 'data/models/',
                'logs_path': 'logs/'
            },
            'trading': {
                'initial_capital': 200.0,
                'max_positions': 3,
                'position_size_pct': 0.1,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04
            },
            'strategies': {
                'funding_arbitrage': {
                    'enabled': True,
                    'allocation': 0.4,
                    'min_funding_rate': 0.01
                },
                'market_making': {
                    'enabled': True,
                    'allocation': 0.3,
                    'spread_pct': 0.001
                },
                'statistical_arbitrage': {
                    'enabled': False,
                    'allocation': 0.2
                },
                'ml_ensemble': {
                    'enabled': False,
                    'allocation': 0.1
                }
            },
            'risk_management': {
                'max_daily_loss_pct': 0.05,
                'max_drawdown_pct': 0.15,
                'position_size_limit_pct': 0.2,
                'correlation_limit': 0.7
            },
            'models': {
                'retrain_interval_days': 7,
                'ensemble': {
                    'enabled': True,
                    'voting_method': 'soft'
                },
                'xgboost': {
                    'enabled': True,
                    'n_estimators': 100
                },
                'lstm': {
                    'enabled': True,
                    'sequence_length': 60
                },
                'random_forest': {
                    'enabled': True,
                    'n_estimators': 50
                }
            }
        }
    
    def _create_default_credentials(self):
        """
        Cria credenciais padrão
        """
        self.credentials = {
            'created_at': datetime.now().isoformat(),
            'version': '1.0'
        }
    
    def _validate_configuration(self) -> bool:
        """
        Valida configuração
        
        Returns:
            bool: True se configuração válida
        """
        try:
            # Verificar seções obrigatórias
            required_sections = ['environment', 'trading', 'strategies', 'risk_management']
            
            for section in required_sections:
                if section not in self.config:
                    logger.error(f"❌ Seção obrigatória ausente: {section}")
                    return False
            
            # Validar valores específicos
            trading_config = self.config['trading']
            
            if trading_config.get('initial_capital', 0) <= 0:
                logger.error("❌ Capital inicial deve ser maior que zero")
                return False
            
            if trading_config.get('max_positions', 0) <= 0:
                logger.error("❌ Número máximo de posições deve ser maior que zero")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na validação: {e}")
            return False
    
    def _validate_binance_credentials(self, api_key: str, api_secret: str, testnet: bool) -> bool:
        """
        Valida credenciais da Binance
        
        Args:
            api_key: Chave da API
            api_secret: Secret da API
            testnet: Se é testnet
            
        Returns:
            bool: True se credenciais válidas
        """
        try:
            # Validações básicas
            if not api_key or not api_secret:
                return False
            
            if len(api_key) < 10 or len(api_secret) < 10:
                return False
            
            # TODO: Implementar teste real da API
            # Por enquanto, apenas validação básica
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na validação das credenciais: {e}")
            return False
    
    def _has_production_credentials(self) -> bool:
        """
        Verifica se tem credenciais de produção
        
        Returns:
            bool: True se tem credenciais de produção
        """
        try:
            if 'binance' not in self.credentials:
                return False
            
            binance_creds = self.credentials['binance']
            
            return (
                binance_creds.get('api_key') and
                binance_creds.get('api_secret') and
                not binance_creds.get('testnet', True)
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar credenciais de produção: {e}")
            return False
    
    def _create_backup(self):
        """
        Cria backup das configurações
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"config_backup_{timestamp}.yaml"
            
            backup_data = {
                'config': self.config,
                'backup_created_at': datetime.now().isoformat(),
                'demo_mode': self.is_demo_mode
            }
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                yaml.dump(backup_data, f, default_flow_style=False, allow_unicode=True)
            
            # Manter apenas os últimos 10 backups
            backups = sorted(self.backup_dir.glob("config_backup_*.yaml"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {e}")
    
    def _get_last_backup_time(self) -> Optional[str]:
        """
        Obtém horário do último backup
        
        Returns:
            Optional[str]: Horário do último backup
        """
        try:
            backups = sorted(self.backup_dir.glob("config_backup_*.yaml"))
            if backups:
                return backups[-1].stat().st_mtime
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter último backup: {e}")
            return None

