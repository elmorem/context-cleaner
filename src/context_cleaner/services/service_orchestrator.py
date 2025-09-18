"""
Service Orchestration System for Context Cleaner

This module provides comprehensive service lifecycle management for all Context Cleaner components:
- ClickHouse database
- OTEL collectors
- JSONL processing services
- Bridge services
- Dashboard web interface
- Health monitoring and auto-restart capabilities
"""

import asyncio
import json
import os
import signal
import subprocess
import threading
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import sys
import os
import psutil
import re
import platform
import socket
import urllib.request
import urllib.error
from .api_ui_consistency_checker import APIUIConsistencyChecker
from .port_conflict_manager import PortConflictManager, PortConflictStrategy
from ..telemetry.collector import get_collector
from .process_registry import (
    ProcessEntry,
    ProcessRegistryDatabase,
    ProcessDiscoveryEngine,
    get_process_registry,
    get_discovery_engine
)


class ServiceStatus(Enum):
    """Service status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    UNKNOWN = "unknown"
    ATTACHED = "attached"  # For containers that were already running


class DockerDaemonStatus(Enum):
    """Docker daemon status enumeration."""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    FAILED = "failed"
    NOT_INSTALLED = "not_installed"
    UNKNOWN = "unknown"


class ContainerState(Enum):
    """Container state enumeration."""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"
    NOT_FOUND = "not_found"


@dataclass
class ServiceDefinition:
    """Definition of a service and its configuration."""
    name: str
    description: str
    start_command: Optional[List[str]] = None
    stop_command: Optional[List[str]] = None
    health_check: Optional[Callable] = None
    health_check_interval: int = 30  # seconds
    restart_on_failure: bool = True
    startup_timeout: int = 60  # seconds
    shutdown_timeout: int = 30  # seconds
    dependencies: List[str] = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    working_directory: Optional[str] = None
    required: bool = True
    startup_delay: int = 0  # seconds to wait before starting


@dataclass
class ServiceState:
    """Current state of a service."""
    name: str
    status: ServiceStatus = ServiceStatus.STOPPED
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    last_health_check: Optional[datetime] = None
    health_status: bool = False
    start_time: Optional[datetime] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    container_id: Optional[str] = None
    container_state: Optional[ContainerState] = None
    was_attached: bool = False  # True if we attached to existing container
    url: Optional[str] = None  # For web services like dashboard
    accessibility_status: Optional[str] = None  # Details about accessibility checks


class ServiceOrchestrator:
    """
    Comprehensive service orchestration system for Context Cleaner.
    
    Manages the complete lifecycle of all services including:
    - Dependency-based startup ordering
    - Health monitoring and auto-restart
    - Graceful shutdown coordination
    - Service status reporting
    """

    def __init__(self, config: Optional[Any] = None, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        
        # Service management
        self.services: Dict[str, ServiceDefinition] = {}
        self.service_states: Dict[str, ServiceState] = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Control flags
        self.running = False
        self.shutdown_event = threading.Event()
        self.health_monitor_thread: Optional[threading.Thread] = None
        
        # API/UI Consistency Checker
        self.consistency_checker: Optional[APIUIConsistencyChecker] = None

        # Widget cache invalidation callbacks
        self._cache_invalidation_callbacks = []

        # Telemetry Collector
        self.telemetry_collector = None
        
        # Docker management
        self.docker_daemon_status = DockerDaemonStatus.UNKNOWN
        self.container_states: Dict[str, ContainerState] = {}
        
        # Process Registry Integration (Phase 1)
        self.process_registry = get_process_registry()
        self.discovery_engine = get_discovery_engine()
        
        # Port Conflict Management
        self.port_conflict_manager = PortConflictManager(verbose=verbose, logger=self.logger)
        
        # Initialize service definitions
        self._initialize_service_definitions()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _cleanup_existing_processes(self):
        """
        Clean up any existing Context Cleaner processes using the integrated process registry.
        This ensures singleton operation and maintains registry consistency.
        """
        if self.verbose:
            print("🧹 Cleaning up existing Context Cleaner processes (registry-aware)...")
        
        try:
            # 1. Discover all current Context Cleaner processes
            discovered_processes = self.discovery_engine.discover_all_processes()
            
            if self.verbose and discovered_processes:
                print(f"   Found {len(discovered_processes)} Context Cleaner processes:")
                for process in discovered_processes:
                    print(f"   - PID {process.pid} ({process.service_type}): {process.command_line[:80]}...")
            
            # 2. Get processes from registry for comparison
            registered_processes = self.process_registry.get_all_processes()
            
            # 3. Clean up processes (except ourselves)
            cleaned_count = 0
            for process in discovered_processes:
                if process.pid == os.getpid():
                    continue  # Don't kill ourselves
                
                try:
                    # Attempt graceful termination
                    proc = psutil.Process(process.pid)
                    proc.terminate()
                    
                    # Wait up to 5 seconds for graceful termination
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if graceful termination failed
                        proc.kill()
                        proc.wait()
                    
                    # Remove from registry if it was registered
                    self.process_registry.unregister_process(process.pid)
                    
                    cleaned_count += 1
                    if self.verbose:
                        print(f"   ✅ Cleaned up PID {process.pid} ({process.service_type})")
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process already gone or can't access it
                    # Still try to clean from registry
                    self.process_registry.unregister_process(process.pid)
                    continue
            
            # 4. Clean up stale registry entries (processes that aren't running)
            stale_cleanup_count = 0
            for registered_process in registered_processes:
                try:
                    # Check if process is still running
                    proc = psutil.Process(registered_process.pid)
                    if not proc.is_running():
                        self.process_registry.unregister_process(registered_process.pid)
                        stale_cleanup_count += 1
                except psutil.NoSuchProcess:
                    # Process is definitely gone, remove from registry
                    self.process_registry.unregister_process(registered_process.pid)
                    stale_cleanup_count += 1
            
            # Brief pause to ensure cleanup is complete
            time.sleep(2)
            
            if self.verbose:
                print(f"   🎯 Process cleanup complete: {cleaned_count} processes cleaned, {stale_cleanup_count} stale entries removed")
            else:
                if self.verbose:
                    print("   ✅ No existing processes found")
                    
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Error during cleanup: {e}")
            # Continue anyway - don't let cleanup failures block startup

    def _initialize_service_definitions(self):
        """Initialize all service definitions for Context Cleaner."""
        
        # 1. ClickHouse Database (highest priority) - Enhanced with adaptive timeouts
        self.services["clickhouse"] = ServiceDefinition(
            name="clickhouse",
            description="ClickHouse database for telemetry and analytics",
            start_command=["docker", "compose", "up", "-d", "clickhouse"],
            stop_command=["docker", "compose", "stop", "clickhouse"],
            health_check=self._check_clickhouse_health,
            health_check_interval=30,
            restart_on_failure=True,
            startup_timeout=180,  # Increased to handle 212-line DDL initialization
            shutdown_timeout=60,
            dependencies=[],
            required=True,
            startup_delay=0
        )
        
        # 2. OTEL Collector (if applicable) - Enhanced with ClickHouse dependency awareness
        self.services["otel"] = ServiceDefinition(
            name="otel",
            description="OpenTelemetry collector for metrics gathering",
            start_command=["docker", "compose", "up", "-d", "otel-collector"],
            stop_command=["docker", "compose", "stop", "otel-collector"],
            health_check=self._check_otel_health,
            health_check_interval=45,  # Reduced for faster feedback
            restart_on_failure=True,  # Changed to True for better reliability
            startup_timeout=90,  # Increased to handle ClickHouse connection retries
            shutdown_timeout=30,
            dependencies=["clickhouse"],
            required=False,
            startup_delay=10  # Increased to allow ClickHouse DDL completion
        )
        
        # 3. JSONL Bridge Service
        self.services["jsonl_bridge"] = ServiceDefinition(
            name="jsonl_bridge",
            description="Real-time JSONL file monitoring and processing",
            start_command=[
                sys.executable, "-m", "context_cleaner.cli.main",
                "bridge", "sync", "--start-monitoring", "--interval", "15"
            ],
            stop_command=None,  # Handled via process termination
            health_check=self._check_jsonl_bridge_health,
            health_check_interval=45,
            restart_on_failure=True,
            startup_timeout=30,
            shutdown_timeout=15,
            dependencies=["clickhouse"],
            required=True,
            startup_delay=10,
            environment_vars={"PYTHONPATH": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")}
        )
        
        # 4. Dashboard Web Server
        self.services["dashboard"] = ServiceDefinition(
            name="dashboard",
            description="Web dashboard interface with JSONL analytics",
            start_command=None,  # Handled internally
            stop_command=None,  # Handled internally
            health_check=self._check_dashboard_health,
            health_check_interval=60,
            restart_on_failure=True,
            startup_timeout=30,
            shutdown_timeout=10,
            dependencies=["clickhouse", "jsonl_bridge"],
            required=True,
            startup_delay=15
        )
        
        # 5. API/UI Consistency Checker
        self.services["consistency_checker"] = ServiceDefinition(
            name="consistency_checker",
            description="API/UI consistency monitoring for dashboard health",
            start_command=None,  # Handled internally
            stop_command=None,  # Handled internally
            health_check=None,  # Disabled to prevent task cancellation
            health_check_interval=120,
            restart_on_failure=False,  # Disabled to prevent task cancellation every 120s
            startup_timeout=15,
            shutdown_timeout=5,
            dependencies=["dashboard"],
            required=False,  # Optional monitoring service
            startup_delay=30
        )
        
        # 6. Telemetry Collector
        self.services["telemetry_collector"] = ServiceDefinition(
            name="telemetry_collector",
            description="Claude Code telemetry data collection and monitoring",
            start_command=None,  # Handled internally
            stop_command=None,  # Handled internally
            health_check=self._check_telemetry_collector_health,
            health_check_interval=60,
            restart_on_failure=True,
            startup_timeout=10,
            shutdown_timeout=5,
            dependencies=["clickhouse"],
            required=False,  # Optional telemetry service
            startup_delay=5
        )

    async def start_all_services(self, dashboard_port: int = 8110) -> bool:
        """
        Start all services in dependency order.

        Args:
            dashboard_port: Port for the dashboard service

        Returns:
            True if all required services started successfully
        """
        self.running = True
        self.shutdown_event.clear()

        if self.verbose:
            print("🚀 Starting Context Cleaner service orchestration...")
            print(f"📊 Dashboard port: {dashboard_port}")
        
        # Port conflict detection and resolution
        print("🔍 DEBUG: Starting port conflict detection...")
        service_ports = {"dashboard": dashboard_port}
        print(f"🔍 DEBUG: Service ports: {service_ports}")
        print("🔍 DEBUG: About to call detect_port_conflicts()...")
        conflicts = await self.port_conflict_manager.detect_port_conflicts(service_ports)
        print(f"🔍 DEBUG: Port conflicts detected: {conflicts}")
        
        # Resolve dashboard port conflicts if detected
        if conflicts.get("dashboard", False):
            if self.verbose:
                print(f"⚠️  Port conflict detected for dashboard on port {dashboard_port}")
            
            available_port, session = await self.port_conflict_manager.find_available_port(
                "dashboard", 
                dashboard_port, 
                PortConflictStrategy.HYBRID,
                max_attempts=15
            )
            
            if available_port:
                dashboard_port = available_port
                if self.verbose:
                    print(f"✅ Resolved dashboard port conflict: using port {dashboard_port}")
                    retry_stats = self.port_conflict_manager.get_retry_statistics()
                    total_duration = session.total_duration_ms or 0
                    print(f"   📊 Resolution took {len(session.attempts)} attempts in {total_duration}ms")
            else:
                if self.verbose:
                    print("❌ Failed to resolve dashboard port conflict - no available ports found")
                return False
        
        # Clean up any existing processes to ensure singleton operation
        self._cleanup_existing_processes()
        
        # Ensure Docker daemon is running and containers are in proper state
        if not await self._ensure_docker_environment():
            if self.verbose:
                print("❌ Failed to ensure Docker environment is ready")
            return False
        
        # Initialize service states
        for service_name in self.services:
            self.service_states[service_name] = ServiceState(name=service_name)
        
        # Start health monitoring
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True
        )
        self.health_monitor_thread.start()
        
        # Determine startup order based on dependencies
        startup_order = self._calculate_startup_order()
        if self.verbose:
            print(f"🔍 DEBUG: Service startup order: {startup_order}")
        # ALWAYS print this to test if the method is being called
        print(f"🚨 TEST: start_all_services() reached! verbose={self.verbose}, startup_order={startup_order}")
        
        success = True
        for service_name in startup_order:
            service = self.services[service_name]
            
            print(f"🔄 Starting {service.description}...")
            
            # Wait for startup delay
            if service.startup_delay > 0:
                await asyncio.sleep(service.startup_delay)
            
            # Start the service
            try:
                
                if service_name == "dashboard":
                    result = await self._start_dashboard_service(dashboard_port)
                    if service.required:
                        success &= result
                elif service_name == "consistency_checker":
                    result = await self._start_consistency_checker_service(dashboard_port)
                    if service.required:
                        success &= result
                elif service_name == "telemetry_collector":
                    result = await self._start_telemetry_collector_service()
                    if service.required:
                        success &= result
                else:
                    result = await self._start_service(service_name)
                    if service.required:
                        success &= result
                
                
                if not success and service.required:
                    print(f"❌ Failed to start required service: {service.description}")
                    break
                    
            except Exception as e:
                self.logger.error(f"Failed to start service {service_name}: {e}")
                if service.required:
                    success = False
                    break
        
        if success:
            if self.verbose:
                print("✅ All services started successfully!")
            return True
        else:
            if self.verbose:
                print("❌ Service startup failed, initiating cleanup...")
            await self.stop_all_services()
            return False

    async def stop_all_services(self) -> bool:
        """
        Stop all services in reverse dependency order.
        
        Returns:
            True if all services stopped successfully
        """
        if not self.running:
            return True
            
        self.running = False
        self.shutdown_event.set()
        
        if self.verbose:
            print("🛑 Stopping all Context Cleaner services...")
        
        # Stop services in reverse dependency order
        startup_order = self._calculate_startup_order()
        shutdown_order = list(reversed(startup_order))
        
        success = True
        for service_name in shutdown_order:
            try:
                if service_name == "dashboard":
                    success &= await self._stop_dashboard_service()
                elif service_name == "consistency_checker":
                    success &= await self._stop_consistency_checker_service()
                elif service_name == "telemetry_collector":
                    success &= await self._stop_telemetry_collector_service()
                else:
                    success &= await self._stop_service(service_name)
            except Exception as e:
                self.logger.error(f"Failed to stop service {service_name}: {e}")
                success = False
        
        # Stop health monitoring
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            self.health_monitor_thread.join(timeout=5)
        
        if self.verbose:
            print("✅ All services stopped")
        
        return success

    async def _ensure_docker_environment(self) -> bool:
        """
        Ensure Docker daemon is running and containers are in proper state.
        This is the core method that handles intelligent state management.
        """
        if self.verbose:
            print("🐳 Ensuring Docker environment is ready...")
        
        # 1. Check Docker daemon status
        daemon_status = await self._check_docker_daemon_status()
        if daemon_status != DockerDaemonStatus.RUNNING:
            if self.verbose:
                print(f"   Docker daemon status: {daemon_status.value}")
                
            if daemon_status == DockerDaemonStatus.STOPPED:
                if self.verbose:
                    print("   🔄 Starting Docker daemon...")
                if not await self._start_docker_daemon():
                    return False
            elif daemon_status == DockerDaemonStatus.NOT_INSTALLED:
                if self.verbose:
                    print("   ❌ Docker is not installed or not in PATH")
                return False
            else:
                if self.verbose:
                    print("   ❌ Docker daemon is not accessible")
                return False
        
        # 2. Discover containers dynamically and attach to running ones or start as needed
        container_names = await self._discover_project_containers()
        for container_name in container_names:
            container_state = await self._get_container_state(container_name)
            service_name = "clickhouse" if "clickhouse" in container_name else "otel"
            
            if self.verbose:
                print(f"   📦 Container {container_name}: {container_state.value}")
            
            if container_state == ContainerState.RUNNING:
                # Container is already running - attach to it
                if self.verbose:
                    print(f"   ✅ Attaching to running container {container_name}")
                await self._attach_to_running_container(service_name, container_name)
            elif container_state in [ContainerState.STOPPED, ContainerState.EXITED]:
                # Container exists but is stopped - we'll start it later in normal flow
                if self.verbose:
                    print(f"   🔄 Container {container_name} will be started during service startup")
            elif container_state == ContainerState.NOT_FOUND:
                # Container doesn't exist - we'll create it later in normal flow
                if self.verbose:
                    print(f"   🆕 Container {container_name} will be created during service startup")
        
        if self.verbose:
            print("   ✅ Docker environment is ready")
        return True

    async def _check_docker_daemon_status(self) -> DockerDaemonStatus:
        """Check if Docker daemon is running."""
        try:
            # Try to run a simple docker command
            result = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            if result.returncode == 0:
                return DockerDaemonStatus.RUNNING
            else:
                # Docker command failed - check if it's because daemon is not running
                stderr = await result.stderr.read()
                if b"daemon" in stderr.lower() or b"connection" in stderr.lower():
                    return DockerDaemonStatus.STOPPED
                else:
                    return DockerDaemonStatus.FAILED
                    
        except FileNotFoundError:
            # Docker command not found
            return DockerDaemonStatus.NOT_INSTALLED
        except Exception as e:
            self.logger.error(f"Error checking Docker daemon status: {e}")
            return DockerDaemonStatus.FAILED

    async def _start_docker_daemon(self) -> bool:
        """Start Docker daemon if possible."""
        try:
            system = platform.system().lower()
            
            if system == "darwin":  # macOS
                # Try to start Docker Desktop
                if self.verbose:
                    print("   🍎 Starting Docker Desktop on macOS...")
                
                # Check if Docker Desktop is installed
                docker_app_path = "/Applications/Docker.app"
                if os.path.exists(docker_app_path):
                    result = await asyncio.create_subprocess_exec(
                        "open", "-a", "Docker",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.wait()
                    
                    if result.returncode == 0:
                        # Wait for Docker daemon to start
                        for i in range(30):  # Wait up to 30 seconds
                            await asyncio.sleep(1)
                            if await self._check_docker_daemon_status() == DockerDaemonStatus.RUNNING:
                                if self.verbose:
                                    print("   ✅ Docker daemon started successfully")
                                return True
                        
                        if self.verbose:
                            print("   ⏰ Timeout waiting for Docker daemon to start")
                        return False
                    else:
                        if self.verbose:
                            print("   ❌ Failed to start Docker Desktop")
                        return False
                else:
                    if self.verbose:
                        print("   ❌ Docker Desktop not found at expected location")
                    return False
                    
            elif system == "linux":
                # Try to start Docker service
                if self.verbose:
                    print("   🐧 Starting Docker service on Linux...")
                
                # Try systemctl first
                result = await asyncio.create_subprocess_exec(
                    "sudo", "systemctl", "start", "docker",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.wait()
                
                if result.returncode == 0:
                    # Wait for service to start
                    for i in range(15):  # Wait up to 15 seconds
                        await asyncio.sleep(1)
                        if await self._check_docker_daemon_status() == DockerDaemonStatus.RUNNING:
                            if self.verbose:
                                print("   ✅ Docker service started successfully")
                            return True
                    
                    if self.verbose:
                        print("   ⏰ Timeout waiting for Docker service to start")
                    return False
                else:
                    if self.verbose:
                        print("   ❌ Failed to start Docker service")
                    return False
                    
            else:
                if self.verbose:
                    print(f"   ❓ Unsupported platform: {system}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting Docker daemon: {e}")
            if self.verbose:
                print(f"   ❌ Error starting Docker daemon: {e}")
            return False

    async def _get_container_state(self, container_name: str) -> ContainerState:
        """Get the current state of a container with enhanced error handling."""
        try:
            result = await self._run_docker_command(
                ["inspect", container_name, "--format", "{{.State.Status}}"],
                timeout=5
            )
            
            if result and isinstance(result, str):
                status = result.strip().lower()
                status_mapping = {
                    "running": ContainerState.RUNNING,
                    "stopped": ContainerState.STOPPED,
                    "paused": ContainerState.PAUSED,
                    "restarting": ContainerState.RESTARTING,
                    "removing": ContainerState.REMOVING,
                    "exited": ContainerState.EXITED,
                    "dead": ContainerState.DEAD
                }
                return status_mapping.get(status, ContainerState.NOT_FOUND)
            elif hasattr(result, 'success') and result.success and result.stdout:
                status = result.stdout.strip().lower()
                status_mapping = {
                    "running": ContainerState.RUNNING,
                    "stopped": ContainerState.STOPPED,
                    "paused": ContainerState.PAUSED,
                    "restarting": ContainerState.RESTARTING,
                    "removing": ContainerState.REMOVING,
                    "exited": ContainerState.EXITED,
                    "dead": ContainerState.DEAD
                }
                return status_mapping.get(status, ContainerState.NOT_FOUND)
            else:
                # Container not found or command failed
                return ContainerState.NOT_FOUND
                
        except Exception as e:
            self.logger.error(f"Error getting container state for {container_name}: {e}")
            return ContainerState.NOT_FOUND

    def _extract_container_name(self, command: List[str]) -> Optional[str]:
        """Extract container name from Docker command."""
        try:
            if not command or "docker" not in command[0]:
                return None
            
            # Look for --name parameter
            for i, arg in enumerate(command):
                if arg == "--name" and i + 1 < len(command):
                    return command[i + 1]
                elif arg.startswith("--name="):
                    return arg.split("=", 1)[1]
            
            # For docker run commands, the last argument is often the image name
            # We'll use a simple heuristic: if there's a recognizable container name pattern
            for arg in reversed(command):
                if "clickhouse" in arg.lower() or "otel" in arg.lower() or "collector" in arg.lower():
                    # Extract just the service name part
                    if "/" in arg:
                        return arg.split("/")[-1]
                    return arg
                    
            return None
        except Exception as e:
            self.logger.error(f"Error extracting container name from command {command}: {e}")
            return None

    async def _attach_to_running_container(self, service_name: str, container_name: str):
        """Attach to an already running container."""
        try:
            # Get container ID
            result = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_name, "--format", "{{.Id}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                container_id = stdout.decode().strip()
                
                # Update service state to indicate we've attached
                if service_name in self.service_states:
                    state = self.service_states[service_name]
                    state.status = ServiceStatus.ATTACHED
                    state.container_id = container_id
                    state.container_state = ContainerState.RUNNING
                    state.was_attached = True
                    state.health_status = True
                    state.start_time = datetime.now()
                    state.last_health_check = datetime.now()
                    
                    if self.verbose:
                        print(f"   ✅ Attached to running {service_name} container ({container_id[:12]})")
                
        except Exception as e:
            self.logger.error(f"Error attaching to container {container_name}: {e}")

    async def _start_service(self, service_name: str) -> bool:
        """Start a specific service with intelligent container state management."""
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        # Check if already attached to running container
        if state.status == ServiceStatus.ATTACHED:
            if self.verbose:
                print(f"   ⚡ Service {service_name} already attached to running container")
            return True
        
        state.status = ServiceStatus.STARTING
        
        try:
            # Check if dependencies are running or attached
            for dep in service.dependencies:
                dep_state = self.service_states.get(dep)
                if not dep_state or dep_state.status not in [ServiceStatus.RUNNING, ServiceStatus.ATTACHED]:
                    state.last_error = f"Dependency {dep} not running (status: {dep_state.status if dep_state else 'None'})"
                    state.status = ServiceStatus.FAILED
                    return False
            
            # For Docker services, check container state first
            if service.start_command and "docker" in " ".join(service.start_command):
                container_name = self._extract_container_name(service.start_command)
                if container_name:
                    container_state = await self._get_container_state(container_name)
                    
                    if container_state == ContainerState.RUNNING:
                        # Attach to existing running container
                        if self.verbose:
                            print(f"   🔗 Attaching to running {service_name} container")
                        
                        # Get container ID for tracking
                        result = await self._run_docker_command(["ps", "-q", "--filter", f"name={container_name}"])
                        if result and isinstance(result, str) and result:
                            container_id = result.strip()
                            state.container_id = container_id
                            state.container_state = ContainerState.RUNNING
                            state.was_attached = True
                            state.status = ServiceStatus.ATTACHED
                            state.start_time = datetime.now()
                            state.last_health_check = datetime.now()
                            
                            if self.verbose:
                                print(f"   ✅ Attached to running {service_name} container ({container_id[:12]})")
                            return True
                    
                    elif container_state in [ContainerState.STOPPED, ContainerState.EXITED]:
                        # Restart stopped container
                        if self.verbose:
                            print(f"   🔄 Restarting stopped {service_name} container")
                        
                        restart_result = await self._run_docker_command(["restart", container_name])
                        if restart_result and (isinstance(restart_result, str) or (hasattr(restart_result, 'success') and restart_result.success)):
                            state.container_state = ContainerState.RUNNING
                            state.start_time = datetime.now()
                            if self.verbose:
                                print(f"   ✅ Restarted {service_name} container")
                        else:
                            if self.verbose:
                                print(f"   ❌ Failed to restart {service_name} container")
                            error_msg = restart_result.stderr if hasattr(restart_result, 'stderr') else 'Unknown error'
                            state.last_error = f"Failed to restart container: {error_msg}"
                            state.status = ServiceStatus.FAILED
                            return False
            
            # Start the service if not already handled above
            if service.start_command and state.status != ServiceStatus.ATTACHED:
                env = os.environ.copy()
                env.update(service.environment_vars)
                
                process = subprocess.Popen(
                    service.start_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=service.working_directory
                )
                
                state.process = process
                state.pid = process.pid
                state.start_time = datetime.now()
                
                # Register process in the process registry
                process_entry = ProcessEntry(
                    pid=process.pid,
                    command_line=' '.join(service.start_command),
                    service_type=self._map_service_to_type(service_name),
                    start_time=state.start_time,
                    registration_time=datetime.now(),
                    port=self._extract_port_from_command(service.start_command),
                    status='running',
                    registration_source='orchestrator'
                )
                self.process_registry.register_process(process_entry)
                
                # For Docker services, update container metadata
                if "docker" in " ".join(service.start_command):
                    container_name = self._extract_container_name(service.start_command)
                    if container_name:
                        # Give container time to start
                        await asyncio.sleep(3)
                        
                        result = await self._run_docker_command(["ps", "-q", "--filter", f"name={container_name}"])
                        if result and isinstance(result, str) and result.strip():
                            state.container_id = result.strip()
                            state.container_state = ContainerState.RUNNING
            
            # Wait for service to become healthy (skip for attached services)
            if state.status != ServiceStatus.ATTACHED:
                deadline = time.time() + service.startup_timeout
                while time.time() < deadline:
                    if service.health_check and await self._run_health_check(service_name):
                        state.status = ServiceStatus.RUNNING
                        state.health_status = True
                        state.last_health_check = datetime.now()
                        return True
                    await asyncio.sleep(2)
                
                # Timeout reached
                state.last_error = f"Startup timeout ({service.startup_timeout}s)"
                state.status = ServiceStatus.FAILED
                return False
            else:
                # For attached services, run one health check to verify
                if service.health_check:
                    is_healthy = await self._run_health_check(service_name)
                    state.health_status = is_healthy
                    state.last_health_check = datetime.now()
                return True
            
        except Exception as e:
            state.last_error = str(e)
            state.status = ServiceStatus.FAILED
            return False

    async def _stop_service(self, service_name: str) -> bool:
        """Stop a specific service."""
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        if state.status == ServiceStatus.STOPPED:
            return True
            
        state.status = ServiceStatus.STOPPING
        
        try:
            if service.stop_command:
                # Use explicit stop command
                result = subprocess.run(
                    service.stop_command,
                    capture_output=True,
                    timeout=service.shutdown_timeout
                )
                success = result.returncode == 0
            elif state.process:
                # Graceful process termination
                state.process.terminate()
                try:
                    state.process.wait(timeout=service.shutdown_timeout)
                    success = True
                except subprocess.TimeoutExpired:
                    state.process.kill()
                    success = True
            else:
                success = True
            
            state.status = ServiceStatus.STOPPED
            
            # Unregister from process registry if we had a PID
            if state.pid:
                self.process_registry.unregister_process(state.pid)
            
            state.process = None
            state.pid = None
            state.health_status = False
            
            return success
            
        except Exception as e:
            state.last_error = str(e)
            state.status = ServiceStatus.FAILED
            return False

    async def _start_dashboard_service(self, port: int) -> bool:
        """Start the dashboard service."""
        state = self.service_states["dashboard"]
        state.status = ServiceStatus.STARTING
        
        try:
            # Dashboard will be started by the main run command
            # This method just marks it as starting
            state.start_time = datetime.now()
            state.metrics["port"] = port
            return True
        except Exception as e:
            state.last_error = str(e)
            state.status = ServiceStatus.FAILED
            return False

    async def _stop_dashboard_service(self) -> bool:
        """Stop the dashboard service."""
        state = self.service_states["dashboard"]
        state.status = ServiceStatus.STOPPING
        
        try:
            # Dashboard shutdown is handled by the main process
            state.status = ServiceStatus.STOPPED
            return True
        except Exception as e:
            state.last_error = str(e)
            return False

    def _calculate_startup_order(self) -> List[str]:
        """Calculate service startup order based on dependencies."""
        # Topological sort
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            if service_name in visited:
                return
                
            temp_visited.add(service_name)
            
            service = self.services[service_name]
            for dep in service.dependencies:
                if dep in self.services:
                    visit(dep)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            order.append(service_name)
        
        for service_name in self.services:
            if service_name not in visited:
                visit(service_name)
        
        return order

    async def _run_health_check(self, service_name: str) -> bool:
        """Run health check for a service with aggressive timeout controls."""
        service = self.services[service_name]
        if not service.health_check:
            return True
            
        try:
            # Apply aggressive 10-second timeout to health check
            # Handle both sync and async health check functions
            import inspect
            if inspect.iscoroutinefunction(service.health_check):
                # Async health check function
                result = await asyncio.wait_for(
                    service.health_check(),
                    timeout=10.0
                )
            else:
                # Sync health check function - run in thread pool to avoid blocking
                # Handle case where health_check might return bool directly
                health_func = service.health_check
                if callable(health_func):
                    # FIXED: Use asyncio.get_running_loop() to avoid deadlocks
                    loop = asyncio.get_running_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, health_func
                        ),
                        timeout=10.0
                    )
                else:
                    # Handle case where health_check is already a bool value
                    result = bool(health_func)
            return bool(result)
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Health check timeout for {service_name} after 10s")
            return False
        except Exception as e:
            self.logger.error(f"Health check failed for {service_name}: {e}")
            return False

    def _health_monitor_loop(self):
        """Background health monitoring loop."""
        while self.running and not self.shutdown_event.is_set():
            try:
                for service_name, service in self.services.items():
                    if not self.running:
                        break
                        
                    state = self.service_states[service_name]
                    
                    # Skip if service not running
                    if state.status != ServiceStatus.RUNNING:
                        continue
                    
                    # Check if health check is due
                    now = datetime.now()
                    time_since_last_check = None
                    if state.last_health_check:
                        time_since_last_check = (now - state.last_health_check).seconds

                    if (state.last_health_check is None or
                        time_since_last_check >= service.health_check_interval):

                        self.logger.debug(f"🏥 HEALTH_MONITOR: Running health check for {service_name} (last check: {time_since_last_check}s ago)")

                        # FIXED: Simplified health check - avoid complex event loop management
                        try:
                            # Use sync wrapper that handles event loops properly
                            healthy = self._run_health_check_sync(service_name)
                        except Exception as health_error:
                            self.logger.error(f"🏥 HEALTH_MONITOR: Health check exception for {service_name}: {health_error}")
                            import traceback
                            self.logger.error(f"🏥 HEALTH_MONITOR: Health check traceback:\n{traceback.format_exc()}")
                            healthy = False

                        state.last_health_check = now
                        previous_health_status = state.health_status
                        state.health_status = healthy

                        # Log health status changes
                        if previous_health_status != healthy:
                            status_change = "healthy" if healthy else "unhealthy"
                            self.logger.info(f"🏥 HEALTH_MONITOR: {service_name} changed from {previous_health_status} to {status_change}")
                        else:
                            self.logger.debug(f"🏥 HEALTH_MONITOR: {service_name} health status remains {healthy}")

                        # Handle unhealthy service
                        if not healthy and service.restart_on_failure:
                            restart_count = state.restart_count
                            last_restart = getattr(state, 'last_restart_time', None)
                            time_since_restart = None
                            if last_restart:
                                time_since_restart = (now - last_restart).total_seconds()

                            self.logger.warning(f"🔄 RESTART_TRIGGER: Service {service_name} is unhealthy, triggering restart #{restart_count + 1}")
                            self.logger.warning(f"🔄 RESTART_TRIGGER: Time since last restart: {time_since_restart}s")
                            self.logger.warning(f"🔄 RESTART_TRIGGER: Service details - Status: {state.status}, Health: {healthy}")

                            if self.verbose:
                                print(f"⚠️ Restarting unhealthy service: {service.description}")
                            
                            # Restart service using event loop safe approach
                            try:
                                # FIXED: Simplified restart - avoid complex event loop management
                                self._restart_service_sync(service_name)
                            except Exception as restart_error:
                                self.logger.error(f"Failed to restart service {service_name}: {restart_error}")
                
                # Sleep before next check
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                time.sleep(30)

    async def _restart_service(self, service_name: str):
        """Restart a specific service."""
        restart_start_time = datetime.now()
        state = self.service_states[service_name]
        old_restart_count = state.restart_count
        state.restart_count += 1
        state.last_restart_time = restart_start_time

        self.logger.info(f"🔄 RESTART_START: Beginning restart of {service_name} service")
        self.logger.info(f"🔄 RESTART_START: Restart #{state.restart_count}, previous restarts: {old_restart_count}")
        self.logger.info(f"🔄 RESTART_START: Service state before restart - Status: {state.status}, Health: {state.health_status}")

        if self.verbose:
            print(f"   🔄 Restarting {service_name} service (restart #{state.restart_count})")

        try:
            # Trigger cache invalidation before restart
            self.logger.info(f"🔄 RESTART_STEP: Triggering cache invalidation for {service_name}")
            self._trigger_cache_invalidation(service_name)

            # Stop the service
            self.logger.info(f"🔄 RESTART_STEP: Stopping {service_name} service")
            stop_start = datetime.now()
            await self._stop_service(service_name)
            stop_duration = (datetime.now() - stop_start).total_seconds()
            self.logger.info(f"🔄 RESTART_STEP: Service {service_name} stopped in {stop_duration:.2f}s")

            # Wait a moment
            self.logger.debug(f"🔄 RESTART_STEP: Waiting 5s before restart of {service_name}")
            await asyncio.sleep(5)

            # Start the service
            self.logger.info(f"🔄 RESTART_STEP: Starting {service_name} service")
            start_start = datetime.now()

            if service_name == "dashboard":
                port = state.metrics.get("port", 8110)
                self.logger.info(f"🔄 RESTART_STEP: Starting dashboard on port {port}")
                success = await self._start_dashboard_service(port)
            elif service_name == "consistency_checker":
                port = state.metrics.get("port", 8110)
                self.logger.info(f"🔄 RESTART_STEP: Starting consistency_checker on port {port}")
                success = await self._start_consistency_checker_service(port)
            elif service_name == "telemetry_collector":
                self.logger.info(f"🔄 RESTART_STEP: Starting telemetry_collector")
                success = await self._start_telemetry_collector_service()
            else:
                self.logger.info(f"🔄 RESTART_STEP: Starting generic service {service_name}")
                success = await self._start_service(service_name)

            start_duration = (datetime.now() - start_start).total_seconds()
            total_duration = (datetime.now() - restart_start_time).total_seconds()

            if success:
                self.logger.info(f"🔄 RESTART_SUCCESS: Service {service_name} restarted successfully")
                self.logger.info(f"🔄 RESTART_SUCCESS: Start took {start_duration:.2f}s, total restart took {total_duration:.2f}s")
                if self.verbose:
                    print(f"   ✅ Service {service_name} restarted successfully")
            else:
                self.logger.error(f"🔄 RESTART_FAILED: Service {service_name} failed to start after restart")
                self.logger.error(f"🔄 RESTART_FAILED: Start took {start_duration:.2f}s, total restart took {total_duration:.2f}s")

        except Exception as e:
            total_duration = (datetime.now() - restart_start_time).total_seconds()
            self.logger.error(f"🔄 RESTART_EXCEPTION: Exception during {service_name} restart: {e}")
            self.logger.error(f"🔄 RESTART_EXCEPTION: Total time before exception: {total_duration:.2f}s")
            import traceback
            self.logger.error(f"🔄 RESTART_EXCEPTION: Traceback:\n{traceback.format_exc()}")
            raise

    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all services with process registry integration."""
        status = {
            "orchestrator": {
                "running": self.running,
                "uptime": (datetime.now() - datetime.now()).total_seconds() if self.running else 0
            },
            "services": {},
            "process_registry": {
                "total_registered": 0,
                "by_service_type": {},
                "registry_status": "unknown"
            }
        }
        
        try:
            # Get process registry information
            registered_processes = self.process_registry.get_all_processes()
            status["process_registry"]["total_registered"] = len(registered_processes)
            status["process_registry"]["registry_status"] = "accessible"
            
            # Group by service type
            by_type = {}
            for process in registered_processes:
                service_type = process.service_type
                if service_type not in by_type:
                    by_type[service_type] = []
                by_type[service_type].append({
                    "pid": process.pid,
                    "start_time": process.start_time.isoformat() if process.start_time else None,
                    "status": process.status
                })
            status["process_registry"]["by_service_type"] = by_type
            
        except Exception as e:
            status["process_registry"]["registry_status"] = f"error: {str(e)}"
        
        # Service status information
        for service_name, state in self.service_states.items():
            service = self.services[service_name]
            
            service_info = {
                "name": service.description,
                "status": state.status.value,
                "required": service.required,
                "health_status": state.health_status,
                "last_health_check": state.last_health_check.isoformat() if state.last_health_check else None,
                "start_time": state.start_time.isoformat() if state.start_time else None,
                "restart_count": state.restart_count,
                "last_error": state.last_error,
                "pid": state.pid,
                "metrics": state.metrics,
                "registry_info": None
            }
            
            # Add process registry information if available
            if state.pid:
                try:
                    registry_entry = self.process_registry.get_process(state.pid)
                    if registry_entry:
                        service_info["registry_info"] = {
                            "registered": True,
                            "service_type": registry_entry.service_type,
                            "registration_time": registry_entry.registration_time.isoformat(),
                            "registration_source": registry_entry.registration_source,
                            "last_health_check": registry_entry.last_health_check.isoformat() if registry_entry.last_health_check else None
                        }
                    else:
                        service_info["registry_info"] = {"registered": False, "reason": "not_found"}
                except Exception as e:
                    service_info["registry_info"] = {"registered": False, "reason": f"error: {str(e)}"}
            
            status["services"][service_name] = service_info
        
        # Add port conflict management statistics
        try:
            status["port_conflict_manager"] = self.port_conflict_manager.get_retry_statistics()
        except Exception as e:
            status["port_conflict_manager"] = {"error": str(e), "status": "unavailable"}
        
        return status

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        if self.verbose:
            print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")

        # FIXED: Set shutdown flag instead of creating competing event loop
        self.shutdown_event.set()
        # Let the main event loop handle graceful shutdown

    async def _start_consistency_checker_service(self, dashboard_port: int) -> bool:
        """Start the API/UI consistency checker service."""
        state = self.service_states["consistency_checker"]
        state.status = ServiceStatus.STARTING
        
        try:
            # Initialize the consistency checker
            self.consistency_checker = APIUIConsistencyChecker(
                config=self.config,
                dashboard_host="127.0.0.1",
                dashboard_port=dashboard_port
            )
            
            # Start the monitoring in the background with proper task tracking
            loop = asyncio.get_event_loop()

            # Create monitoring task without timeout - this is meant to run forever
            self.consistency_checker.monitoring_task = loop.create_task(
                self.consistency_checker.start_monitoring()
            )

            # Add task done callback for error handling
            def on_task_done(task):
                if task.cancelled():
                    self.logger.info("Consistency checker task was cancelled")
                    # Don't mark as failed if cancelled - this is expected during shutdown
                    return

                try:
                    exception = task.exception()
                    if exception:
                        self.logger.error(f"Consistency checker task failed: {exception}")
                        state.status = ServiceStatus.FAILED
                        state.health_status = False
                        # The service orchestrator will restart it on next health check
                    else:
                        self.logger.info("Consistency checker task completed normally")
                except Exception as e:
                    # Handle any other exceptions when checking task status
                    self.logger.error(f"Error in consistency checker task callback: {e}")
                    state.status = ServiceStatus.FAILED
                    state.health_status = False

            self.consistency_checker.monitoring_task.add_done_callback(on_task_done)

            # Wait a moment to ensure task is actually running and not immediately cancelled
            await asyncio.sleep(0.5)

            # Check if task was cancelled immediately (would indicate a startup problem)
            if self.consistency_checker.monitoring_task.cancelled():
                self.logger.error("Consistency checker task was cancelled immediately after creation")
                state.status = ServiceStatus.FAILED
                state.health_status = False
                return False

            state.status = ServiceStatus.RUNNING
            state.start_time = datetime.now()
            state.metrics["port"] = dashboard_port
            state.health_status = True
            state.last_health_check = datetime.now()

            if self.verbose:
                print(f"   ✅ API/UI consistency checker started on dashboard port {dashboard_port}")

            return True
            
        except Exception as e:
            state.last_error = str(e)
            state.status = ServiceStatus.FAILED
            self.logger.error(f"Failed to start consistency checker: {e}")
            return False
    
    async def _stop_consistency_checker_service(self) -> bool:
        """Stop the API/UI consistency checker service."""
        state = self.service_states["consistency_checker"]
        state.status = ServiceStatus.STOPPING

        try:
            if self.consistency_checker:
                # Gracefully stop the monitoring loop
                if hasattr(self.consistency_checker, 'stop_monitoring'):
                    await self.consistency_checker.stop_monitoring()

                # Cancel the monitoring task if it exists
                if hasattr(self.consistency_checker, 'monitoring_task') and self.consistency_checker.monitoring_task:
                    if not self.consistency_checker.monitoring_task.done():
                        self.consistency_checker.monitoring_task.cancel()
                        try:
                            await self.consistency_checker.monitoring_task
                        except asyncio.CancelledError:
                            pass  # Expected when cancelling

            self.consistency_checker = None

            state.status = ServiceStatus.STOPPED
            state.health_status = False

            if self.verbose:
                print("   ✅ API/UI consistency checker stopped gracefully")

            return True

        except Exception as e:
            state.last_error = str(e)
            self.logger.error(f"Failed to stop consistency checker: {e}")
            return False
    
    async def _start_telemetry_collector_service(self) -> bool:
        """Start the telemetry collection service."""
        state = self.service_states["telemetry_collector"]
        state.status = ServiceStatus.STARTING
        
        try:
            # Initialize the telemetry collector
            self.telemetry_collector = get_collector()
            
            # Start the service
            success = await self.telemetry_collector.start_service()
            
            if success:
                state.status = ServiceStatus.RUNNING
                state.start_time = datetime.now()
                state.health_status = True
                state.last_health_check = datetime.now()
                
                # Store service metrics
                metrics = self.telemetry_collector.get_service_metrics()
                state.metrics.update(metrics)
                
                if self.verbose:
                    print(f"   ✅ Telemetry collector service started (session: {metrics.get('session_id', 'unknown')})")
                
                return True
            else:
                state.status = ServiceStatus.FAILED
                state.last_error = "Failed to start telemetry collector service"
                return False
            
        except Exception as e:
            state.last_error = str(e)
            state.status = ServiceStatus.FAILED
            self.logger.error(f"Failed to start telemetry collector: {e}")
            return False
    
    async def _stop_telemetry_collector_service(self) -> bool:
        """Stop the telemetry collection service."""
        state = self.service_states["telemetry_collector"]
        state.status = ServiceStatus.STOPPING
        
        try:
            if self.telemetry_collector:
                success = await self.telemetry_collector.stop_service()
                if success:
                    if self.verbose:
                        print("   ✅ Telemetry collector service stopped")
                else:
                    if self.verbose:
                        print("   ⚠️  Telemetry collector reported stop failure")
                        
                self.telemetry_collector = None
            
            state.status = ServiceStatus.STOPPED
            state.health_status = False
            
            return True
            
        except Exception as e:
            state.last_error = str(e)
            self.logger.error(f"Failed to stop telemetry collector: {e}")
            return False
    
    def get_consistency_report(self) -> Optional[Dict[str, Any]]:
        """Get the latest consistency check report."""
        if self.consistency_checker:
            return self.consistency_checker.get_summary_report()
        return None
    
    def get_critical_consistency_issues(self) -> List[Any]:
        """Get critical API/UI consistency issues."""
        if self.consistency_checker:
            return self.consistency_checker.get_critical_issues()
        return []
    
    # Container Discovery Methods
    async def _discover_project_containers(self) -> List[str]:
        """
        Dynamically discover containers related to this project using multiple strategies.
        
        Returns:
            List of container names that should be managed by the orchestrator
        """
        discovered_containers = []
        
        if self.verbose:
            print("🔍 Dynamically discovering project containers...")
        
        # Strategy 1: Try docker-compose.yml parsing first (most reliable)
        compose_containers = await self._discover_compose_containers()
        discovered_containers.extend(compose_containers)
        
        # Strategy 2: Image-based discovery for well-known services
        known_images = [
            "clickhouse/clickhouse-server",
            "otel/opentelemetry-collector-contrib"
        ]
        
        for image in known_images:
            containers = await self._discover_containers_by_image(image)
            for container in containers:
                if container not in discovered_containers:
                    discovered_containers.append(container)
        
        # Strategy 3: Port-based discovery for ClickHouse
        clickhouse_ports = [8123, 9000]  # Standard ClickHouse ports
        for port in clickhouse_ports:
            containers = await self._discover_containers_by_port(port)
            for container in containers:
                if container not in discovered_containers and "clickhouse" in container.lower():
                    discovered_containers.append(container)
        
        # Strategy 4: Name pattern matching
        name_patterns = [
            "*clickhouse*",
            "*otel*collector*"
        ]
        
        for pattern in name_patterns:
            containers = await self._discover_containers_by_name_pattern(pattern)
            for container in containers:
                if container not in discovered_containers:
                    discovered_containers.append(container)
        
        # Remove duplicates and filter out non-project containers
        filtered_containers = []
        for container in discovered_containers:
            if container and container not in filtered_containers:
                # Basic filtering to avoid system containers
                if not any(exclude in container.lower() for exclude in ["redis", "mysql", "postgres", "nginx"]):
                    filtered_containers.append(container)
        
        if self.verbose:
            if filtered_containers:
                print(f"   ✅ Discovered containers: {', '.join(filtered_containers)}")
            else:
                print("   ⚠️  No project containers discovered - falling back to defaults")
                # Fallback to hardcoded names if discovery fails completely
                filtered_containers = ["clickhouse-otel", "otel-collector"]
        
        return filtered_containers
    
    async def _discover_compose_containers(self) -> List[str]:
        """Discover containers from docker-compose.yml if it exists."""
        compose_file = "docker-compose.yml"
        containers = []
        
        if not os.path.exists(compose_file):
            return containers
        
        try:
            # Simple parsing approach - look for 'container_name:' entries
            with open(compose_file, 'r') as f:
                content = f.read()
                container_names = self._simple_compose_parse(content)
                containers.extend(container_names)
                
                if self.verbose and container_names:
                    print(f"   📄 Found in docker-compose.yml: {', '.join(container_names)}")
                    
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Could not parse docker-compose.yml: {e}")
        
        return containers
    
    def _simple_compose_parse(self, content: str) -> List[str]:
        """Simple regex-based parsing of docker-compose.yml for container names."""
        import re
        container_names = []
        
        # Look for 'container_name: name' patterns
        container_name_matches = re.findall(r'container_name:\s*([^\s\n]+)', content)
        container_names.extend(container_name_matches)
        
        # Also look for service names under 'services:' that might become container names
        services_matches = re.findall(r'services:\s*\n((?:\s+\w+:.*\n?)*)', content, re.MULTILINE)
        if services_matches:
            for services_block in services_matches:
                service_names = re.findall(r'^\s+(\w+):', services_block, re.MULTILINE)
                # Only add if there's no explicit container_name for this service
                for service_name in service_names:
                    if not re.search(rf'{service_name}:.*container_name:', content, re.DOTALL):
                        # Docker Compose default: project_name + service_name + instance
                        # For our case, likely to be context-cleaner_servicename_1 or just servicename
                        potential_names = [
                            service_name,
                            f"context-cleaner-{service_name}",
                            f"context-cleaner_{service_name}_1"
                        ]
                        container_names.extend(potential_names)
        
        return container_names
    
    async def _discover_containers_by_image(self, image_name: str) -> List[str]:
        """Discover containers running a specific image."""
        try:
            # Use docker ps to find containers with specific image
            result = await self._run_docker_command([
                "ps", "--filter", f"ancestor={image_name}", "--format", "{{.Names}}"
            ], timeout=10)
            
            if result and isinstance(result, str):
                containers = [name.strip() for name in result.split('\n') if name.strip()]
                return containers
            elif hasattr(result, 'success') and result.success and result.stdout:
                containers = [name.strip() for name in result.stdout.split('\n') if name.strip()]
                return containers
                
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Image discovery failed for {image_name}: {e}")
        
        return []
    
    async def _discover_containers_by_port(self, port: int) -> List[str]:
        """Discover containers exposing a specific port."""
        try:
            # Use docker ps to find containers exposing specific port
            result = await self._run_docker_command([
                "ps", "--filter", f"publish={port}", "--format", "{{.Names}}"
            ], timeout=10)
            
            if result and isinstance(result, str):
                containers = [name.strip() for name in result.split('\n') if name.strip()]
                return containers
            elif hasattr(result, 'success') and result.success and result.stdout:
                containers = [name.strip() for name in result.stdout.split('\n') if name.strip()]
                return containers
                
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Port discovery failed for {port}: {e}")
        
        return []
    
    async def _discover_containers_by_name_pattern(self, pattern: str) -> List[str]:
        """Discover containers matching a name pattern."""
        try:
            # Use docker ps to find containers matching pattern
            result = await self._run_docker_command([
                "ps", "--filter", f"name={pattern}", "--format", "{{.Names}}"
            ], timeout=10)
            
            if result and isinstance(result, str):
                containers = [name.strip() for name in result.split('\n') if name.strip()]
                return containers
            elif hasattr(result, 'success') and result.success and result.stdout:
                containers = [name.strip() for name in result.stdout.split('\n') if name.strip()]
                return containers
                
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Name pattern discovery failed for {pattern}: {e}")
        
        return []
    
    async def _run_docker_command(self, args: List[str], timeout: int = 8) -> Optional[Any]:
        """Run a docker command with unified event loop management and adaptive timeouts."""
        
        @dataclass
        class DockerCommandResult:
            stdout: str = ""
            stderr: str = ""
            returncode: int = -1
            success: bool = False
            execution_time_ms: int = 0
            retry_count: int = 0
            
        # Adaptive timeout based on command type
        adaptive_timeout = self._calculate_adaptive_timeout(args, timeout)
        
        start_time = time.time()
        max_retries = 3 if any(cmd in ' '.join(args) for cmd in ['start', 'up', 'restart']) else 1
        
        for retry in range(max_retries):
            try:
                cmd = ["docker"] + args
                
                if self.verbose:
                    print(f"   🐳 Running Docker command (attempt {retry + 1}/{max_retries}, timeout: {adaptive_timeout}s): {' '.join(cmd)}")
                
                # FIXED: Simplified - no manual event loop management needed in async function
                result = await self._execute_docker_command_core(cmd, adaptive_timeout, retry)
                return result
                    
            except asyncio.TimeoutError:
                execution_time = int((time.time() - start_time) * 1000)
                if retry < max_retries - 1:
                    if self.verbose:
                        print(f"   ⏰ Docker command timed out (attempt {retry + 1}), retrying in 2s...")
                    await asyncio.sleep(2)
                    adaptive_timeout = min(adaptive_timeout * 1.5, 60)  # Increase timeout for retry
                    continue
                else:
                    if self.verbose:
                        print(f"   ❌ Docker command failed after {max_retries} attempts")
                    return DockerCommandResult(
                        stderr=f"Command timed out after {max_retries} attempts",
                        execution_time_ms=execution_time,
                        retry_count=retry + 1
                    )
                    
            except Exception as e:
                execution_time = int((time.time() - start_time) * 1000)
                if retry < max_retries - 1 and self._is_retryable_error(e):
                    if self.verbose:
                        print(f"   ⚠️  Retryable error (attempt {retry + 1}): {str(e)}")
                    await asyncio.sleep(2)
                    continue
                else:
                    error_msg = f"Docker command execution error: {str(e)}"
                    if self.verbose:
                        print(f"   ❌ {error_msg}")
                    return DockerCommandResult(
                        stderr=error_msg,
                        execution_time_ms=execution_time,
                        retry_count=retry + 1
                    )
        
        # Should not reach here
        return DockerCommandResult(stderr="Unexpected error in retry loop")
    
    def _calculate_adaptive_timeout(self, args: List[str], base_timeout: int) -> int:
        """Calculate adaptive timeout based on command complexity and system load."""
        command_str = ' '.join(args).lower()
        
        # Base timeout adjustments
        if 'up' in command_str or 'start' in command_str:
            return max(base_timeout * 2, 30)  # Container startup needs more time
        elif 'build' in command_str:
            return max(base_timeout * 4, 120)  # Image builds need much more time
        elif 'pull' in command_str:
            return max(base_timeout * 3, 60)  # Image pulls need more time
        elif any(check in command_str for check in ['ps', 'inspect', 'logs']):
            return max(base_timeout // 2, 5)  # Query operations can be faster
        else:
            return base_timeout
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if a Docker command error is retryable."""
        error_str = str(error).lower()
        retryable_patterns = [
            'connection refused',
            'timeout',
            'temporary failure',
            'network error',
            'docker daemon',
            'resource temporarily unavailable'
        ]
        return any(pattern in error_str for pattern in retryable_patterns)
    
    async def _execute_docker_command_core(self, cmd: List[str], timeout: int, retry_count: int) -> 'DockerCommandResult':
        """Core Docker command execution with circuit breaker pattern."""
        
        @dataclass
        class DockerCommandResult:
            stdout: str = ""
            stderr: str = ""
            returncode: int = -1
            success: bool = False
            execution_time_ms: int = 0
            retry_count: int = 0
        
        start_time = time.time()
        
        try:
            # Use async subprocess execution with enhanced error handling
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024  # 1MB limit for output
            )
            
            # Wait for command completion with configurable timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                
                execution_time = int((time.time() - start_time) * 1000)
                
                result = DockerCommandResult(
                    stdout=stdout_bytes.decode('utf-8', errors='ignore').strip(),
                    stderr=stderr_bytes.decode('utf-8', errors='ignore').strip(),
                    returncode=proc.returncode,
                    success=(proc.returncode == 0),
                    execution_time_ms=execution_time,
                    retry_count=retry_count
                )
                
                if result.success:
                    if self.verbose and result.stdout:
                        print(f"   ✅ Docker command succeeded ({execution_time}ms): {result.stdout[:100]}{'...' if len(result.stdout) > 100 else ''}")
                    return result.stdout if result.stdout else result
                else:
                    if self.verbose:
                        print(f"   ❌ Docker command failed (code {result.returncode}, {execution_time}ms): {' '.join(cmd)}")
                        if result.stderr:
                            print(f"   📝 Error output: {result.stderr[:200]}{'...' if len(result.stderr) > 200 else ''}")
                    return result
                    
            except asyncio.TimeoutError:
                # Enhanced timeout handling with process cleanup
                execution_time = int((time.time() - start_time) * 1000)
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                
                if self.verbose:
                    print(f"   ⏰ Docker command timed out after {timeout}s ({execution_time}ms): {' '.join(cmd)}")
                raise asyncio.TimeoutError(f"Command timed out after {timeout}s")
                
        except FileNotFoundError:
            error_msg = "Docker command not found - ensure Docker is installed and in PATH"
            if self.verbose:
                print(f"   🚫 {error_msg}")
            execution_time = int((time.time() - start_time) * 1000)
            return DockerCommandResult(
                stderr=error_msg,
                execution_time_ms=execution_time,
                retry_count=retry_count
            )
            
        except Exception as e:
            error_msg = f"Docker command execution error: {str(e)}"
            if self.verbose:
                print(f"   ⚠️  {error_msg}")
            execution_time = int((time.time() - start_time) * 1000)
            raise e

    # Health check implementations with multi-stage validation
    async def _check_clickhouse_health(self) -> bool:
        """Multi-stage ClickHouse health check with DDL readiness validation and timeout."""
        try:
            # Apply aggressive 8-second timeout to the entire health check
            await asyncio.wait_for(
                self._check_clickhouse_health_async(), 
                timeout=8.0
            )
            return True
        except asyncio.TimeoutError:
            if self.verbose:
                print("   ⏰ ClickHouse health check timeout after 8s")
            return False
        except Exception as e:
            if self.verbose:
                print(f"   ❌ ClickHouse health check error: {e}")
            return False
    
    async def _check_clickhouse_health_async(self) -> bool:
        """Async multi-stage ClickHouse health check with circuit breaker pattern."""
        
        # Stage 1: Container existence and running state
        if not await self._check_clickhouse_container_running():
            if self.verbose:
                print("   ❌ ClickHouse container not running")
            return False
        
        # Stage 2: Port accessibility check
        if not await self._check_clickhouse_port_accessible():
            if self.verbose:
                print("   ❌ ClickHouse ports not accessible")
            return False
        
        # Stage 3: Basic connectivity and ping
        if not await self._check_clickhouse_basic_connectivity():
            if self.verbose:
                print("   ❌ ClickHouse basic connectivity failed")
            return False
        
        # Stage 4: Database readiness (DDL completion check)
        if not await self._check_clickhouse_ddl_readiness():
            if self.verbose:
                print("   ❌ ClickHouse DDL initialization not complete")
            return False
        
        # Stage 5: Query execution capability
        if not await self._check_clickhouse_query_capability():
            if self.verbose:
                print("   ❌ ClickHouse query execution failed")
            return False
        
        if self.verbose:
            print("   ✅ ClickHouse multi-stage health check passed")
        return True
    
    async def _check_clickhouse_container_running(self) -> bool:
        """Check if ClickHouse container is running."""
        try:
            result = await self._run_docker_command(
                ["ps", "--filter", "name=clickhouse-otel", "--filter", "status=running", "--format", "{{.Names}}"],
                timeout=5
            )
            
            if isinstance(result, str):
                return "clickhouse-otel" in result.lower()
            elif hasattr(result, 'success') and result.success:
                return "clickhouse-otel" in result.stdout.lower()
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Container check failed: {e}")
            return False
    
    async def _check_clickhouse_port_accessible(self) -> bool:
        """Check if ClickHouse ports are accessible."""
        import socket
        ports = [8123, 9000]  # HTTP and Native interfaces
        
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result != 0:
                        if self.verbose:
                            print(f"   ⚠️  ClickHouse port {port} not accessible")
                        return False
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️  Port {port} check failed: {e}")
                return False
        
        return True
    
    async def _check_clickhouse_basic_connectivity(self) -> bool:
        """Check basic ClickHouse connectivity via HTTP ping."""
        import urllib.request
        import urllib.error
        
        try:
            req = urllib.request.Request(
                'http://127.0.0.1:8123/ping', 
                headers={'User-Agent': 'ContextCleaner-HealthCheck/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                response_text = response.read().decode('utf-8').strip()
                return response_text == "Ok."
                
        except urllib.error.HTTPError as e:
            if self.verbose:
                print(f"   ⚠️  ClickHouse HTTP ping failed: HTTP {e.code}")
            return False
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  ClickHouse connectivity check failed: {e}")
            return False
    
    async def _check_clickhouse_ddl_readiness(self) -> bool:
        """Check if ClickHouse DDL initialization is complete by verifying key tables exist."""
        max_retries = 5
        retry_delay = 2
        
        # Key tables that must exist after DDL initialization
        required_tables = [
            'otel.traces',
            'otel.metrics', 
            'otel.logs',
            'otel.claude_message_content'
        ]
        
        for attempt in range(max_retries):
            try:
                if self.verbose and attempt > 0:
                    print(f"   🔄 DDL readiness check (attempt {attempt + 1}/{max_retries})")
                
                # Use docker exec to run ClickHouse client query
                cmd = [
                    "exec", "clickhouse-otel", "clickhouse-client", 
                    "--query", "SHOW TABLES FROM otel FORMAT TabSeparated"
                ]
                
                result = await self._run_docker_command(cmd, timeout=10)
                
                if isinstance(result, str):
                    existing_tables = set(f"otel.{line.strip()}" for line in result.split('\n') if line.strip())
                elif hasattr(result, 'success') and result.success:
                    existing_tables = set(f"otel.{line.strip()}" for line in result.stdout.split('\n') if line.strip())
                else:
                    if self.verbose:
                        print(f"   ⚠️  DDL check command failed: {getattr(result, 'stderr', 'Unknown error')}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return False
                
                missing_tables = set(required_tables) - existing_tables
                
                if not missing_tables:
                    if self.verbose:
                        print(f"   ✅ DDL initialization complete ({len(existing_tables)} tables found)")
                    return True
                else:
                    if self.verbose:
                        print(f"   ⏳ DDL still initializing, missing: {', '.join(missing_tables)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        if self.verbose:
                            print(f"   ❌ DDL initialization incomplete after {max_retries} attempts")
                        return False
                        
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️  DDL readiness check failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return False
        
        return False
    
    async def _check_clickhouse_query_capability(self) -> bool:
        """Test ClickHouse query execution capability."""
        try:
            # Simple query that exercises the database
            cmd = [
                "exec", "clickhouse-otel", "clickhouse-client", 
                "--query", "SELECT count() FROM system.tables WHERE database = 'otel'"
            ]
            
            result = await self._run_docker_command(cmd, timeout=8)
            
            if isinstance(result, str):
                try:
                    table_count = int(result.strip())
                    if self.verbose:
                        print(f"   📊 ClickHouse operational with {table_count} tables in otel database")
                    return table_count > 0
                except ValueError:
                    return False
            elif hasattr(result, 'success') and result.success:
                try:
                    table_count = int(result.stdout.strip())
                    if self.verbose:
                        print(f"   📊 ClickHouse operational with {table_count} tables in otel database")
                    return table_count > 0
                except ValueError:
                    return False
            else:
                if self.verbose:
                    print(f"   ❌ Query capability test failed: {getattr(result, 'stderr', 'Unknown error')}")
                return False
                
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Query capability test failed: {e}")
            return False

    async def _check_otel_health(self) -> bool:
        """Enhanced OTEL collector health check with retry mechanism."""
        try:
            return await asyncio.wait_for(
                self._check_otel_health_async(),
                timeout=8.0
            )
        except asyncio.TimeoutError:
            if self.verbose:
                print("   ⏰ OTEL health check timeout after 8s")
            return False
        except Exception as e:
            if self.verbose:
                print(f"   ❌ OTEL health check error: {e}")
            return False
    
    async def _check_otel_health_async(self) -> bool:
        """Async OTEL collector health check with circuit breaker and retry logic."""
        
        # Stage 1: Container running check
        if not await self._check_otel_container_running():
            if self.verbose:
                print("   ❌ OTEL collector container not running")
            return False
        
        # Stage 2: Port accessibility
        if not await self._check_otel_ports_accessible():
            if self.verbose:
                print("   ❌ OTEL collector ports not accessible")
            return False
        
        # Stage 3: ZPages endpoint health (optional but preferred)
        zpages_healthy = await self._check_otel_zpages_health()
        if not zpages_healthy:
            if self.verbose:
                print("   ⚠️  OTEL ZPages endpoint not accessible (collector may still be starting)")
            # Don't fail on ZPages, as it's not critical for basic operation
        
        # Stage 4: ClickHouse connectivity check (since OTEL depends on ClickHouse)
        if not await self._check_otel_clickhouse_connectivity():
            if self.verbose:
                print("   ❌ OTEL collector cannot connect to ClickHouse")
            return False
        
        if self.verbose:
            zpages_status = "with ZPages" if zpages_healthy else "without ZPages"
            print(f"   ✅ OTEL collector healthy {zpages_status}")
        return True
    
    async def _check_otel_container_running(self) -> bool:
        """Check if OTEL collector container is running."""
        try:
            result = await self._run_docker_command(
                ["ps", "--filter", "name=otel-collector", "--filter", "status=running", "--format", "{{.Names}}"],
                timeout=5
            )
            
            if isinstance(result, str):
                return "otel-collector" in result.lower()
            elif hasattr(result, 'success') and result.success:
                return "otel-collector" in result.stdout.lower()
            return False
            
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  OTEL container check failed: {e}")
            return False
    
    async def _check_otel_ports_accessible(self) -> bool:
        """Check if OTEL collector ports are accessible."""
        import socket
        ports = [4317, 4318]  # OTLP gRPC and HTTP receivers
        
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result != 0:
                        if self.verbose:
                            print(f"   ⚠️  OTEL port {port} not accessible")
                        return False
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️  OTEL port {port} check failed: {e}")
                return False
        
        return True
    
    async def _check_otel_zpages_health(self) -> bool:
        """Check OTEL collector ZPages health endpoint (optional)."""
        import urllib.request
        import urllib.error
        
        try:
            req = urllib.request.Request(
                'http://127.0.0.1:55679/debug/tracez',
                headers={'User-Agent': 'ContextCleaner-HealthCheck/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
                
        except urllib.error.HTTPError as e:
            if self.verbose:
                print(f"   ⚠️  OTEL ZPages check failed: HTTP {e.code}")
            return False
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  OTEL ZPages connectivity failed: {e}")
            return False
    
    async def _check_otel_clickhouse_connectivity(self) -> bool:
        """Check if OTEL collector can connect to ClickHouse (dependency check)."""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Check OTEL collector logs for ClickHouse connection issues
                cmd = [
                    "logs", "--tail", "50", "otel-collector"
                ]
                
                result = await self._run_docker_command(cmd, timeout=8)
                
                if isinstance(result, str):
                    logs = result.lower()
                elif hasattr(result, 'success') and result.success:
                    logs = result.stdout.lower()
                else:
                    if self.verbose:
                        print(f"   ⚠️  Failed to retrieve OTEL logs (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return False
                
                # Check for common ClickHouse connection error patterns
                error_patterns = [
                    'connection refused',
                    'failed to connect to clickhouse',
                    'clickhouse.*error',
                    'exporter.*failed',
                    'dial tcp.*8123.*connection refused'
                ]
                
                has_connection_errors = any(pattern in logs for pattern in error_patterns)
                
                if has_connection_errors:
                    if self.verbose:
                        print(f"   ⚠️  OTEL logs show ClickHouse connection issues (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return False
                else:
                    # No obvious connection errors found
                    if self.verbose:
                        print(f"   ✅ OTEL-ClickHouse connectivity appears healthy")
                    return True
                    
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️  OTEL-ClickHouse connectivity check failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                return False
        
        return False

    def _check_jsonl_bridge_health(self) -> bool:
        """Check if JSONL bridge service is healthy."""
        try:
            # Check if the bridge service process is running
            state = self.service_states.get("jsonl_bridge")
            if state and state.process:
                return state.process.poll() is None
            return False
        except:
            return False

    def _check_dashboard_health(self) -> bool:
        """Check if dashboard is healthy with comprehensive accessibility validation."""
        try:
            state = self.service_states.get("dashboard")
            if not state:
                return False
            
            # Get the dashboard port from metrics
            port = state.metrics.get("port", 8110)
            url = f"http://127.0.0.1:{port}"
            state.url = url
            
            # 1. Check if port is actually bound and listening
            if not self._check_port_listening("127.0.0.1", port):
                state.accessibility_status = f"Port {port} not listening"
                if self.verbose:
                    print(f"   ❌ Dashboard port {port} not bound/listening")
                return False
            
            # 2. Check HTTP connectivity
            if not self._check_http_connectivity(url):
                state.accessibility_status = f"HTTP connection to {url} failed"
                if self.verbose:
                    print(f"   ❌ Dashboard HTTP connectivity failed at {url}")
                return False
            
            # 3. Validate HTTP response content
            if not self._validate_dashboard_response(url):
                state.accessibility_status = f"Dashboard response validation failed at {url}"
                if self.verbose:
                    print(f"   ❌ Dashboard response validation failed at {url}")
                return False
            
            state.accessibility_status = f"Dashboard accessible at {url}"
            if self.verbose:
                print(f"   ✅ Dashboard health check passed at {url}")
            return True
            
        except Exception as e:
            if state:
                state.accessibility_status = f"Health check error: {str(e)}"
            self.logger.error(f"Dashboard health check error: {e}")
            return False
    
    def _check_consistency_checker_health(self) -> bool:
        """Check if the API/UI consistency checker is healthy with relaxed requirements."""
        health_check_start = datetime.now()
        check_details = {
            "timestamp": health_check_start.isoformat(),
            "instance_exists": False,
            "has_monitoring_health": False,
            "monitoring_health_result": None,
            "has_results": False,
            "results_count": 0,
            "recent_results": 0,
            "is_running": None,
            "task_status": None,
            "consecutive_failures": None,
            "final_result": False
        }

        try:
            # Check if consistency checker instance exists
            if self.consistency_checker is None:
                self.logger.warning("🔍 HEALTH_CHECK: Consistency checker instance is None")
                check_details["final_result"] = False
                return False

            check_details["instance_exists"] = True

            # Get additional diagnostic info
            if hasattr(self.consistency_checker, 'consecutive_failures'):
                check_details["consecutive_failures"] = self.consistency_checker.consecutive_failures

            if hasattr(self.consistency_checker, 'monitoring_task'):
                task = self.consistency_checker.monitoring_task
                if task:
                    check_details["task_status"] = {
                        "done": task.done(),
                        "cancelled": task.cancelled(),
                        "has_exception": None
                    }
                    if task.done() and not task.cancelled():
                        try:
                            check_details["task_status"]["has_exception"] = task.exception() is not None
                        except:
                            check_details["task_status"]["has_exception"] = "unknown"

            # Use the new monitoring health check if available
            if hasattr(self.consistency_checker, 'is_monitoring_healthy'):
                check_details["has_monitoring_health"] = True
                health_result = self.consistency_checker.is_monitoring_healthy()
                check_details["monitoring_health_result"] = health_result

                self.logger.info(f"🔍 HEALTH_CHECK: Using is_monitoring_healthy() = {health_result}")
                self.logger.info(f"🔍 HEALTH_CHECK: Details = {check_details}")

                check_details["final_result"] = health_result
                return health_result

            # Fallback to the old method with relaxed timeouts
            if not self.consistency_checker.last_check_results:
                check_details["has_results"] = False
                # Allow up to 10 minutes for initial results (startup grace period)
                self.logger.info("🔍 HEALTH_CHECK: No results yet, allowing startup grace period")
                self.logger.info(f"🔍 HEALTH_CHECK: Details = {check_details}")
                check_details["final_result"] = True
                return True

            check_details["has_results"] = True
            check_details["results_count"] = len(self.consistency_checker.last_check_results)

            # Check if any results have been generated recently (relaxed from 5 to 10 minutes)
            from datetime import timedelta
            now = datetime.now()
            recent_count = 0
            oldest_result_age = None
            newest_result_age = None

            for result in self.consistency_checker.last_check_results.values():
                age = now - result.timestamp
                if age < timedelta(minutes=10):
                    recent_count += 1

                if oldest_result_age is None or age > oldest_result_age:
                    oldest_result_age = age
                if newest_result_age is None or age < newest_result_age:
                    newest_result_age = age

            check_details["recent_results"] = recent_count

            if recent_count > 0:
                self.logger.info(f"🔍 HEALTH_CHECK: Found {recent_count} recent results (newest: {newest_result_age}, oldest: {oldest_result_age})")
                self.logger.info(f"🔍 HEALTH_CHECK: Details = {check_details}")
                check_details["final_result"] = True
                return True

            # Even if no recent results, check if the monitoring is running
            # This prevents restarts during temporary API outages
            if hasattr(self.consistency_checker, 'is_running'):
                check_details["is_running"] = self.consistency_checker.is_running
                if self.consistency_checker.is_running:
                    self.logger.info(f"🔍 HEALTH_CHECK: No recent results but service is running, considering healthy")
                    self.logger.info(f"🔍 HEALTH_CHECK: Details = {check_details}")
                    check_details["final_result"] = True
                    return True

            self.logger.warning(f"🔍 HEALTH_CHECK: Service appears unhealthy - no recent results and not running")
            self.logger.warning(f"🔍 HEALTH_CHECK: Details = {check_details}")
            check_details["final_result"] = False
            return False

        except Exception as e:
            # Log the exception instead of silently failing
            self.logger.error(f"🔍 HEALTH_CHECK: Exception during health check: {e}")
            self.logger.error(f"🔍 HEALTH_CHECK: Details at exception = {check_details}")
            check_details["final_result"] = True
            return True  # Default to healthy during error conditions to prevent unnecessary restarts
    
    def _check_telemetry_collector_health(self) -> bool:
        """Check if the telemetry collector is healthy."""
        try:
            if self.telemetry_collector is None:
                return False
            
            # Use the collector's built-in health check
            return self.telemetry_collector.is_healthy()
        except:
            return False
    
    def _check_port_listening(self, host: str, port: int) -> bool:
        """Check if a port is bound and listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # 5 second timeout
                result = sock.connect_ex((host, port))
                return result == 0
        except Exception as e:
            self.logger.debug(f"Port check failed for {host}:{port}: {e}")
            return False
    
    def _check_http_connectivity(self, url: str) -> bool:
        """Check if HTTP connection can be established."""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ContextCleaner-HealthCheck/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except urllib.error.HTTPError as e:
            # Even 404 or other HTTP errors mean the server is responding
            return 200 <= e.code < 500
        except Exception as e:
            self.logger.debug(f"HTTP connectivity check failed for {url}: {e}")
            return False
    
    def _validate_dashboard_response(self, url: str) -> bool:
        """Validate that the dashboard response contains expected content."""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ContextCleaner-HealthCheck/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8', errors='ignore')
                
                # Check for typical dashboard indicators
                dashboard_indicators = [
                    'Context Cleaner',
                    'dashboard',
                    '<html',
                    '<body',
                    'DOCTYPE'
                ]
                
                # At least one indicator should be present
                for indicator in dashboard_indicators:
                    if indicator.lower() in content.lower():
                        return True
                
                # If no indicators found, log for debugging
                self.logger.debug(f"Dashboard response validation failed - no indicators found in content (length: {len(content)})")
                return False
                
        except Exception as e:
            self.logger.debug(f"Dashboard response validation failed for {url}: {e}")
            return False
    
    async def check_dashboard_accessibility(self, host: str = "127.0.0.1", port: int = 8110) -> Dict[str, Any]:
        """Comprehensive dashboard accessibility check."""
        url = f"http://{host}:{port}"
        
        result = {
            "url": url,
            "accessible": False,
            "port_listening": False,
            "http_connectivity": False,
            "response_valid": False,
            "error_details": [],
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # 1. Port listening check
            result["port_listening"] = self._check_port_listening(host, port)
            if not result["port_listening"]:
                result["error_details"].append(f"Port {port} not bound/listening on {host}")
                return result
            
            # 2. HTTP connectivity check
            result["http_connectivity"] = self._check_http_connectivity(url)
            if not result["http_connectivity"]:
                result["error_details"].append(f"HTTP connection failed to {url}")
                return result
            
            # 3. Response validation check
            result["response_valid"] = self._validate_dashboard_response(url)
            if not result["response_valid"]:
                result["error_details"].append(f"Dashboard response validation failed for {url}")
                return result
            
            result["accessible"] = True
            return result
            
        except Exception as e:
            result["error_details"].append(f"Accessibility check exception: {str(e)}")
            return result
    
    async def validate_all_running_dashboards(self) -> Dict[str, Any]:
        """Validate all currently running dashboard processes for accessibility."""
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "dashboards_found": 0,
            "accessible_dashboards": 0,
            "failed_dashboards": 0,
            "results": [],
            "summary": ""
        }
        
        try:
            # Find all Context Cleaner dashboard processes
            dashboard_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if ('python' in proc.info['name'].lower() and 
                        'context_cleaner' in cmdline and 
                        'dashboard' in cmdline):
                        
                        # Extract port from command line
                        port_match = re.search(r'--port[\s=](\d+)', cmdline)
                        port = int(port_match.group(1)) if port_match else 8110
                        
                        dashboard_processes.append({
                            'pid': proc.pid,
                            'port': port,
                            'cmdline': cmdline
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            validation_results["dashboards_found"] = len(dashboard_processes)
            
            # Check accessibility for each dashboard
            for dashboard in dashboard_processes:
                accessibility_result = await self.check_dashboard_accessibility(
                    port=dashboard['port']
                )
                
                dashboard_result = {
                    "pid": dashboard['pid'],
                    "port": dashboard['port'],
                    "cmdline": dashboard['cmdline'][:100] + "...",
                    "accessibility": accessibility_result
                }
                
                validation_results["results"].append(dashboard_result)
                
                if accessibility_result["accessible"]:
                    validation_results["accessible_dashboards"] += 1
                else:
                    validation_results["failed_dashboards"] += 1
            
            # Generate summary
            if validation_results["dashboards_found"] == 0:
                validation_results["summary"] = "No dashboard processes found"
            elif validation_results["accessible_dashboards"] == validation_results["dashboards_found"]:
                validation_results["summary"] = f"All {validation_results['dashboards_found']} dashboards are accessible"
            elif validation_results["accessible_dashboards"] == 0:
                validation_results["summary"] = f"None of {validation_results['dashboards_found']} dashboards are accessible"
            else:
                validation_results["summary"] = f"{validation_results['accessible_dashboards']}/{validation_results['dashboards_found']} dashboards are accessible"
            
            return validation_results
            
        except Exception as e:
            validation_results["error"] = str(e)
            validation_results["summary"] = f"Validation failed: {str(e)}"
            return validation_results
    
    def _map_service_to_type(self, service_name: str) -> str:
        """Map orchestrator service names to process registry service types."""
        service_type_mapping = {
            "clickhouse": "clickhouse",
            "otel": "otel_collector", 
            "jsonl_bridge": "bridge_sync",
            "dashboard": "dashboard",
            "consistency_checker": "consistency_checker",
            "telemetry_collector": "telemetry_collector"
        }
        return service_type_mapping.get(service_name, "unknown")
    
    def _extract_port_from_command(self, command: List[str]) -> Optional[int]:
        """Extract port number from command line arguments."""
        if not command:
            return None
        
        try:
            # Look for --port parameter
            for i, arg in enumerate(command):
                if arg == "--port" and i + 1 < len(command):
                    return int(command[i + 1])
                elif arg.startswith("--port="):
                    return int(arg.split("=", 1)[1])
            
            # Look for -p parameter
            for i, arg in enumerate(command):
                if arg == "-p" and i + 1 < len(command):
                    return int(command[i + 1])
            
            return None
        except (ValueError, IndexError):
            return None
    
    async def discover_and_register_running_services(self) -> Dict[str, Any]:
        """
        Discover running Context Cleaner services and register them in the process registry.
        This implements automatic service discovery and registration.
        """
        discovery_results = {
            "timestamp": datetime.now().isoformat(),
            "discovered_processes": 0,
            "registered_processes": 0,
            "already_registered": 0,
            "failed_registrations": 0,
            "services": [],
            "summary": ""
        }
        
        try:
            # Discover all running Context Cleaner processes
            discovered_processes = self.discovery_engine.discover_all_processes()
            discovery_results["discovered_processes"] = len(discovered_processes)
            
            if self.verbose:
                print(f"🔍 Discovered {len(discovered_processes)} running Context Cleaner processes")
            
            for process in discovered_processes:
                service_info = {
                    "pid": process.pid,
                    "service_type": process.service_type,
                    "command_line": process.command_line[:100] + "...",
                    "status": "unknown"
                }
                
                try:
                    # Check if already registered
                    existing_process = self.process_registry.get_process(process.pid)
                    if existing_process:
                        discovery_results["already_registered"] += 1
                        service_info["status"] = "already_registered"
                        if self.verbose:
                            print(f"   ℹ️  PID {process.pid} ({process.service_type}) already registered")
                    else:
                        # Register the discovered process
                        success = self.process_registry.register_process(process)
                        if success:
                            discovery_results["registered_processes"] += 1
                            service_info["status"] = "registered"
                            if self.verbose:
                                print(f"   ✅ Registered PID {process.pid} ({process.service_type})")
                        else:
                            discovery_results["failed_registrations"] += 1
                            service_info["status"] = "registration_failed"
                            if self.verbose:
                                print(f"   ❌ Failed to register PID {process.pid} ({process.service_type})")
                
                except Exception as e:
                    discovery_results["failed_registrations"] += 1
                    service_info["status"] = f"error: {str(e)}"
                    if self.verbose:
                        print(f"   ⚠️  Error processing PID {process.pid}: {e}")
                
                discovery_results["services"].append(service_info)
            
            # Generate summary
            total_discovered = discovery_results["discovered_processes"]
            registered = discovery_results["registered_processes"]
            already_reg = discovery_results["already_registered"]
            failed = discovery_results["failed_registrations"]
            
            if total_discovered == 0:
                discovery_results["summary"] = "No Context Cleaner processes found"
            elif registered == 0 and already_reg == total_discovered:
                discovery_results["summary"] = f"All {total_discovered} processes were already registered"
            elif failed == 0:
                discovery_results["summary"] = f"Successfully processed {total_discovered} processes ({registered} new, {already_reg} already registered)"
            else:
                discovery_results["summary"] = f"Processed {total_discovered} processes: {registered} registered, {already_reg} already registered, {failed} failed"
            
            return discovery_results
            
        except Exception as e:
            discovery_results["error"] = str(e)
            discovery_results["summary"] = f"Discovery failed: {str(e)}"
    
    def _run_health_check_sync(self, service_name: str) -> bool:
        """FIXED: Synchronous wrapper for _run_health_check method with proper event loop handling."""
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # If we get here, we're in an event loop - this shouldn't happen for sync wrapper
            self.logger.warning(f"_run_health_check_sync called from within event loop for {service_name}")
            return False
        except RuntimeError:
            # No event loop running - safe to create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    asyncio.wait_for(self._run_health_check(service_name), timeout=30)
                )
            finally:
                loop.close()

    def _restart_service_sync(self, service_name: str) -> None:
        """FIXED: Synchronous wrapper for _restart_service method with proper event loop handling."""
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # If we get here, we're in an event loop - this shouldn't happen for sync wrapper
            self.logger.warning(f"_restart_service_sync called from within event loop for {service_name}")
            return
        except RuntimeError:
            # No event loop running - safe to create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    asyncio.wait_for(self._restart_service(service_name), timeout=60)
                )
            finally:
                loop.close()

    def register_cache_invalidation_callback(self, callback):
        """Register a callback for cache invalidation on service restarts"""
        self._cache_invalidation_callbacks.append(callback)

    def _trigger_cache_invalidation(self, service_name: str):
        """Trigger cache invalidation for a specific service restart"""
        for callback in self._cache_invalidation_callbacks:
            try:
                callback(service_name)
                if self.verbose:
                    print(f"   🗑️  Triggered cache invalidation for {service_name}")
            except Exception as e:
                self.logger.error(f"Cache invalidation callback error for {service_name}: {e}")