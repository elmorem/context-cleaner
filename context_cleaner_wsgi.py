#!/usr/bin/env python3
"""
WSGI entry point for Context Cleaner Dashboard (Gunicorn)
"""
import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

try:
    from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
    from context_cleaner.config.settings import ContextCleanerConfig
    
    # Load configuration
    config = ContextCleanerConfig.default()
    
    # Create dashboard instance
    dashboard = ComprehensiveHealthDashboard(config=config)
    
    # Export WSGI application
    application = dashboard.app
    
    # Initialize SocketIO for production
    socketio = dashboard.socketio
    
    if __name__ == "__main__":
        # Fallback to development server if run directly
        dashboard.start_server(host="0.0.0.0", port=8081, production=False)
        
except Exception as e:
    print(f"Error creating WSGI application: {e}")
    sys.exit(1)
