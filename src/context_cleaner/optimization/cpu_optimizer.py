"""
CPU Usage Optimizer

Advanced CPU optimization to maintain <5% background CPU usage through
intelligent scheduling, async processing, and adaptive workload management.
"""

import asyncio
import threading
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
import logging

from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels for CPU scheduling."""
    CRITICAL = 1     # Must run immediately (user-triggered)
    HIGH = 2         # Important background tasks
    MEDIUM = 3       # Regular maintenance
    LOW = 4          # Optimization and cleanup


@dataclass
class CPUSnapshot:
    """CPU usage snapshot at a point in time."""
    timestamp: datetime
    cpu_percent: float
    cpu_count: int
    load_avg: Optional[float]
    active_threads: int
    pending_tasks: int
    throttle_level: int  # 0=none, 1=light, 2=moderate, 3=aggressive


@dataclass
class ScheduledTask:
    """A task scheduled for background execution."""
    name: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: TaskPriority
    created_at: datetime
    max_duration_ms: int
    retry_count: int = 0
    max_retries: int = 3


class AdaptiveScheduler:
    """
    Adaptive task scheduler that dynamically adjusts execution based on CPU load.
    """
    
    def __init__(self, max_workers: int = 2, target_cpu_percent: float = 3.0):
        """
        Initialize adaptive scheduler.
        
        Args:
            max_workers: Maximum worker threads
            target_cpu_percent: Target CPU usage percentage
        """
        self.max_workers = max_workers
        self.target_cpu_percent = target_cpu_percent
        self.critical_cpu_percent = 8.0  # Above this, aggressive throttling
        
        # Task queues by priority
        self._task_queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        
        # Worker thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="CPUOptimizer"
        )
        
        # Scheduling state
        self._is_running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._throttle_level = 0  # Current throttling level
        
        # Performance tracking
        self._cpu_snapshots: deque = deque(maxlen=60)  # Last 60 measurements
        self._task_execution_times: Dict[str, List[float]] = {}
        
        # Adaptive settings
        self._current_batch_size = 1
        self._current_delay_ms = 100
        self._last_optimization = datetime.now()
        
    def start(self):
        """Start the adaptive scheduler."""
        if self._is_running:
            return
        
        self._is_running = True
        self._stop_event.clear()
        
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, 
            daemon=True, 
            name="AdaptiveScheduler"
        )
        self._scheduler_thread.start()
        
        logger.info(f"Adaptive scheduler started (target CPU: {self.target_cpu_percent}%)")
    
    def stop(self):
        """Stop the adaptive scheduler."""
        if not self._is_running:
            return
        
        self._is_running = False
        self._stop_event.set()
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5.0)
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("Adaptive scheduler stopped")
    
    def schedule_task(self, name: str, func: Callable, *args, 
                     priority: TaskPriority = TaskPriority.MEDIUM,
                     max_duration_ms: int = 500, **kwargs):
        """
        Schedule a task for background execution.
        
        Args:
            name: Task identifier
            func: Function to execute
            args: Positional arguments
            priority: Task priority level
            max_duration_ms: Maximum allowed execution time
            kwargs: Keyword arguments
        """
        task = ScheduledTask(
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            created_at=datetime.now(),
            max_duration_ms=max_duration_ms
        )
        
        self._task_queues[priority].append(task)
        logger.debug(f"Scheduled task: {name} (priority: {priority.name})")
    
    def _scheduler_loop(self):
        """Main scheduler loop with adaptive CPU management."""
        while not self._stop_event.is_set():
            try:
                # Take CPU measurement
                cpu_snapshot = self._take_cpu_snapshot()
                self._cpu_snapshots.append(cpu_snapshot)
                
                # Update throttling based on CPU usage
                self._update_throttling(cpu_snapshot.cpu_percent)
                
                # Process tasks based on current throttling level
                if self._throttle_level == 0:
                    # Normal operation
                    tasks_processed = self._process_task_batch(self._current_batch_size)
                elif self._throttle_level == 1:
                    # Light throttling - reduce batch size
                    tasks_processed = self._process_task_batch(1)
                elif self._throttle_level == 2:
                    # Moderate throttling - only high priority
                    tasks_processed = self._process_priority_tasks([TaskPriority.CRITICAL, TaskPriority.HIGH])
                else:
                    # Aggressive throttling - only critical tasks
                    tasks_processed = self._process_priority_tasks([TaskPriority.CRITICAL])
                
                # Adaptive delay based on CPU usage and throttling
                delay = self._calculate_adaptive_delay()
                self._stop_event.wait(timeout=delay / 1000.0)
                
                # Periodic optimization
                if datetime.now() - self._last_optimization > timedelta(minutes=5):
                    self._optimize_scheduling_parameters()
                    self._last_optimization = datetime.now()
                
            except Exception as e:
                logger.warning(f"Scheduler loop error: {e}")
                self._stop_event.wait(timeout=5.0)
    
    def _take_cpu_snapshot(self) -> CPUSnapshot:
        """Take current CPU usage snapshot."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Get load average (Unix systems)
        try:
            load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None
        except (OSError, AttributeError):
            load_avg = None
        
        # Count active threads and pending tasks
        active_threads = threading.active_count()
        pending_tasks = sum(len(queue) for queue in self._task_queues.values())
        
        return CPUSnapshot(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            load_avg=load_avg,
            active_threads=active_threads,
            pending_tasks=pending_tasks,
            throttle_level=self._throttle_level
        )
    
    def _update_throttling(self, cpu_percent: float):
        """Update throttling level based on current CPU usage."""
        old_throttle = self._throttle_level
        
        if cpu_percent > self.critical_cpu_percent:
            self._throttle_level = 3  # Aggressive
        elif cpu_percent > self.target_cpu_percent * 2:
            self._throttle_level = 2  # Moderate
        elif cpu_percent > self.target_cpu_percent * 1.5:
            self._throttle_level = 1  # Light
        else:
            self._throttle_level = 0  # Normal
        
        if self._throttle_level != old_throttle:
            logger.debug(f"Throttling level changed: {old_throttle} -> {self._throttle_level} "
                        f"(CPU: {cpu_percent:.1f}%)")
    
    def _process_task_batch(self, batch_size: int) -> int:
        """Process a batch of tasks from queues."""
        tasks_processed = 0
        
        # Process tasks by priority order
        for priority in TaskPriority:
            queue = self._task_queues[priority]
            
            # Process up to batch_size tasks from this priority level
            for _ in range(min(batch_size, len(queue))):
                if tasks_processed >= batch_size:
                    break
                
                task = queue.popleft()
                if self._execute_task(task):
                    tasks_processed += 1
                
            if tasks_processed >= batch_size:
                break
        
        return tasks_processed
    
    def _process_priority_tasks(self, allowed_priorities: List[TaskPriority]) -> int:
        """Process tasks only from specified priority levels."""
        tasks_processed = 0
        
        for priority in allowed_priorities:
            queue = self._task_queues[priority]
            
            while queue and tasks_processed < 2:  # Limit even high priority tasks
                task = queue.popleft()
                if self._execute_task(task):
                    tasks_processed += 1
        
        return tasks_processed
    
    def _execute_task(self, task: ScheduledTask) -> bool:
        """Execute a single task with timing and error handling."""
        start_time = time.perf_counter()
        
        try:
            # Submit task to thread pool with timeout
            future = self._executor.submit(task.func, *task.args, **task.kwargs)
            
            # Wait for completion with timeout
            timeout_seconds = task.max_duration_ms / 1000.0
            result = future.result(timeout=timeout_seconds)
            
            # Record execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self._record_task_execution(task.name, execution_time_ms)
            
            logger.debug(f"Task completed: {task.name} ({execution_time_ms:.1f}ms)")
            return True
            
        except Exception as e:
            # Handle task failure
            task.retry_count += 1
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            if task.retry_count <= task.max_retries:
                # Retry with lower priority
                retry_priority = TaskPriority(min(task.priority.value + 1, TaskPriority.LOW.value))
                self._task_queues[retry_priority].append(task)
                logger.debug(f"Task failed, retrying: {task.name} (attempt {task.retry_count})")
            else:
                logger.warning(f"Task failed permanently: {task.name} - {e}")
            
            self._record_task_execution(task.name, execution_time_ms, failed=True)
            return False
    
    def _record_task_execution(self, task_name: str, execution_time_ms: float, failed: bool = False):
        """Record task execution metrics."""
        if task_name not in self._task_execution_times:
            self._task_execution_times[task_name] = []
        
        # Keep last 50 execution times per task
        timings = self._task_execution_times[task_name]
        timings.append(execution_time_ms if not failed else -execution_time_ms)
        if len(timings) > 50:
            self._task_execution_times[task_name] = timings[-50:]
    
    def _calculate_adaptive_delay(self) -> float:
        """Calculate adaptive delay between processing cycles."""
        base_delay = 100  # 100ms base delay
        
        # Increase delay based on throttling level
        throttle_multiplier = [1.0, 2.0, 4.0, 8.0][self._throttle_level]
        
        # Adjust based on recent CPU usage
        if len(self._cpu_snapshots) >= 5:
            recent_cpu = [s.cpu_percent for s in list(self._cpu_snapshots)[-5:]]
            avg_cpu = sum(recent_cpu) / len(recent_cpu)
            
            if avg_cpu > self.target_cpu_percent:
                cpu_multiplier = 1 + (avg_cpu - self.target_cpu_percent) * 0.2
            else:
                cpu_multiplier = 1.0
        else:
            cpu_multiplier = 1.0
        
        # Calculate final delay
        delay = base_delay * throttle_multiplier * cpu_multiplier
        
        # Clamp to reasonable bounds
        return max(50.0, min(5000.0, delay))  # 50ms to 5s
    
    def _optimize_scheduling_parameters(self):
        """Optimize scheduling parameters based on performance history."""
        if len(self._cpu_snapshots) < 10:
            return
        
        # Analyze recent CPU usage
        recent_cpu = [s.cpu_percent for s in list(self._cpu_snapshots)[-20:]]
        avg_cpu = sum(recent_cpu) / len(recent_cpu)
        
        # Adjust batch size based on performance
        if avg_cpu < self.target_cpu_percent * 0.8:
            # CPU usage is low, can increase batch size
            self._current_batch_size = min(4, self._current_batch_size + 1)
        elif avg_cpu > self.target_cpu_percent * 1.2:
            # CPU usage is high, decrease batch size
            self._current_batch_size = max(1, self._current_batch_size - 1)
        
        logger.debug(f"Optimized batch size: {self._current_batch_size} (avg CPU: {avg_cpu:.1f}%)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler performance statistics."""
        current_snapshot = self._take_cpu_snapshot()
        
        # Queue statistics
        queue_stats = {}
        total_pending = 0
        for priority in TaskPriority:
            count = len(self._task_queues[priority])
            queue_stats[priority.name.lower()] = count
            total_pending += count
        
        # CPU trend analysis
        if len(self._cpu_snapshots) >= 5:
            recent_cpu = [s.cpu_percent for s in list(self._cpu_snapshots)[-10:]]
            avg_cpu = sum(recent_cpu) / len(recent_cpu)
            cpu_trend = "stable"
            if recent_cpu[-1] > recent_cpu[0] + 1.0:
                cpu_trend = "increasing"
            elif recent_cpu[-1] < recent_cpu[0] - 1.0:
                cpu_trend = "decreasing"
        else:
            avg_cpu = current_snapshot.cpu_percent
            cpu_trend = "unknown"
        
        # Task execution statistics
        task_stats = {}
        for task_name, timings in self._task_execution_times.items():
            successful_timings = [t for t in timings if t > 0]
            failed_count = len([t for t in timings if t < 0])
            
            if successful_timings:
                task_stats[task_name] = {
                    "total_executions": len(timings),
                    "successful": len(successful_timings),
                    "failed": failed_count,
                    "avg_duration_ms": round(sum(successful_timings) / len(successful_timings), 1),
                    "success_rate": round((len(successful_timings) / len(timings)) * 100, 1)
                }
        
        return {
            "cpu": {
                "current_percent": round(current_snapshot.cpu_percent, 1),
                "target_percent": self.target_cpu_percent,
                "avg_percent": round(avg_cpu, 1),
                "trend": cpu_trend,
                "throttle_level": self._throttle_level
            },
            "scheduling": {
                "is_running": self._is_running,
                "current_batch_size": self._current_batch_size,
                "total_pending_tasks": total_pending,
                "queue_breakdown": queue_stats,
                "active_threads": current_snapshot.active_threads
            },
            "tasks": task_stats,
            "performance": {
                "snapshots_count": len(self._cpu_snapshots),
                "load_avg": current_snapshot.load_avg,
                "cpu_count": current_snapshot.cpu_count
            }
        }


class CPUOptimizer:
    """
    Main CPU optimizer coordinating adaptive scheduling and resource management
    to maintain <5% background CPU usage.
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize CPU optimizer."""
        self.config = config or ContextCleanerConfig.from_env()
        
        # CPU targets
        self.target_cpu_percent = 3.0  # Target <5%, aim for 3%
        self.critical_cpu_percent = 8.0  # Critical threshold
        
        # Adaptive scheduler
        self._scheduler = AdaptiveScheduler(
            max_workers=2,
            target_cpu_percent=self.target_cpu_percent
        )
        
        # Resource monitoring
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Performance tracking
        self._performance_history: deque = deque(maxlen=100)
        self._optimization_count = 0
        
        logger.info(f"CPU optimizer initialized (target: {self.target_cpu_percent}%)")
    
    def start(self):
        """Start CPU optimization system."""
        self._scheduler.start()
        
        self._is_monitoring = True
        self._stop_monitoring.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop, 
            daemon=True, 
            name="CPUOptimizer"
        )
        self._monitor_thread.start()
        
        logger.info("CPU optimizer started")
    
    def stop(self):
        """Stop CPU optimization system."""
        self._is_monitoring = False
        self._stop_monitoring.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3.0)
        
        self._scheduler.stop()
        logger.info("CPU optimizer stopped")
    
    def schedule_background_task(self, name: str, func: Callable, *args, 
                                priority: TaskPriority = TaskPriority.MEDIUM,
                                max_duration_ms: int = 500, **kwargs):
        """
        Schedule a background task with CPU-aware execution.
        
        Args:
            name: Task identifier
            func: Function to execute
            args: Positional arguments  
            priority: Task priority level
            max_duration_ms: Maximum execution time
            kwargs: Keyword arguments
        """
        self._scheduler.schedule_task(
            name=name,
            func=func,
            *args,
            priority=priority,
            max_duration_ms=max_duration_ms,
            **kwargs
        )
    
    def _monitoring_loop(self):
        """Monitor CPU usage and trigger optimizations."""
        while not self._stop_monitoring.is_set():
            try:
                # Get scheduler stats (includes CPU measurement)
                stats = self._scheduler.get_stats()
                current_cpu = stats["cpu"]["current_percent"]
                
                # Record performance
                self._performance_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": current_cpu,
                    "throttle_level": stats["cpu"]["throttle_level"],
                    "pending_tasks": stats["scheduling"]["total_pending_tasks"]
                })
                
                # Trigger additional optimizations if needed
                if current_cpu > self.critical_cpu_percent:
                    logger.warning(f"Critical CPU usage: {current_cpu:.1f}%")
                    self._emergency_optimization()
                
                # Long-term monitoring interval (60 seconds)
                self._stop_monitoring.wait(timeout=60.0)
                
            except Exception as e:
                logger.warning(f"CPU monitoring error: {e}")
                self._stop_monitoring.wait(timeout=120.0)
    
    def _emergency_optimization(self):
        """Emergency CPU optimization for critical situations."""
        self._optimization_count += 1
        logger.warning("Performing emergency CPU optimization")
        
        # Clear low and medium priority task queues
        for priority in [TaskPriority.LOW, TaskPriority.MEDIUM]:
            queue = self._scheduler._task_queues[priority]
            cleared_count = len(queue)
            queue.clear()
            if cleared_count > 0:
                logger.debug(f"Cleared {cleared_count} {priority.name} priority tasks")
        
        # Force garbage collection to free resources
        import gc
        collected = gc.collect()
        logger.debug(f"Emergency GC freed {collected} objects")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive CPU performance report."""
        scheduler_stats = self._scheduler.get_stats()
        
        # Calculate performance trends
        if len(self._performance_history) >= 10:
            recent_history = list(self._performance_history)[-20:]
            cpu_values = [h["cpu_percent"] for h in recent_history]
            avg_cpu = sum(cpu_values) / len(cpu_values)
            max_cpu = max(cpu_values)
            
            # Calculate trend
            first_half = cpu_values[:len(cpu_values)//2]
            second_half = cpu_values[len(cpu_values)//2:]
            trend_direction = "stable"
            if sum(second_half) / len(second_half) > sum(first_half) / len(first_half) + 0.5:
                trend_direction = "increasing"
            elif sum(second_half) / len(second_half) < sum(first_half) / len(first_half) - 0.5:
                trend_direction = "decreasing"
        else:
            avg_cpu = scheduler_stats["cpu"]["current_percent"]
            max_cpu = avg_cpu
            trend_direction = "unknown"
        
        # Performance health score
        health_score = self._calculate_cpu_health(scheduler_stats["cpu"]["current_percent"], avg_cpu)
        
        # Recommendations
        recommendations = self._generate_cpu_recommendations(scheduler_stats, avg_cpu, max_cpu)
        
        return {
            "summary": {
                "current_cpu_percent": scheduler_stats["cpu"]["current_percent"],
                "target_cpu_percent": self.target_cpu_percent,
                "avg_cpu_percent": round(avg_cpu, 1),
                "max_cpu_percent": round(max_cpu, 1),
                "health_score": health_score,
                "trend": trend_direction
            },
            "scheduler": scheduler_stats,
            "optimization": {
                "emergency_optimizations": self._optimization_count,
                "monitoring_active": self._is_monitoring,
                "performance_samples": len(self._performance_history)
            },
            "recommendations": recommendations
        }
    
    def _calculate_cpu_health(self, current_cpu: float, avg_cpu: float) -> int:
        """Calculate CPU health score (0-100)."""
        score = 100
        
        # Current usage penalty
        if current_cpu > self.target_cpu_percent:
            excess = current_cpu - self.target_cpu_percent
            score -= min(40, excess * 8)  # Significant penalty for high current usage
        
        # Average usage penalty
        if avg_cpu > self.target_cpu_percent:
            excess = avg_cpu - self.target_cpu_percent
            score -= min(30, excess * 6)
        
        # Critical usage penalty
        if current_cpu > self.critical_cpu_percent:
            score -= 20
        
        return max(0, int(score))
    
    def _generate_cpu_recommendations(self, stats: Dict[str, Any], avg_cpu: float, 
                                    max_cpu: float) -> List[str]:
        """Generate CPU optimization recommendations."""
        recommendations = []
        
        current_cpu = stats["cpu"]["current_percent"]
        pending_tasks = stats["scheduling"]["total_pending_tasks"]
        throttle_level = stats["cpu"]["throttle_level"]
        
        # High CPU usage
        if current_cpu > self.target_cpu_percent:
            recommendations.append(
                f"Current CPU usage ({current_cpu:.1f}%) exceeds target. "
                f"Consider reducing background task frequency or enabling more aggressive throttling."
            )
        
        # High average usage
        if avg_cpu > self.target_cpu_percent:
            recommendations.append(
                f"Average CPU usage ({avg_cpu:.1f}%) above target. "
                f"System may benefit from task queue optimization or worker reduction."
            )
        
        # Task queue buildup
        if pending_tasks > 50:
            recommendations.append(
                f"Large task queue ({pending_tasks} pending). "
                f"Consider increasing task timeout limits or worker threads."
            )
        
        # Throttling active
        if throttle_level > 0:
            throttle_names = ["none", "light", "moderate", "aggressive"]
            recommendations.append(
                f"CPU throttling active ({throttle_names[throttle_level]}). "
                f"Background processing is automatically reduced."
            )
        
        # Positive feedback
        if current_cpu <= self.target_cpu_percent and avg_cpu <= self.target_cpu_percent:
            recommendations.append(
                "CPU usage is within optimal ranges. Background processing is efficient."
            )
        
        return recommendations
    
    def force_optimization(self):
        """Force immediate CPU optimization."""
        logger.info("Forcing CPU optimization")
        self._emergency_optimization()
        return self._scheduler.get_stats()