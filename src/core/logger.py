"""
Logger - Sistema de logging personalizado
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import json

class ColoredFormatter(logging.Formatter):
    """
    Formatter colorido para console
    """
    
    # Códigos de cores ANSI
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        # Adicionar cor baseada no nível
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Formatação personalizada
        record.levelname = f"{color}{record.levelname}{reset}"
        
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """
    Formatter JSON para logs estruturados
    """
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adicionar informações extras se disponíveis
        if hasattr(record, 'strategy'):
            log_entry['strategy'] = record.strategy
        
        if hasattr(record, 'symbol'):
            log_entry['symbol'] = record.symbol
        
        if hasattr(record, 'trade_id'):
            log_entry['trade_id'] = record.trade_id
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_size: str = "100MB",
    backup_count: int = 5,
    json_format: bool = False
):
    """
    Configura sistema de logging
    
    Args:
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho para arquivo de log (opcional)
        max_size: Tamanho máximo do arquivo de log
        backup_count: Número de backups a manter
        json_format: Se deve usar formato JSON
    """
    
    # Converter string de tamanho para bytes
    def parse_size(size_str: str) -> int:
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remover handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if json_format:
        console_formatter = JSONFormatter()
    else:
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (se especificado)
    if log_file:
        # Criar diretório se não existir
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handler rotativo
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=parse_size(max_size),
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # Sempre usar JSON para arquivos
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        
        root_logger.addHandler(file_handler)
    
    # Configurar loggers específicos
    _configure_specific_loggers()
    
    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info(f"Sistema de logging configurado - Nível: {level}")

def _configure_specific_loggers():
    """
    Configura loggers específicos para componentes
    """
    
    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('websocket').setLevel(logging.WARNING)
    logging.getLogger('binance').setLevel(logging.INFO)
    
    # Configurar loggers do sistema
    trading_loggers = [
        'strategies',
        'execution', 
        'risk',
        'data',
        'models'
    ]
    
    for logger_name in trading_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

class TradingLogger:
    """
    Logger especializado para trading com contexto adicional
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """
        Define contexto para logs subsequentes
        """
        self.context.update(kwargs)
    
    def clear_context(self):
        """
        Limpa contexto
        """
        self.context.clear()
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """
        Log com contexto adicional
        """
        # Combinar contexto atual com kwargs
        extra = {**self.context, **kwargs}
        
        # Criar record personalizado
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            __file__,
            0,
            message,
            (),
            None
        )
        
        # Adicionar informações extras
        for key, value in extra.items():
            setattr(record, key, value)
        
        self.logger.handle(record)
    
    def debug(self, message: str, **kwargs):
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def trade(self, message: str, trade_id: str, symbol: str, **kwargs):
        """
        Log específico para trades
        """
        self._log_with_context(
            logging.INFO, 
            message, 
            trade_id=trade_id,
            symbol=symbol,
            **kwargs
        )
    
    def strategy(self, message: str, strategy: str, **kwargs):
        """
        Log específico para estratégias
        """
        self._log_with_context(
            logging.INFO,
            message,
            strategy=strategy,
            **kwargs
        )
    
    def risk(self, message: str, risk_type: str, **kwargs):
        """
        Log específico para risco
        """
        self._log_with_context(
            logging.WARNING,
            message,
            risk_type=risk_type,
            **kwargs
        )

def get_trading_logger(name: str) -> TradingLogger:
    """
    Obtém logger especializado para trading
    
    Args:
        name: Nome do logger
        
    Returns:
        TradingLogger: Logger especializado
    """
    return TradingLogger(name)

