"""
Modern API module for Context Cleaner Dashboard

This module provides a clean, scalable API architecture to replace the legacy
Flask-based dashboard with standardized contracts, real-time capabilities,
and proper separation of concerns.
"""

from .models import APIResponse, PaginatedResponse, EventType, WebSocketMessage
from .services import DashboardService, TelemetryService, CacheService
from .repositories import TelemetryRepository, ClickHouseTelemetryRepository
from .websocket import ConnectionManager, EventBus
from .app import create_app

__all__ = [
    "APIResponse",
    "PaginatedResponse",
    "EventType",
    "WebSocketMessage",
    "DashboardService",
    "TelemetryService",
    "CacheService",
    "TelemetryRepository",
    "ClickHouseTelemetryRepository",
    "ConnectionManager",
    "EventBus",
    "create_app",
]
