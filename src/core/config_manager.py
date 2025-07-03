"""
Config Manager - Gerenciamento de configurações do sistema
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Gerenciador de configurações do sistema
    
    Funcionalidades:
    - Carregamento de configurações YAML
    - Substituição de variáveis de ambiente
    - Validação de configurações
    - Hot reload de configurações
    - Backup de configurações
    """
    
    def __init__(self, config_path: str):
        """
        Inicializa o gerenciador de configurações
        
        Args:
            config_path: Caminho para arquivo de configuração
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.last_modified: Optional[float] = None
        
        # Carregar configurações iniciais
        self.reload_config()
    
    def reload_config(self) -> bool:
        """
        Recarrega configurações do arquivo
        
        Returns:
            bool: True se recarregamento bem-sucedido
        """
        try:
            if not self.config_path.exists():
                logger.error(f"Arquivo de configuração não encontrado: {self.config_path}")
                return False
            
            # Verificar se arquivo foi modificado
            current_modified = self.config_path.stat().st_mtime
            if self.last_modified and current_modified == self.last_modified:
                return True  # Não modificado
            
            # Carregar arquivo YAML
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            # Substituir variáveis de ambiente
            self.config = self._substitute_env_vars(raw_config)
            self.last_modified = current_modified
            
            logger.info(f"Configurações carregadas de: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """
        Retorna configurações completas
        
        Returns:
            Dict: Configurações do sistema
        """
        return self.config.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de configuração por chave
        
        Args:
            key: Chave da configuração (suporta notação de ponto)
            default: Valor padrão se chave não encontrada
            
        Returns:
            Any: Valor da configuração
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """
        Define valor de configuração
        
        Args:
            key: Chave da configuração (suporta notação de ponto)
            value: Valor a ser definido
            
        Returns:
            bool: True se definição bem-sucedida
        """
        try:
            keys = key.split('.')
            config = self.config
            
            # Navegar até o penúltimo nível
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # Definir valor
            config[keys[-1]] = value
            return True
            
        except Exception as e:
            logger.error(f"Erro ao definir configuração {key}: {e}")
            return False
    
    def save_config(self, backup: bool = True) -> bool:
        """
        Salva configurações no arquivo
        
        Args:
            backup: Se deve criar backup antes de salvar
            
        Returns:
            bool: True se salvamento bem-sucedido
        """
        try:
            # Criar backup se solicitado
            if backup:
                self._create_backup()
            
            # Salvar configurações
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configurações salvas em: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Valida configurações carregadas
        
        Returns:
            bool: True se configurações válidas
        """
        required_sections = [
            'exchange', 'capital', 'risk_management',
            'strategies', 'data', 'execution'
        ]
        
        for section in required_sections:
            if section not in self.config:
                logger.error(f"Seção obrigatória '{section}' não encontrada!")
                return False
        
        # Validações específicas
        if not self._validate_exchange_config():
            return False
        
        if not self._validate_capital_config():
            return False
        
        if not self._validate_risk_config():
            return False
        
        return True
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """
        Substitui variáveis de ambiente nas configurações
        
        Args:
            config: Configuração a ser processada
            
        Returns:
            Any: Configuração com variáveis substituídas
        """
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            # Extrair nome da variável
            var_name = config[2:-1]
            default_value = None
            
            # Suporte para valor padrão: ${VAR:default}
            if ':' in var_name:
                var_name, default_value = var_name.split(':', 1)
            
            # Obter valor da variável de ambiente
            env_value = os.getenv(var_name, default_value)
            
            if env_value is None:
                logger.warning(f"Variável de ambiente '{var_name}' não encontrada!")
                return config
            
            return env_value
        else:
            return config
    
    def _validate_exchange_config(self) -> bool:
        """
        Valida configurações da exchange
        """
        exchange = self.config.get('exchange', {})
        
        if not exchange.get('api_key'):
            logger.error("API key da exchange não configurada!")
            return False
        
        if not exchange.get('api_secret'):
            logger.error("API secret da exchange não configurada!")
            return False
        
        if exchange.get('name') not in ['binance', 'bybit', 'okx']:
            logger.error("Exchange não suportada!")
            return False
        
        return True
    
    def _validate_capital_config(self) -> bool:
        """
        Valida configurações de capital
        """
        capital = self.config.get('capital', {})
        
        initial_balance = capital.get('initial_balance', 0)
        if initial_balance <= 0:
            logger.error("Capital inicial deve ser maior que zero!")
            return False
        
        return True
    
    def _validate_risk_config(self) -> bool:
        """
        Valida configurações de risco
        """
        risk = self.config.get('risk_management', {})
        
        max_risk = risk.get('max_portfolio_risk', 0)
        if max_risk <= 0 or max_risk > 1:
            logger.error("Risco máximo do portfolio deve estar entre 0 e 1!")
            return False
        
        max_drawdown = risk.get('max_drawdown', 0)
        if max_drawdown <= 0 or max_drawdown > 1:
            logger.error("Drawdown máximo deve estar entre 0 e 1!")
            return False
        
        return True
    
    def _create_backup(self):
        """
        Cria backup das configurações atuais
        """
        try:
            backup_dir = self.config_path.parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f'config_backup_{timestamp}.yaml'
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Backup criado: {backup_path}")
            
        except Exception as e:
            logger.warning(f"Erro ao criar backup: {e}")
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Obtém configuração específica de uma estratégia
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            Dict: Configuração da estratégia
        """
        strategies = self.config.get('strategies', {})
        return strategies.get(strategy_name, {})
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """
        Verifica se uma estratégia está habilitada
        
        Args:
            strategy_name: Nome da estratégia
            
        Returns:
            bool: True se estratégia habilitada
        """
        strategy_config = self.get_strategy_config(strategy_name)
        return strategy_config.get('enabled', False)
    
    def get_enabled_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna apenas estratégias habilitadas
        
        Returns:
            Dict: Estratégias habilitadas
        """
        strategies = self.config.get('strategies', {})
        return {
            name: config for name, config in strategies.items()
            if config.get('enabled', False)
        }
    
    def export_config(self, format: str = 'yaml') -> str:
        """
        Exporta configurações em formato específico
        
        Args:
            format: Formato de exportação ('yaml', 'json')
            
        Returns:
            str: Configurações exportadas
        """
        if format.lower() == 'json':
            return json.dumps(self.config, indent=2, default=str)
        else:
            return yaml.dump(self.config, default_flow_style=False, indent=2)
    
    def __str__(self) -> str:
        """
        Representação string do gerenciador
        """
        return f"ConfigManager(path={self.config_path}, sections={len(self.config)})"

