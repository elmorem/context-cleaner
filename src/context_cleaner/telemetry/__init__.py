"""
Telemetry module for Claude Code analytics and automation.

This module provides infrastructure for collecting, analyzing, and acting on
telemetry data from Claude Code sessions to optimize performance, cost, and reliability.

Key features:
- Error recovery and resilience patterns
- Cost optimization and budget management
- Workflow pattern recognition and automation
- Real-time analytics and insights
"""

from .clients.clickhouse_client import ClickHouseClient
from .error_recovery.manager import ErrorRecoveryManager
from .cost_optimization.engine import CostOptimizationEngine
from .jsonl_enhancement.jsonl_processor_service import JsonlProcessorService
from .jsonl_enhancement.full_content_queries import FullContentQueries

__version__ = "1.1.0"

__all__ = [
    "ClickHouseClient",
    "ErrorRecoveryManager",
    "CostOptimizationEngine",
    "JsonlProcessorService",
    "FullContentQueries",
]
