"""
Distributed Task Execution System for Context Cleaner
Enables horizontal scaling and load distribution across multiple nodes
"""

import asyncio
import json
import logging
import pickle
import socket
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import websockets
from websockets.server import serve as ws_serve
from .task_processing import Task, TaskResult, TaskStatus, TaskPriority, AdvancedTaskProcessor


class NodeStatus(Enum):
    """Node status in the distributed system"""
    ACTIVE = "active"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class MessageType(Enum):
    """Message types for node communication"""
    HEARTBEAT = "heartbeat"
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    NODE_STATUS = "node_status"
    LOAD_BALANCE_REQUEST = "load_balance_request"
    CLUSTER_UPDATE = "cluster_update"
    SHUTDOWN = "shutdown"


@dataclass
class NodeInfo:
    """Information about a node in the distributed system"""
    node_id: str
    host: str
    port: int
    status: NodeStatus
    cpu_count: int
    memory_gb: float
    current_load: float = 0.0
    active_tasks: int = 0
    max_tasks: int = 50
    last_heartbeat: float = field(default_factory=time.time)
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['capabilities'] = list(data['capabilities'])  # Convert set to list
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeInfo':
        """Create from dictionary"""
        data['capabilities'] = set(data['capabilities'])  # Convert list to set
        data['status'] = NodeStatus(data['status'])
        return cls(**data)


@dataclass
class ClusterMessage:
    """Message for inter-node communication"""
    message_id: str
    sender_id: str
    recipient_id: Optional[str]  # None for broadcast
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize to JSON"""
        data = asdict(self)
        data['message_type'] = data['message_type'].value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'ClusterMessage':
        """Deserialize from JSON"""
        data = json.loads(json_str)
        data['message_type'] = MessageType(data['message_type'])
        return cls(**data)


class LoadBalancer:
    """Intelligent load balancer for distributing tasks across nodes"""

    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}
        self.task_node_mapping: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)

    def add_node(self, node: NodeInfo):
        """Add a node to the cluster"""
        self.nodes[node.node_id] = node
        self.logger.info(f"Added node {node.node_id} at {node.address}")

    def remove_node(self, node_id: str):
        """Remove a node from the cluster"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.logger.info(f"Removed node {node_id}")

    def update_node_status(self, node_id: str, status: NodeStatus, load: float = None, active_tasks: int = None):
        """Update node status and metrics"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.status = status
            node.last_heartbeat = time.time()

            if load is not None:
                node.current_load = load
            if active_tasks is not None:
                node.active_tasks = active_tasks

    def get_optimal_node(self, task: Task) -> Optional[NodeInfo]:
        """Select the optimal node for task execution"""
        available_nodes = [
            node for node in self.nodes.values()
            if node.status == NodeStatus.ACTIVE and node.active_tasks < node.max_tasks
        ]

        if not available_nodes:
            return None

        # Score nodes based on multiple factors
        def score_node(node: NodeInfo) -> float:
            load_score = 1.0 - node.current_load  # Lower load is better
            capacity_score = 1.0 - (node.active_tasks / node.max_tasks)  # More capacity is better

            # Capability matching
            capability_score = 1.0
            if hasattr(task, 'required_capabilities'):
                required_caps = getattr(task, 'required_capabilities', set())
                if required_caps:
                    matches = len(required_caps.intersection(node.capabilities))
                    capability_score = matches / len(required_caps) if required_caps else 1.0

            # Priority bonus for high-priority tasks
            priority_bonus = 1.0
            if task.priority in [TaskPriority.CRITICAL, TaskPriority.HIGH]:
                priority_bonus = 1.2

            return (load_score * 0.4 + capacity_score * 0.4 + capability_score * 0.2) * priority_bonus

        # Select node with highest score
        best_node = max(available_nodes, key=score_node)
        self.task_node_mapping[task.id] = best_node.node_id

        return best_node

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get overall cluster status"""
        total_nodes = len(self.nodes)
        active_nodes = len([n for n in self.nodes.values() if n.status == NodeStatus.ACTIVE])
        total_tasks = sum(n.active_tasks for n in self.nodes.values())
        total_capacity = sum(n.max_tasks for n in self.nodes.values())
        avg_load = sum(n.current_load for n in self.nodes.values()) / total_nodes if total_nodes > 0 else 0

        return {
            'total_nodes': total_nodes,
            'active_nodes': active_nodes,
            'total_active_tasks': total_tasks,
            'total_capacity': total_capacity,
            'cluster_utilization': total_tasks / total_capacity if total_capacity > 0 else 0,
            'average_load': avg_load,
            'nodes': {node_id: node.to_dict() for node_id, node in self.nodes.items()}
        }

    def rebalance_tasks(self) -> List[Tuple[str, str, str]]:
        """Identify tasks that should be moved for better load distribution"""
        rebalance_suggestions = []

        # Find overloaded and underloaded nodes
        overloaded_nodes = [n for n in self.nodes.values() if n.current_load > 0.8]
        underloaded_nodes = [n for n in self.nodes.values() if n.current_load < 0.4 and n.status == NodeStatus.ACTIVE]

        for overloaded_node in overloaded_nodes:
            for underloaded_node in underloaded_nodes:
                if overloaded_node.active_tasks > underloaded_node.active_tasks + 2:
                    # Suggest moving a task
                    rebalance_suggestions.append((
                        "rebalance",
                        overloaded_node.node_id,
                        underloaded_node.node_id
                    ))
                    break

        return rebalance_suggestions


