"""
FastAPI Application Factory

Creates the modern API application with proper dependency injection,
middleware, WebSocket support, and integration with existing systems.
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import List, Optional, Dict, Any
import logging
import asyncio
import uuid
import traceback
from datetime import datetime

from .models import (
    APIResponse, PaginatedResponse, WidgetRequest, MetricsRequest,
    CacheInvalidationRequest, DashboardOverviewResponse, WidgetListResponse,
    ErrorDetails, ValidationErrorResponse, ValidationErrorDetail
)
from .services import DashboardService, TelemetryService
from .repositories import ClickHouseTelemetryRepository
from .cache import MultiLevelCache, InMemoryCache
from .cache_manager import AdvancedCacheManager
from .response_optimization import (
    CompressionMiddleware, OptimizedJSONResponse, ResponseStreamFactory,
    create_optimized_response, performance_metrics
)
from .websocket import ConnectionManager, EventBus, HeartbeatManager
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from context_cleaner.telemetry.context_rot.config import ApplicationConfig, ConfigManager
from context_cleaner.optimization.memory_profiler import memory_profiler, memory_health_check
from context_cleaner.optimization.efficient_structures import object_manager, efficient_structures_health_check
from context_cleaner.optimization.streaming_processor import streaming_health_check, gc_optimizer
from context_cleaner.optimization.dashboard_rendering import (
    lazy_loading_manager, websocket_streaming_manager, ui_responsiveness_optimizer,
    dashboard_rendering_health_check
)
from context_cleaner.optimization.task_processing import (
    AdvancedTaskProcessor, TaskPriority, task_processor_decorator
)
from context_cleaner.optimization.distributed_execution import (
    DistributedTaskCoordinator, NodeStatus
)
from context_cleaner.optimization.task_scheduler import (
    AdvancedTaskScheduler, ScheduleType, RetryStrategy, ScheduleConfig, RetryConfig,
    TaskLifecycleState
)

logger = logging.getLogger(__name__)

def create_app(
    config: Optional[ApplicationConfig] = None
) -> FastAPI:
    """
    Create and configure the FastAPI application

    Args:
        config: Application configuration. If None, loads default configuration.

    Returns:
        Configured FastAPI application
    """
    # Initialize configuration if not provided
    if config is None:
        config_manager = ConfigManager()
        config = config_manager.get_config()

    app = FastAPI(
        title=config.api.title,
        description="Modern API for Context Cleaner Dashboard with real-time capabilities",
        version=config.api.version,
        debug=config.enable_debug_mode
    )

    # Compression middleware (add before CORS)
    app.add_middleware(
        CompressionMiddleware,
        minimum_size=500,
        compression_level=6,
        exclude_paths=["/ws/", "/metrics"],  # Exclude WebSocket and metrics endpoints
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Global exception handlers for unified error responses
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTPException and convert to APIResponse format"""
        request_id = str(uuid.uuid4())

        # If the detail is already a structured error (from create_error_response)
        if isinstance(exc.detail, dict):
            return JSONResponse(
                status_code=exc.status_code,
                content=APIResponse(
                    success=False,
                    error=exc.detail.get("message", "HTTP Error"),
                    error_code=exc.detail.get("code", "HTTP_ERROR"),
                    metadata={
                        "status_code": exc.status_code,
                        "endpoint": str(request.url),
                        "method": request.method
                    },
                    request_id=request_id
                ).model_dump()
            )

        # Handle simple string detail
        return JSONResponse(
            status_code=exc.status_code,
            content=APIResponse(
                success=False,
                error=exc.detail,
                error_code="HTTP_ERROR",
                metadata={
                    "status_code": exc.status_code,
                    "endpoint": str(request.url),
                    "method": request.method
                },
                request_id=request_id
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors with detailed field information"""
        request_id = str(uuid.uuid4())

        validation_details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"][1:])  # Skip 'body'
            validation_details.append(ValidationErrorDetail(
                field=field,
                message=error["msg"],
                value=error.get("input")
            ))

        return JSONResponse(
            status_code=422,
            content=APIResponse(
                success=False,
                error="Request validation failed",
                error_code="VALIDATION_ERROR",
                data=ValidationErrorResponse(details=validation_details).model_dump(),
                metadata={
                    "endpoint": str(request.url),
                    "method": request.method,
                    "validation_errors": len(validation_details)
                },
                request_id=request_id
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions with consistent format"""
        request_id = str(uuid.uuid4())

        # Log the full exception for debugging
        error_traceback = traceback.format_exc()
        logger.error(f"Unhandled exception in {request.method} {request.url}: {exc}")
        logger.error(f"Traceback: {error_traceback}")

        # Don't expose internal error details in production
        if debug:
            error_message = str(exc)
            metadata = {
                "exception_type": type(exc).__name__,
                "traceback": error_traceback.split('\n')[-10:]  # Last 10 lines
            }
        else:
            error_message = "Internal server error"
            metadata = {"exception_type": type(exc).__name__}

        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error=error_message,
                error_code="INTERNAL_SERVER_ERROR",
                metadata={
                    **metadata,
                    "endpoint": str(request.url),
                    "method": request.method
                },
                request_id=request_id
            ).model_dump()
        )

    # Global state - will be initialized in startup event
    app.state.clickhouse_client = None
    app.state.cache_service = None
    app.state.advanced_cache_manager = None
    app.state.dashboard_service = None
    app.state.telemetry_service = None
    app.state.connection_manager = None
    app.state.event_bus = None
    app.state.heartbeat_manager = None

    # Phase 4.5: Background Task Optimization components
    app.state.task_processor = None
    app.state.task_scheduler = None
    app.state.distributed_coordinator = None

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup"""
        try:
            logger.info("Starting Context Cleaner API...")

            # Initialize ClickHouse client
            app.state.clickhouse_client = ClickHouseClient(
                host=config.database.clickhouse_host,
                port=config.database.clickhouse_port,
                database="otel"
            )
            await app.state.clickhouse_client.initialize()

            # Initialize cache service
            try:
                app.state.cache_service = MultiLevelCache(redis_url=config.api.redis_url)
            except Exception as e:
                logger.warning(f"Redis not available, falling back to in-memory cache: {e}")
                app.state.cache_service = InMemoryCache()

            # Initialize advanced cache manager
            app.state.advanced_cache_manager = AdvancedCacheManager(app.state.cache_service)

            # Start memory profiling for production monitoring
            if config.enable_debug_mode:
                memory_profiler.start_monitoring()
                logger.info("Memory profiling enabled for debug mode")

            # Initialize repository
            telemetry_repo = ClickHouseTelemetryRepository(app.state.clickhouse_client)

            # Initialize WebSocket components
            if config.api.enable_websockets:
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

            # Initialize Phase 4.5: Background Task Optimization components
            if config.enable_debug_mode:
                logger.info("Initializing Phase 4.5 optimization components...")

                # Initialize advanced task processor
                app.state.task_processor = AdvancedTaskProcessor(
                    max_concurrent_tasks=50,
                    enable_resource_monitoring=True
                )
                await app.state.task_processor.start_processing()

                # Initialize task scheduler
                app.state.task_scheduler = AdvancedTaskScheduler(
                    task_processor=app.state.task_processor,
                    max_concurrent_scheduled=100
                )
                await app.state.task_scheduler.start()

                # Initialize distributed coordinator (as single node for now)
                app.state.distributed_coordinator = DistributedTaskCoordinator(
                    node_id=f"context-cleaner-{uuid.uuid4().hex[:8]}",
                    host="localhost",
                    port=8765,
                    is_master=True
                )
                await app.state.distributed_coordinator.start()

                logger.info("Phase 4.5 optimization components initialized successfully")

            logger.info("Context Cleaner API started successfully")

        except Exception as e:
            logger.error(f"Error during startup: {e}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean shutdown of services"""
        try:
            logger.info("Shutting down Context Cleaner API...")

            # Stop memory profiling
            memory_profiler.stop_monitoring()

            # Restore GC thresholds
            gc_optimizer.restore_original_thresholds()

            # Clean up object pools
            cleanup_stats = object_manager.force_cleanup()
            logger.info(f"Object pool cleanup: {cleanup_stats}")

            # Shutdown Phase 4.5 components
            if app.state.distributed_coordinator:
                await app.state.distributed_coordinator.stop()
                logger.info("Distributed coordinator stopped")

            if app.state.task_scheduler:
                await app.state.task_scheduler.stop()
                logger.info("Task scheduler stopped")

            if app.state.task_processor:
                await app.state.task_processor.stop_processing()
                app.state.task_processor.shutdown()
                logger.info("Task processor stopped")

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

    def get_task_processor() -> AdvancedTaskProcessor:
        """Get task processor instance"""
        if not app.state.task_processor:
            raise HTTPException(status_code=503, detail="Task processor not available")
        return app.state.task_processor

    def get_task_scheduler() -> AdvancedTaskScheduler:
        """Get task scheduler instance"""
        if not app.state.task_scheduler:
            raise HTTPException(status_code=503, detail="Task scheduler not available")
        return app.state.task_scheduler

    def get_distributed_coordinator() -> DistributedTaskCoordinator:
        """Get distributed coordinator instance"""
        if not app.state.distributed_coordinator:
            raise HTTPException(status_code=503, detail="Distributed coordinator not available")
        return app.state.distributed_coordinator

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
    if config.api.enable_websockets:
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
            # Transform to legacy format but use APIResponse structure
            legacy_response = {
                "status": "healthy" if health.overall_healthy else "unhealthy",
                "database_status": health.database_status,
                "response_time": health.response_time_ms,
                "uptime": health.uptime_seconds,
                "error_rate": health.error_rate
            }

            return APIResponse(
                success=True,
                data=legacy_response,
                metadata={"endpoint": "legacy_health_report", "version": "legacy"},
                request_id=str(uuid.uuid4())
            ).model_dump()
        except Exception as e:
            logger.error(f"Legacy health report failed: {e}")
            # Exception will be caught by global handler, but let's be explicit
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable"
            )

    @app.get("/api/telemetry-widgets")
    async def legacy_telemetry_widgets(dashboard_service: DashboardService = Depends(get_dashboard_service)):
        """Legacy telemetry widgets endpoint for backward compatibility"""
        try:
            # Get standard widget types
            widget_types = ["error_monitor", "cost_tracker", "model_efficiency", "timeout_risk"]
            widgets_data = await dashboard_service.get_multiple_widgets(widget_types)

            # Transform to legacy format but use APIResponse structure
            legacy_widgets = {}
            for widget_type, widget_data in widgets_data.items():
                legacy_widgets[widget_type] = {
                    "status": widget_data.status,
                    "data": widget_data.data,
                    "last_updated": widget_data.last_updated.isoformat()
                }

            return APIResponse(
                success=True,
                data=legacy_widgets,
                metadata={
                    "endpoint": "legacy_telemetry_widgets",
                    "version": "legacy",
                    "widget_count": len(legacy_widgets)
                },
                request_id=str(uuid.uuid4())
            ).model_dump()
        except Exception as e:
            logger.error(f"Legacy telemetry widgets failed: {e}")
            # Exception will be caught by global handler, but let's be explicit
            raise HTTPException(
                status_code=404,
                detail="Telemetry not available"
            )

    # Performance monitoring endpoint
    @app.get("/api/v1/performance/stats")
    async def get_performance_stats():
        """Get comprehensive performance statistics"""
        try:
            stats = {
                'cache_manager_stats': await app.state.advanced_cache_manager.get_performance_stats(),
                'response_optimization_stats': performance_metrics.get_stats(),
                'timestamp': datetime.now().isoformat()
            }

            return create_optimized_response(stats)

        except Exception as e:
            logger.error(f"Performance stats failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Streaming endpoint for large datasets
    @app.get("/api/v1/telemetry/sessions/stream")
    async def stream_sessions(
        limit: int = Query(1000, ge=1, le=10000, description="Maximum number of sessions"),
        format: str = Query("json", regex="^(json|csv)$", description="Response format"),
        telemetry_service: TelemetryService = Depends(get_telemetry_service)
    ):
        """Stream large session datasets"""
        try:
            # Create async generator for session data
            async def session_generator():
                # This would need to be implemented in the service layer
                # For now, simulate with batch processing
                batch_size = 100
                for offset in range(0, limit, batch_size):
                    batch_limit = min(batch_size, limit - offset)
                    batch_sessions = await telemetry_service.get_active_sessions(limit=batch_limit)

                    for session in batch_sessions:
                        yield session

            # Return appropriate streaming response
            if format == "csv":
                return ResponseStreamFactory.create_csv_stream(
                    session_generator(),
                    filename=f"sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )
            else:
                return ResponseStreamFactory.create_json_stream(
                    session_generator(),
                    chunk_size=50,
                    filename=f"sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

        except Exception as e:
            logger.error(f"Session streaming failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Cache warmup endpoint
    @app.post("/api/v1/cache/warmup")
    async def warmup_cache():
        """Warm up cache with essential data"""
        try:
            warm_configs = [
                {
                    'endpoint': 'dashboard_overview',
                    'data_fetcher': lambda: app.state.dashboard_service.get_dashboard_overview()
                },
                {
                    'endpoint': 'system_health',
                    'data_fetcher': lambda: app.state.dashboard_service.get_system_status()
                }
            ]

            results = await app.state.advanced_cache_manager.warm_cache(warm_configs)

            return create_optimized_response({
                'success': True,
                'warmup_results': results,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Cache warmup failed: {e}")
            return create_optimized_response({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Cache invalidation by dependency
    @app.post("/api/v1/cache/invalidate/dependency")
    async def invalidate_cache_dependency(
        resource_type: str = Query(..., description="Resource type to invalidate"),
        resource_id: str = Query("global", description="Resource ID to invalidate")
    ):
        """Invalidate cache by dependency"""
        try:
            count = await app.state.advanced_cache_manager.invalidate_by_dependency(
                resource_type, resource_id
            )

            return create_optimized_response({
                'success': True,
                'invalidated_count': count,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Cache dependency invalidation failed: {e}")
            return create_optimized_response({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Memory monitoring endpoints
    @app.get("/api/v1/memory/status")
    async def get_memory_status():
        """Get comprehensive memory status"""
        try:
            stats = {
                'memory_profiler': await memory_health_check(),
                'efficient_structures': await efficient_structures_health_check(),
                'streaming_processor': await streaming_health_check(),
                'object_pools': object_manager.get_comprehensive_stats(),
                'gc_optimizer': gc_optimizer.get_gc_stats(),
                'timestamp': datetime.now().isoformat()
            }

            return create_optimized_response(stats)

        except Exception as e:
            logger.error(f"Memory status check failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/memory/profile")
    async def get_memory_profile():
        """Get detailed memory profiling data"""
        try:
            summary = memory_profiler.get_memory_summary()
            top_consumers = memory_profiler.get_top_memory_consumers(20)

            return create_optimized_response({
                'memory_summary': summary,
                'top_consumers': top_consumers,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Memory profile failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/memory/gc/force")
    async def force_garbage_collection():
        """Force garbage collection and cleanup"""
        try:
            gc_stats = memory_profiler.force_gc_and_measure()
            cleanup_stats = object_manager.force_cleanup()
            optimizer_stats = gc_optimizer.force_efficient_collection()

            return create_optimized_response({
                'gc_stats': gc_stats,
                'object_cleanup': cleanup_stats,
                'optimizer_collection': optimizer_stats,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Force GC failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/memory/export")
    async def export_memory_report(
        filepath: str = Query(..., description="Output file path for memory report")
    ):
        """Export comprehensive memory report"""
        try:
            memory_profiler.export_memory_report(filepath)

            return create_optimized_response({
                'success': True,
                'exported_to': filepath,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Memory report export failed: {e}")
            return create_optimized_response({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Dashboard Rendering Optimization endpoints
    @app.get("/api/v1/dashboard/rendering/status")
    async def get_dashboard_rendering_status():
        """Get comprehensive dashboard rendering optimization status"""
        try:
            stats = await dashboard_rendering_health_check()
            return create_optimized_response(stats)

        except Exception as e:
            logger.error(f"Dashboard rendering status check failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/dashboard/lazy-loading/stats")
    async def get_lazy_loading_stats():
        """Get lazy loading performance statistics"""
        try:
            stats = lazy_loading_manager.get_performance_stats()
            return create_optimized_response({
                'lazy_loading_stats': stats,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Lazy loading stats failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/dashboard/websocket/stats")
    async def get_websocket_streaming_stats():
        """Get WebSocket streaming performance statistics"""
        try:
            stats = websocket_streaming_manager.get_streaming_stats()
            return create_optimized_response({
                'websocket_streaming_stats': stats,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"WebSocket streaming stats failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/dashboard/ui-performance/stats")
    async def get_ui_performance_stats():
        """Get UI responsiveness optimization statistics"""
        try:
            stats = ui_responsiveness_optimizer.get_ui_performance_stats()
            return create_optimized_response({
                'ui_performance_stats': stats,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"UI performance stats failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # Phase 4.5: Background Task Optimization endpoints
    @app.get("/api/v1/tasks/processor/status")
    async def get_task_processor_status(
        task_processor: AdvancedTaskProcessor = Depends(get_task_processor)
    ):
        """Get comprehensive task processor status"""
        try:
            status = task_processor.get_status()
            return create_optimized_response({
                'task_processor_status': status,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task processor status check failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/tasks/submit")
    async def submit_task(
        name: str = Query(..., description="Task name"),
        priority: str = Query("NORMAL", description="Task priority (CRITICAL, HIGH, NORMAL, LOW, DEFERRED)"),
        timeout: Optional[float] = Query(None, description="Task timeout in seconds"),
        task_processor: AdvancedTaskProcessor = Depends(get_task_processor)
    ):
        """Submit a simple task for processing"""
        try:
            # Example task function
            def example_task():
                import time
                time.sleep(1)  # Simulate work
                return {"result": "Task completed successfully", "timestamp": datetime.now().isoformat()}

            task_priority = TaskPriority[priority.upper()]

            task_id = await task_processor.submit_task(
                name=name,
                func=example_task,
                priority=task_priority,
                timeout=timeout
            )

            return create_optimized_response({
                'task_id': task_id,
                'status': 'submitted',
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task submission failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/tasks/{task_id}/result")
    async def get_task_result(
        task_id: str = Path(..., description="Task ID"),
        task_processor: AdvancedTaskProcessor = Depends(get_task_processor)
    ):
        """Get result for a specific task"""
        try:
            result = task_processor.get_task_result(task_id)

            if result:
                return create_optimized_response({
                    'task_id': task_id,
                    'status': result.status.value,
                    'result': result.result,
                    'error': str(result.error) if result.error else None,
                    'execution_time': result.execution_time,
                    'memory_used': result.memory_used,
                    'retry_count': result.retry_count,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return create_optimized_response({
                    'task_id': task_id,
                    'status': 'not_found',
                    'timestamp': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Task result retrieval failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/tasks/scheduler/status")
    async def get_task_scheduler_status(
        task_scheduler: AdvancedTaskScheduler = Depends(get_task_scheduler)
    ):
        """Get comprehensive task scheduler status"""
        try:
            status = task_scheduler.get_scheduler_status()
            return create_optimized_response({
                'task_scheduler_status': status,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task scheduler status check failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/tasks/schedule")
    async def schedule_task(
        name: str = Query(..., description="Task name"),
        schedule_type: str = Query("IMMEDIATE", description="Schedule type (IMMEDIATE, DELAYED, PERIODIC, CRON)"),
        delay_seconds: Optional[float] = Query(None, description="Delay in seconds for DELAYED type"),
        interval_seconds: Optional[float] = Query(None, description="Interval in seconds for PERIODIC type"),
        cron_expression: Optional[str] = Query(None, description="Cron expression for CRON type"),
        priority: str = Query("NORMAL", description="Task priority"),
        max_retries: int = Query(3, description="Maximum retry attempts"),
        task_scheduler: AdvancedTaskScheduler = Depends(get_task_scheduler)
    ):
        """Schedule a task with advanced scheduling options"""
        try:
            # Example task function
            def example_scheduled_task():
                import time
                time.sleep(0.5)  # Simulate work
                return {"result": "Scheduled task completed", "timestamp": datetime.now().isoformat()}

            # Create schedule config
            schedule_config = ScheduleConfig(
                schedule_type=ScheduleType[schedule_type.upper()],
                delay_seconds=delay_seconds,
                interval_seconds=interval_seconds,
                cron_expression=cron_expression
            )

            # Create retry config
            retry_config = RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_attempts=max_retries,
                base_delay=1.0
            )

            task_id = await task_scheduler.schedule_task(
                name=name,
                func=example_scheduled_task,
                schedule_config=schedule_config,
                retry_config=retry_config,
                priority=TaskPriority[priority.upper()]
            )

            return create_optimized_response({
                'task_id': task_id,
                'status': 'scheduled',
                'schedule_type': schedule_type,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task scheduling failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/tasks/scheduler/{task_id}/status")
    async def get_scheduled_task_status(
        task_id: str = Path(..., description="Scheduled task ID"),
        task_scheduler: AdvancedTaskScheduler = Depends(get_task_scheduler)
    ):
        """Get status of a scheduled task"""
        try:
            status = task_scheduler.get_task_status(task_id)

            if status:
                return create_optimized_response({
                    'task_status': status,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return create_optimized_response({
                    'task_id': task_id,
                    'status': 'not_found',
                    'timestamp': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Scheduled task status retrieval failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/tasks/scheduler/{task_id}/cancel")
    async def cancel_scheduled_task(
        task_id: str = Path(..., description="Scheduled task ID"),
        task_scheduler: AdvancedTaskScheduler = Depends(get_task_scheduler)
    ):
        """Cancel a scheduled task"""
        try:
            success = task_scheduler.cancel_task(task_id)

            return create_optimized_response({
                'task_id': task_id,
                'cancelled': success,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task cancellation failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/tasks/distributed/cluster/status")
    async def get_cluster_status(
        coordinator: DistributedTaskCoordinator = Depends(get_distributed_coordinator)
    ):
        """Get comprehensive cluster status"""
        try:
            status = coordinator.get_cluster_status()
            return create_optimized_response({
                'cluster_status': status,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Cluster status check failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/tasks/distributed/submit")
    async def submit_distributed_task(
        name: str = Query(..., description="Task name"),
        priority: str = Query("NORMAL", description="Task priority"),
        timeout: Optional[float] = Query(None, description="Task timeout in seconds"),
        coordinator: DistributedTaskCoordinator = Depends(get_distributed_coordinator)
    ):
        """Submit a task for distributed execution"""
        try:
            # Example distributed task function
            def example_distributed_task():
                import time
                import random
                time.sleep(random.uniform(1, 3))  # Simulate variable work
                return {
                    "result": "Distributed task completed",
                    "node_id": coordinator.node_id,
                    "timestamp": datetime.now().isoformat()
                }

            task_id = await coordinator.submit_distributed_task(
                name=name,
                func=example_distributed_task,
                priority=TaskPriority[priority.upper()],
                timeout=timeout
            )

            return create_optimized_response({
                'task_id': task_id,
                'status': 'submitted_distributed',
                'master_node': coordinator.node_id,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Distributed task submission failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.get("/api/v1/tasks/distributed/{task_id}/result")
    async def get_distributed_task_result(
        task_id: str = Path(..., description="Distributed task ID"),
        timeout: Optional[float] = Query(10.0, description="Wait timeout in seconds"),
        coordinator: DistributedTaskCoordinator = Depends(get_distributed_coordinator)
    ):
        """Get result for a distributed task"""
        try:
            result = await coordinator.get_distributed_task_result(task_id, timeout=timeout)

            if result:
                return create_optimized_response({
                    'task_id': task_id,
                    'status': result.status.value,
                    'result': result.result,
                    'error': str(result.error) if result.error else None,
                    'execution_time': result.execution_time,
                    'memory_used': result.memory_used,
                    'retry_count': result.retry_count,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return create_optimized_response({
                    'task_id': task_id,
                    'status': 'timeout_or_not_found',
                    'timestamp': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Distributed task result retrieval failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    @app.post("/api/v1/tasks/scheduler/cleanup")
    async def cleanup_completed_tasks(
        older_than_hours: int = Query(24, description="Clean up tasks older than specified hours"),
        task_scheduler: AdvancedTaskScheduler = Depends(get_task_scheduler)
    ):
        """Clean up old completed tasks"""
        try:
            task_scheduler.cleanup_completed_tasks(older_than_hours=older_than_hours)

            return create_optimized_response({
                'cleanup_completed': True,
                'older_than_hours': older_than_hours,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Task cleanup failed: {e}")
            return create_optimized_response({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

    # WebSocket endpoint for dashboard streaming
    @app.websocket("/ws/dashboard")
    async def websocket_dashboard_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time dashboard updates"""
        connection_id = None
        try:
            # Accept connection
            connection_id = await websocket_streaming_manager.connect(websocket)

            # Subscribe to default channels
            await websocket_streaming_manager.subscribe(connection_id, [
                'performance', 'components', 'system_health'
            ])

            # Handle incoming messages
            while True:
                try:
                    message = await websocket.receive_text()
                    data = json.loads(message)

                    # Handle subscription changes
                    if data.get('type') == 'subscribe':
                        channels = data.get('channels', [])
                        await websocket_streaming_manager.subscribe(connection_id, channels)

                    elif data.get('type') == 'unsubscribe':
                        channels = data.get('channels', [])
                        await websocket_streaming_manager.unsubscribe(connection_id, channels)

                    elif data.get('type') == 'ping':
                        # Respond to ping with pong including timestamp
                        await websocket_streaming_manager.send_to_connection(
                            connection_id,
                            {'type': 'pong', 'timestamp': data.get('timestamp')},
                            batch=False
                        )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"WebSocket message handling error: {e}")
                    break

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            if connection_id:
                await websocket_streaming_manager.disconnect(connection_id)

    return app


# Global dependency injection functions for testing
_dashboard_service_instance = None
_telemetry_service_instance = None

def get_dashboard_service() -> DashboardService:
    """Global dependency function for dashboard service (testing support)"""
    global _dashboard_service_instance
    if _dashboard_service_instance is None:
        raise HTTPException(status_code=503, detail="Dashboard service not available")
    return _dashboard_service_instance

def get_telemetry_service() -> TelemetryService:
    """Global dependency function for telemetry service (testing support)"""
    global _telemetry_service_instance
    if _telemetry_service_instance is None:
        raise HTTPException(status_code=503, detail="Telemetry service not available")
    return _telemetry_service_instance

def set_test_services(dashboard_service: DashboardService, telemetry_service: TelemetryService):
    """Set service instances for testing"""
    global _dashboard_service_instance, _telemetry_service_instance
    _dashboard_service_instance = dashboard_service
    _telemetry_service_instance = telemetry_service


# Factory function for different environments
def create_production_app() -> FastAPI:
    """Create production-ready app instance"""
    config_manager = ConfigManager()
    config = config_manager.get_config()
    # Override for production environment
    config.database.clickhouse_host = "clickhouse-otel"  # Docker container name
    config.api.redis_url = "redis://redis:6379"
    config.api.enable_websockets = True
    config.enable_debug_mode = False
    return create_app(config)

def create_development_app() -> FastAPI:
    """Create development app instance"""
    config_manager = ConfigManager()
    config = config_manager.get_config()
    # Override for development environment
    config.database.clickhouse_host = "localhost"
    config.api.redis_url = "redis://localhost:6379"
    config.api.enable_websockets = True
    config.enable_debug_mode = True
    return create_app(config)

def create_testing_app() -> FastAPI:
    """Create testing app instance with minimal real dependencies"""
    config_manager = ConfigManager()
    config = config_manager.get_config()
    # Override for testing environment
    config.database.clickhouse_host = "localhost"
    config.api.redis_url = "redis://localhost:6379"  # Will fallback to in-memory if not available
    config.api.enable_websockets = False  # Disable WebSockets for testing
    config.enable_debug_mode = True
    return create_app(config)