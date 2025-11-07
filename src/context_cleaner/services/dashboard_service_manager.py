"""
Dashboard Service Manager with Singleton Pattern and Process Orchestration

⚠️  DEPRECATED: This module is deprecated as of Phase 2 modular refactoring.
Dashboard singleton enforcement has been consolidated into ServiceOrchestrator
to eliminate service management redundancy and leverage unified infrastructure.

Use ServiceOrchestrator.ensure_singleton_dashboard() instead.

LEGACY FUNCTIONALITY (for backward compatibility):
This module provides comprehensive dashboard service management to prevent the port conflict
chaos caused by dozens of competing dashboard instances. It implements:

- Singleton pattern for dashboard instances
- Process discovery and cleanup capabilities
- Integration with existing PortConflictManager
- Lock files and PID tracking for race condition prevention
- Graceful shutdown of competing instances
- Service health monitoring and validation

Key Features:
- Detects all existing dashboard processes using various startup patterns
- Gracefully terminates competing instances with SIGTERM before SIGKILL
- Uses PortConflictManager for intelligent port selection
- Provides comprehensive logging and error handling
- Integrates with ServiceOrchestrator architecture
- Maintains state persistence through lock files
"""

import asyncio
import fcntl
import json
import logging
import os
import psutil
import re
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from threading import Lock

from .port_conflict_manager import PortConflictManager, PortConflictStrategy
from .process_registry import get_process_registry, ProcessEntry
from context_cleaner.api.models import create_error_response