class DistributedTaskCoordinator:
    """Coordinates task execution across a distributed cluster"""

    def __init__(self,
                 node_id: str,
                 host: str = "localhost",
                 port: int = 8765,
                 is_master: bool = False):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.is_master = is_master

        # Local task processor
        self.local_processor = AdvancedTaskProcessor()

        # Cluster management (only for master node)
        self.load_balancer = LoadBalancer() if is_master else None
        self.master_host: Optional[str] = None
        self.master_port: Optional[int] = None

        # Node information
        import psutil
        self.node_info = NodeInfo(
            node_id=node_id,
            host=host,
            port=port,
            status=NodeStatus.ACTIVE,
            cpu_count=psutil.cpu_count(),
            memory_gb=psutil.virtual_memory().total / (1024**3),
            max_tasks=50
        )

        # Communication
        self.connected_nodes: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.websocket_server = None
        self.master_connection: Optional[websockets.WebSocketClientProtocol] = None

        # Task tracking
        self.pending_results: Dict[str, asyncio.Future] = {}
        self.distributed_tasks: Dict[str, str] = {}  # task_id -> node_id

        # Control
        self.running = False
        self.heartbeat_task: Optional[asyncio.Task] = None

        self.logger = logging.getLogger(__name__)

    async def start(self, master_host: Optional[str] = None, master_port: Optional[int] = None):
        """Start the distributed coordinator"""
        self.running = True

        # Start local task processor
        await self.local_processor.start_processing()

        # Start WebSocket server for incoming connections
        self.websocket_server = await ws_serve(
            self._handle_websocket_connection,
            self.host,
            self.port
        )

        if self.is_master:
            # Master node initialization
            if self.load_balancer:
                self.load_balancer.add_node(self.node_info)
            self.logger.info(f"Master node {self.node_id} started on {self.host}:{self.port}")
        else:
            # Worker node - connect to master
            if master_host and master_port:
                self.master_host = master_host
                self.master_port = master_port
                await self._connect_to_master()
            self.logger.info(f"Worker node {self.node_id} started on {self.host}:{self.port}")

        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """Stop the distributed coordinator"""
        self.running = False

        # Stop heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close connections
        if self.master_connection:
            await self.master_connection.close()

        for connection in self.connected_nodes.values():
            await connection.close()

        # Stop WebSocket server
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()

        # Stop local processor
        await self.local_processor.stop_processing()
        self.local_processor.shutdown()

        self.logger.info(f"Node {self.node_id} stopped")

    async def _connect_to_master(self):
        """Connect to the master node"""
        try:
            uri = f"ws://{self.master_host}:{self.master_port}"
            self.master_connection = await websockets.connect(uri)

            # Send initial registration
            registration_msg = ClusterMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.node_id,
                recipient_id=None,
                message_type=MessageType.CLUSTER_UPDATE,
                payload={'action': 'register', 'node_info': self.node_info.to_dict()}
            )

            await self.master_connection.send(registration_msg.to_json())
            self.logger.info(f"Connected to master at {self.master_host}:{self.master_port}")

            # Start listening for messages from master
            asyncio.create_task(self._listen_to_master())

        except Exception as e:
            self.logger.error(f"Failed to connect to master: {e}")

    async def _listen_to_master(self):
        """Listen for messages from master node"""
        try:
            async for message in self.master_connection:
                try:
                    cluster_msg = ClusterMessage.from_json(message)
                    await self._handle_cluster_message(cluster_msg)
                except Exception as e:
                    self.logger.error(f"Error processing master message: {e}")
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Connection to master lost")
        except Exception as e:
            self.logger.error(f"Error listening to master: {e}")

    async def _handle_websocket_connection(self, websocket, path):
        """Handle incoming WebSocket connections"""
        try:
            async for message in websocket:
                try:
                    cluster_msg = ClusterMessage.from_json(message)

                    # Register the connection if it's a new node
                    if cluster_msg.message_type == MessageType.CLUSTER_UPDATE:
                        payload = cluster_msg.payload
                        if payload.get('action') == 'register':
                            node_info = NodeInfo.from_dict(payload['node_info'])
                            self.connected_nodes[cluster_msg.sender_id] = websocket

                            if self.is_master and self.load_balancer:
                                self.load_balancer.add_node(node_info)

                            self.logger.info(f"Node {cluster_msg.sender_id} registered")

                    await self._handle_cluster_message(cluster_msg)

                except Exception as e:
                    self.logger.error(f"Error processing WebSocket message: {e}")

        except websockets.exceptions.ConnectionClosed:
            # Remove disconnected node
            for node_id, conn in list(self.connected_nodes.items()):
                if conn == websocket:
                    del self.connected_nodes[node_id]
                    if self.is_master and self.load_balancer:
                        self.load_balancer.remove_node(node_id)
                    self.logger.info(f"Node {node_id} disconnected")
                    break

    async def _handle_cluster_message(self, message: ClusterMessage):
        """Handle cluster communication messages"""
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            # Receive task for execution
            await self._handle_task_assignment(message)

        elif message.message_type == MessageType.TASK_RESULT:
            # Receive task result
            await self._handle_task_result(message)

        elif message.message_type == MessageType.HEARTBEAT:
            # Update node status
            if self.is_master and self.load_balancer:
                payload = message.payload
                self.load_balancer.update_node_status(
                    message.sender_id,
                    NodeStatus(payload.get('status', 'active')),
                    payload.get('load'),
                    payload.get('active_tasks')
                )

        elif message.message_type == MessageType.NODE_STATUS:
            # Handle node status updates
            if self.is_master and self.load_balancer:
                payload = message.payload
                self.load_balancer.update_node_status(
                    message.sender_id,
                    NodeStatus(payload['status']),
                    payload.get('load'),
                    payload.get('active_tasks')
                )

    async def _handle_task_assignment(self, message: ClusterMessage):
        """Handle assigned task execution"""
        payload = message.payload

        try:
            # Deserialize task
            task_data = payload['task']
            task = Task(
                id=task_data['id'],
                name=task_data['name'],
                priority=TaskPriority(task_data['priority']),
                func=pickle.loads(bytes.fromhex(task_data['func_pickle'])),
                args=tuple(task_data.get('args', [])),
                kwargs=task_data.get('kwargs', {}),
                timeout=task_data.get('timeout'),
                max_retries=task_data.get('max_retries', 3)
            )

            # Execute task locally
            task_id = await self.local_processor.submit_task(
                name=task.name,
                func=task.func,
                args=task.args,
                kwargs=task.kwargs,
                priority=task.priority,
                timeout=task.timeout,
                max_retries=task.max_retries
            )

            # Monitor task completion and send result back
            asyncio.create_task(self._monitor_task_completion(task_id, message.sender_id))

        except Exception as e:
            self.logger.error(f"Error handling task assignment: {e}")

    async def _monitor_task_completion(self, task_id: str, requester_id: str):
        """Monitor task completion and send result back"""
        try:
            # Wait for task completion
            while True:
                result = self.local_processor.get_task_result(task_id)
                if result:
                    break
                await asyncio.sleep(0.1)

            # Send result back
            result_msg = ClusterMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.node_id,
                recipient_id=requester_id,
                message_type=MessageType.TASK_RESULT,
                payload={
                    'task_id': task_id,
                    'status': result.status.value,
                    'result': pickle.dumps(result.result).hex() if result.result else None,
                    'error': str(result.error) if result.error else None,
                    'execution_time': result.execution_time,
                    'memory_used': result.memory_used
                }
            )

            if self.is_master:
                # Send to requesting worker
                if requester_id in self.connected_nodes:
                    await self.connected_nodes[requester_id].send(result_msg.to_json())
            else:
                # Send to master
                if self.master_connection:
                    await self.master_connection.send(result_msg.to_json())

        except Exception as e:
            self.logger.error(f"Error monitoring task completion: {e}")

    async def _handle_task_result(self, message: ClusterMessage):
        """Handle task result from worker node"""
        payload = message.payload
        task_id = payload['task_id']

        if task_id in self.pending_results:
            # Create result object
            result = TaskResult(
                task_id=task_id,
                status=TaskStatus(payload['status']),
                result=pickle.loads(bytes.fromhex(payload['result'])) if payload.get('result') else None,
                error=Exception(payload['error']) if payload.get('error') else None,
                execution_time=payload.get('execution_time', 0.0),
                memory_used=payload.get('memory_used', 0)
            )

            # Set future result
            future = self.pending_results[task_id]
            if not future.done():
                future.set_result(result)

            del self.pending_results[task_id]

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to maintain cluster connectivity"""
        while self.running:
            try:
                # Update local node info
                import psutil
                self.node_info.current_load = psutil.cpu_percent(interval=0.1) / 100.0
                self.node_info.active_tasks = len(self.local_processor.running_tasks)

                # Send heartbeat
                if not self.is_master and self.master_connection:
                    heartbeat_msg = ClusterMessage(
                        message_id=str(uuid.uuid4()),
                        sender_id=self.node_id,
                        recipient_id=None,
                        message_type=MessageType.HEARTBEAT,
                        payload={
                            'status': self.node_info.status.value,
                            'load': self.node_info.current_load,
                            'active_tasks': self.node_info.active_tasks
                        }
                    )

                    await self.master_connection.send(heartbeat_msg.to_json())

                await asyncio.sleep(30)  # Heartbeat every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)

    async def submit_distributed_task(self,
                                    name: str,
                                    func: callable,
                                    args: tuple = (),
                                    kwargs: dict = None,
                                    priority: TaskPriority = TaskPriority.NORMAL,
                                    timeout: Optional[float] = None,
                                    max_retries: int = 3) -> str:
        """Submit a task for distributed execution"""
        if not self.is_master:
            raise RuntimeError("Only master node can submit distributed tasks")

        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())

        # Create task
        task = Task(
            id=task_id,
            name=name,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
            max_retries=max_retries
        )

        # Find optimal node
        if self.load_balancer:
            target_node = self.load_balancer.get_optimal_node(task)

            if not target_node:
                # No available nodes, execute locally
                return await self.local_processor.submit_task(
                    name=name, func=func, args=args, kwargs=kwargs,
                    priority=priority, timeout=timeout, max_retries=max_retries
                )

            # Send task to worker node
            task_msg = ClusterMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.node_id,
                recipient_id=target_node.node_id,
                message_type=MessageType.TASK_ASSIGNMENT,
                payload={
                    'task': {
                        'id': task.id,
                        'name': task.name,
                        'priority': task.priority.value,
                        'func_pickle': pickle.dumps(task.func).hex(),
                        'args': list(task.args),
                        'kwargs': task.kwargs,
                        'timeout': task.timeout,
                        'max_retries': task.max_retries
                    }
                }
            )

            # Create future for result
            future = asyncio.Future()
            self.pending_results[task_id] = future
            self.distributed_tasks[task_id] = target_node.node_id

            # Send task
            if target_node.node_id in self.connected_nodes:
                await self.connected_nodes[target_node.node_id].send(task_msg.to_json())

            return task_id

        # Fallback to local execution
        return await self.local_processor.submit_task(
            name=name, func=func, args=args, kwargs=kwargs,
            priority=priority, timeout=timeout, max_retries=max_retries
        )

    async def get_distributed_task_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Get result for a distributed task"""
        if task_id in self.pending_results:
            try:
                if timeout:
                    result = await asyncio.wait_for(self.pending_results[task_id], timeout=timeout)
                else:
                    result = await self.pending_results[task_id]
                return result
            except asyncio.TimeoutError:
                return None

        # Check local processor
        return self.local_processor.get_task_result(task_id)

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get comprehensive cluster status"""
        if not self.is_master or not self.load_balancer:
            return {'error': 'Only master node provides cluster status'}

        cluster_status = self.load_balancer.get_cluster_status()
        cluster_status['master_node'] = self.node_id
        cluster_status['local_processor_status'] = self.local_processor.get_status()

        return cluster_status