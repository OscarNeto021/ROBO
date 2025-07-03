"""
Retry Utils - Utilitários para retry com back-off exponencial

Este módulo implementa funções e decoradores para retry com back-off exponencial,
permitindo operações robustas em APIs externas com tratamento adequado de falhas
temporárias e limites de taxa.

Inclui idempotência na lógica de retry para evitar ordens duplicadas.
"""

import time
import logging
import functools
import random
import uuid
from typing import Any, Callable, Dict, List, Optional, Type, Union, TypeVar
import traceback

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    before_sleep_log,
    RetryError
)

import requests  # Adicionado para resolver referência

from ..core.logger import get_trading_logger
from ..risk.circuit_breaker import check_before_order

logger = get_trading_logger(__name__)

# Tipos para tipagem
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Exceções comuns que devem ser retentadas
RETRY_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    requests.exceptions.RequestException,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError
)

def retry_with_backoff(
    max_attempts: int = 5,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exception_types: Optional[Union[Type[Exception], List[Type[Exception]]]] = None
) -> Callable[[F], F]:
    """
    Decorador para retry com back-off exponencial
    
    Args:
        max_attempts: Número máximo de tentativas
        min_wait: Tempo mínimo de espera em segundos
        max_wait: Tempo máximo de espera em segundos
        exception_types: Tipos de exceção que devem ser retentados
        
    Returns:
        Callable: Decorador configurado
    """
    if exception_types is None:
        exception_types = RETRY_EXCEPTIONS
    
    if not isinstance(exception_types, (list, tuple)):
        exception_types = (exception_types,)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Configurar retry com tenacity
            @retry(
                retry=retry_if_exception_type(exception_types),
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait) + wait_random(0, 1),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True
            )
            def _retry_func() -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Log detalhado da exceção
                    logger.warning(
                        f"Erro na execução de {func.__name__}: {e}. "
                        f"Stack: {traceback.format_exc().splitlines()[-3:-1]}"
                    )
                    raise
            
            try:
                return _retry_func()
            except RetryError as e:
                logger.error(
                    f"Falha após {max_attempts} tentativas em {func.__name__}: {e.last_attempt.exception()}"
                )
                raise e.last_attempt.exception()
        
        return wrapper  # type: ignore
    
    return decorator

def generate_client_order_id(symbol: str, side: str) -> str:
    """
    Gera um ID de ordem único para garantir idempotência
    
    Args:
        symbol: Símbolo do par
        side: Lado da ordem (buy/sell)
        
    Returns:
        str: ID de ordem único
    """
    # Formato: btc_elite_<timestamp>_<uuid4_curto>_<symbol>_<side>
    timestamp = int(time.time() * 1000)
    uuid_short = str(uuid.uuid4())[:8]
    # Remover caracteres não alfanuméricos do símbolo
    clean_symbol = ''.join(c for c in symbol if c.isalnum()).lower()
    
    return f"btc_elite_{timestamp}_{uuid_short}_{clean_symbol}_{side}"

def check_order_exists(
    client: Any,
    symbol: str,
    client_order_id: str,
    **kwargs: Any
) -> Optional[Dict[str, Any]]:
    """
    Verifica se uma ordem com o client_order_id especificado já existe
    
    Args:
        client: Cliente da API
        symbol: Símbolo do par
        client_order_id: ID de cliente da ordem
        **kwargs: Parâmetros adicionais
        
    Returns:
        Optional[Dict[str, Any]]: Ordem existente ou None
    """
    try:
        # Tentar obter ordens abertas
        open_orders = []
        
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_open_orders'):
            # Cliente ccxt
            open_orders = client.fetch_open_orders(symbol, **kwargs)
        elif hasattr(client, 'get_open_orders'):
            # Cliente python-binance
            open_orders = client.get_open_orders(symbol=symbol, **kwargs)
        else:
            # Tentar método genérico
            open_orders = client.open_orders(symbol=symbol, **kwargs)
        
        # Procurar ordem com o client_order_id especificado
        for order in open_orders:
            order_id = order.get('clientOrderId', '')
            if not order_id:
                order_id = order.get('client_order_id', '')
            
            if order_id == client_order_id:
                logger.info(f"Ordem existente encontrada com client_order_id {client_order_id}")
                return order
        
        # Verificar também ordens recentes (algumas exchanges permitem isso)
        if hasattr(client, 'fetch_orders'):
            try:
                recent_orders = client.fetch_orders(symbol, limit=10, **kwargs)
                for order in recent_orders:
                    order_id = order.get('clientOrderId', '')
                    if not order_id:
                        order_id = order.get('client_order_id', '')
                    
                    if order_id == client_order_id:
                        logger.info(f"Ordem recente encontrada com client_order_id {client_order_id}")
                        return order
            except Exception as e:
                logger.warning(f"Erro ao verificar ordens recentes: {e}")
        
        return None
    except Exception as e:
        logger.warning(f"Erro ao verificar existência da ordem: {e}")
        return None

