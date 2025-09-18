"""
Advanced Task Scheduling and Retry Mechanisms for Context Cleaner
Implements sophisticated scheduling algorithms, retry strategies, and task lifecycle management
"""

import asyncio
import heapq
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import croniter
import json
from .task_processing import Task, TaskResult, TaskStatus, TaskPriority, AdvancedTaskProcessor


class ScheduleType(Enum):
    """Types of task scheduling"""
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    PERIODIC = "periodic"
    CRON = "cron"
    CONDITIONAL = "conditional"
    DEPENDENCY_BASED = "dependency_based"


class RetryStrategy(Enum):
    """Retry strategy types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI = "fibonacci"
    CUSTOM = "custom"


class TaskLifecycleState(Enum):
    """Extended task lifecycle states"""
    SCHEDULED = "scheduled"
    WAITING_DEPENDENCIES = "waiting_dependencies"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRYING = "retrying"
    EXPIRED = "expired"


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    strategy: RetryStrategy
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_exceptions: Set[type] = field(default_factory=lambda: {Exception})
    custom_retry_func: Optional[Callable[[int, Exception], float]] = None


@dataclass
class ScheduleConfig:
    """Configuration for task scheduling"""
    schedule_type: ScheduleType
    execute_at: Optional[datetime] = None
    delay_seconds: Optional[float] = None
    interval_seconds: Optional[float] = None
    cron_expression: Optional[str] = None
    max_executions: Optional[int] = None
    expire_at: Optional[datetime] = None
    timezone: Optional[str] = None
    condition_func: Optional[Callable[[], bool]] = None
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class ScheduledTask:
    """Extended task with scheduling and retry information"""
    base_task: Task
    schedule_config: ScheduleConfig
    retry_config: RetryConfig

    # Runtime state
    state: TaskLifecycleState = TaskLifecycleState.SCHEDULED
    execution_count: int = 0
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None
    failure_count: int = 0
    last_error: Optional[Exception] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Execution history
    execution_history: List[Dict[str, Any]] = field(default_factory=list)

    def __lt__(self, other):
        """Priority comparison for scheduling queue"""
        if self.next_execution and other.next_execution:
            return self.next_execution < other.next_execution
        elif self.next_execution:
            return True
        elif other.next_execution:
            return False
        return self.base_task.priority.value < other.base_task.priority.value

    def update_state(self, new_state: TaskLifecycleState, error: Optional[Exception] = None):
        """Update task state and metadata"""
        self.state = new_state
        self.updated_at = datetime.utcnow()

        if error:
            self.last_error = error
            self.failure_count += 1

    def can_execute(self) -> bool:
        """Check if task can be executed now"""
        if self.state not in [TaskLifecycleState.READY, TaskLifecycleState.RETRYING]:
            return False

        if self.schedule_config.expire_at and datetime.utcnow() > self.schedule_config.expire_at:
            self.update_state(TaskLifecycleState.EXPIRED)
            return False

        if self.schedule_config.max_executions and self.execution_count >= self.schedule_config.max_executions:
            return False

        if self.next_execution and datetime.utcnow() < self.next_execution:
            return False

        return True

    def should_retry(self, error: Exception) -> bool:
        """Determine if task should be retried based on error and config"""
        if self.failure_count >= self.retry_config.max_attempts:
            return False

        # Check if error type is in retry list
        error_type = type(error)
        return any(issubclass(error_type, exc_type) for exc_type in self.retry_config.retry_on_exceptions)

    def calculate_next_execution(self) -> Optional[datetime]:
        """Calculate when this task should next be executed"""
        now = datetime.utcnow()

        if self.schedule_config.schedule_type == ScheduleType.IMMEDIATE:
            return now

        elif self.schedule_config.schedule_type == ScheduleType.DELAYED:
            if self.schedule_config.delay_seconds:
                return now + timedelta(seconds=self.schedule_config.delay_seconds)

        elif self.schedule_config.schedule_type == ScheduleType.PERIODIC:
            if self.schedule_config.interval_seconds:
                if self.last_execution:
                    return self.last_execution + timedelta(seconds=self.schedule_config.interval_seconds)
                else:
                    return now

        elif self.schedule_config.schedule_type == ScheduleType.CRON:
            if self.schedule_config.cron_expression:
                cron = croniter.croniter(self.schedule_config.cron_expression, now)
                return cron.get_next(datetime)

        elif self.schedule_config.schedule_type == ScheduleType.CONDITIONAL:
            if self.schedule_config.condition_func and self.schedule_config.condition_func():
                return now

        return None

    def calculate_retry_delay(self) -> float:
        """Calculate delay before retry based on retry strategy"""
        attempt = self.failure_count

        if self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** (attempt - 1))

        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * attempt

        elif self.retry_config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.retry_config.base_delay

        elif self.retry_config.strategy == RetryStrategy.FIBONACCI:
            def fibonacci(n):
                if n <= 1:
                    return n
                a, b = 0, 1
                for _ in range(2, n + 1):
                    a, b = b, a + b
                return b
            delay = self.retry_config.base_delay * fibonacci(attempt)

        elif self.retry_config.strategy == RetryStrategy.CUSTOM:
            if self.retry_config.custom_retry_func:
                delay = self.retry_config.custom_retry_func(attempt, self.last_error)
            else:
                delay = self.retry_config.base_delay

        else:
            delay = self.retry_config.base_delay

        # Apply jitter to prevent thundering herd
        if self.retry_config.jitter:
            import random
            jitter_factor = 0.1  # 10% jitter
            jitter = random.uniform(-jitter_factor, jitter_factor) * delay
            delay = delay + jitter

        # Clamp to max delay
        return min(delay, self.retry_config.max_delay)


class DependencyResolver:
    """Resolves task dependencies and maintains execution order"""

    def __init__(self):
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()

    def add_dependency(self, task_id: str, depends_on: str):
        """Add a dependency relationship"""
        if task_id not in self.dependency_graph:
            self.dependency_graph[task_id] = set()
        self.dependency_graph[task_id].add(depends_on)

    def remove_dependency(self, task_id: str, depends_on: str):
        """Remove a dependency relationship"""
        if task_id in self.dependency_graph:
            self.dependency_graph[task_id].discard(depends_on)

    def mark_completed(self, task_id: str):
        """Mark a task as completed"""
        self.completed_tasks.add(task_id)

    def mark_failed(self, task_id: str):
        """Mark a task as failed"""
        self.failed_tasks.add(task_id)

    def can_execute(self, task_id: str) -> bool:
        """Check if a task's dependencies are satisfied"""
        if task_id not in self.dependency_graph:
            return True

        dependencies = self.dependency_graph[task_id]

        # All dependencies must be completed
        return dependencies.issubset(self.completed_tasks)

    def get_ready_tasks(self, all_task_ids: Set[str]) -> Set[str]:
        """Get all tasks that are ready to execute"""
        ready_tasks = set()

        for task_id in all_task_ids:
            if task_id not in self.completed_tasks and task_id not in self.failed_tasks:
                if self.can_execute(task_id):
                    ready_tasks.add(task_id)

        return ready_tasks

    def detect_cycles(self) -> List[List[str]]:
        """Detect circular dependencies in the graph"""
        def dfs(node, path, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            cycles = []
            if node in self.dependency_graph:
                for neighbor in self.dependency_graph[node]:
                    if neighbor in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(neighbor)
                        cycles.append(path[cycle_start:] + [neighbor])
                    elif neighbor not in visited:
                        cycles.extend(dfs(neighbor, path.copy(), visited, rec_stack))

            rec_stack.remove(node)
            return cycles

        visited = set()
        all_cycles = []

        for node in self.dependency_graph:
            if node not in visited:
                all_cycles.extend(dfs(node, [], visited, set()))

        return all_cycles


class AdvancedTaskScheduler:
    """Advanced task scheduler with sophisticated scheduling and retry mechanisms"""

    def __init__(self,
                 task_processor: AdvancedTaskProcessor,
                 max_concurrent_scheduled: int = 100):
        self.task_processor = task_processor
        self.max_concurrent_scheduled = max_concurrent_scheduled

        # Scheduling queues
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.schedule_queue = []  # Priority queue for next executions
        self.waiting_dependencies: Dict[str, ScheduledTask] = {}

        # Dependency management
        self.dependency_resolver = DependencyResolver()

        # Scheduler control
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.dependency_checker_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            'tasks_scheduled': 0,
            'tasks_executed': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_retried': 0,
            'tasks_expired': 0,
            'average_execution_time': 0.0,
            'average_retry_count': 0.0
        }

        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the task scheduler"""
        if self.running:
            return

        self.running = True

        # Start scheduler loop
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.dependency_checker_task = asyncio.create_task(self._dependency_checker_loop())

        self.logger.info("Advanced task scheduler started")

    async def stop(self):
        """Stop the task scheduler"""
        if not self.running:
            return

        self.running = False

        # Cancel scheduler tasks
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        if self.dependency_checker_task:
            self.dependency_checker_task.cancel()
            try:
                await self.dependency_checker_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Advanced task scheduler stopped")

    async def schedule_task(self,
                          name: str,
                          func: Callable,
                          schedule_config: ScheduleConfig,
                          retry_config: Optional[RetryConfig] = None,
                          args: Tuple = (),
                          kwargs: Optional[Dict[str, Any]] = None,
                          priority: TaskPriority = TaskPriority.NORMAL,
                          timeout: Optional[float] = None,
                          tags: Optional[Set[str]] = None) -> str:
        """Schedule a task with advanced scheduling and retry configuration"""

        task_id = str(uuid.uuid4())
        kwargs = kwargs or {}
        tags = tags or set()

        # Create base task
        base_task = Task(
            id=task_id,
            name=name,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
            tags=tags
        )

        # Default retry config
        if retry_config is None:
            retry_config = RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_attempts=3,
                base_delay=1.0
            )

        # Create scheduled task
        scheduled_task = ScheduledTask(
            base_task=base_task,
            schedule_config=schedule_config,
            retry_config=retry_config
        )

        # Calculate initial execution time
        scheduled_task.next_execution = scheduled_task.calculate_next_execution()

        # Handle dependencies
        if schedule_config.dependencies:
            scheduled_task.update_state(TaskLifecycleState.WAITING_DEPENDENCIES)
            self.waiting_dependencies[task_id] = scheduled_task

            # Register dependencies
            for dep_id in schedule_config.dependencies:
                self.dependency_resolver.add_dependency(task_id, dep_id)
        else:
            scheduled_task.update_state(TaskLifecycleState.READY)
            heapq.heappush(self.schedule_queue, scheduled_task)

        self.scheduled_tasks[task_id] = scheduled_task
        self.stats['tasks_scheduled'] += 1

        self.logger.info(f"Scheduled task {task_id} ({name}) with {schedule_config.schedule_type.value} schedule")

        return task_id

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = datetime.utcnow()
                executed_tasks = []

                # Process ready tasks
                while self.schedule_queue and len(executed_tasks) < self.max_concurrent_scheduled:
                    # Peek at next task
                    if not self.schedule_queue:
                        break

                    next_task = self.schedule_queue[0]

                    # Check if it's time to execute
                    if next_task.next_execution and next_task.next_execution > current_time:
                        break

                    # Remove from queue
                    scheduled_task = heapq.heappop(self.schedule_queue)

                    # Verify task can still execute
                    if not scheduled_task.can_execute():
                        if scheduled_task.state == TaskLifecycleState.EXPIRED:
                            self.stats['tasks_expired'] += 1
                        continue

                    # Execute task
                    await self._execute_scheduled_task(scheduled_task)
                    executed_tasks.append(scheduled_task)

                # Sleep briefly before next iteration
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(1.0)

    async def _dependency_checker_loop(self):
        """Check for tasks whose dependencies are now satisfied"""
        while self.running:
            try:
                ready_task_ids = self.dependency_resolver.get_ready_tasks(
                    set(self.waiting_dependencies.keys())
                )

                for task_id in ready_task_ids:
                    if task_id in self.waiting_dependencies:
                        scheduled_task = self.waiting_dependencies[task_id]
                        scheduled_task.update_state(TaskLifecycleState.READY)

                        # Move to schedule queue
                        heapq.heappush(self.schedule_queue, scheduled_task)
                        del self.waiting_dependencies[task_id]

                        self.logger.info(f"Task {task_id} dependencies satisfied, moved to ready queue")

                await asyncio.sleep(1.0)  # Check dependencies every second

            except Exception as e:
                self.logger.error(f"Error in dependency checker loop: {e}")
                await asyncio.sleep(5.0)

    async def _execute_scheduled_task(self, scheduled_task: ScheduledTask):
        """Execute a scheduled task"""
        try:
            scheduled_task.update_state(TaskLifecycleState.RUNNING)
            scheduled_task.execution_count += 1
            scheduled_task.last_execution = datetime.utcnow()

            # Record execution start
            execution_record = {
                'attempt': scheduled_task.execution_count,
                'started_at': scheduled_task.last_execution.isoformat(),
                'retry_count': scheduled_task.failure_count
            }

            # Submit to task processor
            processor_task_id = await self.task_processor.submit_task(
                name=scheduled_task.base_task.name,
                func=scheduled_task.base_task.func,
                args=scheduled_task.base_task.args,
                kwargs=scheduled_task.base_task.kwargs,
                priority=scheduled_task.base_task.priority,
                timeout=scheduled_task.base_task.timeout,
                tags=scheduled_task.base_task.tags
            )

            # Monitor execution
            asyncio.create_task(self._monitor_task_execution(scheduled_task, processor_task_id, execution_record))

            self.stats['tasks_executed'] += 1

        except Exception as e:
            self.logger.error(f"Error executing scheduled task {scheduled_task.base_task.id}: {e}")
            await self._handle_task_failure(scheduled_task, e)

    async def _monitor_task_execution(self, scheduled_task: ScheduledTask, processor_task_id: str, execution_record: Dict[str, Any]):
        """Monitor task execution and handle completion/failure"""
        try:
            # Wait for task completion
            result = None
            while not result:
                result = self.task_processor.get_task_result(processor_task_id)
                if not result:
                    await asyncio.sleep(0.1)

            # Record execution end
            execution_record['completed_at'] = datetime.utcnow().isoformat()
            execution_record['execution_time'] = result.execution_time
            execution_record['memory_used'] = result.memory_used
            execution_record['status'] = result.status.value

            if result.status == TaskStatus.COMPLETED:
                await self._handle_task_success(scheduled_task, result, execution_record)
            else:
                execution_record['error'] = str(result.error) if result.error else "Unknown error"
                await self._handle_task_failure(scheduled_task, result.error, execution_record)

        except Exception as e:
            execution_record['error'] = str(e)
            execution_record['completed_at'] = datetime.utcnow().isoformat()
            await self._handle_task_failure(scheduled_task, e, execution_record)

    async def _handle_task_success(self, scheduled_task: ScheduledTask, result: TaskResult, execution_record: Dict[str, Any]):
        """Handle successful task execution"""
        scheduled_task.update_state(TaskLifecycleState.COMPLETED)
        scheduled_task.execution_history.append(execution_record)

        # Mark as completed for dependency resolution
        self.dependency_resolver.mark_completed(scheduled_task.base_task.id)

        self.stats['tasks_completed'] += 1

        # Update average execution time
        total_completed = self.stats['tasks_completed']
        current_avg = self.stats['average_execution_time']
        self.stats['average_execution_time'] = (current_avg * (total_completed - 1) + result.execution_time) / total_completed

        # Schedule next execution for periodic tasks
        await self._schedule_next_execution(scheduled_task)

        self.logger.info(f"Task {scheduled_task.base_task.id} completed successfully")

    async def _handle_task_failure(self, scheduled_task: ScheduledTask, error: Exception, execution_record: Optional[Dict[str, Any]] = None):
        """Handle task execution failure"""
        scheduled_task.update_state(TaskLifecycleState.FAILED, error)

        if execution_record:
            scheduled_task.execution_history.append(execution_record)

        # Check if should retry
        if scheduled_task.should_retry(error):
            await self._schedule_retry(scheduled_task)
        else:
            # Mark as permanently failed
            self.dependency_resolver.mark_failed(scheduled_task.base_task.id)
            self.stats['tasks_failed'] += 1

            self.logger.error(f"Task {scheduled_task.base_task.id} failed permanently: {error}")

    async def _schedule_retry(self, scheduled_task: ScheduledTask):
        """Schedule a task for retry"""
        retry_delay = scheduled_task.calculate_retry_delay()
        scheduled_task.next_execution = datetime.utcnow() + timedelta(seconds=retry_delay)
        scheduled_task.update_state(TaskLifecycleState.RETRYING)

        # Re-add to schedule queue
        heapq.heappush(self.schedule_queue, scheduled_task)

        self.stats['tasks_retried'] += 1

        # Update average retry count
        total_retried = self.stats['tasks_retried']
        current_avg = self.stats['average_retry_count']
        self.stats['average_retry_count'] = (current_avg * (total_retried - 1) + scheduled_task.failure_count) / total_retried

        self.logger.info(f"Task {scheduled_task.base_task.id} scheduled for retry in {retry_delay:.2f} seconds")

    async def _schedule_next_execution(self, scheduled_task: ScheduledTask):
        """Schedule next execution for recurring tasks"""
        if scheduled_task.schedule_config.schedule_type in [ScheduleType.PERIODIC, ScheduleType.CRON]:
            # Calculate next execution
            next_exec = scheduled_task.calculate_next_execution()

            if next_exec and (not scheduled_task.schedule_config.max_executions or
                            scheduled_task.execution_count < scheduled_task.schedule_config.max_executions):

                # Reset state for next execution
                scheduled_task.next_execution = next_exec
                scheduled_task.update_state(TaskLifecycleState.READY)

                # Re-add to schedule queue
                heapq.heappush(self.schedule_queue, scheduled_task)

                self.logger.info(f"Task {scheduled_task.base_task.id} scheduled for next execution at {next_exec}")

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task"""
        if task_id in self.scheduled_tasks:
            scheduled_task = self.scheduled_tasks[task_id]
            scheduled_task.update_state(TaskLifecycleState.CANCELLED)

            # Remove from queues
            if task_id in self.waiting_dependencies:
                del self.waiting_dependencies[task_id]

            # Note: Can't easily remove from heapq, but cancelled tasks will be skipped

            self.logger.info(f"Task {task_id} cancelled")
            return True

        return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a scheduled task"""
        if task_id in self.scheduled_tasks:
            scheduled_task = self.scheduled_tasks[task_id]
            if scheduled_task.state in [TaskLifecycleState.READY, TaskLifecycleState.RETRYING]:
                scheduled_task.update_state(TaskLifecycleState.PAUSED)
                self.logger.info(f"Task {task_id} paused")
                return True

        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        if task_id in self.scheduled_tasks:
            scheduled_task = self.scheduled_tasks[task_id]
            if scheduled_task.state == TaskLifecycleState.PAUSED:
                scheduled_task.update_state(TaskLifecycleState.READY)
                heapq.heappush(self.schedule_queue, scheduled_task)
                self.logger.info(f"Task {task_id} resumed")
                return True

        return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a scheduled task"""
        if task_id in self.scheduled_tasks:
            scheduled_task = self.scheduled_tasks[task_id]
            return {
                'task_id': task_id,
                'name': scheduled_task.base_task.name,
                'state': scheduled_task.state.value,
                'execution_count': scheduled_task.execution_count,
                'failure_count': scheduled_task.failure_count,
                'last_execution': scheduled_task.last_execution.isoformat() if scheduled_task.last_execution else None,
                'next_execution': scheduled_task.next_execution.isoformat() if scheduled_task.next_execution else None,
                'last_error': str(scheduled_task.last_error) if scheduled_task.last_error else None,
                'created_at': scheduled_task.created_at.isoformat(),
                'updated_at': scheduled_task.updated_at.isoformat(),
                'schedule_type': scheduled_task.schedule_config.schedule_type.value,
                'execution_history': scheduled_task.execution_history
            }
        return None

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status"""
        return {
            'running': self.running,
            'scheduled_tasks': len(self.scheduled_tasks),
            'ready_tasks': len(self.schedule_queue),
            'waiting_dependencies': len(self.waiting_dependencies),
            'statistics': self.stats.copy(),
            'dependency_cycles': self.dependency_resolver.detect_cycles()
        }

    def get_tasks_by_state(self, state: TaskLifecycleState) -> List[Dict[str, Any]]:
        """Get all tasks in a specific state"""
        tasks = []
        for task_id, scheduled_task in self.scheduled_tasks.items():
            if scheduled_task.state == state:
                status = self.get_task_status(task_id)
                if status:
                    tasks.append(status)
        return tasks

    def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """Clean up old completed tasks to free memory"""
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        tasks_to_remove = []

        for task_id, scheduled_task in self.scheduled_tasks.items():
            if (scheduled_task.state in [TaskLifecycleState.COMPLETED, TaskLifecycleState.FAILED, TaskLifecycleState.CANCELLED] and
                scheduled_task.updated_at < cutoff_time):
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self.scheduled_tasks[task_id]

        self.logger.info(f"Cleaned up {len(tasks_to_remove)} old completed tasks")