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
from .api_ui_consistency_checker import APIUIConsistencyChecker


class ServiceStatus(Enum):
    """Service status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    UNKNOWN = "unknown"


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

    async def _start_service(self, service_name: str) -> bool:
        """Start a specific service."""
        service = self.services[service_name]
        state = self.service_states[service_name]
        
        state.status = ServiceStatus.STARTING
        
        try:
            # Check if dependencies are running
            for dep in service.dependencies:
                dep_state = self.service_states.get(dep)
                if not dep_state or dep_state.status != ServiceStatus.RUNNING:
                    state.last_error = f"Dependency {dep} not running"
                    state.status = ServiceStatus.FAILED
                    return False
            
            # Start the service
            if service.start_command:
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
            
            # Wait for service to become healthy
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
        """Check if dashboard is healthy."""
        try:
            # Dashboard health is managed by the main process
            # This is a placeholder for future HTTP health checks
            return True
        except:
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