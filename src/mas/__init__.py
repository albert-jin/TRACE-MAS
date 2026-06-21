"""
MAS (Multi-Agent System) module for evomas.

This module provides MAS specification, loading, runtime execution, and interpretation.
"""

from .spec import MasSpec
from .loader import load_mas_from_file
from .runtime import MasRuntime

__all__ = ['MasSpec', 'load_mas_from_file', 'MasRuntime', 'interpret_mas', 'run_mas_cli']


def interpret_mas(*args, **kwargs):
    """Lazy import to avoid loading platform-specific runner dependencies."""
    from .interpreter import interpret_mas as _interpret_mas
    return _interpret_mas(*args, **kwargs)


def run_mas_cli(*args, **kwargs):
    """Lazy import to avoid loading platform-specific runner dependencies."""
    from .interpreter import run_mas_cli as _run_mas_cli
    return _run_mas_cli(*args, **kwargs)
