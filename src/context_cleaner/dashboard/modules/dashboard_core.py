"""
Dashboard Core Orchestration and Infrastructure

Phase 2.7 Extraction: Core dashboard coordination and server management
Extracted from core infrastructure logic in comprehensive_health_dashboard.py
Implements clean service orchestration and eliminates legacy patterns

Contains:
- Core dashboard orchestration and service coordination
- Server lifecycle management (development/production)
- Configuration management and dependency injection
- Service integration patterns for all extracted modules
- WSGI application setup for production deployments
- Health monitoring and circuit breaker integration
- Clean separation of concerns and single responsibility
"""

import asyncio
import json
import logging
import multiprocessing
import os
import sys
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from flask import Flask
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)


class DashboardConfigurationManager:
    """
    Unified configuration management for dashboard services
    Extracted from dashboard initialization logic
    Implements dependency injection and service configuration
    """

    def __init__(self, config=None):
        # Create default config if None provided (backwards compatibility)
        from context_cleaner.telemetry.context_rot.config import ApplicationConfig

        self.config = config or ApplicationConfig.default()

        # Server configuration
        self.host = "127.0.0.1"
        self.port = 8080
        self.debug = False

        # Runtime state
        self._is_running = False
        self._start_time = time.time()

        # Alert thresholds for monitoring
        self._alert_thresholds = {
            "memory_mb": 50.0,
            "cpu_percent": 5.0,
            "memory_critical_mb": 60.0,
            "cpu_critical_percent": 8.0,
        }
        self._last_alerts: Dict[str, datetime] = {}
        self._alert_cooldown_minutes = 5

    def get_templates_directory(self) -> str:
        """Get templates directory path for Flask"""
        return str(Path(__file__).parent.parent / "templates")

    def get_flask_config(self) -> Dict[str, Any]:
        """Get Flask application configuration"""
        return {
            "SECRET_KEY": "context-cleaner-comprehensive-dashboard",
            "TEMPLATES_AUTO_RELOAD": True,
        }

    def get_socketio_config(self) -> Dict[str, Any]:
        """Get SocketIO configuration"""
        return {"cors_allowed_origins": "*", "async_mode": "eventlet"}

    def get_basic_dashboard_metrics(self) -> Dict[str, Any]:
        """Get basic dashboard metrics for monitoring"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - self._start_time,
            "is_running": self._is_running,
            "alert_thresholds": self._alert_thresholds,
        }


class DashboardServiceIntegrator:
    """
    Integrates all extracted dashboard modules into unified service
    Extracted from service initialization logic
    Implements clean dependency injection between modules
    """

    def __init__(self, config_manager: DashboardConfigurationManager):
        self.config_manager = config_manager

        # Service instances (initialized by setup methods)
        self.cache_dashboard = None
        self.dashboard_cache = None
        self.cache_coordinator = None
        self.realtime_manager = None
        self.realtime_coordinator = None
        self.analytics_manager = None
        self.telemetry_manager = None

        # Core analysis services
        self.health_scorer = None
        self.pattern_recognizer = None
        self.context_analyzer = None

        # Enhanced reliability infrastructure
        self.health_monitor = None
        self.dashboard_metrics_breaker = None

    def initialize_core_services(self):
        """Initialize core analysis services"""
        try:
            from context_cleaner.analysis.cache_discovery import CacheDiscoveryService
            from context_cleaner.analysis.usage_patterns import UsagePatternAnalyzer
            from context_cleaner.analysis.token_efficiency import (
                TokenEfficiencyAnalyzer,
            )
            from context_cleaner.analysis.temporal_context import (
                TemporalContextAnalyzer,
            )
            from context_cleaner.analysis.enhanced_context import (
                EnhancedContextAnalyzer,
            )
            from context_cleaner.scoring.context_health_scorer import (
                ContextHealthScorer,
            )
            from context_cleaner.recognition.advanced_pattern_recognizer import (
                AdvancedPatternRecognizer,
            )

            # Initialize core services
            self.cache_discovery = CacheDiscoveryService()
            self.usage_analyzer = UsagePatternAnalyzer()
            self.token_analyzer = TokenEfficiencyAnalyzer()
            self.temporal_analyzer = TemporalContextAnalyzer()
            self.enhanced_analyzer = EnhancedContextAnalyzer()
            self.health_scorer = ContextHealthScorer()
            self.pattern_recognizer = AdvancedPatternRecognizer()

            logger.info("✅ Core analysis services initialized")

        except ImportError as e:
            logger.warning(f"Some core services not available: {e}")

    def initialize_optional_services(self):
        """Initialize optional analysis services with graceful fallback"""
        # Context Window Analysis
        try:
            from context_cleaner.analysis.context_window_analyzer import (
                ContextWindowAnalyzer,
            )

            self.context_analyzer = ContextWindowAnalyzer()
            logger.info("✅ Context window analyzer initialized")
        except ImportError:
            logger.info("Context window analyzer not available")
            self.context_analyzer = None

        # Project Summary Analytics
        try:
            from context_cleaner.analysis.project_summary_analytics import (
                ProjectSummaryAnalytics,
            )

            self.project_summary_analytics = ProjectSummaryAnalytics()
            logger.info("✅ Project summary analytics initialized")
        except ImportError:
            logger.info("Project summary analytics not available")
            self.project_summary_analytics = None

    def initialize_cache_services(self):
        """Initialize cache dashboard and management services"""
        try:
            from context_cleaner.optimization.cache_dashboard import (
                CacheEnhancedDashboard,
            )
            from .dashboard_cache import DashboardCache, CacheCoordinator

            self.cache_dashboard = CacheEnhancedDashboard()
            self.dashboard_cache = DashboardCache(
                cache_dashboard=self.cache_dashboard,
                telemetry_widgets=None,  # Will be set after telemetry initialization
            )
            self.cache_coordinator = CacheCoordinator(self.dashboard_cache)

            logger.info("✅ Cache services initialized")

        except ImportError as e:
            logger.warning(f"Cache services not available: {e}")

    def initialize_realtime_services(self, socketio: SocketIO, dashboard_instance):
        """Initialize WebSocket-first real-time services"""
        try:
            from .dashboard_realtime import DashboardRealtime, RealtimeCoordinator

            self.realtime_manager = DashboardRealtime(
                dashboard_instance=dashboard_instance, socketio=socketio
            )
            self.realtime_coordinator = RealtimeCoordinator(self.realtime_manager)

            logger.info("✅ Real-time services initialized")

        except ImportError as e:
            logger.error(f"Real-time services initialization failed: {e}")

    def initialize_analytics_services(self):
        """Initialize analytics and chart generation services"""
        try:
            from .dashboard_analytics import DashboardAnalytics, AnalyticsCoordinator

            self.analytics_manager = DashboardAnalytics(
                dashboard_cache=self.dashboard_cache,
                realtime_manager=self.realtime_manager,
            )
            self.analytics_coordinator = AnalyticsCoordinator(self.analytics_manager)

            logger.info("✅ Analytics services initialized")

        except ImportError as e:
            logger.warning(f"Analytics services not available: {e}")

    def initialize_telemetry_services(self):
        """Initialize telemetry and monitoring services"""
        try:
            from .dashboard_telemetry import DashboardTelemetry, TelemetryCoordinator

            self.telemetry_manager = DashboardTelemetry(
                dashboard_cache=self.dashboard_cache,
                realtime_manager=self.realtime_manager,
            )
            self.telemetry_coordinator = TelemetryCoordinator(self.telemetry_manager)

            # Link telemetry widgets to cache for delegation
            if self.dashboard_cache and self.telemetry_manager.telemetry_enabled:
                self.dashboard_cache.telemetry_widgets = (
                    self.telemetry_manager.initializer.telemetry_widgets
                )

            logger.info("✅ Telemetry services initialized")

        except ImportError as e:
            logger.warning(f"Telemetry services not available: {e}")

    def initialize_reliability_infrastructure(self):
        """Initialize enhanced reliability infrastructure"""
        try:
            from context_cleaner.core.enhanced_health_monitor import (
                EnhancedHealthMonitor,
            )
            from context_cleaner.core.circuit_breaker import (
                CircuitBreaker,
                CircuitBreakerConfig,
            )

            # Initialize health monitor for dependency checking
            self.health_monitor = EnhancedHealthMonitor()

            # Initialize circuit breaker for dashboard metrics endpoint
            dashboard_metrics_config = CircuitBreakerConfig(
                name="dashboard_metrics", failure_threshold=3, recovery_timeout=30
            )
            self.dashboard_metrics_breaker = CircuitBreaker(dashboard_metrics_config)

            logger.info("✅ Enhanced reliability infrastructure initialized")

        except ImportError as e:
            logger.info(f"Enhanced reliability features not available: {e}")
            self.health_monitor = None
            self.dashboard_metrics_breaker = None

    def setup_all_services(self, socketio: SocketIO, dashboard_instance) -> bool:
        """Setup all dashboard services with proper dependency order"""
        try:
            # Initialize services in dependency order
            self.initialize_core_services()
            self.initialize_optional_services()
            self.initialize_cache_services()
            self.initialize_realtime_services(socketio, dashboard_instance)
            self.initialize_analytics_services()
            self.initialize_telemetry_services()
            self.initialize_reliability_infrastructure()

            logger.info("🚀 All dashboard services initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            return False

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all initialized services"""
        return {
            "cache_dashboard": self.cache_dashboard is not None,
            "dashboard_cache": self.dashboard_cache is not None,
            "realtime_manager": self.realtime_manager is not None,
            "analytics_manager": self.analytics_manager is not None,
            "telemetry_manager": self.telemetry_manager is not None,
            "health_monitor": self.health_monitor is not None,
            "context_analyzer": self.context_analyzer is not None,
            "project_summary_analytics": hasattr(self, "project_summary_analytics")
            and self.project_summary_analytics is not None,
        }


