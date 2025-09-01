"""
Dashboard components for Context Cleaner.

The comprehensive health dashboard is now the primary interface, integrating
all features from advanced_dashboard, real_time_performance_dashboard,
analytics_dashboard, and cache_dashboard into a single unified system.

Legacy dashboard classes remain available for backwards compatibility
but delegate to the comprehensive dashboard.
"""

# Primary dashboard - comprehensive health dashboard with all integrated features
from .comprehensive_health_dashboard import ComprehensiveHealthDashboard

# Legacy compatibility dashboards - these now delegate to comprehensive dashboard
from .web_server import ProductivityDashboard

# AnalyticsDashboard compatibility wrapper
class AnalyticsDashboard:
    """Compatibility wrapper that delegates to ComprehensiveHealthDashboard."""
    
    def __init__(self, config=None):
        self.comprehensive_dashboard = ComprehensiveHealthDashboard(config=config)
        self.app = self.comprehensive_dashboard.app
        self.config = config
    
    def start_server(self, host="127.0.0.1", port=8080, debug=False, open_browser=True):
        """Start comprehensive dashboard server."""
        return self.comprehensive_dashboard.start_server(
            host=host, port=port, debug=debug, open_browser=open_browser
        )

# Export comprehensive dashboard as the primary interface
__all__ = [
    # Primary comprehensive dashboard
    "ComprehensiveHealthDashboard",
    
    # Legacy compatibility interfaces (delegate to comprehensive dashboard)
    "ProductivityDashboard",
    "AnalyticsDashboard",
]

# Default dashboard alias for easy access
# Users can import ComprehensiveHealthDashboard or use the alias
Dashboard = ComprehensiveHealthDashboard