@retry_with_backoff(max_attempts=5, min_wait=2, max_wait=60)
def safe_order(client: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    Função segura para envio de ordens com retry e idempotência
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        **kwargs: Parâmetros da ordem
        
    Returns:
        Dict: Resposta da API
    """
    # Verificar circuit breaker
    if not check_before_order():
        raise RuntimeError("Trading desabilitado pelo circuit breaker")
    
    # Garantir que temos um client_order_id para idempotência
    symbol = kwargs.get('symbol', '')
    side = kwargs.get('side', '').lower()
    
    # Diferentes clientes usam diferentes nomes de parâmetros
    client_order_id = kwargs.get('clientOrderId', '')
    if not client_order_id:
        client_order_id = kwargs.get('client_order_id', '')
    
    if not client_order_id:
        # Gerar um novo client_order_id
        client_order_id = generate_client_order_id(symbol, side)
        
        # Adicionar aos parâmetros da ordem
        if hasattr(client, 'create_order'):
            # Cliente ccxt
            kwargs['clientOrderId'] = client_order_id
        else:
            # Cliente python-binance
            kwargs['newClientOrderId'] = client_order_id
    
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'create_order'):
            # Cliente ccxt
            return client.create_order(**kwargs)
        elif hasattr(client, 'new_order'):
            # Cliente python-binance
            return client.new_order(**kwargs)
        else:
            # Tentar método genérico
            return client.order(**kwargs)
    except Exception as e:
        logger.warning(f"Erro ao enviar ordem: {e}")
        
        # Verificar se a ordem já foi enviada com sucesso
        if client_order_id:
            existing_order = check_order_exists(client, symbol, client_order_id)
            if existing_order:
                logger.info(f"Ordem já existe, retornando ordem existente: {existing_order}")
                return existing_order
        
        # Se não encontrou ordem existente, propaga a exceção para retry
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=10)
def safe_cancel_order(client: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    Função segura para cancelamento de ordens com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        **kwargs: Parâmetros do cancelamento
        
    Returns:
        Dict: Resposta da API
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'cancel_order'):
            # Cliente ccxt
            return client.cancel_order(**kwargs)
        elif hasattr(client, 'cancel_order'):
            # Cliente python-binance
            return client.cancel_order(**kwargs)
        else:
            # Tentar método genérico
            return client.cancel(**kwargs)
    except Exception as e:
        logger.warning(f"Erro ao cancelar ordem: {e}")
        
        # Verificar se a ordem já foi cancelada
        symbol = kwargs.get('symbol', '')
        order_id = kwargs.get('id', kwargs.get('orderId', ''))
        
        if symbol and order_id:
            try:
                # Tentar obter a ordem
                if hasattr(client, 'fetch_order'):
                    order = client.fetch_order(order_id, symbol)
                elif hasattr(client, 'get_order'):
                    order = client.get_order(symbol=symbol, orderId=order_id)
                else:
                    # Sem método para verificar, propaga a exceção
                    raise
                
                # Verificar se a ordem já está cancelada
                status = order.get('status', '').lower()
                if status in ['canceled', 'cancelled', 'canceled', 'expired']:
                    logger.info(f"Ordem {order_id} já está cancelada")
                    return order
            except Exception as inner_e:
                logger.warning(f"Erro ao verificar status da ordem: {inner_e}")
        
        # Se não conseguiu verificar ou a ordem não está cancelada, propaga a exceção
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=5)
def safe_fetch_balance(client: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    Função segura para obter saldo com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        **kwargs: Parâmetros adicionais
        
    Returns:
        Dict: Resposta da API
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_balance'):
            # Cliente ccxt
            return client.fetch_balance(**kwargs)
        elif hasattr(client, 'get_account'):
            # Cliente python-binance
            return client.get_account(**kwargs)
        else:
            # Tentar método genérico
            return client.balance(**kwargs)
    except Exception as e:
        logger.warning(f"Erro ao obter saldo: {e}")
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=5)
def safe_fetch_ticker(client: Any, symbol: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Função segura para obter ticker com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        symbol: Símbolo do par
        **kwargs: Parâmetros adicionais
        
    Returns:
        Dict: Resposta da API
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_ticker'):
            # Cliente ccxt
            return client.fetch_ticker(symbol, **kwargs)
        elif hasattr(client, 'get_ticker'):
            # Cliente python-binance
            return client.get_ticker(symbol=symbol, **kwargs)
        else:
            # Tentar método genérico
            return client.ticker(symbol=symbol, **kwargs)
    except Exception as e:
        logger.warning(f"Erro ao obter ticker para {symbol}: {e}")
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=5)
def safe_fetch_ohlcv(client: Any, symbol: str, timeframe: str, **kwargs: Any) -> List[List[float]]:
    """
    Função segura para obter OHLCV com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        symbol: Símbolo do par
        timeframe: Timeframe (ex: '1m', '1h')
        **kwargs: Parâmetros adicionais
        
    Returns:
        List[List[float]]: Dados OHLCV
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_ohlcv'):
            # Cliente ccxt
            return client.fetch_ohlcv(symbol, timeframe, **kwargs)
        elif hasattr(client, 'get_klines'):
            # Cliente python-binance
            interval = timeframe
            return client.get_klines(symbol=symbol, interval=interval, **kwargs)
        else:
            # Tentar método genérico
            return client.ohlcv(symbol=symbol, interval=timeframe, **kwargs)
    except Exception as e:
        logger.warning(f"Erro ao obter OHLCV para {symbol} ({timeframe}): {e}")
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=5)
def safe_fetch_funding_rate(client: Any, symbol: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Função segura para obter funding rate com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        symbol: Símbolo do par
        **kwargs: Parâmetros adicionais
        
    Returns:
        Dict: Resposta da API
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_funding_rate'):
            # Cliente ccxt
            return client.fetch_funding_rate(symbol, **kwargs)
        elif hasattr(client, 'get_funding_rate'):
            # Cliente python-binance
            return client.get_funding_rate(symbol=symbol, **kwargs)
        elif hasattr(client, 'futures_mark_price'):
            # Cliente python-binance futures
            return client.futures_mark_price(symbol=symbol, **kwargs)
        else:
            # Tentar método genérico
            return client.funding_rate(symbol=symbol, **kwargs)
    except Exception as e:
        logger.warning(f"Erro ao obter funding rate para {symbol}: {e}")
        raise

@retry_with_backoff(max_attempts=3, min_wait=1, max_wait=5)
def safe_fetch_open_orders(client: Any, symbol: Optional[str] = None, **kwargs: Any) -> List[Dict[str, Any]]:
    """
    Função segura para obter ordens abertas com retry
    
    Args:
        client: Cliente da API (ccxt ou python-binance)
        symbol: Símbolo do par (opcional)
        **kwargs: Parâmetros adicionais
        
    Returns:
        List[Dict[str, Any]]: Lista de ordens abertas
    """
    try:
        # Detectar tipo de cliente
        if hasattr(client, 'fetch_open_orders'):
            # Cliente ccxt
            return client.fetch_open_orders(symbol, **kwargs)
        elif hasattr(client, 'get_open_orders'):
            # Cliente python-binance
            params = {'symbol': symbol} if symbol else {}
            params.update(kwargs)
            return client.get_open_orders(**params)
        else:
            # Tentar método genérico
            params = {'symbol': symbol} if symbol else {}
            params.update(kwargs)
            return client.open_orders(**params)
    except Exception as e:
        logger.warning(f"Erro ao obter ordens abertas: {e}")
        raise

def robust_order_placement(
    client: Any,
    order_params: Dict[str, Any],
    max_attempts: int = 5,
    rate_limiter: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Função robusta para colocação de ordens com rate limiting, retry e idempotência
    
    Args:
        client: Cliente da API
        order_params: Parâmetros da ordem
        max_attempts: Número máximo de tentativas
        rate_limiter: Instância de IntelligentRateLimiter
        
    Returns:
        Dict: Resposta da API
    """
    # Verificar circuit breaker
    if not check_before_order():
        raise RuntimeError("Trading desabilitado pelo circuit breaker")
    
    # Aplicar rate limiting se disponível
    if rate_limiter is not None:
        endpoint = 'order'
        weight = 1
        rate_limiter.check_and_wait(endpoint, weight)
    
    # Garantir que temos um client_order_id para idempotência
    symbol = order_params.get('symbol', '')
    side = order_params.get('side', '').lower()
    
    # Diferentes clientes usam diferentes nomes de parâmetros
    client_order_id = order_params.get('clientOrderId', '')
    if not client_order_id:
        client_order_id = order_params.get('client_order_id', '')
        if not client_order_id:
            client_order_id = order_params.get('newClientOrderId', '')
    
    if not client_order_id:
        # Gerar um novo client_order_id
        client_order_id = generate_client_order_id(symbol, side)
        
        # Adicionar aos parâmetros da ordem
        if hasattr(client, 'create_order'):
            # Cliente ccxt
            order_params['clientOrderId'] = client_order_id
        else:
            # Cliente python-binance
            order_params['newClientOrderId'] = client_order_id
    
    # Verificar se a ordem já existe antes de tentar enviar
    existing_order = check_order_exists(client, symbol, client_order_id)
    if existing_order:
        logger.info(f"Ordem já existe, retornando ordem existente: {existing_order}")
        return existing_order
    
    # Tentar enviar ordem com retry e idempotência
    return safe_order(client, **order_params)

