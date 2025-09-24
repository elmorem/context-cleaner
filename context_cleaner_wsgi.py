#!/usr/bin/env python3
"""
WSGI entry point for Context Cleaner Dashboard (Gunicorn)
Application Factory Pattern for Production Deployment
"""
import sys
import os
import logging
from pathlib import Path

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

logger.info("🔧 WSGI Application Factory Starting...")

def create_app():
    """Application factory for creating Flask app instance."""
    try:
        logger.info("📦 Loading Context Cleaner modules...")
        from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
        from context_cleaner.telemetry.context_rot.config import ApplicationConfig

        logger.info("⚙️ Loading configuration...")
        config = ApplicationConfig.default()
        
        logger.info("🏗️ Creating dashboard instance...")
        dashboard = ComprehensiveHealthDashboard(config=config)
        
        logger.info("✅ Dashboard created successfully")
        logger.info("📡 Initializing SocketIO for production...")
        
        # Ensure SocketIO uses eventlet async mode
        if dashboard.socketio.async_mode != 'eventlet':
            logger.warning(
                "⚠️ SocketIO async_mode is %s, expected 'eventlet'",
                dashboard.socketio.async_mode,
            )
        else:
            logger.info("✅ SocketIO configured with eventlet async mode")
        
        logger.info("🎯 WSGI application ready")
        return dashboard.app, dashboard.socketio
        
    except Exception as e:
        logger.error("❌ Error creating WSGI application: %s", e)
        import traceback
        logger.error("📋 Traceback\n%s", traceback.format_exc())
        raise

# Create application using factory pattern
logger.info("🏭 Invoking application factory...")
app, socketio = create_app()

# Export WSGI application for Gunicorn
application = app

# For compatibility with some WSGI servers
wsgi_app = app

logger.info("🚀 WSGI application exported successfully")
logger.info(f"📊 Flask app: {app}")
logger.info(f"📡 SocketIO: {socketio}")

if __name__ == "__main__":
    # Fallback to development server if run directly
    logger.info("🔧 Running in development mode (direct execution)")
    import socketio as sio_module
    
    # Use SocketIO's run method for development
    socketio.run(app, host="0.0.0.0", port=8081, debug=False)
