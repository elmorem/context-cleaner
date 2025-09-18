"""
WebSocket and Event Bus Implementation

Provides real-time communication infrastructure for the dashboard
with connection management, event routing, and graceful fallback.
"""

import asyncio
import json
import logging
import weakref
from typing import Dict, Set, List, Any, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class EventBus:
    """Event bus for internal event handling and WebSocket broadcasting"""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.websocket_manager: Optional['ConnectionManager'] = None
        self._lock = asyncio.Lock()

    def set_websocket_manager(self, manager: 'ConnectionManager'):
        """Set the WebSocket manager for broadcasting"""
        self.websocket_manager = manager

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.debug(f"Handler subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from an event type"""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(handler)
                logger.debug(f"Handler unsubscribed from event: {event_type}")
            except ValueError:
                pass

    async def emit(self, event_type: str, data: Any):
        """Emit an event to all subscribers and WebSocket clients"""
        async with self._lock:
            # Handle internal subscribers
            if event_type in self.subscribers:
                for handler in self.subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event_type}: {e}")

            # Broadcast to WebSocket subscribers
            if self.websocket_manager:
                message = {
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }
                await self.websocket_manager.broadcast_to_topic(event_type, message)

    async def emit_to_client(self, client_id: str, event_type: str, data: Any):
        """Emit event to specific client"""
        if self.websocket_manager:
            message = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            await self.websocket_manager.send_to_client(client_id, message)

