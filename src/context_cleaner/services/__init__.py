"""
Context Cleaner Services Module

This module provides comprehensive service orchestration for Context Cleaner,
including dependency management, health monitoring, and graceful shutdown.
"""

try:
    from .service_orchestrator import ServiceOrchestrator, ServiceStatus, ServiceDefinition, ServiceState
    _ORCHESTRATOR_IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - missing orchestrator path
    ServiceOrchestrator = None  # type: ignore[assignment]
    ServiceStatus = None  # type: ignore[assignment]
    ServiceDefinition = None  # type: ignore[assignment]
    ServiceState = None  # type: ignore[assignment]
    _ORCHESTRATOR_IMPORT_ERROR = exc

from .api_ui_consistency_checker import APIUIConsistencyChecker, ConsistencyStatus
from .port_conflict_manager import PortConflictManager, PortConflictStrategy, PortConflictSession

__all__ = [
    'ServiceOrchestrator',
    'ServiceStatus', 
    'ServiceDefinition',
    'ServiceState',
    'APIUIConsistencyChecker',
    'ConsistencyStatus',
    'PortConflictManager',
    'PortConflictStrategy',
    'PortConflictSession'
]
