"""
Context Cleaner - Advanced productivity tracking and context optimization.

This package provides comprehensive tools for monitoring and improving development
productivity through intelligent context analysis, performance tracking, and
optimization recommendations.
"""

__version__ = "0.2.2"
__author__ = "Context Cleaner Team"
__email__ = "team@context-cleaner.dev"

__all__ = [
    "ContextCleanerConfig",
    "ProductivityAnalyzer",
    "ProductivityDashboard",
]


def __getattr__(name: str):
    if name == "ContextCleanerConfig":
        from .config.settings import ContextCleanerConfig as _ContextCleanerConfig

        return _ContextCleanerConfig
    if name == "ProductivityAnalyzer":
        from .analytics.productivity_analyzer import ProductivityAnalyzer as _ProductivityAnalyzer

        return _ProductivityAnalyzer
    if name == "ProductivityDashboard":
        from .dashboard.web_server import ProductivityDashboard as _ProductivityDashboard

        return _ProductivityDashboard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
