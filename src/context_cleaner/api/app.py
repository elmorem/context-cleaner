"""
FastAPI Application Factory

Creates the modern API application with proper dependency injection,
middleware, WebSocket support, and integration with existing systems.
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
import asyncio
import uuid
from datetime import datetime

from .models import (
    APIResponse, PaginatedResponse, WidgetRequest, MetricsRequest,
    CacheInvalidationRequest, DashboardOverviewResponse, WidgetListResponse
)
from .services import DashboardService, TelemetryService
from .repositories import ClickHouseTelemetryRepository
from .cache import MultiLevelCache, InMemoryCache
from .websocket import ConnectionManager, EventBus, HeartbeatManager
from ..telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)

def create_app(
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 9000,
    redis_url: str = "redis://localhost:6379",
    enable_websockets: bool = True,
    debug: bool = False
) -> FastAPI:
    """
    Create and configure the FastAPI application

    Args:
        clickhouse_host: ClickHouse server host
        clickhouse_port: ClickHouse server port
        redis_url: Redis connection URL for caching
        enable_websockets: Enable WebSocket support
        debug: Enable debug mode

    Returns:
        Configured FastAPI application
    """

    app = FastAPI(
        title="Context Cleaner API",
        description="Modern API for Context Cleaner Dashboard with real-time capabilities",
        version="2.0.0",
        debug=debug
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Add React dev server
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Global state - will be initialized in startup event
    app.state.clickhouse_client = None
    app.state.cache_service = None
    app.state.dashboard_service = None
    app.state.telemetry_service = None
    app.state.connection_manager = None
    app.state.event_bus = None
    app.state.heartbeat_manager = None

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup"""
        try:
            logger.info("Starting Context Cleaner API...")

            # Initialize ClickHouse client
            app.state.clickhouse_client = ClickHouseClient(
                host=clickhouse_host,
                port=clickhouse_port,
                database="otel"
            )
            await app.state.clickhouse_client.initialize()

            # Initialize cache service
            try:
                app.state.cache_service = MultiLevelCache(redis_url=redis_url)
            except Exception as e:
                logger.warning(f"Redis not available, falling back to in-memory cache: {e}")
                app.state.cache_service = InMemoryCache()

            # Initialize repository
            telemetry_repo = ClickHouseTelemetryRepository(app.state.clickhouse_client)

            # Initialize WebSocket components
            if enable_websockets:
                app.state.connection_manager = ConnectionManager()
                app.state.event_bus = EventBus()
                app.state.event_bus.set_websocket_manager(app.state.connection_manager)

                app.state.heartbeat_manager = HeartbeatManager(app.state.connection_manager)
                await app.state.heartbeat_manager.start()

            # Initialize services
            app.state.dashboard_service = DashboardService(
                telemetry_repo=telemetry_repo,
                cache_service=app.state.cache_service,
                event_bus=app.state.event_bus or EventBus()
            )

            app.state.telemetry_service = TelemetryService(
                telemetry_repo=telemetry_repo,
                cache_service=app.state.cache_service
            )

            logger.info("Context Cleaner API started successfully")

        except Exception as e:
            logger.error(f"Error during startup: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean shutdown of services"""
        try:
            logger.info("Shutting down Context Cleaner API...")

            if app.state.heartbeat_manager:
                await app.state.heartbeat_manager.stop()

            if app.state.clickhouse_client:
                await app.state.clickhouse_client.close()

            logger.info("Context Cleaner API shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    # Dependency injection helpers
    def get_dashboard_service() -> DashboardService:
        """Get dashboard service instance"""
        if not app.state.dashboard_service:
            raise HTTPException(status_code=503, detail="Dashboard service not available")
        return app.state.dashboard_service

    def get_telemetry_service() -> TelemetryService:
        """Get telemetry service instance"""
        if not app.state.telemetry_service:
            raise HTTPException(status_code=503, detail="Telemetry service not available")
        return app.state.telemetry_service

    def get_connection_manager() -> ConnectionManager:
        """Get WebSocket connection manager"""
        if not app.state.connection_manager:
            raise HTTPException(status_code=503, detail="WebSocket not available")
        return app.state.connection_manager

    # API Routes
    @app.get("/api/v1/health", response_model=APIResponse[Dict[str, Any]])
    async def health_check(dashboard_service: DashboardService = Depends(get_dashboard_service)):
        """System health check endpoint"""
        try:
            health = await dashboard_service.get_system_status()
            return APIResponse(
                success=True,
                data=health.to_dict(),
                metadata={"endpoint": "health", "version": "v1"},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return APIResponse(
                success=False,
                error="Health check failed",
                error_code="HEALTH_CHECK_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.get("/api/v1/dashboard/overview", response_model=APIResponse[DashboardOverviewResponse])
    async def get_dashboard_overview(dashboard_service: DashboardService = Depends(get_dashboard_service)):
        """Get complete dashboard overview"""
        try:
            overview = await dashboard_service.get_dashboard_overview()
            return APIResponse(
                success=True,
                data=overview,
                metadata={"endpoint": "dashboard/overview", "cached": False},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Dashboard overview failed: {e}")
            return APIResponse(
                success=False,
                error="Failed to get dashboard overview",
                error_code="DASHBOARD_OVERVIEW_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.get("/api/v1/widgets/{widget_type}", response_model=APIResponse[Dict[str, Any]])
    async def get_widget_data(
        widget_type: str = Path(..., description="Widget type identifier"),
        session_id: Optional[str] = Query(None, description="Optional session ID filter"),
        time_range_days: int = Query(7, ge=1, le=30, description="Time range in days"),
        force_refresh: bool = Query(False, description="Force cache refresh"),
        dashboard_service: DashboardService = Depends(get_dashboard_service)
    ):
        """Get data for specific widget"""
        try:
            widget_data = await dashboard_service.get_widget_data(
                widget_type=widget_type,
                session_id=session_id,
                time_range_days=time_range_days,
                force_refresh=force_refresh
            )

            return APIResponse(
                success=True,
                data=widget_data.to_dict(),
                metadata={
                    "widget_type": widget_type,
                    "time_range_days": time_range_days,
                    "cached": not force_refresh
                },
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Widget data failed for {widget_type}: {e}")
            return APIResponse(
                success=False,
                error=f"Failed to get widget data for {widget_type}",
                error_code="WIDGET_DATA_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.get("/api/v1/widgets", response_model=APIResponse[WidgetListResponse])
    async def get_multiple_widgets(
        widget_types: List[str] = Query(..., description="List of widget types"),
        session_id: Optional[str] = Query(None, description="Optional session ID filter"),
        time_range_days: int = Query(7, ge=1, le=30, description="Time range in days"),
        dashboard_service: DashboardService = Depends(get_dashboard_service)
    ):
        """Get multiple widgets efficiently"""
        try:
            widgets_data = await dashboard_service.get_multiple_widgets(
                widget_types=widget_types,
                session_id=session_id,
                time_range_days=time_range_days
            )

            widgets_list = list(widgets_data.values())

            response_data = WidgetListResponse(
                widgets=widgets_list,
                total_count=len(widgets_list),
                healthy_count=sum(1 for w in widgets_list if w.status == "healthy"),
                warning_count=sum(1 for w in widgets_list if w.status == "warning"),
                critical_count=sum(1 for w in widgets_list if w.status == "critical")
            )

            return APIResponse(
                success=True,
                data=response_data,
                metadata={"widget_types": widget_types, "time_range_days": time_range_days},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Multiple widgets failed: {e}")
            return APIResponse(
                success=False,
                error="Failed to get multiple widgets",
                error_code="MULTIPLE_WIDGETS_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.get("/api/v1/telemetry/sessions", response_model=APIResponse[List[Dict[str, Any]]])
    async def get_active_sessions(
        limit: int = Query(50, ge=1, le=200, description="Maximum number of sessions"),
        telemetry_service: TelemetryService = Depends(get_telemetry_service)
    ):
        """Get active sessions"""
        try:
            sessions = await telemetry_service.get_active_sessions(limit=limit)
            return APIResponse(
                success=True,
                data=sessions,
                metadata={"limit": limit, "count": len(sessions)},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Active sessions failed: {e}")
            return APIResponse(
                success=False,
                error="Failed to get active sessions",
                error_code="ACTIVE_SESSIONS_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.get("/api/v1/telemetry/cost-analysis", response_model=APIResponse[Dict[str, Any]])
    async def get_cost_analysis(
        days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
        dashboard_service: DashboardService = Depends(get_dashboard_service)
    ):
        """Get comprehensive cost analysis"""
        try:
            analysis = await dashboard_service.get_cost_analysis(days=days)
            return APIResponse(
                success=True,
                data=analysis,
                metadata={"analysis_period_days": days},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Cost analysis failed: {e}")
            return APIResponse(
                success=False,
                error="Failed to get cost analysis",
                error_code="COST_ANALYSIS_FAILED",
                request_id=str(uuid.uuid4())
            )

    @app.post("/api/v1/cache/invalidate", response_model=APIResponse[Dict[str, Any]])
    async def invalidate_cache(
        request: CacheInvalidationRequest,
        dashboard_service: DashboardService = Depends(get_dashboard_service)
    ):
        """Invalidate cache entries"""
        try:
            success = await dashboard_service.invalidate_cache(request.pattern)
            return APIResponse(
                success=success,
                data={"pattern": request.pattern, "invalidated": success},
                metadata={"scope": request.scope},
                request_id=str(uuid.uuid4())
            )
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return APIResponse(
                success=False,
                error="Failed to invalidate cache",
                error_code="CACHE_INVALIDATION_FAILED",
                request_id=str(uuid.uuid4())
            )

    # WebSocket endpoint
    if enable_websockets:
        @app.websocket("/ws/v1/realtime")
        async def websocket_endpoint(
            websocket: WebSocket,
            client_id: str = Query(..., description="Unique client identifier"),
            connection_manager: ConnectionManager = Depends(get_connection_manager)
        ):
            """WebSocket endpoint for real-time updates"""
            try:
                await connection_manager.connect(websocket, client_id)
                logger.info(f"WebSocket client connected: {client_id}")

                while True:
                    try:
                        # Receive message from client
                        message = await websocket.receive_text()
                        await connection_manager.handle_client_message(client_id, message)

                    except WebSocketDisconnect:
                        logger.info(f"WebSocket client disconnected: {client_id}")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket error for client {client_id}: {e}")
                        break

            except Exception as e:
                logger.error(f"WebSocket connection error for {client_id}: {e}")
            finally:
                await connection_manager.disconnect(client_id)

        @app.get("/api/v1/websocket/stats", response_model=APIResponse[Dict[str, Any]])
        async def get_websocket_stats(connection_manager: ConnectionManager = Depends(get_connection_manager)):
            """Get WebSocket connection statistics"""
            try:
                stats = await connection_manager.get_connection_stats()
                return APIResponse(
                    success=True,
                    data=stats,
                    request_id=str(uuid.uuid4())
                )
            except Exception as e:
                logger.error(f"WebSocket stats failed: {e}")
                return APIResponse(
                    success=False,
                    error="Failed to get WebSocket stats",
                    error_code="WEBSOCKET_STATS_FAILED",
                    request_id=str(uuid.uuid4())
                )

    # Legacy compatibility routes (for gradual migration)
    @app.get("/api/health-report")
    async def legacy_health_report(dashboard_service: DashboardService = Depends(get_dashboard_service)):
        """Legacy health report endpoint for backward compatibility"""
        try:
            health = await dashboard_service.get_system_status()
            # Transform to legacy format
            legacy_response = {
                "status": "healthy" if health.overall_healthy else "unhealthy",
                "database_status": health.database_status,
                "response_time": health.response_time_ms,
                "uptime": health.uptime_seconds,
                "error_rate": health.error_rate
            }
            return JSONResponse(content=legacy_response)
        except Exception as e:
            logger.error(f"Legacy health report failed: {e}")
            return JSONResponse(
                content={"error": "Service temporarily unavailable"},
                status_code=503
            )

    @app.get("/api/telemetry-widgets")
    async def legacy_telemetry_widgets(dashboard_service: DashboardService = Depends(get_dashboard_service)):
        """Legacy telemetry widgets endpoint for backward compatibility"""
        try:
            # Get standard widget types
            widget_types = ["error_monitor", "cost_tracker", "model_efficiency", "timeout_risk"]
            widgets_data = await dashboard_service.get_multiple_widgets(widget_types)

            # Transform to legacy format
            legacy_widgets = {}
            for widget_type, widget_data in widgets_data.items():
                legacy_widgets[widget_type] = {
                    "status": widget_data.status,
                    "data": widget_data.data,
                    "last_updated": widget_data.last_updated.isoformat()
                }

            return JSONResponse(content=legacy_widgets)
        except Exception as e:
            logger.error(f"Legacy telemetry widgets failed: {e}")
            return JSONResponse(
                content={"error": "Telemetry not available"},
                status_code=404
            )

    return app

# Factory function for different environments
def create_production_app() -> FastAPI:
    """Create production-ready app instance"""
    return create_app(
        clickhouse_host="clickhouse-otel",  # Docker container name
        redis_url="redis://redis:6379",
        enable_websockets=True,
        debug=False
    )

def create_development_app() -> FastAPI:
    """Create development app instance"""
    return create_app(
        clickhouse_host="localhost",
        redis_url="redis://localhost:6379",
        enable_websockets=True,
        debug=True
    )

def create_testing_app() -> FastAPI:
    """Create testing app instance with in-memory cache"""
    return create_app(
        clickhouse_host="localhost",
        redis_url="redis://localhost:6379",  # Will fallback to in-memory if not available
        enable_websockets=False,  # Disable WebSockets for testing
        debug=True
    )