class DashboardState(Enum):
    """Dashboard service states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    CONFLICT_DETECTED = "conflict_detected"
    CLEANUP_IN_PROGRESS = "cleanup_in_progress"


class ProcessKillMethod(Enum):
    """Methods for terminating dashboard processes."""

    GRACEFUL = "graceful"  # SIGTERM with timeout
    FORCE = "force"  # SIGKILL immediate
    HYBRID = "hybrid"  # SIGTERM then SIGKILL


@dataclass
class DashboardProcessInfo:
    """Information about a discovered dashboard process."""

    pid: int
    port: int
    host: str
    command_line: str
    start_time: datetime
    process_type: str  # 'cli', 'direct', 'run_command'
    is_accessible: bool = False
    accessibility_error: Optional[str] = None
    cleanup_attempted: bool = False
    cleanup_success: bool = False
    cleanup_error: Optional[str] = None


@dataclass
class DashboardLockInfo:
    """Lock file information for singleton enforcement."""

    lock_file_path: Path
    pid: int
    port: int
    host: str
    start_time: datetime
    dashboard_url: str
    is_valid: bool = True


class DashboardServiceManager:
    """
    Singleton Dashboard Service Manager for Context Cleaner.

    Prevents multiple dashboard instances by:
    1. Discovering all existing dashboard processes
    2. Gracefully terminating competing instances
    3. Using intelligent port selection via PortConflictManager
    4. Managing singleton state through lock files
    5. Providing comprehensive process cleanup and health monitoring
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        config: Optional[Any] = None,
        verbose: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the dashboard service manager."""

        # DEPRECATION WARNING
        import warnings

        warnings.warn(
            "DashboardServiceManager is deprecated. Use ServiceOrchestrator.ensure_singleton_dashboard() instead. "
            "This class will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )

        if self._initialized:
            return

        self.config = config
        self.verbose = verbose
        self.logger = logger or logging.getLogger(__name__)

        # Core state management
        self.current_state = DashboardState.STOPPED
        self.current_dashboard_info: Optional[DashboardProcessInfo] = None
        self.last_cleanup_time: Optional[datetime] = None

        # Lock file management
        self.lock_directory = Path.home() / ".context_cleaner" / "locks"
        self.lock_directory.mkdir(parents=True, exist_ok=True)
        self.dashboard_lock_file = self.lock_directory / "dashboard.lock"
        self.current_lock_handle: Optional[int] = None

        # Process discovery and management
        self.port_conflict_manager = PortConflictManager(
            verbose=verbose, logger=self.logger
        )
        self.process_registry = get_process_registry()
        self.discovered_processes: List[DashboardProcessInfo] = []

        # Dashboard process detection patterns
        self.detection_patterns = [
            # CLI patterns
            r"python.*-m.*src\.context_cleaner\.cli\.main.*dashboard",
            r"python.*-m.*context_cleaner\.cli\.main.*dashboard",
            r"python.*-m.*src\.context_cleaner\.cli\.main.*run.*--dashboard-port",
            r"python.*-m.*context_cleaner\.cli\.main.*run.*--dashboard-port",
            # Direct instantiation patterns
            r"python.*ComprehensiveHealthDashboard",
            r"python.*context_cleaner.*dashboard.*start_server",
            # Generic Context Cleaner dashboard patterns
            r"context_cleaner.*dashboard",
            r"context-cleaner.*dashboard",
        ]

        # Configuration
        self.cleanup_timeout_seconds = 10
        self.port_check_timeout_seconds = 5
        self.max_discovery_attempts = 3
        self.health_check_interval = 30

        # Threading
        self.cleanup_thread: Optional[threading.Thread] = None
        self.health_monitor_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        self._initialized = True

        if self.verbose:
            self.logger.info("Dashboard Service Manager initialized successfully")

    async def ensure_singleton_dashboard(
        self, requested_port: int, host: str = "127.0.0.1", force_cleanup: bool = False
    ) -> Tuple[int, str]:
        """
        Ensure only one dashboard instance is running.

        Args:
            requested_port: The desired port for the dashboard
            host: The host to bind to
            force_cleanup: Force cleanup even if current process is healthy

        Returns:
            Tuple of (actual_port, dashboard_url) for the singleton instance

        Raises:
            RuntimeError: If singleton enforcement fails
        """

        if self.verbose:
            self.logger.info(
                f"🔒 Ensuring singleton dashboard on {host}:{requested_port}"
            )

        try:
            # 1. DISCOVERY PHASE: Find all existing dashboard processes
            await self._discover_dashboard_processes()

            # 2. CONFLICT ANALYSIS PHASE: Determine what needs cleanup
            conflicts = self._analyze_process_conflicts(requested_port, host)

            if self.verbose:
                self.logger.info(
                    f"📊 Discovery results: {len(self.discovered_processes)} processes found, "
                    f"{len(conflicts)} conflicts requiring cleanup"
                )

            # 3. CLEANUP PHASE: Remove conflicting instances
            if conflicts or force_cleanup:
                self.current_state = DashboardState.CLEANUP_IN_PROGRESS
                cleanup_success = await self._cleanup_conflicting_processes(conflicts)

                if not cleanup_success:
                    raise RuntimeError(
                        "Failed to cleanup conflicting dashboard processes"
                    )

                # Brief pause to ensure cleanup is complete
                await asyncio.sleep(2)

            # 4. PORT RESOLUTION PHASE: Find available port using conflict manager
            available_port, port_session = (
                await self.port_conflict_manager.find_available_port(
                    service_name="dashboard",
                    original_port=requested_port,
                    strategy=PortConflictStrategy.HYBRID,
                    max_attempts=15,
                )
            )

            if available_port is None:
                raise RuntimeError(f"No available port found near {requested_port}")

            # 5. LOCK ACQUISITION PHASE: Secure singleton state
            lock_acquired = await self._acquire_dashboard_lock(available_port, host)
            if not lock_acquired:
                raise RuntimeError("Failed to acquire dashboard singleton lock")

            # 6. FINAL VALIDATION PHASE: Ensure clean state
            dashboard_url = f"http://{host}:{available_port}"

            # Update current dashboard info
            self.current_dashboard_info = DashboardProcessInfo(
                pid=os.getpid(),
                port=available_port,
                host=host,
                command_line=" ".join(
                    ["python"] + [arg for arg in __import__("sys").argv]
                ),
                start_time=datetime.now(),
                process_type="managed_singleton",
                is_accessible=False,  # Will be updated when server starts
            )

            self.current_state = DashboardState.STARTING

            if self.verbose:
                self.logger.info(f"✅ Singleton dashboard ready: {dashboard_url}")
                if available_port != requested_port:
                    self.logger.info(
                        f"📝 Port changed from {requested_port} to {available_port} due to conflicts"
                    )

            return available_port, dashboard_url

        except Exception as e:
            self.current_state = DashboardState.FAILED
            self.logger.error(f"❌ Singleton dashboard enforcement failed: {e}")
            raise RuntimeError(f"Dashboard singleton enforcement failed: {e}") from e

    async def _discover_dashboard_processes(self) -> List[DashboardProcessInfo]:
        """
        Discover all running Context Cleaner dashboard processes.

        Returns:
            List of discovered dashboard process information
        """

        if self.verbose:
            self.logger.info("🔍 Discovering existing dashboard processes...")

        self.discovered_processes.clear()
        discovered_count = 0

        try:
            # Iterate through all running processes
            for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
                try:
                    proc_info = proc.info
                    if not proc_info["cmdline"]:
                        continue

                    cmdline = " ".join(proc_info["cmdline"])

                    # Check if this process matches any dashboard pattern
                    is_dashboard = False
                    process_type = "unknown"

                    for pattern in self.detection_patterns:
                        if re.search(pattern, cmdline, re.IGNORECASE):
                            is_dashboard = True

                            # Determine process type
                            if "cli.main" in cmdline:
                                if "--dashboard-port" in cmdline or "run" in cmdline:
                                    process_type = "run_command"
                                else:
                                    process_type = "cli"
                            else:
                                process_type = "direct"
                            break

                    if is_dashboard:
                        # Extract port information
                        port = self._extract_port_from_cmdline(cmdline)
                        host = self._extract_host_from_cmdline(cmdline)

                        if port:
                            dashboard_info = DashboardProcessInfo(
                                pid=proc_info["pid"],
                                port=port,
                                host=host,
                                command_line=cmdline,
                                start_time=datetime.fromtimestamp(
                                    proc_info["create_time"]
                                ),
                                process_type=process_type,
                            )

                            # Check if the dashboard is actually accessible
                            (
                                dashboard_info.is_accessible,
                                dashboard_info.accessibility_error,
                            ) = await self._check_dashboard_accessibility(host, port)

                            self.discovered_processes.append(dashboard_info)
                            discovered_count += 1

                            if self.verbose:
                                status = (
                                    "✅ accessible"
                                    if dashboard_info.is_accessible
                                    else "❌ not accessible"
                                )
                                self.logger.info(
                                    f"   📋 Found PID {dashboard_info.pid} on {host}:{port} ({status})"
                                )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
                except Exception as e:
                    if self.verbose:
                        self.logger.debug(f"Error processing process: {e}")
                    continue

            if self.verbose:
                if discovered_count == 0:
                    self.logger.info("   ✅ No existing dashboard processes found")
                else:
                    self.logger.info(
                        f"   📊 Discovery complete: {discovered_count} dashboard processes found"
                    )

            return self.discovered_processes

        except Exception as e:
            self.logger.error(f"Process discovery failed: {e}")
            return []

    def _analyze_process_conflicts(
        self, requested_port: int, requested_host: str
    ) -> List[DashboardProcessInfo]:
        """
        Analyze discovered processes to identify conflicts requiring cleanup.

        Args:
            requested_port: The port we want to use
            requested_host: The host we want to bind to

        Returns:
            List of processes that conflict and need cleanup
        """

        conflicts = []

        for process_info in self.discovered_processes:
            # Skip our own process
            if process_info.pid == os.getpid():
                continue

            should_cleanup = False

            # Always cleanup if on the exact requested port/host
            if (
                process_info.port == requested_port
                and process_info.host == requested_host
            ):
                should_cleanup = True

            # Also cleanup non-accessible processes (likely zombies)
            elif not process_info.is_accessible:
                should_cleanup = True

            # Cleanup processes on ports in the conflict range
            elif abs(process_info.port - requested_port) <= 5:
                should_cleanup = True

            if should_cleanup:
                conflicts.append(process_info)
                if self.verbose:
                    reason = f"port {process_info.port} conflicts with requested {requested_port}"
                    if not process_info.is_accessible:
                        reason += " (not accessible)"
                    self.logger.info(f"   ⚠️  PID {process_info.pid}: {reason}")

        return conflicts

    async def _cleanup_conflicting_processes(
        self, conflicts: List[DashboardProcessInfo]
    ) -> bool:
        """
        Cleanup conflicting dashboard processes with graceful shutdown.

        Args:
            conflicts: List of processes to cleanup

        Returns:
            True if all cleanups succeeded
        """

        if not conflicts:
            return True

        if self.verbose:
            self.logger.info(
                f"🧹 Cleaning up {len(conflicts)} conflicting processes..."
            )

        cleanup_success = True

        for process_info in conflicts:
            try:
                if self.verbose:
                    self.logger.info(
                        f"   🛑 Terminating PID {process_info.pid} on port {process_info.port}"
                    )

                # Mark cleanup as attempted
                process_info.cleanup_attempted = True

                # Get the process
                try:
                    proc = psutil.Process(process_info.pid)
                except psutil.NoSuchProcess:
                    # Process already gone
                    process_info.cleanup_success = True
                    continue

                # Graceful termination with SIGTERM
                proc.terminate()

                # Wait up to cleanup_timeout_seconds for graceful termination
                try:
                    proc.wait(timeout=self.cleanup_timeout_seconds)
                    process_info.cleanup_success = True

                    if self.verbose:
                        self.logger.info(
                            f"   ✅ Gracefully terminated PID {process_info.pid}"
                        )

                except psutil.TimeoutExpired:
                    # Force kill if graceful termination failed
                    if self.verbose:
                        self.logger.info(
                            f"   🔨 Force killing PID {process_info.pid} (graceful timeout)"
                        )

                    try:
                        proc.kill()
                        proc.wait(timeout=5)
                        process_info.cleanup_success = True
                    except Exception as kill_error:
                        process_info.cleanup_error = str(kill_error)
                        process_info.cleanup_success = False
                        cleanup_success = False

                        if self.verbose:
                            self.logger.error(
                                f"   ❌ Failed to force kill PID {process_info.pid}: {kill_error}"
                            )

                # Unregister from process registry if present
                try:
                    self.process_registry.unregister_process(process_info.pid)
                except Exception as reg_error:
                    if self.verbose:
                        self.logger.debug(
                            f"Registry cleanup error for PID {process_info.pid}: {reg_error}"
                        )

            except Exception as e:
                process_info.cleanup_error = str(e)
                process_info.cleanup_success = False
                cleanup_success = False

                self.logger.error(f"Failed to cleanup PID {process_info.pid}: {e}")

        # Record cleanup time
        self.last_cleanup_time = datetime.now()

        # Brief verification pause
        await asyncio.sleep(1)

        # Verify cleanup success
        still_running = []
        for process_info in conflicts:
            try:
                proc = psutil.Process(process_info.pid)
                if proc.is_running():
                    still_running.append(process_info.pid)
            except psutil.NoSuchProcess:
                # Process is gone, which is what we want
                pass

        if still_running:
            cleanup_success = False
            self.logger.error(f"❌ Failed to cleanup processes: {still_running}")
        elif self.verbose:
            self.logger.info("   ✅ All conflicting processes cleaned up successfully")

        return cleanup_success

    async def _acquire_dashboard_lock(self, port: int, host: str) -> bool:
        """
        Acquire exclusive lock for dashboard singleton.

        Args:
            port: The port the dashboard will use
            host: The host the dashboard will bind to

        Returns:
            True if lock acquired successfully
        """

        try:
            # Create lock info
            lock_info = DashboardLockInfo(
                lock_file_path=self.dashboard_lock_file,
                pid=os.getpid(),
                port=port,
                host=host,
                start_time=datetime.now(),
                dashboard_url=f"http://{host}:{port}",
            )

            # Open lock file for exclusive access
            lock_fd = os.open(
                str(self.dashboard_lock_file),
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o644,
            )

            try:
                # Try to acquire exclusive lock
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write lock information
                lock_data = {
                    "pid": lock_info.pid,
                    "port": lock_info.port,
                    "host": lock_info.host,
                    "start_time": lock_info.start_time.isoformat(),
                    "dashboard_url": lock_info.dashboard_url,
                    "lock_acquired_at": datetime.now().isoformat(),
                }

                os.write(lock_fd, json.dumps(lock_data, indent=2).encode())
                os.fsync(lock_fd)

                # Store lock handle for later release
                self.current_lock_handle = lock_fd

                if self.verbose:
                    self.logger.info(
                        f"🔒 Acquired dashboard lock: {self.dashboard_lock_file}"
                    )

                return True

            except (IOError, OSError) as lock_error:
                # Lock acquisition failed
                os.close(lock_fd)

                if self.verbose:
                    self.logger.warning(
                        f"Failed to acquire dashboard lock: {lock_error}"
                    )

                return False

        except Exception as e:
            self.logger.error(f"Lock acquisition error: {e}")
            return False

    def release_dashboard_lock(self) -> bool:
        """
        Release the dashboard singleton lock.

        Returns:
            True if lock released successfully
        """

        try:
            if self.current_lock_handle is not None:
                try:
                    fcntl.flock(self.current_lock_handle, fcntl.LOCK_UN)
                    os.close(self.current_lock_handle)
                    self.current_lock_handle = None
                except (IOError, OSError):
                    pass  # Lock might already be released

            # Remove lock file
            try:
                self.dashboard_lock_file.unlink(missing_ok=True)
            except Exception:
                pass

            if self.verbose:
                self.logger.info("🔓 Released dashboard lock")

            return True

        except Exception as e:
            self.logger.error(f"Lock release error: {e}")
            return False

    async def _check_dashboard_accessibility(
        self, host: str, port: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a dashboard is accessible on the given host:port.

        Args:
            host: Host to check
            port: Port to check

        Returns:
            Tuple of (is_accessible, error_message)
        """

        try:
            # 1. Check if port is listening
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.port_check_timeout_seconds)

            result = sock.connect_ex((host, port))
            sock.close()

            if result != 0:
                return False, f"Port {port} not listening"

            # 2. Check HTTP response (basic)
            try:
                import urllib.request
                import urllib.error

                url = f"http://{host}:{port}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "DashboardServiceManager/1.0"}
                )

                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        return True, None
                    else:
                        return False, f"HTTP {response.status}"

            except urllib.error.URLError as http_error:
                # Server might be starting or have different endpoints
                if "Connection refused" in str(http_error):
                    return False, "Connection refused"
                else:
                    # Server is responding but might not be fully ready
                    return True, None

        except Exception as e:
            return False, str(e)

    def _extract_port_from_cmdline(self, cmdline: str) -> Optional[int]:
        """Extract port number from command line."""

        # Look for --port parameter
        port_patterns = [
            r"--port[\s=](\d+)",
            r"--dashboard-port[\s=](\d+)",
            r"-p[\s=](\d+)",
        ]

        for pattern in port_patterns:
            match = re.search(pattern, cmdline)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

        # Default dashboard ports if no explicit port found
        if "dashboard" in cmdline.lower():
            return 8110  # Default dashboard port

        return None

    def _extract_host_from_cmdline(self, cmdline: str) -> str:
        """Extract host from command line, default to 127.0.0.1."""

        host_patterns = [r"--host[\s=]([^\s]+)", r"-h[\s=]([^\s]+)"]

        for pattern in host_patterns:
            match = re.search(pattern, cmdline)
            if match:
                return match.group(1)

        return "127.0.0.1"  # Default host

    def mark_dashboard_running(self, port: int, host: str = "127.0.0.1") -> bool:
        """
        Mark the current dashboard as running and accessible.

        Args:
            port: Port the dashboard is running on
            host: Host the dashboard is bound to

        Returns:
            True if marked successfully
        """

        try:
            self.current_state = DashboardState.RUNNING

            if self.current_dashboard_info:
                self.current_dashboard_info.port = port
                self.current_dashboard_info.host = host
                self.current_dashboard_info.is_accessible = True
                self.current_dashboard_info.accessibility_error = None

            # Register in process registry
            try:
                process_entry = ProcessEntry(
                    pid=os.getpid(),
                    command_line=" ".join(__import__("sys").argv),
                    service_type="dashboard",
                    start_time=datetime.now(),
                    registration_time=datetime.now(),
                    port=port,
                    status="running",
                    registration_source="dashboard_service_manager",
                )
                self.process_registry.register_process(process_entry)
            except Exception as reg_error:
                if self.verbose:
                    self.logger.debug(
                        f"Process registry registration error: {reg_error}"
                    )

            if self.verbose:
                self.logger.info(f"✅ Dashboard marked as running on {host}:{port}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to mark dashboard as running: {e}")
            return False

    def get_dashboard_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of dashboard service management.

        Returns:
            Dictionary with current status information
        """

        status = {
            "singleton_manager": {
                "state": self.current_state.value,
                "lock_file": str(self.dashboard_lock_file),
                "lock_acquired": self.current_lock_handle is not None,
                "last_cleanup_time": (
                    self.last_cleanup_time.isoformat()
                    if self.last_cleanup_time
                    else None
                ),
                "initialized_at": datetime.now().isoformat(),
            },
            "current_dashboard": None,
            "discovered_processes": [],
            "cleanup_summary": {
                "total_discovered": len(self.discovered_processes),
                "cleanup_attempted": 0,
                "cleanup_successful": 0,
                "cleanup_failed": 0,
            },
            "port_conflict_manager": {},
        }

        # Current dashboard info
        if self.current_dashboard_info:
            status["current_dashboard"] = {
                "pid": self.current_dashboard_info.pid,
                "port": self.current_dashboard_info.port,
                "host": self.current_dashboard_info.host,
                "url": f"http://{self.current_dashboard_info.host}:{self.current_dashboard_info.port}",
                "start_time": self.current_dashboard_info.start_time.isoformat(),
                "process_type": self.current_dashboard_info.process_type,
                "is_accessible": self.current_dashboard_info.is_accessible,
                "accessibility_error": self.current_dashboard_info.accessibility_error,
            }

        # Discovered processes info
        for process_info in self.discovered_processes:
            process_status = {
                "pid": process_info.pid,
                "port": process_info.port,
                "host": process_info.host,
                "process_type": process_info.process_type,
                "start_time": process_info.start_time.isoformat(),
                "is_accessible": process_info.is_accessible,
                "accessibility_error": process_info.accessibility_error,
                "cleanup_attempted": process_info.cleanup_attempted,
                "cleanup_success": process_info.cleanup_success,
                "cleanup_error": process_info.cleanup_error,
            }
            status["discovered_processes"].append(process_status)

            # Update cleanup summary
            if process_info.cleanup_attempted:
                status["cleanup_summary"]["cleanup_attempted"] += 1
                if process_info.cleanup_success:
                    status["cleanup_summary"]["cleanup_successful"] += 1
                else:
                    status["cleanup_summary"]["cleanup_failed"] += 1

        # Port conflict manager stats
        try:
            status["port_conflict_manager"] = (
                self.port_conflict_manager.get_retry_statistics()
            )
        except Exception as e:
            status["port_conflict_manager"] = {"error": str(e)}

        return status

    def cleanup_all_dashboards(self, exclude_current: bool = True) -> Dict[str, Any]:
        """
        Cleanup all discovered dashboard processes.

        Args:
            exclude_current: Whether to exclude the current process from cleanup

        Returns:
            Dictionary with cleanup results
        """

        if self.verbose:
            self.logger.info("🧹 Starting comprehensive dashboard cleanup...")

        # Run discovery first to get latest state
        try:
            asyncio.run(self._discover_dashboard_processes())
        except Exception as e:
            self.logger.error(f"Failed to discover processes for cleanup: {e}")
            raise create_error_response(
                f"Process discovery failed: {str(e)}",
                "PROCESS_DISCOVERY_ERROR",
                500,
                {"details": str(e)},
            )

        # Filter processes to cleanup
        processes_to_cleanup = []
        for process_info in self.discovered_processes:
            if exclude_current and process_info.pid == os.getpid():
                continue
            processes_to_cleanup.append(process_info)

        if not processes_to_cleanup:
            return {
                "message": "No dashboard processes found for cleanup",
                "cleaned_count": 0,
                "total_found": len(self.discovered_processes),
            }

        # Perform cleanup
        try:
            cleanup_success = asyncio.run(
                self._cleanup_conflicting_processes(processes_to_cleanup)
            )

            cleanup_results = {
                "cleanup_requested": len(processes_to_cleanup),
                "cleanup_successful": sum(
                    1 for p in processes_to_cleanup if p.cleanup_success
                ),
                "cleanup_failed": sum(
                    1
                    for p in processes_to_cleanup
                    if p.cleanup_attempted and not p.cleanup_success
                ),
                "overall_success": cleanup_success,
                "timestamp": datetime.now().isoformat(),
                "processes": [],
            }

            for process_info in processes_to_cleanup:
                cleanup_results["processes"].append(
                    {
                        "pid": process_info.pid,
                        "port": process_info.port,
                        "cleanup_success": process_info.cleanup_success,
                        "cleanup_error": process_info.cleanup_error,
                    }
                )

            return cleanup_results

        except Exception as e:
            raise create_error_response(
                f"Cleanup operation failed: {str(e)}",
                "CLEANUP_OPERATION_ERROR",
                500,
                {"details": str(e)},
            )

    def shutdown(self) -> bool:
        """
        Shutdown the dashboard service manager.

        Returns:
            True if shutdown successful
        """

        try:
            if self.verbose:
                self.logger.info("🛑 Shutting down Dashboard Service Manager...")

            # Signal shutdown to background threads
            self._shutdown_event.set()

            # Wait for background threads to finish
            if self.cleanup_thread and self.cleanup_thread.is_alive():
                self.cleanup_thread.join(timeout=5)

            if self.health_monitor_thread and self.health_monitor_thread.is_alive():
                self.health_monitor_thread.join(timeout=5)

            # Release the dashboard lock
            self.release_dashboard_lock()

            # Update state
            self.current_state = DashboardState.STOPPED

            if self.verbose:
                self.logger.info("✅ Dashboard Service Manager shutdown complete")

            return True

        except Exception as e:
            self.logger.error(f"Shutdown error: {e}")
            return False


# Convenience functions for external use
_global_dashboard_manager: Optional[DashboardServiceManager] = None


def get_dashboard_service_manager(
    config: Optional[Any] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> DashboardServiceManager:
    """
    Get or create the global dashboard service manager instance.

    Args:
        config: Configuration object
        verbose: Enable verbose logging
        logger: Logger instance

    Returns:
        DashboardServiceManager singleton instance
    """
    global _global_dashboard_manager

    if _global_dashboard_manager is None:
        _global_dashboard_manager = DashboardServiceManager(
            config=config, verbose=verbose, logger=logger
        )

    return _global_dashboard_manager


async def ensure_singleton_dashboard(
    requested_port: int,
    host: str = "127.0.0.1",
    config: Optional[Any] = None,
    verbose: bool = False,
    force_cleanup: bool = False,
) -> Tuple[int, str]:
    """
    Convenience function to ensure singleton dashboard.

    Args:
        requested_port: Desired port for dashboard
        host: Host to bind to
        config: Configuration object
        verbose: Enable verbose logging
        force_cleanup: Force cleanup of existing processes

    Returns:
        Tuple of (actual_port, dashboard_url)
    """

    manager = get_dashboard_service_manager(config=config, verbose=verbose)
    return await manager.ensure_singleton_dashboard(
        requested_port=requested_port, host=host, force_cleanup=force_cleanup
    )


def cleanup_all_dashboard_processes(
    exclude_current: bool = True, verbose: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to cleanup all dashboard processes.

    Args:
        exclude_current: Whether to exclude current process
        verbose: Enable verbose logging

    Returns:
        Dictionary with cleanup results
    """

    manager = get_dashboard_service_manager(verbose=verbose)
    return manager.cleanup_all_dashboards(exclude_current=exclude_current)
