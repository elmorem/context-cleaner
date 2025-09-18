"""
Advanced Task Processing System for Context Cleaner
Implements async task processing with priority queues, resource monitoring, and distributed execution
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import heapq
import psutil
import threading
from functools import wraps
import json
import pickle
from pathlib import Path


class TaskPriority(Enum):
    """Task priority levels for processing queue"""
    CRITICAL = 0    # System-critical tasks (e.g., memory cleanup)
    HIGH = 1        # User-facing operations (e.g., dashboard updates)
    NORMAL = 2      # Standard processing tasks (e.g., context analysis)
    LOW = 3         # Background optimization (e.g., cache cleanup)
    DEFERRED = 4    # Non-urgent tasks (e.g., statistics generation)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class TaskResult:
    """Task execution result container"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    memory_used: int = 0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Task definition with priority and metadata"""
    id: str
    name: str
    priority: TaskPriority
    func: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    dependencies: Set[str] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        """Priority queue comparison - lower priority value = higher priority"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class ResourceMonitor:
    """Intelligent resource utilization monitoring"""

    def __init__(self):
        self.cpu_threshold = 80.0  # CPU usage percentage
        self.memory_threshold = 85.0  # Memory usage percentage
        self.disk_threshold = 90.0  # Disk usage percentage
        self.monitoring = False
        self.stats_history = []
        self.max_history = 1000

    def start_monitoring(self):
        """Start resource monitoring"""
        self.monitoring = True

    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False

    def get_current_stats(self) -> Dict[str, float]:
        """Get current system resource statistics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        stats = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / (1024**3),
            'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0.0,
            'timestamp': time.time()
        }

        if self.monitoring and len(self.stats_history) < self.max_history:
            self.stats_history.append(stats)

        return stats

    def is_system_overloaded(self) -> bool:
        """Check if system is currently overloaded"""
        stats = self.get_current_stats()
        return (
            stats['cpu_percent'] > self.cpu_threshold or
            stats['memory_percent'] > self.memory_threshold or
            stats['disk_percent'] > self.disk_threshold
        )

    def get_optimal_worker_count(self) -> int:
        """Calculate optimal worker count based on system resources"""
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # Base on CPU cores but consider memory constraints
        optimal_workers = min(cpu_count, int(memory_gb / 2))  # 2GB per worker

        # Adjust based on current load
        if self.is_system_overloaded():
            optimal_workers = max(1, optimal_workers // 2)

        return optimal_workers

    def get_resource_trend(self, minutes: int = 5) -> Dict[str, str]:
        """Analyze resource usage trend over specified minutes"""
        if not self.stats_history:
            return {'cpu': 'stable', 'memory': 'stable', 'disk': 'stable'}

        cutoff_time = time.time() - (minutes * 60)
        recent_stats = [s for s in self.stats_history if s['timestamp'] > cutoff_time]

        if len(recent_stats) < 2:
            return {'cpu': 'stable', 'memory': 'stable', 'disk': 'stable'}

        # Calculate trends
        trends = {}
        for metric in ['cpu_percent', 'memory_percent', 'disk_percent']:
            values = [s[metric] for s in recent_stats]
            if len(values) >= 2:
                change = values[-1] - values[0]
                if change > 5:
                    trends[metric.replace('_percent', '')] = 'increasing'
                elif change < -5:
                    trends[metric.replace('_percent', '')] = 'decreasing'
                else:
                    trends[metric.replace('_percent', '')] = 'stable'
            else:
                trends[metric.replace('_percent', '')] = 'stable'

        return trends


class TaskExecutor(ABC):
    """Abstract base class for task executors"""

    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """Execute a task and return result"""
        pass

    @abstractmethod
    def shutdown(self):
        """Shutdown the executor"""
        pass


class AsyncTaskExecutor(TaskExecutor):
    """Executor for async tasks"""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, task: Task) -> TaskResult:
        """Execute an async task"""
        async with self.semaphore:
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss

            try:
                if asyncio.iscoroutinefunction(task.func):
                    if task.timeout:
                        result = await asyncio.wait_for(
                            task.func(*task.args, **task.kwargs),
                            timeout=task.timeout
                        )
                    else:
                        result = await task.func(*task.args, **task.kwargs)
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    if task.timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(None, task.func, *task.args),
                            timeout=task.timeout
                        )
                    else:
                        result = await loop.run_in_executor(None, task.func, *task.args)

                execution_time = time.time() - start_time
                memory_used = psutil.Process().memory_info().rss - start_memory

                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    execution_time=execution_time,
                    memory_used=memory_used
                )

            except Exception as e:
                execution_time = time.time() - start_time
                return TaskResult(
                    task_id=task.id,
                    status=TaskStatus.FAILED,
                    error=e,
                    execution_time=execution_time
                )

    def shutdown(self):
        """Shutdown async executor"""
        pass


