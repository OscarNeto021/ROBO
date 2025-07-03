"""
Core module - Componentes centrais do sistema
"""

"""Inicialização do módulo core."""

from importlib import import_module

__all__ = ["SystemManager", "ConfigManager", "setup_logging"]

def __getattr__(name):
    if name == "SystemManager":
        return import_module(".system_manager", __name__).SystemManager
    if name == "ConfigManager":
        return import_module(".config_manager", __name__).ConfigManager
    if name == "setup_logging":
        return import_module(".logger", __name__).setup_logging
    raise AttributeError(f"module {__name__} has no attribute {name}")

