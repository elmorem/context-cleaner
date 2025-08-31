"""Dashboard components for Context Cleaner."""

from .web_server import ProductivityDashboard
from .analytics_dashboard import AnalyticsDashboard
# Optional import - may not be available in all configurations
try:
    from .comprehensive_health_dashboard import ComprehensiveHealthDashboard
    COMPREHENSIVE_DASHBOARD_AVAILABLE = True
except ImportError:
    COMPREHENSIVE_DASHBOARD_AVAILABLE = False

# Build __all__ list dynamically
__all__ = [
    "ProductivityDashboard", 
    "AnalyticsDashboard",
]

# Add comprehensive dashboard if available
if COMPREHENSIVE_DASHBOARD_AVAILABLE:
    __all__.append("ComprehensiveHealthDashboard")
