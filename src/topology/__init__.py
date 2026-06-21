"""
Topology module for evomas.

This module provides context passing and communication management for multi-agent systems.
"""

from .context import Context
from .routing import RoutingConfig
from .merge import merge_reports
from .ranking import rank_reports, select_visible_reports

__all__ = ['Context', 'RoutingConfig', 'merge_reports', 'rank_reports', 'select_visible_reports']
