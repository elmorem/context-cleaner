"""
Unit tests for the Process Registry system.

Tests the centralized process registry database and basic functionality
following established testing standards.
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from src.context_cleaner.services.process_registry import (
    ProcessEntry,
    ProcessRegistryDatabase,
    ProcessDiscoveryEngine,
    get_process_registry,
    get_discovery_engine
)


class TestProcessEntry:
    """Test suite for ProcessEntry dataclass."""
    
    def test_create_basic_process_entry(self):
        """Test creating a basic ProcessEntry."""
        entry = ProcessEntry(
            pid=12345,
            command_line="python -m context_cleaner.dashboard",
            service_type="dashboard",
            start_time=datetime.now(),
            registration_time=datetime.now()
        )
        
        assert entry.pid == 12345
        assert entry.service_type == "dashboard"
        assert entry.status == "running"  # Default value
        assert entry.port is None  # Default value
        assert entry.host == "127.0.0.1"  # Default value
    
    def test_process_entry_to_dict(self):
        """Test ProcessEntry.to_dict() method."""
        start_time = datetime.now()
        reg_time = datetime.now()
        
        entry = ProcessEntry(
            pid=11111,
            command_line="test command",
            service_type="test",
            start_time=start_time,
            registration_time=reg_time,
            port=9999
        )
        
        data = entry.to_dict()
        
        assert data["pid"] == 11111
        assert data["command_line"] == "test command"
        assert data["service_type"] == "test"
        assert data["port"] == 9999
        assert "start_time" in data
        assert "registration_time" in data
    
    def test_process_entry_from_dict(self):
        """Test ProcessEntry.from_dict() method."""
        start_time = datetime.now()
        reg_time = datetime.now()
        
        data = {
            "pid": 22222,
            "command_line": "another test command",
            "service_type": "dashboard",
            "start_time": start_time,
            "registration_time": reg_time,
            "port": 8888,
            "status": "stopped",
            # Extra database fields that should be filtered out
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        entry = ProcessEntry.from_dict(data)
        
        assert entry.pid == 22222
        assert entry.command_line == "another test command"
        assert entry.service_type == "dashboard"
        assert entry.port == 8888
        assert entry.status == "stopped"


class TestProcessRegistryDatabase:
    """Test suite for ProcessRegistryDatabase."""
    
    def setup_method(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_processes.db"
        self.registry = ProcessRegistryDatabase(str(self.db_path))
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """Test database is properly initialized."""
        assert self.db_path.exists()
    
    def test_register_process(self):
        """Test registering a new process."""
        entry = ProcessEntry(
            pid=12345,
            command_line="test command",
            service_type="dashboard",
            start_time=datetime.now(),
            registration_time=datetime.now(),
            port=8080
        )
        
        success = self.registry.register_process(entry)
        assert success is True
        
        # Verify process was registered
        processes = self.registry.get_all_processes()
        assert len(processes) == 1
        assert processes[0].pid == 12345
        assert processes[0].service_type == "dashboard"
    
    def test_unregister_process(self):
        """Test unregistering a process."""
        entry = ProcessEntry(
            pid=33333,
            command_line="test command",
            service_type="bridge_sync",
            start_time=datetime.now(),
            registration_time=datetime.now()
        )
        
        # Register process
        self.registry.register_process(entry)
        assert len(self.registry.get_all_processes()) == 1
        
        # Unregister process
        success = self.registry.unregister_process(33333)
        assert success is True
        
        # Verify process was removed
        processes = self.registry.get_all_processes()
        assert len(processes) == 0
    
    def test_get_process_by_pid(self):
        """Test retrieving a process by PID."""
        entry = ProcessEntry(
            pid=44444,
            command_line="specific command",
            service_type="telemetry_collector",
            start_time=datetime.now(),
            registration_time=datetime.now(),
            port=8181
        )
        
        self.registry.register_process(entry)
        
        # Retrieve by PID
        retrieved = self.registry.get_process(44444)
        assert retrieved is not None
        assert retrieved.pid == 44444
        assert retrieved.service_type == "telemetry_collector"
        
        # Try non-existent PID
        missing = self.registry.get_process(99999)
        assert missing is None
    
    def test_get_processes_by_type(self):
        """Test retrieving processes by service type."""
        # Register multiple processes of different types
        entries = [
            ProcessEntry(
                pid=1001, command_line="dashboard 1", service_type="dashboard",
                start_time=datetime.now(), registration_time=datetime.now()
            ),
            ProcessEntry(
                pid=1002, command_line="dashboard 2", service_type="dashboard",
                start_time=datetime.now(), registration_time=datetime.now()
            ),
            ProcessEntry(
                pid=2001, command_line="bridge sync", service_type="bridge_sync",
                start_time=datetime.now(), registration_time=datetime.now()
            )
        ]
        
        for entry in entries:
            self.registry.register_process(entry)
        
        # Get dashboard processes
        dashboard_processes = self.registry.get_processes_by_type("dashboard")
        assert len(dashboard_processes) == 2
        assert all(p.service_type == "dashboard" for p in dashboard_processes)
        
        # Get bridge_sync processes
        bridge_processes = self.registry.get_processes_by_type("bridge_sync")
        assert len(bridge_processes) == 1
        assert bridge_processes[0].service_type == "bridge_sync"


class TestProcessDiscoveryEngine:
    """Test suite for ProcessDiscoveryEngine."""
    
    def setup_method(self):
        """Set up test environment."""
        self.discovery = ProcessDiscoveryEngine()
    
    def test_determine_service_type(self):
        """Test service type determination from command line."""
        test_cases = [
            ("python -m context_cleaner.dashboard --port 8080", "dashboard"),
            ("python -m context_cleaner.bridge sync", "bridge_sync"),
            ("python -m context_cleaner.telemetry.collector", "telemetry_collector"),
            ("python -m context_cleaner.cli run", "orchestrator"),
            ("python -m context_cleaner.other", "unknown")
        ]
        
        for cmdline, expected_type in test_cases:
            result = self.discovery._determine_service_type(cmdline)
            assert result == expected_type
    
    @patch('psutil.process_iter')
    def test_discover_all_processes_basic(self, mock_process_iter):
        """Test basic process discovery functionality."""
        # Mock a simple Context Cleaner process
        mock_process = Mock()
        mock_process.info = {
            'pid': 2001,
            'name': 'python',
            'cmdline': ['python', '-m', 'context_cleaner.dashboard'],
            'create_time': 1234567890.0
        }
        
        mock_process_iter.return_value = [mock_process]
        
        # Discover processes
        discovered = self.discovery.discover_all_processes()
        
        # Should find 1 Context Cleaner process
        assert len(discovered) == 1
        assert discovered[0].pid == 2001
        assert discovered[0].service_type == "dashboard"


class TestGlobalRegistryFunctions:
    """Test global registry functions."""
    
    def test_get_process_registry(self):
        """Test getting global process registry instance."""
        registry1 = get_process_registry()
        registry2 = get_process_registry()
        
        # Should return same instance (singleton-like behavior)
        assert registry1 is registry2
        assert isinstance(registry1, ProcessRegistryDatabase)
    
    def test_get_discovery_engine(self):
        """Test getting discovery engine instance."""
        engine1 = get_discovery_engine()
        engine2 = get_discovery_engine()
        
        # Should return same instance (singleton-like behavior)
        assert engine1 is engine2
        assert isinstance(engine1, ProcessDiscoveryEngine)


class TestProcessRegistryIntegration:
    """Integration tests for process registry system."""
    
    def setup_method(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_integration.db"
        self.registry = ProcessRegistryDatabase(str(self.db_path))
        self.discovery = ProcessDiscoveryEngine()
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    @patch('psutil.process_iter')
    def test_discover_and_register_basic(self, mock_process_iter):
        """Test basic discover and register functionality."""
        # Mock discovered process
        mock_process = Mock()
        mock_process.info = {
            'pid': 7001,
            'name': 'python',
            'cmdline': ['python', '-m', 'context_cleaner.dashboard'],
            'create_time': 1234567890.0
        }
        mock_process_iter.return_value = [mock_process]
        
        # Discover processes
        discovered = self.discovery.discover_all_processes()
        assert len(discovered) == 1
        
        # Register discovered process
        success = self.registry.register_process(discovered[0])
        assert success is True
        
        # Verify process is registered
        registered = self.registry.get_all_processes()
        assert len(registered) == 1
        assert registered[0].pid == 7001
        assert registered[0].service_type == "dashboard"