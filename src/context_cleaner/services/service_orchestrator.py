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
from ..telemetry.collector import get_collector


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
        
        # Telemetry Collector
        self.telemetry_collector = None
        
        # Docker management
        self.docker_daemon_status = DockerDaemonStatus.UNKNOWN
        self.container_states: Dict[str, ContainerState] = {}
        
        # Initialize service definitions
        self._initialize_service_definitions()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _cleanup_existing_processes(self):
        """
        Clean up any existing Context Cleaner processes to ensure singleton operation.
        This prevents multiple instances of the same service from running.
        """
        if self.verbose:
            print("🧹 Cleaning up existing Context Cleaner processes...")
        
        try:
            # Find all processes matching Context Cleaner patterns
            context_cleaner_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # Check for Context Cleaner processes
                    if ('python' in proc.info['name'].lower() and 
                        'context_cleaner' in cmdline and
                        proc.pid != os.getpid()):  # Don't kill ourselves
                        
                        context_cleaner_processes.append({
                            'pid': proc.pid,
                            'cmdline': cmdline,
                            'process': proc
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if context_cleaner_processes:
                if self.verbose:
                    print(f"   Found {len(context_cleaner_processes)} existing processes to clean up:")
                    for proc_info in context_cleaner_processes:
                        print(f"   - PID {proc_info['pid']}: {proc_info['cmdline'][:80]}...")
                
                # Terminate processes gracefully
                for proc_info in context_cleaner_processes:
                    try:
                        proc = proc_info['process']
                        proc.terminate()
                        
                        # Wait up to 5 seconds for graceful termination
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            # Force kill if graceful termination failed
                            proc.kill()
                            proc.wait()
                            
                        if self.verbose:
                            print(f"   ✅ Cleaned up PID {proc_info['pid']}")
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process already gone or can't access it
                        continue
                
                # Brief pause to ensure cleanup is complete
                time.sleep(2)
                
                if self.verbose:
                    print("   🎯 Process cleanup complete")
            else:
                if self.verbose:
                    print("   ✅ No existing processes found")
                    
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Error during cleanup: {e}")
            # Continue anyway - don't let cleanup failures block startup

    def _initialize_service_definitions(self):
        """Initialize all service definitions for Context Cleaner."""
        
        # 1. ClickHouse Database (highest priority)
        self.services["clickhouse"] = ServiceDefinition(
            name="clickhouse",
            description="ClickHouse database for telemetry and analytics",
            start_command=["docker", "compose", "up", "-d", "clickhouse-otel"],
            stop_command=["docker", "compose", "stop", "clickhouse-otel"],
            health_check=self._check_clickhouse_health,
            health_check_interval=30,
            restart_on_failure=True,
            startup_timeout=120,
            shutdown_timeout=60,
            dependencies=[],
            required=True,
            startup_delay=0
        )
        
        # 2. OTEL Collector (if applicable)
        self.services["otel"] = ServiceDefinition(
            name="otel",
            description="OpenTelemetry collector for metrics gathering",
            start_command=["docker", "compose", "up", "-d", "otel-collector"],
            stop_command=["docker", "compose", "stop", "otel-collector"],
            health_check=self._check_otel_health,
            health_check_interval=60,
            restart_on_failure=False,  # Optional service
            startup_timeout=60,
            shutdown_timeout=30,
            dependencies=["clickhouse"],
            required=False,
            startup_delay=5
        )
        
        # 3. JSONL Bridge Service
        self.services["jsonl_bridge"] = ServiceDefinition(
            name="jsonl_bridge",
            description="Real-time JSONL file monitoring and processing",
            start_command=[
                sys.executable, "-m", "src.context_cleaner.cli.main",
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
            startup_delay=10
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
            health_check=self._check_consistency_checker_health,
            health_check_interval=120,
            restart_on_failure=True,
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
        
        success = True
        for service_name in startup_order:
            service = self.services[service_name]
            
            if self.verbose:
                print(f"🔄 Starting {service.description}...")
            
            # Wait for startup delay
            if service.startup_delay > 0:
                await asyncio.sleep(service.startup_delay)
            
            # Start the service
            try:
                if service_name == "dashboard":
                    success &= await self._start_dashboard_service(dashboard_port)
                elif service_name == "consistency_checker":
                    success &= await self._start_consistency_checker_service(dashboard_port)
                elif service_name == "telemetry_collector":
                    success &= await self._start_telemetry_collector_service()
                else:
                    success &= await self._start_service(service_name)
                
                if not success and service.required:
                    if self.verbose:
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
        
        # 2. Check container states and attach to running ones or start as needed
        container_names = ["clickhouse-otel", "otel-collector"]
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
        """Get the current state of a container."""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_name, "--format", "{{.State.Status}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                status = stdout.decode().strip().lower()
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
                # Container not found
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
                        if result and result.returncode == 0:
                            container_id = result.stdout.strip()
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
                        if restart_result and restart_result.returncode == 0:
                            state.container_state = ContainerState.RUNNING
                            state.start_time = datetime.now()
                            if self.verbose:
                                print(f"   ✅ Restarted {service_name} container")
                        else:
                            if self.verbose:
                                print(f"   ❌ Failed to restart {service_name} container")
                            state.last_error = f"Failed to restart container: {restart_result.stderr if restart_result else 'Unknown error'}"
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
                
                # For Docker services, update container metadata
                if "docker" in " ".join(service.start_command):
                    container_name = self._extract_container_name(service.start_command)
                    if container_name:
                        # Give container time to start
                        await asyncio.sleep(3)
                        
                        result = await self._run_docker_command(["ps", "-q", "--filter", f"name={container_name}"])
                        if result and result.returncode == 0 and result.stdout.strip():
                            state.container_id = result.stdout.strip()
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
        """Run health check for a service."""
        service = self.services[service_name]
        if not service.health_check:
            return True
            
        try:
            # Run health check in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                service.health_check
            )
            return bool(result)
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
                    if (state.last_health_check is None or 
                        (now - state.last_health_check).seconds >= service.health_check_interval):
                        
                        # Run health check
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        healthy = loop.run_until_complete(self._run_health_check(service_name))
                        loop.close()
                        
                        state.last_health_check = now
                        state.health_status = healthy
                        
                        # Handle unhealthy service
                        if not healthy and service.restart_on_failure:
                            self.logger.warning(f"Service {service_name} is unhealthy, restarting...")
                            if self.verbose:
                                print(f"⚠️ Restarting unhealthy service: {service.description}")
                            
                            # Restart service
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._restart_service(service_name))
                            loop.close()
                
                # Sleep before next check
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                time.sleep(30)

    async def _restart_service(self, service_name: str):
        """Restart a specific service."""
        state = self.service_states[service_name]
        state.restart_count += 1
        
        # Stop the service
        await self._stop_service(service_name)
        
        # Wait a moment
        await asyncio.sleep(5)
        
        # Start the service
        if service_name == "dashboard":
            port = state.metrics.get("port", 8110)
            await self._start_dashboard_service(port)
        elif service_name == "consistency_checker":
            port = state.metrics.get("port", 8110)
            await self._start_consistency_checker_service(port)
        elif service_name == "telemetry_collector":
            await self._start_telemetry_collector_service()
        else:
            await self._start_service(service_name)

    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all services."""
        status = {
            "orchestrator": {
                "running": self.running,
                "uptime": (datetime.now() - datetime.now()).total_seconds() if self.running else 0
            },
            "services": {}
        }
        
        for service_name, state in self.service_states.items():
            service = self.services[service_name]
            
            status["services"][service_name] = {
                "name": service.description,
                "status": state.status.value,
                "required": service.required,
                "health_status": state.health_status,
                "last_health_check": state.last_health_check.isoformat() if state.last_health_check else None,
                "start_time": state.start_time.isoformat() if state.start_time else None,
                "restart_count": state.restart_count,
                "last_error": state.last_error,
                "pid": state.pid,
                "metrics": state.metrics
            }
        
        return status

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        if self.verbose:
            print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        
        # Run shutdown in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.stop_all_services())
        loop.close()

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
            
            # Start the monitoring in the background
            loop = asyncio.get_event_loop()
            loop.create_task(self.consistency_checker.start_monitoring())
            
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
            # The consistency checker monitoring loop should stop when self.running becomes False
            self.consistency_checker = None
            
            state.status = ServiceStatus.STOPPED
            state.health_status = False
            
            if self.verbose:
                print("   ✅ API/UI consistency checker stopped")
            
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

    # Health check implementations
    def _check_clickhouse_health(self) -> bool:
        """Check if ClickHouse is healthy."""
        try:
            result = subprocess.run(
                ["docker", "exec", "clickhouse-otel", "clickhouse-client", "--query", "SELECT 1"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False

    def _check_otel_health(self) -> bool:
        """Check if OTEL collector is healthy."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=otel-collector", "--filter", "status=running"],
                capture_output=True,
                timeout=5
            )
            return "otel-collector" in result.stdout.decode()
        except:
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
        """Check if the API/UI consistency checker is healthy."""
        try:
            # Check if consistency checker instance exists and has recent results
            if self.consistency_checker is None:
                return False
            
            # Check if we have recent consistency check results (within last 5 minutes)
            if not self.consistency_checker.last_check_results:
                return False
            
            # Check if any results have been generated recently
            from datetime import timedelta
            now = datetime.now()
            for result in self.consistency_checker.last_check_results.values():
                if now - result.timestamp < timedelta(minutes=5):
                    return True
            
            return False
        except:
            return False
    
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