class DashboardServerManager:
    """
    Manages dashboard server lifecycle and deployment
    Extracted from server start/stop logic
    Supports both development and production deployment
    """

    def __init__(
        self,
        app: Flask,
        socketio: SocketIO,
        config_manager: DashboardConfigurationManager,
    ):
        self.app = app
        self.socketio = socketio
        self.config_manager = config_manager

    def start_server(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        debug: bool = False,
        open_browser: bool = True,
        production: Optional[bool] = None,
        gunicorn_workers: Optional[int] = None,
    ):
        """Start the dashboard server with smart production/development detection and robust fallback"""
        self.config_manager.host = host
        self.config_manager.port = port
        self.config_manager.debug = debug
        self.config_manager._is_running = True

        # Smart auto-detection: try production first unless explicitly disabled
        if production is None:
            production = self._should_use_production_server()
            logger.info(
                f"🔍 Auto-detected server mode: {'production' if production else 'development'}"
            )

        if production:
            logger.info(
                f"🚀 Attempting to start with Gunicorn (production) on http://{host}:{port}"
            )
            try:
                self._start_production_server(
                    host, port, gunicorn_workers, open_browser
                )
            except Exception as e:
                logger.warning(f"💡 Production server failed: {e}")
                logger.info("🔄 Falling back to development server...")
                self._start_development_server(host, port, debug, open_browser)
        else:
            logger.info(
                f"🛠️ Starting with Flask development server on http://{host}:{port}"
            )
            self._start_development_server(host, port, debug, open_browser)

    def _start_development_server(
        self, host: str, port: int, debug: bool, open_browser: bool
    ):
        """Start Flask development server with Werkzeug"""
        if open_browser:
            # Open browser after a short delay
            threading.Timer(
                1.0, lambda: webbrowser.open(f"http://{host}:{port}")
            ).start()

        try:
            self.socketio.run(
                self.app,
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,  # Disable reloader to prevent threading issues
                allow_unsafe_werkzeug=True,  # Allow development server for testing
            )
        except KeyboardInterrupt:
            logger.info("Shutting down development server...")
            self.stop_server()
        except Exception as e:
            logger.error(f"Development server error: {e}")
            raise

    def _start_production_server(
        self, host: str, port: int, workers: Optional[int], open_browser: bool
    ):
        """Start production server using Gunicorn"""
        try:
            logger.info("🔧 === GUNICORN STARTUP DIAGNOSTICS ===")

            # Set workers count
            if workers is None:
                workers = multiprocessing.cpu_count() * 2 + 1
            logger.info(
                f"📊 Workers configuration: {workers} (CPU count: {multiprocessing.cpu_count()})"
            )

            # Check if Gunicorn is installed
            gunicorn_path = shutil.which("gunicorn")
            if gunicorn_path:
                logger.info(f"✅ Gunicorn found at: {gunicorn_path}")
            else:
                logger.warning(
                    "⚠️  Gunicorn executable not found on PATH; will invoke via current Python interpreter"
                )

            try:
                subprocess.run(
                    [sys.executable, "-m", "gunicorn", "--version"],
                    check=True,
                    capture_output=True,
                )
                logger.info(
                    f"✅ Gunicorn module available in interpreter: {sys.executable}"
                )
            except Exception as exc:
                logger.error("❌ Gunicorn invocation failed: %s", exc)
                raise

            # Create WSGI application entry point
            logger.info("📝 Creating WSGI entry point...")
            self._create_wsgi_entry_point()
            logger.info("✅ WSGI entry point created successfully")

            # Verify WSGI file
            wsgi_file = Path.cwd() / "context_cleaner_wsgi.py"
            if wsgi_file.exists():
                logger.info(f"✅ WSGI file exists: {wsgi_file}")
                logger.info(f"📏 WSGI file size: {wsgi_file.stat().st_size} bytes")
            else:
                logger.error(f"❌ WSGI file not found: {wsgi_file}")
                raise FileNotFoundError(f"WSGI file not found: {wsgi_file}")

            # Open browser if requested
            if open_browser:
                threading.Timer(
                    2.0, lambda: webbrowser.open(f"http://{host}:{port}")
                ).start()

            # Build Gunicorn command
            cmd = [
                sys.executable,
                "-m",
                "gunicorn",
                "--bind",
                f"{host}:{port}",
                "--workers",
                str(workers),
                "--worker-class",
                "uvicorn.workers.UvicornWorker",
                "--timeout",
                "300",
                "--keep-alive",
                "5",
                "--access-logfile",
                "-",
                "--error-logfile",
                "-",
                "--log-level",
                "info",
                "context_cleaner_wsgi:application",
            ]

            logger.info(f"🚀 Starting Gunicorn with command: {' '.join(cmd)}")

            # Start Gunicorn
            try:
                subprocess.run(cmd, check=True, cwd=Path.cwd())
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Gunicorn failed with exit code {e.returncode}")
                raise
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down production server...")
                self.stop_server()

        except Exception as e:
            logger.error(f"Production server startup failed: {e}")
            raise  # Let the main start_server method handle the fallback

    def _should_use_production_server(self) -> bool:
        """Smart auto-detection of whether to use production server"""
        # Check if gunicorn is available
        try:
            import subprocess

            subprocess.run(
                ["gunicorn", "--version"], capture_output=True, check=True, timeout=5
            )
            logger.debug("✅ Gunicorn is available")
            gunicorn_available = True
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            logger.debug("❌ Gunicorn not available or not working")
            gunicorn_available = False

        # Check environment indicators
        import os

        env_indicators = {
            "FLASK_ENV": os.getenv("FLASK_ENV", "").lower(),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "").lower(),
            "DEPLOYMENT_ENV": os.getenv("DEPLOYMENT_ENV", "").lower(),
        }

        # Force development server if explicitly set
        is_dev_env = any(
            env in ["development", "dev", "local"] for env in env_indicators.values()
        )

        # Force production server if explicitly set
        is_prod_env = any(
            env in ["production", "prod", "staging"] for env in env_indicators.values()
        )

        # Auto-detection logic
        if is_dev_env:
            logger.debug("🛠️ Environment indicates development mode")
            return False
        elif is_prod_env:
            logger.debug("🚀 Environment indicates production mode")
            return gunicorn_available
        else:
            # Default: try production if gunicorn is available
            logger.debug(
                "🔍 No explicit environment set, defaulting based on gunicorn availability"
            )
            return gunicorn_available

    def _create_wsgi_entry_point(self):
        """Create WSGI entry point for Gunicorn"""
        wsgi_content = '''"""
WSGI Entry Point for Context Cleaner Dashboard

This file is auto-generated for production deployment with Gunicorn.
"""

import sys
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Import the main dashboard application
    from src.context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard

    # Create the dashboard instance
    dashboard = ComprehensiveHealthDashboard()

    # The WSGI application that Gunicorn will use
    application = dashboard.app

    print("✅ WSGI application loaded successfully")

except Exception as e:
    print(f"❌ WSGI application failed to load: {e}")
    raise

if __name__ == "__main__":
    print("⚠️  This is a WSGI entry point. Use with Gunicorn or similar WSGI server.")
    print("For development, run the dashboard directly.")
'''

        wsgi_file = Path.cwd() / "context_cleaner_wsgi.py"
        try:
            with open(wsgi_file, "w", encoding="utf-8") as f:
                f.write(wsgi_content)
            logger.info(f"📝 WSGI entry point written to: {wsgi_file}")
        except Exception as e:
            logger.error(f"Failed to create WSGI entry point: {e}")
            raise

    def stop_server(self):
        """Stop the dashboard server gracefully"""
        try:
            self.config_manager._is_running = False
            logger.info("🛑 Dashboard server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")


