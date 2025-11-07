"""
Dashboard Rendering Optimization System - Phase 4.4

Implements lazy loading, WebSocket streaming, and UI responsiveness optimizations
for high-performance dashboard rendering with thousands of widgets and real-time data.
"""

import asyncio
import json
import logging
import time
import weakref
from typing import Dict, List, Any, Optional, Callable, Set, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import uuid

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class ComponentPriority(Enum):
    """Component loading priority levels"""

    CRITICAL = 1  # Above-the-fold, immediately visible
    HIGH = 2  # Important widgets, visible on scroll
    NORMAL = 3  # Standard widgets, load as needed
    LOW = 4  # Background widgets, lazy load
    DEFERRED = 5  # Load only when explicitly requested


@dataclass
class LazyLoadConfig:
    """Configuration for lazy loading behavior"""

    viewport_buffer: int = 200  # Pixels before/after viewport to trigger loading
    batch_size: int = 5  # Number of components to load simultaneously
    priority_boost_timeout: int = 2  # Seconds to boost priority for visible items
    intersection_threshold: float = 0.1  # Visibility percentage to trigger loading
    preload_critical: bool = True  # Always preload critical components
    enable_predictive_loading: bool = True  # Predict user scrolling behavior


@dataclass
class ComponentState:
    """State tracking for dashboard components"""

    component_id: str
    priority: ComponentPriority = ComponentPriority.NORMAL
    is_loaded: bool = False
    is_visible: bool = False
    is_loading: bool = False
    last_rendered: Optional[datetime] = None
    render_count: int = 0
    error_count: int = 0
    load_time_ms: float = 0.0
    data_size_bytes: int = 0
    update_frequency: int = 30  # Seconds between updates
    dependencies: Set[str] = field(default_factory=set)
    subscribers: Set[str] = field(default_factory=set)


