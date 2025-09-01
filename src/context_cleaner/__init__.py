"""
Context Cleaner - Advanced productivity tracking and context optimization.

This package provides comprehensive tools for monitoring and improving development
productivity through intelligent context analysis, performance tracking, and
optimization recommendations.
"""

__version__ = "0.2.2"
__author__ = "Context Cleaner Team"
__email__ = "team@context-cleaner.dev"

from .config.settings import ContextCleanerConfig
from .analytics.productivity_analyzer import ProductivityAnalyzer
from .dashboard.web_server import ProductivityDashboard

__all__ = [
    "ContextCleanerConfig",
    "ProductivityAnalyzer",
    "ProductivityDashboard",
]