class ProcessTaskExecutor(TaskExecutor):
    """Executor for CPU-intensive tasks using process pool"""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or psutil.cpu_count()
        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)

    async def execute(self, task: Task) -> TaskResult:
        """Execute a task in process pool"""
        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            if task.timeout:
                result = await asyncio.wait_for(
                    loop.run_in_executor(self.executor, task.func, *task.args),
                    timeout=task.timeout
                )
            else:
                result = await loop.run_in_executor(self.executor, task.func, *task.args)

            execution_time = time.time() - start_time

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                result=result,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=e,
                execution_time=execution_time
            )

    def shutdown(self):
        """Shutdown process executor"""
        self.executor.shutdown(wait=True)


class ThreadTaskExecutor(TaskExecutor):
    """Executor for I/O-bound tasks using thread pool"""

    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(32, (psutil.cpu_count() or 1) + 4)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    async def execute(self, task: Task) -> TaskResult:
        """Execute a task in thread pool"""
        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            if task.timeout:
                result = await asyncio.wait_for(
                    loop.run_in_executor(self.executor, task.func, *task.args),
                    timeout=task.timeout
                )
            else:
                result = await loop.run_in_executor(self.executor, task.func, *task.args)

            execution_time = time.time() - start_time

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                result=result,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=e,
                execution_time=execution_time
            )

    def shutdown(self):
        """Shutdown thread executor"""
        self.executor.shutdown(wait=True)