class LazyLoadingManager:
    """Advanced lazy loading manager with intersection observation and priority queuing"""

    def __init__(self, config: LazyLoadConfig = None):
        self.config = config or LazyLoadConfig()
        self.components: Dict[str, ComponentState] = {}
        self.loading_queue = {priority: deque() for priority in ComponentPriority}
        self.active_loaders = 0
        self.max_concurrent_loaders = 3

        # Performance tracking
        self.load_stats = {
            "total_loads": 0,
            "successful_loads": 0,
            "failed_loads": 0,
            "average_load_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Viewport tracking
        self.viewport_components: Set[str] = set()
        self.scroll_velocity = 0.0
        self.scroll_direction = "down"
        self.last_scroll_time = time.time()

        # Component cache for rendered content
        self.render_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry: Dict[str, datetime] = {}

        logger.info("LazyLoadingManager initialized with advanced optimization")

    def register_component(
        self,
        component_id: str,
        priority: ComponentPriority = ComponentPriority.NORMAL,
        dependencies: Set[str] = None,
        update_frequency: int = 30,
    ) -> None:
        """Register a component for lazy loading management"""

        self.components[component_id] = ComponentState(
            component_id=component_id,
            priority=priority,
            dependencies=dependencies or set(),
            update_frequency=update_frequency,
        )

        # Preload critical components
        if priority == ComponentPriority.CRITICAL and self.config.preload_critical:
            self.queue_component_load(component_id, force=True)

        logger.debug(f"Registered component {component_id} with priority {priority}")

    def queue_component_load(self, component_id: str, force: bool = False) -> None:
        """Queue a component for loading with priority handling"""

        if component_id not in self.components:
            logger.warning(f"Component {component_id} not registered")
            return

        component = self.components[component_id]

        # Skip if already loaded or loading (unless forced)
        if not force and (component.is_loaded or component.is_loading):
            return

        # Add to priority queue
        priority = component.priority
        if component_id not in self.loading_queue[priority]:
            self.loading_queue[priority].append(component_id)

        # Start processing if under limit
        if self.active_loaders < self.max_concurrent_loaders:
            asyncio.create_task(self._process_loading_queue())

    async def _process_loading_queue(self) -> None:
        """Process the loading queue with priority ordering"""

        if self.active_loaders >= self.max_concurrent_loaders:
            return

        self.active_loaders += 1

        try:
            # Process by priority (CRITICAL first, DEFERRED last)
            for priority in ComponentPriority:
                if self.loading_queue[priority]:
                    component_id = self.loading_queue[priority].popleft()
                    await self._load_component(component_id)
                    break
        finally:
            self.active_loaders -= 1

            # Continue processing if queue has items
            if any(queue for queue in self.loading_queue.values()):
                asyncio.create_task(self._process_loading_queue())

    async def _load_component(self, component_id: str) -> bool:
        """Load a single component with performance tracking"""

        component = self.components.get(component_id)
        if not component:
            return False

        component.is_loading = True
        start_time = time.time()

        try:
            # Check cache first
            if self._is_cache_valid(component_id):
                self.load_stats["cache_hits"] += 1
                component.is_loaded = True
                component.last_rendered = datetime.now()
                logger.debug(f"Component {component_id} loaded from cache")
                return True

            self.load_stats["cache_misses"] += 1

            # Load dependencies first
            for dep_id in component.dependencies:
                if dep_id in self.components and not self.components[dep_id].is_loaded:
                    await self._load_component(dep_id)

            # Simulate component loading (replace with actual implementation)
            await asyncio.sleep(0.1)  # Simulated async load

            # Update component state
            load_time = (time.time() - start_time) * 1000
            component.load_time_ms = load_time
            component.is_loaded = True
            component.is_loading = False
            component.render_count += 1
            component.last_rendered = datetime.now()

            # Update stats
            self.load_stats["total_loads"] += 1
            self.load_stats["successful_loads"] += 1
            self._update_average_load_time(load_time)

            logger.debug(f"Component {component_id} loaded in {load_time:.2f}ms")
            return True

        except Exception as e:
            component.error_count += 1
            component.is_loading = False
            self.load_stats["failed_loads"] += 1
            logger.error(f"Failed to load component {component_id}: {e}")
            return False

    def update_viewport(
        self, visible_components: Set[str], scroll_info: Dict[str, Any]
    ) -> None:
        """Update viewport information and trigger appropriate loading"""

        # Update scroll tracking
        current_time = time.time()
        time_delta = current_time - self.last_scroll_time

        if time_delta > 0:
            scroll_delta = scroll_info.get("scroll_y", 0) - getattr(
                self, "_last_scroll_y", 0
            )
            self.scroll_velocity = abs(scroll_delta) / time_delta
            self.scroll_direction = "down" if scroll_delta > 0 else "up"
            self._last_scroll_y = scroll_info.get("scroll_y", 0)

        self.last_scroll_time = current_time

        # Update visible components
        newly_visible = visible_components - self.viewport_components
        newly_hidden = self.viewport_components - visible_components

        self.viewport_components = visible_components

        # Mark components as visible/hidden
        for component_id in newly_visible:
            if component_id in self.components:
                self.components[component_id].is_visible = True
                # Boost priority for visible components
                self._boost_component_priority(component_id)

        for component_id in newly_hidden:
            if component_id in self.components:
                self.components[component_id].is_visible = False

        # Predictive loading based on scroll velocity
        if self.config.enable_predictive_loading and self.scroll_velocity > 100:
            self._predict_and_preload(scroll_info)

    def _boost_component_priority(self, component_id: str) -> None:
        """Temporarily boost component priority when it becomes visible"""

        component = self.components.get(component_id)
        if not component or component.is_loaded:
            return

        # Boost priority if not already critical
        if component.priority != ComponentPriority.CRITICAL:
            original_priority = component.priority
            component.priority = ComponentPriority.HIGH

            # Queue for immediate loading
            self.queue_component_load(component_id)

            # Reset priority after timeout
            async def reset_priority():
                await asyncio.sleep(self.config.priority_boost_timeout)
                if component_id in self.components:
                    self.components[component_id].priority = original_priority

            asyncio.create_task(reset_priority())

    def _predict_and_preload(self, scroll_info: Dict[str, Any]) -> None:
        """Predict user scrolling behavior and preload components"""

        # Calculate predicted viewport based on scroll velocity and direction
        viewport_height = scroll_info.get("viewport_height", 800)
        scroll_y = scroll_info.get("scroll_y", 0)

        # Predict where user will be in next 2 seconds
        predicted_scroll = scroll_y + (
            self.scroll_velocity * 2 * (1 if self.scroll_direction == "down" else -1)
        )
        predicted_viewport_start = max(
            0, predicted_scroll - self.config.viewport_buffer
        )
        predicted_viewport_end = (
            predicted_scroll + viewport_height + self.config.viewport_buffer
        )

        # Find components in predicted viewport
        for component_id, component in self.components.items():
            if not component.is_loaded and self._is_in_predicted_viewport(
                component_id, predicted_viewport_start, predicted_viewport_end
            ):
                self.queue_component_load(component_id)

    def _is_in_predicted_viewport(
        self, component_id: str, start: float, end: float
    ) -> bool:
        """Check if component is in predicted viewport (placeholder implementation)"""
        # This would integrate with actual DOM position tracking
        return True  # Simplified for now

    def _is_cache_valid(self, component_id: str) -> bool:
        """Check if cached component data is still valid"""

        if component_id not in self.render_cache:
            return False

        expiry = self.cache_expiry.get(component_id)
        if not expiry or datetime.now() > expiry:
            # Remove expired cache
            self.render_cache.pop(component_id, None)
            self.cache_expiry.pop(component_id, None)
            return False

        return True

    def cache_component(
        self, component_id: str, data: Dict[str, Any], ttl_seconds: int = 300
    ) -> None:
        """Cache component data with TTL"""

        self.render_cache[component_id] = data
        self.cache_expiry[component_id] = datetime.now() + timedelta(
            seconds=ttl_seconds
        )

        component = self.components.get(component_id)
        if component:
            component.data_size_bytes = len(json.dumps(data))

    def _update_average_load_time(self, load_time: float) -> None:
        """Update rolling average load time"""

        current_avg = self.load_stats["average_load_time_ms"]
        total_loads = self.load_stats["successful_loads"]

        if total_loads == 1:
            self.load_stats["average_load_time_ms"] = load_time
        else:
            # Rolling average
            self.load_stats["average_load_time_ms"] = (
                current_avg * (total_loads - 1) + load_time
            ) / total_loads

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""

        component_stats = {
            "total_components": len(self.components),
            "loaded_components": sum(
                1 for c in self.components.values() if c.is_loaded
            ),
            "visible_components": len(self.viewport_components),
            "loading_components": sum(
                1 for c in self.components.values() if c.is_loading
            ),
            "error_components": sum(
                1 for c in self.components.values() if c.error_count > 0
            ),
        }

        return {
            "lazy_loading_stats": self.load_stats,
            "component_stats": component_stats,
            "queue_stats": {
                priority.name: len(queue)
                for priority, queue in self.loading_queue.items()
            },
            "performance_metrics": {
                "active_loaders": self.active_loaders,
                "scroll_velocity": self.scroll_velocity,
                "scroll_direction": self.scroll_direction,
                "cache_size": len(self.render_cache),
            },
        }


class WebSocketStreamingManager:
    """High-performance WebSocket streaming for real-time dashboard updates"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(
            set
        )  # channel -> connection_ids
        self.connection_channels: Dict[str, Set[str]] = defaultdict(
            set
        )  # connection_id -> channels

        # Performance metrics
        self.message_stats = {
            "messages_sent": 0,
            "messages_failed": 0,
            "bytes_sent": 0,
            "connections_total": 0,
            "connections_active": 0,
        }

        # Message batching for performance
        self.message_batches: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}
        self.batch_size = 10
        self.batch_timeout = 0.1  # 100ms

        logger.info("WebSocketStreamingManager initialized")

    async def connect(self, websocket: WebSocket, connection_id: str = None) -> str:
        """Accept WebSocket connection and register it"""

        if not connection_id:
            connection_id = str(uuid.uuid4())

        await websocket.accept()

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.now(),
            "messages_sent": 0,
            "bytes_sent": 0,
            "last_activity": datetime.now(),
        }

        self.message_stats["connections_total"] += 1
        self.message_stats["connections_active"] = len(self.active_connections)

        logger.info(f"WebSocket connection established: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Clean up WebSocket connection"""

        # Remove from active connections
        self.active_connections.pop(connection_id, None)
        self.connection_metadata.pop(connection_id, None)

        # Clean up subscriptions
        channels = self.connection_channels.pop(connection_id, set())
        for channel in channels:
            self.subscriptions[channel].discard(connection_id)

        # Cancel any pending batch timers
        if connection_id in self.batch_timers:
            self.batch_timers[connection_id].cancel()
            del self.batch_timers[connection_id]

        self.message_stats["connections_active"] = len(self.active_connections)

        logger.info(f"WebSocket connection closed: {connection_id}")

    async def subscribe(self, connection_id: str, channels: List[str]) -> None:
        """Subscribe connection to specific channels"""

        if connection_id not in self.active_connections:
            logger.warning(f"Connection {connection_id} not found for subscription")
            return

        for channel in channels:
            self.subscriptions[channel].add(connection_id)
            self.connection_channels[connection_id].add(channel)

        logger.debug(f"Connection {connection_id} subscribed to channels: {channels}")

    async def unsubscribe(self, connection_id: str, channels: List[str]) -> None:
        """Unsubscribe connection from specific channels"""

        for channel in channels:
            self.subscriptions[channel].discard(connection_id)
            self.connection_channels[connection_id].discard(channel)

        logger.debug(
            f"Connection {connection_id} unsubscribed from channels: {channels}"
        )

    async def broadcast(
        self, channel: str, message: Dict[str, Any], batch: bool = True
    ) -> int:
        """Broadcast message to all subscribers of a channel"""

        if channel not in self.subscriptions:
            return 0

        connection_ids = list(self.subscriptions[channel])

        if batch:
            # Add to batch for efficient sending
            for conn_id in connection_ids:
                self._add_to_batch(conn_id, message)
        else:
            # Send immediately
            sent_count = 0
            for conn_id in connection_ids:
                if await self._send_message(conn_id, message):
                    sent_count += 1
            return sent_count

        return len(connection_ids)

    async def send_to_connection(
        self, connection_id: str, message: Dict[str, Any], batch: bool = True
    ) -> bool:
        """Send message to specific connection"""

        if batch:
            self._add_to_batch(connection_id, message)
            return True
        else:
            return await self._send_message(connection_id, message)

    def _add_to_batch(self, connection_id: str, message: Dict[str, Any]) -> None:
        """Add message to batch for efficient sending"""

        self.message_batches[connection_id].append(message)

        # Start batch timer if not already running
        if connection_id not in self.batch_timers:
            self.batch_timers[connection_id] = asyncio.create_task(
                self._flush_batch_after_timeout(connection_id)
            )

        # Flush batch if it reaches size limit
        if len(self.message_batches[connection_id]) >= self.batch_size:
            asyncio.create_task(self._flush_batch(connection_id))

    async def _flush_batch_after_timeout(self, connection_id: str) -> None:
        """Flush batch after timeout"""

        await asyncio.sleep(self.batch_timeout)
        await self._flush_batch(connection_id)

    async def _flush_batch(self, connection_id: str) -> None:
        """Flush accumulated messages for a connection"""

        if connection_id not in self.message_batches:
            return

        batch = self.message_batches[connection_id]
        if not batch:
            return

        # Clear batch and timer
        self.message_batches[connection_id] = []
        if connection_id in self.batch_timers:
            self.batch_timers[connection_id].cancel()
            del self.batch_timers[connection_id]

        # Send batched messages
        if len(batch) == 1:
            await self._send_message(connection_id, batch[0])
        else:
            batched_message = {
                "type": "batch",
                "messages": batch,
                "timestamp": datetime.now().isoformat(),
            }
            await self._send_message(connection_id, batched_message)

    async def _send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send single message to connection"""

        websocket = self.active_connections.get(connection_id)
        if not websocket:
            return False

        try:
            message_json = json.dumps(message)
            await websocket.send_text(message_json)

            # Update metrics
            self.message_stats["messages_sent"] += 1
            self.message_stats["bytes_sent"] += len(message_json)

            metadata = self.connection_metadata.get(connection_id)
            if metadata:
                metadata["messages_sent"] += 1
                metadata["bytes_sent"] += len(message_json)
                metadata["last_activity"] = datetime.now()

            return True

        except WebSocketDisconnect:
            logger.info(f"Connection {connection_id} disconnected during send")
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            self.message_stats["messages_failed"] += 1
            return False

    async def broadcast_performance_update(self, metrics: Dict[str, Any]) -> None:
        """Broadcast performance metrics to all performance channel subscribers"""

        message = {
            "type": "performance_update",
            "data": metrics,
            "timestamp": datetime.now().isoformat(),
        }

        await self.broadcast("performance", message)

    async def broadcast_component_update(
        self, component_id: str, data: Dict[str, Any]
    ) -> None:
        """Broadcast component update to relevant subscribers"""

        message = {
            "type": "component_update",
            "component_id": component_id,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

        await self.broadcast(f"component:{component_id}", message)
        await self.broadcast("components", message)

    def get_streaming_stats(self) -> Dict[str, Any]:
        """Get WebSocket streaming statistics"""

        return {
            "connection_stats": {
                "active_connections": len(self.active_connections),
                "total_connections": self.message_stats["connections_total"],
                "subscriptions_count": sum(
                    len(subs) for subs in self.subscriptions.values()
                ),
            },
            "message_stats": dict(self.message_stats),
            "batch_stats": {
                "pending_batches": len(self.message_batches),
                "batch_size_limit": self.batch_size,
                "batch_timeout_ms": self.batch_timeout * 1000,
            },
            "channel_stats": {
                "total_channels": len(self.subscriptions),
                "channels": [
                    {"name": channel, "subscribers": len(subs)}
                    for channel, subs in self.subscriptions.items()
                ],
            },
        }


class UIResponsivenessOptimizer:
    """Advanced UI responsiveness optimization with virtual scrolling and smart rendering"""

    def __init__(self):
        self.render_queue = deque()
        self.pending_updates = {}
        self.debounce_timers = {}
        self.virtual_scroll_configs = {}

        # Performance tracking
        self.ui_metrics = {
            "render_operations": 0,
            "skipped_renders": 0,
            "average_render_time_ms": 0.0,
            "fps_samples": deque(maxlen=60),
            "interaction_delays": deque(maxlen=100),
        }

        logger.info("UIResponsivenessOptimizer initialized")

    def debounce_update(
        self, component_id: str, update_func: Callable, delay_ms: int = 100
    ) -> None:
        """Debounce rapid updates to prevent UI thrashing"""

        # Cancel existing timer if any
        if component_id in self.debounce_timers:
            self.debounce_timers[component_id].cancel()

        # Create new timer
        async def delayed_update():
            await asyncio.sleep(delay_ms / 1000)
            try:
                await update_func()
                self.ui_metrics["render_operations"] += 1
            except Exception as e:
                logger.error(f"Error in debounced update for {component_id}: {e}")
            finally:
                self.debounce_timers.pop(component_id, None)

        self.debounce_timers[component_id] = asyncio.create_task(delayed_update())

    def setup_virtual_scrolling(
        self, container_id: str, config: Dict[str, Any]
    ) -> None:
        """Configure virtual scrolling for large lists"""

        self.virtual_scroll_configs[container_id] = {
            "item_height": config.get("item_height", 50),
            "buffer_size": config.get("buffer_size", 10),
            "total_items": config.get("total_items", 0),
            "viewport_height": config.get("viewport_height", 600),
            "render_batch_size": config.get("render_batch_size", 20),
        }

        logger.debug(f"Virtual scrolling configured for {container_id}")

    def calculate_virtual_viewport(
        self, container_id: str, scroll_top: int
    ) -> Dict[str, Any]:
        """Calculate which items should be rendered in virtual scrolling"""

        config = self.virtual_scroll_configs.get(container_id)
        if not config:
            return {"start_index": 0, "end_index": 0, "total_height": 0}

        item_height = config["item_height"]
        buffer_size = config["buffer_size"]
        viewport_height = config["viewport_height"]
        total_items = config["total_items"]

        # Calculate visible range
        start_index = max(0, (scroll_top // item_height) - buffer_size)
        visible_items = (viewport_height // item_height) + (2 * buffer_size)
        end_index = min(total_items, start_index + visible_items)

        return {
            "start_index": start_index,
            "end_index": end_index,
            "visible_count": end_index - start_index,
            "total_height": total_items * item_height,
            "offset_y": start_index * item_height,
        }

    async def queue_render_operation(
        self, operation: Callable, priority: int = 5
    ) -> None:
        """Queue render operation with priority"""

        self.render_queue.append(
            {"operation": operation, "priority": priority, "queued_at": time.time()}
        )

        # Process queue if not already processing
        if len(self.render_queue) == 1:
            asyncio.create_task(self._process_render_queue())

    async def _process_render_queue(self) -> None:
        """Process render operations in priority order"""

        while self.render_queue:
            # Sort by priority (lower number = higher priority)
            self.render_queue = deque(
                sorted(self.render_queue, key=lambda x: x["priority"])
            )

            operation_info = self.render_queue.popleft()
            operation = operation_info["operation"]

            start_time = time.time()

            try:
                await operation()

                # Track performance
                render_time = (time.time() - start_time) * 1000
                self._update_render_metrics(render_time)

            except Exception as e:
                logger.error(f"Error in render operation: {e}")
                self.ui_metrics["skipped_renders"] += 1

    def _update_render_metrics(self, render_time_ms: float) -> None:
        """Update UI performance metrics"""

        # Update average render time
        current_avg = self.ui_metrics["average_render_time_ms"]
        ops_count = self.ui_metrics["render_operations"]

        if ops_count == 1:
            self.ui_metrics["average_render_time_ms"] = render_time_ms
        else:
            self.ui_metrics["average_render_time_ms"] = (
                current_avg * (ops_count - 1) + render_time_ms
            ) / ops_count

        # Track FPS estimation
        current_time = time.time()
        self.ui_metrics["fps_samples"].append(current_time)

    def get_current_fps(self) -> float:
        """Calculate current FPS based on recent operations"""

        samples = self.ui_metrics["fps_samples"]
        if len(samples) < 2:
            return 0.0

        time_span = samples[-1] - samples[0]
        if time_span == 0:
            return 0.0

        return (len(samples) - 1) / time_span

    def get_ui_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive UI performance statistics"""

        return {
            "render_metrics": {
                "operations_completed": self.ui_metrics["render_operations"],
                "operations_skipped": self.ui_metrics["skipped_renders"],
                "average_render_time_ms": self.ui_metrics["average_render_time_ms"],
                "current_fps": self.get_current_fps(),
            },
            "queue_stats": {
                "pending_operations": len(self.render_queue),
                "debounced_updates": len(self.debounce_timers),
            },
            "virtual_scroll_stats": {
                "configured_containers": len(self.virtual_scroll_configs),
                "containers": list(self.virtual_scroll_configs.keys()),
            },
        }


# Global instances
lazy_loading_manager = LazyLoadingManager()
websocket_streaming_manager = WebSocketStreamingManager()
ui_responsiveness_optimizer = UIResponsivenessOptimizer()


async def dashboard_rendering_health_check() -> Dict[str, Any]:
    """Health check for dashboard rendering optimization system"""

    try:
        # Test lazy loading
        lazy_stats = lazy_loading_manager.get_performance_stats()

        # Test WebSocket streaming
        streaming_stats = websocket_streaming_manager.get_streaming_stats()

        # Test UI responsiveness
        ui_stats = ui_responsiveness_optimizer.get_ui_performance_stats()

        return {
            "dashboard_rendering_healthy": True,
            "lazy_loading_stats": lazy_stats,
            "streaming_stats": streaming_stats,
            "ui_performance_stats": ui_stats,
            "optimization_status": {
                "lazy_loading_active": len(lazy_loading_manager.components) > 0,
                "websocket_connections_active": len(
                    websocket_streaming_manager.active_connections
                )
                > 0,
                "ui_optimization_active": len(
                    ui_responsiveness_optimizer.virtual_scroll_configs
                )
                > 0,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Dashboard rendering health check failed: {e}")
        return {
            "dashboard_rendering_healthy": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
