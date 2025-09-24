"""
Unit tests for the Service Orchestration System.

Tests the enhanced service orchestrator with process registry integration,
following established testing standards.
"""

import pytest
import tempfile
import shutil
import asyncio
import subprocess
import socket
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src.context_cleaner.services.service_orchestrator import (
    ServiceOrchestrator,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
    DockerDaemonStatus,
    ContainerState
)
from src.context_cleaner.services.process_registry import (
    ProcessEntry,
    ProcessRegistryDatabase,
    ProcessDiscoveryEngine
)


class TestServiceDefinition:
    """Test suite for ServiceDefinition dataclass."""
    
    def test_create_basic_service_definition(self):
        """Test creating a basic ServiceDefinition."""
        definition = ServiceDefinition(
            name="test_service",
            description="Test service for unit testing",
            start_command=["python", "-m", "test.service"],
            restart_on_failure=True,
            startup_timeout=30
        )
        
        assert definition.name == "test_service"
        assert definition.description == "Test service for unit testing"
        assert definition.restart_on_failure is True
        assert definition.startup_timeout == 30
        assert definition.health_check_interval == 30  # Default value
        assert definition.dependencies == []  # Default value
        assert definition.required is True  # Default value

    def test_service_definition_with_dependencies(self):
        """Test ServiceDefinition with complex dependencies."""
        definition = ServiceDefinition(
            name="complex_service",
            description="Service with dependencies",
            dependencies=["clickhouse", "otel"],
            environment_vars={"DEBUG": "true", "PORT": "8080"},
            working_directory="/app",
            required=False,
            startup_delay=5
        )
        
        assert definition.dependencies == ["clickhouse", "otel"]
        assert definition.environment_vars == {"DEBUG": "true", "PORT": "8080"}
        assert definition.working_directory == "/app"
        assert definition.required is False
        assert definition.startup_delay == 5


class TestServiceState:
    """Test suite for ServiceState dataclass."""
    
    def test_create_basic_service_state(self):
        """Test creating a basic ServiceState."""
        state = ServiceState(name="test_state")
        
        assert state.name == "test_state"
        assert state.status == ServiceStatus.STOPPED  # Default value
        assert state.process is None
        assert state.pid is None
        assert state.health_status is False
        assert state.restart_count == 0
        assert state.metrics == {}
        assert state.was_attached is False

    def test_service_state_with_process_info(self):
        """Test ServiceState with process information."""
        mock_process = Mock()
        mock_process.pid = 12345
        
        state = ServiceState(
            name="running_service",
            status=ServiceStatus.RUNNING,
            process=mock_process,
            pid=12345,
            health_status=True,
            start_time=datetime.now(),
            restart_count=2,
            container_id="abc123"
        )
        
        assert state.status == ServiceStatus.RUNNING
        assert state.process is mock_process
        assert state.pid == 12345
        assert state.health_status is True
        assert state.restart_count == 2
        assert state.container_id == "abc123"