class AdvancedTaskProcessor:
    """Advanced task processing system with priority queues and resource monitoring"""

    def __init__(self,
                 max_concurrent_tasks: int = 50,
                 enable_resource_monitoring: bool = True):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue = []  # Priority queue (heapq)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.failed_tasks: Dict[str, TaskResult] = {}
        self.task_dependencies: Dict[str, Set[str]] = {}

        # Resource monitoring
        self.resource_monitor = ResourceMonitor() if enable_resource_monitoring else None

        # Executors
        self.async_executor = AsyncTaskExecutor(max_concurrent_tasks // 3)
        self.process_executor = ProcessTaskExecutor()
        self.thread_executor = ThreadTaskExecutor()

        # Processing control
        self.processing = False
        self.processor_task: Optional[asyncio.Task] = None
        self.stats = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0
        }

        # Thread safety
        self.queue_lock = asyncio.Lock()

        self.logger = logging.getLogger(__name__)

    async def submit_task(self,
                         name: str,
                         func: Callable,
                         args: Tuple = (),
                         kwargs: Optional[Dict[str, Any]] = None,
                         priority: TaskPriority = TaskPriority.NORMAL,
                         timeout: Optional[float] = None,
                         max_retries: int = 3,
                         dependencies: Optional[Set[str]] = None,
                         tags: Optional[Set[str]] = None,
                         executor_type: str = 'async') -> str:
        """Submit a task for processing"""
        task_id = str(uuid.uuid4())
        kwargs = kwargs or {}
        dependencies = dependencies or set()
        tags = tags or set()

        task = Task(
            id=task_id,
            name=name,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
            max_retries=max_retries,
            dependencies=dependencies,
            tags=tags,
            metadata={'executor_type': executor_type}
        )

        async with self.queue_lock:
            heapq.heappush(self.task_queue, task)
            if dependencies:
                self.task_dependencies[task_id] = dependencies

        self.stats['tasks_submitted'] += 1
        self.logger.info(f"Task {task_id} ({name}) submitted with priority {priority.name}")

        return task_id

    def _get_executor(self, executor_type: str) -> TaskExecutor:
        """Get appropriate executor for task type"""
        if executor_type == 'process':
            return self.process_executor
        elif executor_type == 'thread':
            return self.thread_executor
        else:
            return self.async_executor

    def _can_execute_task(self, task: Task) -> bool:
        """Check if task dependencies are satisfied"""
        if task.id in self.task_dependencies:
            dependencies = self.task_dependencies[task.id]
            # All dependencies must be completed successfully
            return all(dep_id in self.completed_tasks for dep_id in dependencies)
        return True

    async def _execute_task_with_retry(self, task: Task) -> TaskResult:
        """Execute task with retry logic"""
        retry_count = 0
        last_error = None

        while retry_count <= task.max_retries:
            try:
                executor = self._get_executor(task.metadata.get('executor_type', 'async'))
                result = await executor.execute(task)

                if result.status == TaskStatus.COMPLETED:
                    result.retry_count = retry_count
                    return result
                else:
                    last_error = result.error

            except Exception as e:
                last_error = e

            retry_count += 1
            if retry_count <= task.max_retries:
                self.logger.warning(f"Task {task.id} failed, retrying ({retry_count}/{task.max_retries})")
                await asyncio.sleep(task.retry_delay * retry_count)  # Exponential backoff

        # All retries exhausted
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.FAILED,
            error=last_error,
            retry_count=retry_count - 1
        )

    async def _process_tasks(self):
        """Main task processing loop"""
        while self.processing:
            try:
                # Check resource constraints
                if self.resource_monitor and self.resource_monitor.is_system_overloaded():
                    await asyncio.sleep(1.0)  # Wait for resources to free up
                    continue

                # Check if we can start more tasks
                if len(self.running_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(0.1)
                    continue

                # Get next available task
                available_task = None
                async with self.queue_lock:
                    # Find a task whose dependencies are satisfied
                    temp_queue = []
                    while self.task_queue:
                        candidate = heapq.heappop(self.task_queue)
                        if self._can_execute_task(candidate):
                            available_task = candidate
                            break
                        else:
                            temp_queue.append(candidate)

                    # Put back tasks that couldn't run
                    for task in temp_queue:
                        heapq.heappush(self.task_queue, task)

                if not available_task:
                    await asyncio.sleep(0.1)
                    continue

                # Execute the task
                self.logger.info(f"Starting execution of task {available_task.id} ({available_task.name})")

                async def run_task():
                    try:
                        result = await self._execute_task_with_retry(available_task)

                        # Update statistics
                        self.stats['total_execution_time'] += result.execution_time

                        if result.status == TaskStatus.COMPLETED:
                            self.completed_tasks[available_task.id] = result
                            self.stats['tasks_completed'] += 1
                            self.logger.info(f"Task {available_task.id} completed successfully")
                        else:
                            self.failed_tasks[available_task.id] = result
                            self.stats['tasks_failed'] += 1
                            self.logger.error(f"Task {available_task.id} failed: {result.error}")

                        # Update average execution time
                        total_tasks = self.stats['tasks_completed'] + self.stats['tasks_failed']
                        if total_tasks > 0:
                            self.stats['average_execution_time'] = self.stats['total_execution_time'] / total_tasks

                        # Clean up dependencies
                        if available_task.id in self.task_dependencies:
                            del self.task_dependencies[available_task.id]

                    finally:
                        # Remove from running tasks
                        if available_task.id in self.running_tasks:
                            del self.running_tasks[available_task.id]

                # Start task execution
                task_coroutine = asyncio.create_task(run_task())
                self.running_tasks[available_task.id] = task_coroutine

            except Exception as e:
                self.logger.error(f"Error in task processing loop: {e}")
                await asyncio.sleep(1.0)

    async def start_processing(self):
        """Start the task processor"""
        if self.processing:
            return

        self.processing = True
        if self.resource_monitor:
            self.resource_monitor.start_monitoring()

        self.processor_task = asyncio.create_task(self._process_tasks())
        self.logger.info("Task processor started")

    async def stop_processing(self):
        """Stop the task processor"""
        if not self.processing:
            return

        self.processing = False

        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass

        # Wait for running tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)

        if self.resource_monitor:
            self.resource_monitor.stop_monitoring()

        self.logger.info("Task processor stopped")

    def shutdown(self):
        """Shutdown all executors"""
        self.async_executor.shutdown()
        self.process_executor.shutdown()
        self.thread_executor.shutdown()

    def get_status(self) -> Dict[str, Any]:
        """Get current processor status"""
        status = {
            'processing': self.processing,
            'queue_size': len(self.task_queue),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'failed_tasks': len(self.failed_tasks),
            'statistics': self.stats.copy()
        }

        if self.resource_monitor:
            status['resource_stats'] = self.resource_monitor.get_current_stats()
            status['system_overloaded'] = self.resource_monitor.is_system_overloaded()
            status['optimal_workers'] = self.resource_monitor.get_optimal_worker_count()

        return status

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get result for a specific task"""
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        elif task_id in self.failed_tasks:
            return self.failed_tasks[task_id]
        return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        # Check if task is running
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            del self.running_tasks[task_id]
            return True

        # Check if task is in queue
        async def cancel_from_queue():
            async with self.queue_lock:
                # Rebuild queue without the cancelled task
                remaining_tasks = []
                cancelled = False

                while self.task_queue:
                    task = heapq.heappop(self.task_queue)
                    if task.id == task_id:
                        cancelled = True
                    else:
                        remaining_tasks.append(task)

                # Rebuild heap
                self.task_queue = remaining_tasks
                heapq.heapify(self.task_queue)

                return cancelled

        # This would need to be called from an async context
        return False

    def get_tasks_by_tag(self, tag: str) -> List[Task]:
        """Get all tasks with a specific tag"""
        tasks = []
        for task in self.task_queue:
            if tag in task.tags:
                tasks.append(task)
        return tasks


def task_processor_decorator(processor: AdvancedTaskProcessor,
                           priority: TaskPriority = TaskPriority.NORMAL,
                           executor_type: str = 'async',
                           timeout: Optional[float] = None):
    """Decorator to automatically submit function calls as tasks"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            task_id = await processor.submit_task(
                name=func.__name__,
                func=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                executor_type=executor_type,
                timeout=timeout
            )
            return task_id
        return wrapper
    return decorator