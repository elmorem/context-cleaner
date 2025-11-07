"""
Context Cleaner Dashboard Modular Components

Phase 2: Modular refactoring of comprehensive_health_dashboard.py
Surgical extraction maintaining full functionality and backward compatibility.

Modules:
- dashboard_models: Data models, enums, and data structures
- dashboard_core: Flask app setup, routing coordination, middleware
- dashboard_cache: Unified caching strategy and cache management
- dashboard_realtime: WebSocket handling and real-time updates
- dashboard_analytics: Analytics widgets and data processing
- dashboard_telemetry: Telemetry integration and monitoring
"""

# Module version tracking for rollback safety
__version__ = "2.0.0-phase2"

# Import all modules for backward compatibility
from .dashboard_models import *
from .dashboard_core import *
from .dashboard_cache import *
from .dashboard_realtime import *
from .dashboard_analytics import *
from .dashboard_telemetry import *