class ConnectionManager:
    """WebSocket connection manager with subscription handling"""

    def __init__(self):
        self.active_connections: Dict[str, 'WebSocket'] = {}
        self.client_subscriptions: Dict[str, Set[str]] = {}
        self.topic_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket, client_id: str):
        """Accept a new WebSocket connection"""
        try:
            await websocket.accept()
            async with self._lock:
                self.active_connections[client_id] = websocket
                self.client_subscriptions[client_id] = set()

            logger.info(f"WebSocket client connected: {client_id}")

            # Send welcome message
            welcome_msg = {
                "type": "connection.established",
                "data": {
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat(),
                    "available_topics": [
                        "dashboard.metrics.updated",
                        "widget.data.updated",
                        "system.health.changed",
                        "cost.threshold.exceeded"
                    ]
                },
                "timestamp": datetime.now().isoformat()
            }
            await self._send_message(websocket, welcome_msg)

        except Exception as e:
            logger.error(f"Error connecting client {client_id}: {e}")
            raise

    async def disconnect(self, client_id: str):
        """Handle client disconnection"""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]

            # Clean up subscriptions
            if client_id in self.client_subscriptions:
                for topic in self.client_subscriptions[client_id]:
                    if topic in self.topic_subscribers:
                        self.topic_subscribers[topic].discard(client_id)
                        if not self.topic_subscribers[topic]:
                            del self.topic_subscribers[topic]
                del self.client_subscriptions[client_id]

        logger.info(f"WebSocket client disconnected: {client_id}")

    async def subscribe(self, client_id: str, topic: str):
        """Subscribe client to a topic"""
        async with self._lock:
            if client_id not in self.client_subscriptions:
                logger.warning(f"Client {client_id} not found for subscription")
                return False

            self.client_subscriptions[client_id].add(topic)

            if topic not in self.topic_subscribers:
                self.topic_subscribers[topic] = set()
            self.topic_subscribers[topic].add(client_id)

        logger.debug(f"Client {client_id} subscribed to topic: {topic}")
        return True

    async def unsubscribe(self, client_id: str, topic: str):
        """Unsubscribe client from a topic"""
        async with self._lock:
            if client_id in self.client_subscriptions:
                self.client_subscriptions[client_id].discard(topic)

            if topic in self.topic_subscribers:
                self.topic_subscribers[topic].discard(client_id)
                if not self.topic_subscribers[topic]:
                    del self.topic_subscribers[topic]

        logger.debug(f"Client {client_id} unsubscribed from topic: {topic}")

    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any]):
        """Broadcast message to all subscribers of a topic"""
        if topic not in self.topic_subscribers:
            return

        subscribers = list(self.topic_subscribers[topic])  # Copy to avoid modification during iteration
        disconnected_clients = []

        for client_id in subscribers:
            if client_id in self.active_connections:
                try:
                    websocket = self.active_connections[client_id]
                    await self._send_message(websocket, message)
                except Exception as e:
                    logger.warning(f"Error sending to client {client_id}: {e}")
                    disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

        if subscribers:
            logger.debug(f"Broadcasted to {len(subscribers)} clients on topic: {topic}")

    async def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to specific client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await self._send_message(websocket, message)
                return True
            except Exception as e:
                logger.warning(f"Error sending to client {client_id}: {e}")
                await self.disconnect(client_id)
        return False

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        async with self._lock:
            return {
                "active_connections": len(self.active_connections),
                "total_subscriptions": sum(len(subs) for subs in self.client_subscriptions.values()),
                "topics_with_subscribers": len(self.topic_subscribers),
                "clients": list(self.active_connections.keys()),
                "topic_subscriber_counts": {
                    topic: len(subscribers) for topic, subscribers in self.topic_subscribers.items()
                }
            }

    async def handle_client_message(self, client_id: str, message: str) -> bool:
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "subscribe":
                topic = data.get("topic")
                if topic:
                    await self.subscribe(client_id, topic)
                    # Send acknowledgment
                    ack_msg = {
                        "type": "subscription.ack",
                        "data": {"topic": topic, "subscribed": True},
                        "timestamp": datetime.now().isoformat()
                    }
                    await self.send_to_client(client_id, ack_msg)
                    return True

            elif message_type == "unsubscribe":
                topic = data.get("topic")
                if topic:
                    await self.unsubscribe(client_id, topic)
                    # Send acknowledgment
                    ack_msg = {
                        "type": "unsubscription.ack",
                        "data": {"topic": topic, "subscribed": False},
                        "timestamp": datetime.now().isoformat()
                    }
                    await self.send_to_client(client_id, ack_msg)
                    return True

            elif message_type == "ping":
                # Respond to ping with pong
                pong_msg = {
                    "type": "pong",
                    "data": {"timestamp": datetime.now().isoformat()},
                    "timestamp": datetime.now().isoformat()
                }
                await self.send_to_client(client_id, pong_msg)
                return True

            else:
                logger.warning(f"Unknown message type from client {client_id}: {message_type}")
                return False

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}: {message}")
            return False
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            return False

    async def _send_message(self, websocket, message: Dict[str, Any]):
        """Send message to WebSocket connection"""
        try:
            message_str = json.dumps(message, default=self._json_serializer)
            await websocket.send_text(message_str)
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            raise

    def _json_serializer(self, obj):
        """Custom JSON serializer for WebSocket messages"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'dict'):  # Pydantic models
            return obj.dict()
        elif hasattr(obj, '__dict__'):  # Other objects
            return obj.__dict__
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

class HeartbeatManager:
    """Manages WebSocket connection heartbeats"""

    def __init__(self, connection_manager: ConnectionManager, interval: int = 30):
        self.connection_manager = connection_manager
        self.interval = interval
        self._heartbeat_task = None
        self._running = False

    async def start(self):
        """Start heartbeat task"""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Heartbeat manager started with {self.interval}s interval")

    async def stop(self):
        """Stop heartbeat task"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat manager stopped")

    async def _heartbeat_loop(self):
        """Main heartbeat loop"""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._send_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _send_heartbeats(self):
        """Send heartbeat to all connected clients"""
        stats = await self.connection_manager.get_connection_stats()
        if stats["active_connections"] > 0:
            heartbeat_msg = {
                "type": "heartbeat",
                "data": {
                    "server_time": datetime.now().isoformat(),
                    "active_connections": stats["active_connections"]
                },
                "timestamp": datetime.now().isoformat()
            }
            # Broadcast heartbeat as system message
            await self.connection_manager.broadcast_to_topic("system.heartbeat", heartbeat_msg)