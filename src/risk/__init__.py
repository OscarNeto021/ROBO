"""
Risk module - Componentes de gestão de risco do sistema

Este módulo contém componentes para gestão de risco, incluindo:
- Circuit Breaker: Interrompe operações em condições extremas
- Risk Manager: Gerencia limites de risco e exposição
"""

from .circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
    initialize_circuit_breaker,
    is_trading_enabled,
    check_before_order
)

__all__ = [
    'CircuitBreaker',
    'get_circuit_breaker',
    'initialize_circuit_breaker',
    'is_trading_enabled',
    'check_before_order'
]