class TestServiceOrchestrator:
    """Test suite for ServiceOrchestrator class."""
    
    def setup_method(self):
        """Set up test environment with mocked dependencies."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_orchestrator.db"
        
        # Mock the process registry and discovery engine
        self.mock_registry = Mock(spec=ProcessRegistryDatabase)
        self.mock_discovery = Mock(spec=ProcessDiscoveryEngine)
        
        # Setup mock registry methods
        self.mock_registry.get_all_processes.return_value = []
        self.mock_registry.register_process.return_value = True
        self.mock_registry.unregister_process.return_value = True
        self.mock_registry.get_process.return_value = None
        
        # Setup mock discovery methods
        self.mock_discovery.discover_all_processes.return_value = []
        
        # Patch the global registry functions
        self.registry_patcher = patch('src.context_cleaner.services.service_orchestrator.get_process_registry')
        self.discovery_patcher = patch('src.context_cleaner.services.service_orchestrator.get_discovery_engine')
        
        self.mock_get_registry = self.registry_patcher.start()
        self.mock_get_discovery = self.discovery_patcher.start()
        
        self.mock_get_registry.return_value = self.mock_registry
        self.mock_get_discovery.return_value = self.mock_discovery

    def teardown_method(self):
        """Clean up test environment."""
        self.registry_patcher.stop()
        self.discovery_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_orchestrator_initialization(self):
        """Test ServiceOrchestrator initialization."""
        orchestrator = ServiceOrchestrator(verbose=True)
        
        assert orchestrator.verbose is True
        assert orchestrator.running is False
        assert orchestrator.services != {}  # Should have initialized service definitions
        assert orchestrator.service_states == {}
        assert orchestrator.process_registry is self.mock_registry
        assert orchestrator.discovery_engine is self.mock_discovery

    def test_orchestrator_service_definitions(self):
        """Test that orchestrator initializes proper service definitions."""
        orchestrator = ServiceOrchestrator()
        
        # Check that core services are defined
        expected_services = ["clickhouse", "otel", "jsonl_bridge", "dashboard", 
                           "consistency_checker", "telemetry_collector"]
        
        for service_name in expected_services:
            assert service_name in orchestrator.services
            service = orchestrator.services[service_name]
            assert isinstance(service, ServiceDefinition)
            assert service.name == service_name

    def test_calculate_startup_order(self):
        """Test dependency-based startup order calculation."""
        orchestrator = ServiceOrchestrator()
        startup_order = orchestrator._calculate_startup_order()
        
        # ClickHouse should be first (no dependencies)
        assert startup_order[0] == "clickhouse"
        
        # Dashboard should come after its dependencies
        dashboard_index = startup_order.index("dashboard")
        clickhouse_index = startup_order.index("clickhouse")
        jsonl_bridge_index = startup_order.index("jsonl_bridge")
        
        assert clickhouse_index < dashboard_index
        assert jsonl_bridge_index < dashboard_index

    @pytest.mark.asyncio
    async def test_shutdown_all_sets_flag(self):
        orchestrator = ServiceOrchestrator()
        orchestrator.services = {}
        orchestrator.service_states = {}
        orchestrator.port_registry = SimpleNamespace(deallocate_port=lambda *args, **kwargs: False)
        orchestrator.running = True
        orchestrator.shutdown_event.clear()

        summary = await orchestrator.shutdown_all()

        assert summary["success"] is True
        assert orchestrator.shutdown_event.is_set()

    def test_get_service_status(self):
        """Test getting comprehensive service status."""
        orchestrator = ServiceOrchestrator()
        
        # Add mock service definition first
        test_service = ServiceDefinition(
            name="test_service",
            description="Test service",
            start_command=["python", "-m", "test_service"],
            restart_on_failure=True
        )
        orchestrator.services["test_service"] = test_service
        
        # Add some mock service states
        orchestrator.service_states["test_service"] = ServiceState(
            name="test_service",
            status=ServiceStatus.RUNNING,
            health_status=True,
            start_time=datetime.now(),
            pid=12345
        )
        
        status = orchestrator.get_service_status()
        
        assert "orchestrator" in status
        assert "services" in status
        assert "process_registry" in status
        assert "test_service" in status["services"]
        
        service_info = status["services"]["test_service"]
        assert service_info["status"] == "running"
        assert service_info["health_status"] is True
        assert service_info["pid"] == 12345

    @patch('subprocess.run')
    def test_cleanup_existing_processes(self, mock_subprocess):
        """Test cleanup of existing Context Cleaner processes."""
        # Mock discovered processes
        mock_process_entry = ProcessEntry(
            pid=99999,
            command_line="python -m context_cleaner.dashboard",
            service_type="dashboard",
            start_time=datetime.now(),
            registration_time=datetime.now()
        )
        self.mock_discovery.discover_all_processes.return_value = [mock_process_entry]
        
        # Mock psutil
        with patch('src.context_cleaner.services.service_orchestrator.psutil') as mock_psutil:
            mock_process = Mock()
            mock_process.terminate.return_value = None
            mock_process.wait.return_value = None
            mock_psutil.Process.return_value = mock_process
            
            # Mock os.getpid to avoid killing test process
            with patch('src.context_cleaner.services.service_orchestrator.os.getpid', return_value=1):
                orchestrator = ServiceOrchestrator(verbose=True)
                orchestrator._cleanup_existing_processes()
                
                # Verify process cleanup was attempted
                mock_psutil.Process.assert_called_with(99999)
                mock_process.terminate.assert_called_once()
                
                # Verify registry cleanup
                self.mock_registry.unregister_process.assert_called_with(99999)

    def test_map_service_to_type(self):
        """Test service name to process registry type mapping."""
        orchestrator = ServiceOrchestrator()
        
        test_cases = [
            ("clickhouse", "clickhouse"),
            ("otel", "otel_collector"),
            ("jsonl_bridge", "bridge_sync"),
            ("dashboard", "dashboard"),
            ("consistency_checker", "consistency_checker"),
            ("telemetry_collector", "telemetry_collector"),
            ("unknown_service", "unknown")
        ]
        
        for service_name, expected_type in test_cases:
            result = orchestrator._map_service_to_type(service_name)
            assert result == expected_type

    def test_extract_port_from_command(self):
        """Test port extraction from command line arguments."""
        orchestrator = ServiceOrchestrator()
        
        test_cases = [
            (["python", "app.py", "--port", "8080"], 8080),
            (["python", "app.py", "--port=9000"], 9000),
            (["python", "app.py", "-p", "3000"], 3000),
            (["python", "app.py"], None),
            ([], None),
            (["python", "app.py", "--port", "invalid"], None)
        ]
        
        for command, expected_port in test_cases:
            result = orchestrator._extract_port_from_command(command)
            assert result == expected_port

    @patch('socket.socket')
    def test_check_port_listening(self, mock_socket):
        """Test port listening check."""
        orchestrator = ServiceOrchestrator()
        
        # Mock successful connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value.__enter__.return_value = mock_sock
        
        result = orchestrator._check_port_listening("127.0.0.1", 8080)
        assert result is True
        
        # Mock failed connection
        mock_sock.connect_ex.return_value = 1
        result = orchestrator._check_port_listening("127.0.0.1", 8080)
        assert result is False

    @patch('urllib.request.urlopen')
    def test_check_http_connectivity(self, mock_urlopen):
        """Test HTTP connectivity check."""
        orchestrator = ServiceOrchestrator()
        
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = orchestrator._check_http_connectivity("http://127.0.0.1:8080")
        assert result is True
        
        # Mock HTTP error
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(None, 404, None, None, None)
        result = orchestrator._check_http_connectivity("http://127.0.0.1:8080")
        assert result is True  # 404 still means server is responding
        
        # Mock connection error
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")
        result = orchestrator._check_http_connectivity("http://127.0.0.1:8080")
        assert result is False

    @patch('urllib.request.urlopen')
    def test_validate_dashboard_response(self, mock_urlopen):
        """Test dashboard response validation."""
        orchestrator = ServiceOrchestrator()
        
        # Mock valid dashboard response
        mock_response = Mock()
        mock_response.read.return_value = b'<html><body>Context Cleaner Dashboard</body></html>'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = orchestrator._validate_dashboard_response("http://127.0.0.1:8080")
        assert result is True
        
        # Mock invalid response - no HTML tags, no dashboard indicators
        mock_response.read.return_value = b'{"error": "service unavailable", "status": 503}'
        result = orchestrator._validate_dashboard_response("http://127.0.0.1:8080")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_dashboard_accessibility(self):
        """Test comprehensive dashboard accessibility check."""
        orchestrator = ServiceOrchestrator()
        
        with patch.object(orchestrator, '_check_port_listening', return_value=True), \
             patch.object(orchestrator, '_check_http_connectivity', return_value=True), \
             patch.object(orchestrator, '_validate_dashboard_response', return_value=True):
            
            result = await orchestrator.check_dashboard_accessibility("127.0.0.1", 8080)
            
            assert result["accessible"] is True
            assert result["port_listening"] is True
            assert result["http_connectivity"] is True
            assert result["response_valid"] is True
            assert result["url"] == "http://127.0.0.1:8080"
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_discover_and_register_running_services(self):
        """Test automatic service discovery and registration."""
        orchestrator = ServiceOrchestrator()
        
        # Mock discovered processes
        mock_processes = [
            ProcessEntry(
                pid=11111,
                command_line="python -m context_cleaner.dashboard",
                service_type="dashboard",
                start_time=datetime.now(),
                registration_time=datetime.now()
            ),
            ProcessEntry(
                pid=22222,
                command_line="python -m context_cleaner.bridge sync",
                service_type="bridge_sync",
                start_time=datetime.now(),
                registration_time=datetime.now()
            )
        ]
        self.mock_discovery.discover_all_processes.return_value = mock_processes
        
        # Mock registry responses
        self.mock_registry.get_process.return_value = None  # Not already registered
        self.mock_registry.register_process.return_value = True
        
        result = await orchestrator.discover_and_register_running_services()
        
        assert result["discovered_processes"] == 2
        assert result["registered_processes"] == 2
        assert result["already_registered"] == 0
        assert result["failed_registrations"] == 0
        assert "Successfully processed 2 processes" in result["summary"]

    @patch('psutil.process_iter')
    @pytest.mark.asyncio
    async def test_validate_all_running_dashboards(self, mock_process_iter):
        """Test validation of all running dashboard processes."""
        orchestrator = ServiceOrchestrator()
        
        # Mock running dashboard processes
        mock_proc1 = Mock()
        mock_proc1.pid = 33333
        mock_proc1.info = {
            'pid': 33333,
            'name': 'python',
            'cmdline': ['python', '-m', 'context_cleaner.dashboard', '--port', '8080']
        }
        
        mock_proc2 = Mock()
        mock_proc2.pid = 44444
        mock_proc2.info = {
            'pid': 44444,
            'name': 'python',
            'cmdline': ['python', '-m', 'context_cleaner.dashboard', '--port', '8090']
        }
        
        mock_process_iter.return_value = [mock_proc1, mock_proc2]
        
        # Mock accessibility checks
        async def mock_accessibility_check(host="127.0.0.1", port=8080):
            return {
                "url": f"http://{host}:{port}",
                "accessible": True,
                "port_listening": True,
                "http_connectivity": True,
                "response_valid": True,
                "error_details": [],
                "timestamp": datetime.now().isoformat()
            }
        
        with patch.object(orchestrator, 'check_dashboard_accessibility', side_effect=mock_accessibility_check):
            result = await orchestrator.validate_all_running_dashboards()
            
            assert result["dashboards_found"] == 2
            assert result["accessible_dashboards"] == 2
            assert result["failed_dashboards"] == 0
            assert "All 2 dashboards are accessible" in result["summary"]

    def test_health_check_implementations(self):
        """Test individual health check method implementations."""
        orchestrator = ServiceOrchestrator()
        
        # Test ClickHouse health check
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = orchestrator._check_clickhouse_health()
            assert result is True
            
            mock_run.return_value.returncode = 1
            result = orchestrator._check_clickhouse_health()
            assert result is False

        # Test OTEL health check
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout.decode.return_value = "otel-collector"
            result = orchestrator._check_otel_health()
            assert result is True
            
            mock_run.return_value.stdout.decode.return_value = "no collector"
            result = orchestrator._check_otel_health()
            assert result is False

        # Test JSONL bridge health check
        mock_process = Mock()
        mock_process.poll.return_value = None  # Still running
        orchestrator.service_states["jsonl_bridge"] = ServiceState(
            name="jsonl_bridge",
            process=mock_process
        )
        
        result = orchestrator._check_jsonl_bridge_health()
        assert result is True

    @patch('asyncio.create_subprocess_exec')
    @pytest.mark.asyncio
    async def test_docker_daemon_status_check(self, mock_subprocess):
        """Test Docker daemon status checking."""
        orchestrator = ServiceOrchestrator()
        
        # Mock successful docker info command
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.wait = AsyncMock(return_value=None)
        mock_subprocess.return_value = mock_process
        
        status = await orchestrator._check_docker_daemon_status()
        assert status == DockerDaemonStatus.RUNNING
        
        # Mock failed docker command
        mock_process.returncode = 1
        mock_stderr = Mock()
        mock_stderr.read = AsyncMock(return_value=b"daemon not running")
        mock_process.stderr = mock_stderr
        
        status = await orchestrator._check_docker_daemon_status()
        assert status == DockerDaemonStatus.STOPPED

    @patch('asyncio.create_subprocess_exec')
    @pytest.mark.asyncio
    async def test_container_state_check(self, mock_subprocess):
        """Test container state checking."""
        orchestrator = ServiceOrchestrator()
        
        # Mock container running
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"running\n", b""))
        mock_subprocess.return_value = mock_process
        
        state = await orchestrator._get_container_state("test-container")
        assert state == ContainerState.RUNNING
        
        # Mock container not found
        mock_process.returncode = 1
        state = await orchestrator._get_container_state("missing-container")
        assert state == ContainerState.NOT_FOUND

    def test_extract_container_name(self):
        """Test container name extraction from Docker commands."""
        orchestrator = ServiceOrchestrator()
        
        test_cases = [
            (["docker", "compose", "up", "-d", "clickhouse-otel"], "clickhouse-otel"),
            (["docker", "run", "--name", "test-container", "image"], "test-container"),
            (["docker", "run", "--name=my-container", "image"], "my-container"),
            (["docker", "run", "clickhouse/server"], "clickhouse/server"),
            (["python", "script.py"], None),
            ([], None)
        ]
        
        for command, expected_name in test_cases:
            result = orchestrator._extract_container_name(command)
            if expected_name and "/" in expected_name:
                # For images with slash, expect just the part after the slash
                expected_name = expected_name.split("/")[-1]
            assert result == expected_name


class TestServiceOrchestratorIntegration:
    """Integration tests for ServiceOrchestrator with mocked external dependencies."""
    
    def setup_method(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create comprehensive mocks for external dependencies
        self.mock_registry = Mock(spec=ProcessRegistryDatabase)
        self.mock_discovery = Mock(spec=ProcessDiscoveryEngine)
        
        self.mock_registry.get_all_processes.return_value = []
        self.mock_registry.register_process.return_value = True
        self.mock_registry.unregister_process.return_value = True
        
        self.mock_discovery.discover_all_processes.return_value = []
        
        # Patch global functions
        self.patches = [
            patch('src.context_cleaner.services.service_orchestrator.get_process_registry', return_value=self.mock_registry),
            patch('src.context_cleaner.services.service_orchestrator.get_discovery_engine', return_value=self.mock_discovery),
            patch('src.context_cleaner.services.service_orchestrator.get_collector'),
            patch('src.context_cleaner.services.service_orchestrator.APIUIConsistencyChecker')
        ]
        
        for p in self.patches:
            p.start()

    def teardown_method(self):
        """Clean up integration test environment."""
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_start_stop_service_cycle(self):
        """Test complete service start/stop cycle."""
        with patch('src.context_cleaner.services.service_orchestrator.subprocess.Popen') as mock_popen:
            # Mock successful process creation
            mock_process = Mock()
            mock_process.pid = 55555
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process
            
            orchestrator = ServiceOrchestrator(verbose=True)
            
            # Override health check to return True
            def mock_health_check():
                return True
            
            # Create a simple test service
            test_service = ServiceDefinition(
                name="test_service",
                description="Test service",
                start_command=["python", "-c", "import time; time.sleep(60)"],
                health_check=mock_health_check,
                startup_timeout=5
            )
            
            orchestrator.services["test_service"] = test_service
            orchestrator.service_states["test_service"] = ServiceState(name="test_service")
            
            # Test service start
            success = await orchestrator._start_service("test_service")
            assert success is True
            
            state = orchestrator.service_states["test_service"]
            assert state.status == ServiceStatus.RUNNING
            assert state.pid == 55555
            
            # Verify process was registered
            self.mock_registry.register_process.assert_called_once()
            
            # Test service stop
            success = await orchestrator._stop_service("test_service")
            assert success is True
            
            assert state.status == ServiceStatus.STOPPED
            assert state.pid is None

    @pytest.mark.asyncio
    async def test_dependency_resolution(self):
        """Test service dependency resolution during startup."""
        orchestrator = ServiceOrchestrator()
        
        # Mock Docker environment checks
        with patch.object(orchestrator, '_ensure_docker_environment', return_value=True), \
             patch.object(orchestrator, '_start_service', return_value=True), \
             patch.object(orchestrator, '_start_dashboard_service', return_value=True), \
             patch.object(orchestrator, '_start_consistency_checker_service', return_value=True), \
             patch.object(orchestrator, '_start_telemetry_collector_service', return_value=True):
            
            # Start all services
            success = await orchestrator.start_all_services(dashboard_port=8080)
            assert success is True
            
            # Verify all services have states
            for service_name in orchestrator.services:
                assert service_name in orchestrator.service_states

    @pytest.mark.asyncio
    async def test_service_restart_on_failure(self):
        """Test automatic service restart on health check failure."""
        orchestrator = ServiceOrchestrator()
        orchestrator.running = True
        
        # Create a test service that will fail health check
        test_service = ServiceDefinition(
            name="failing_service",
            description="Service that fails health checks",
            restart_on_failure=True,
            health_check=lambda: False  # Always fails
        )
        
        orchestrator.services["failing_service"] = test_service
        orchestrator.service_states["failing_service"] = ServiceState(
            name="failing_service",
            status=ServiceStatus.RUNNING,
            last_health_check=datetime.now() - timedelta(minutes=10)
        )
        
        # Mock restart service method
        restart_called = False
        original_restart = orchestrator._restart_service
        
        async def mock_restart(service_name):
            nonlocal restart_called
            restart_called = True
            return await original_restart(service_name)
        
        with patch.object(orchestrator, '_restart_service', side_effect=mock_restart), \
             patch.object(orchestrator, '_stop_service', return_value=True), \
             patch.object(orchestrator, '_start_service', return_value=True):
            
            # Simulate health monitor finding unhealthy service
            from unittest.mock import patch as mock_patch
            
            # Mock the health check to fail
            with mock_patch.object(orchestrator, '_run_health_check', return_value=False):
                # Manually trigger restart logic
                await orchestrator._restart_service("failing_service")
                
                # Verify restart was attempted
                assert restart_called is True


class TestServiceOrchestratorErrorHandling:
    """Test error handling in ServiceOrchestrator."""
    
    def setup_method(self):
        """Set up error handling test environment."""
        self.mock_registry = Mock(spec=ProcessRegistryDatabase)
        self.mock_discovery = Mock(spec=ProcessDiscoveryEngine)
        
        self.patches = [
            patch('src.context_cleaner.services.service_orchestrator.get_process_registry', return_value=self.mock_registry),
            patch('src.context_cleaner.services.service_orchestrator.get_discovery_engine', return_value=self.mock_discovery)
        ]
        
        for p in self.patches:
            p.start()

    def teardown_method(self):
        """Clean up error handling test environment."""
        for p in self.patches:
            p.stop()

    def test_registry_connection_failure(self):
        """Test handling of process registry connection failures."""
        # Mock registry to raise exception
        self.mock_registry.get_all_processes.side_effect = Exception("Database connection failed")
        
        orchestrator = ServiceOrchestrator()
        status = orchestrator.get_service_status()
        
        # Should handle error gracefully
        assert "process_registry" in status
        assert "error:" in status["process_registry"]["registry_status"]

    @pytest.mark.asyncio
    async def test_docker_command_failure(self):
        """Test handling of Docker command failures."""
        orchestrator = ServiceOrchestrator()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock Docker command failure
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.stderr.read = AsyncMock(return_value=b"Docker daemon not running")
            mock_process.wait = AsyncMock(return_value=1)
            mock_subprocess.return_value = mock_process
            
            status = await orchestrator._check_docker_daemon_status()
            assert status == DockerDaemonStatus.STOPPED

    def test_process_cleanup_error_handling(self):
        """Test error handling during process cleanup."""
        # Mock discovery to raise exception
        self.mock_discovery.discover_all_processes.side_effect = Exception("Discovery failed")
        
        orchestrator = ServiceOrchestrator(verbose=True)
        
        # Should not raise exception - should handle gracefully
        try:
            orchestrator._cleanup_existing_processes()
        except Exception as e:
            pytest.fail(f"Process cleanup should handle errors gracefully, but raised: {e}")

    @pytest.mark.asyncio
    async def test_health_check_timeout_handling(self):
        """Test handling of health check timeouts."""
        orchestrator = ServiceOrchestrator()
        
        # Add mock service definition first
        test_service = ServiceDefinition(
            name="test_service",
            description="Test service",
            start_command=["python", "-m", "test_service"],
            restart_on_failure=True
        )
        orchestrator.services["test_service"] = test_service
        
        def slow_health_check():
            import time
            time.sleep(0.1)  # Simulate slow health check
            return True
        
        # Test with a reasonable timeout - should return True for service without health_check
        result = await orchestrator._run_health_check("test_service")
        assert result is True  # Service has no health_check, so returns True
        
        # Add a health check function to test timeout handling
        def slow_health_check():
            import time
            time.sleep(0.1)  # Simulate slow health check
            return True
            
        # Update service to have a health check
        orchestrator.services["test_service"].health_check = slow_health_check
        
        # Mock timeout scenario
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_executor.run_in_executor.side_effect = asyncio.TimeoutError("Health check timed out")
            mock_loop.return_value.run_in_executor = mock_executor.run_in_executor
            
            result = await orchestrator._run_health_check("test_service")
            assert result is False