class DashboardCoreOrchestrator:
    """
    Main orchestrator for all dashboard services and infrastructure
    Extracted from comprehensive dashboard initialization
    Provides clean coordination and single point of control
    """

    def __init__(self, cache_dir: Optional[Path] = None, config: Optional[Any] = None):
        # Initialize configuration manager
        self.config_manager = DashboardConfigurationManager(config)

        # Create Flask application
        self.app = Flask(
            __name__, template_folder=self.config_manager.get_templates_directory()
        )
        self.app.config.update(self.config_manager.get_flask_config())

        # Setup CORS headers for API access
        @self.app.after_request
        def after_request(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )
            return response

        # Initialize SocketIO for real-time updates
        socketio_config = self.config_manager.get_socketio_config()
        self.socketio = SocketIO(self.app, **socketio_config)

        # Initialize service integrator
        self.service_integrator = DashboardServiceIntegrator(self.config_manager)

        # Initialize server manager
        self.server_manager = DashboardServerManager(
            self.app, self.socketio, self.config_manager
        )

        logger.info("🚀 Dashboard core orchestrator initialized")

    def initialize_all_services(self, dashboard_instance) -> bool:
        """Initialize all dashboard services"""
        return self.service_integrator.setup_all_services(
            self.socketio, dashboard_instance
        )

    def start_realtime_infrastructure(self):
        """Start real-time infrastructure if available"""
        if self.service_integrator.realtime_coordinator:
            self.service_integrator.realtime_coordinator.setup_realtime_infrastructure()

    def start_server(self, **kwargs):
        """Start the dashboard server"""
        return self.server_manager.start_server(**kwargs)

    def stop_server(self):
        """Stop the dashboard server"""
        # Stop real-time infrastructure
        if self.service_integrator.realtime_coordinator:
            self.service_integrator.realtime_coordinator.shutdown_realtime_infrastructure()

        # Stop server
        return self.server_manager.stop_server()

    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all orchestrator components"""
        return {
            "config_manager": True,
            "flask_app": self.app is not None,
            "socketio": self.socketio is not None,
            "service_integrator": self.service_integrator is not None,
            "server_manager": self.server_manager is not None,
            "services_status": self.service_integrator.get_service_status(),
            "basic_metrics": self.config_manager.get_basic_dashboard_metrics(),
        }

    def get_app(self) -> Flask:
        """Get Flask application instance for routing setup"""
        return self.app

    def get_socketio(self) -> SocketIO:
        """Get SocketIO instance for real-time features"""
        return self.socketio

    def get_service_integrator(self) -> DashboardServiceIntegrator:
        """Get service integrator for module access"""
        return self.service_integrator


class ModuleStatus:
    """Track module extraction status"""

    EXTRACTION_STATUS = "extracted"
    ORIGINAL_LINES = 800  # Core infrastructure, server management, service coordination
    TARGET_LINES = 600
    REDUCTION_TARGET = "Clean service orchestration with single responsibility and eliminated duplication"


logger.info(
    f"dashboard_core module extracted - Status: {ModuleStatus.EXTRACTION_STATUS}"
)
