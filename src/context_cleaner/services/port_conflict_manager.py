"""
Port Conflict Detection and Retry Management System

This module provides comprehensive port conflict detection and automatic retry
mechanisms for Context Cleaner services. It handles:
- Port availability checking
- Port conflict detection
- Automatic port selection with fallback strategies
- Retry monitoring and logging
"""

import asyncio
import socket
import time
import logging
import threading
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta


class PortConflictStrategy(Enum):
    """Strategy for handling port conflicts."""
    INCREMENT = "increment"  # Try port+1, port+2, etc.
    PREDEFINED_LIST = "predefined_list"  # Try from predefined fallback ports
    RANDOM_RANGE = "random_range"  # Try random ports in a range
    HYBRID = "hybrid"  # Combination of strategies


class RetryStatus(Enum):
    """Status of retry attempts."""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCESS = "success"
    FAILED = "failed"
    EXHAUSTED = "exhausted"


@dataclass
class PortRetryAttempt:
    """Details of a single port retry attempt."""
    attempt_number: int
    port: int
    timestamp: datetime
    error_message: Optional[str] = None
    success: bool = False
    duration_ms: Optional[int] = None


@dataclass
class PortConflictSession:
    """Tracks a complete port conflict resolution session."""
    service_name: str
    original_port: int
    strategy: PortConflictStrategy
    max_attempts: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: RetryStatus = RetryStatus.PENDING
    attempts: List[PortRetryAttempt] = field(default_factory=list)
    successful_port: Optional[int] = None
    total_duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class PortConflictManager:
    """
    Manages port conflict detection and automatic retry with fallback strategies.
    
    This system automatically detects port conflicts and retries service startup
    on alternative ports until successful or maximum attempts reached.
    """
    
    def __init__(self, verbose: bool = False, logger: Optional[logging.Logger] = None):
        self.verbose = verbose
        self.logger = logger or logging.getLogger(__name__)
        
        # Port ranges and fallback configurations
        self.default_fallback_ports = {
            "dashboard": [8080, 8081, 8082, 8083, 8084, 8085, 8088, 8110, 8200, 8333, 8888, 9000, 9001, 9002],
            "clickhouse": [8123, 8124, 8125, 8126, 8127],
            "otel": [4317, 4318, 4319, 4320, 4321]
        }
        
        # Active retry sessions
        self.active_sessions: Dict[str, PortConflictSession] = {}
        
        # Configuration
        self.default_max_attempts = 10
        self.default_timeout_seconds = 5
        self.port_check_timeout = 2
        
    def is_port_available(self, port: int, host: str = "127.0.0.1") -> Tuple[bool, Optional[str]]:
        """
        Check if a port is available for binding.

        Args:
            port: Port number to check
            host: Host address to check (default: 127.0.0.1)

        Returns:
            Tuple of (is_available, error_message)
        """
        import asyncio
        import concurrent.futures

        def _check_port_sync():
            """Synchronous port check to run in executor"""
            try:
                # Try to bind to the port
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(self.port_check_timeout)

                result = sock.bind((host, port))
                sock.close()
                return True, None

            except socket.error as e:
                error_msg = f"Port {port} unavailable: {e}"
                return False, error_msg
            except Exception as e:
                error_msg = f"Port check error for {port}: {e}"
                return False, error_msg

        try:
            # Run synchronously since socket operations are fast and we're in a controlled environment
            return _check_port_sync()

        except Exception as e:
            error_msg = f"Port check error for {port}: {e}"
            return False, error_msg
    
    async def detect_port_conflicts(self, service_ports: Dict[str, int]) -> Dict[str, bool]:
        """
        Detect port conflicts for multiple services.
        
        Args:
            service_ports: Dictionary mapping service names to port numbers
            
        Returns:
            Dictionary mapping service names to conflict status (True = conflict)
        """
        conflicts = {}
        
        for service_name, port in service_ports.items():
            available, error = self.is_port_available(port)
            conflicts[service_name] = not available
            
            if not available and self.verbose:
                print(f"⚠️  Port conflict detected: {service_name} port {port} - {error}")
        
        return conflicts
    
    def _generate_fallback_ports(
        self, 
        original_port: int, 
        service_name: str, 
        strategy: PortConflictStrategy,
        max_attempts: int
    ) -> List[int]:
        """Generate list of fallback ports based on strategy."""
        ports = []
        
        if strategy == PortConflictStrategy.INCREMENT:
            # Try incrementing ports: original+1, original+2, etc.
            for i in range(1, max_attempts + 1):
                ports.append(original_port + i)
                
        elif strategy == PortConflictStrategy.PREDEFINED_LIST:
            # Use predefined fallback ports for this service type
            fallback_ports = self.default_fallback_ports.get(service_name, [])
            # Remove original port if it's in the list
            fallback_ports = [p for p in fallback_ports if p != original_port]
            ports.extend(fallback_ports[:max_attempts])
            
        elif strategy == PortConflictStrategy.RANDOM_RANGE:
            # Generate random ports in safe range (8000-9999)
            import random
            used_ports = {original_port}
            for _ in range(max_attempts):
                while True:
                    port = random.randint(8000, 9999)
                    if port not in used_ports:
                        ports.append(port)
                        used_ports.add(port)
                        break
                        
        elif strategy == PortConflictStrategy.HYBRID:
            # Combination: predefined first, then increment, then random
            predefined = self.default_fallback_ports.get(service_name, [])
            predefined = [p for p in predefined if p != original_port]
            
            # Add predefined ports first
            ports.extend(predefined[:max_attempts//2])
            
            # Add increment ports
            for i in range(1, (max_attempts//3) + 1):
                candidate = original_port + i
                if candidate not in ports:
                    ports.append(candidate)
                    
            # Fill remaining with random if needed
            import random
            used_ports = set(ports + [original_port])
            while len(ports) < max_attempts:
                port = random.randint(8000, 9999)
                if port not in used_ports:
                    ports.append(port)
                    used_ports.add(port)
        
        return ports[:max_attempts]
    
    async def start_retry_session(
        self,
        service_name: str,
        original_port: int,
        strategy: PortConflictStrategy = PortConflictStrategy.HYBRID,
        max_attempts: int = None
    ) -> PortConflictSession:
        """
        Start a new port conflict retry session.
        
        Args:
            service_name: Name of the service
            original_port: Originally requested port
            strategy: Port selection strategy
            max_attempts: Maximum retry attempts
            
        Returns:
            PortConflictSession object for tracking
        """
        if max_attempts is None:
            max_attempts = self.default_max_attempts
            
        session = PortConflictSession(
            service_name=service_name,
            original_port=original_port,
            strategy=strategy,
            max_attempts=max_attempts,
            start_time=datetime.now(),
            status=RetryStatus.PENDING
        )
        
        self.active_sessions[service_name] = session
        
        if self.verbose:
            print(f"🔄 Starting port retry session: {service_name} (original port: {original_port})")
            print(f"   Strategy: {strategy.value}, Max attempts: {max_attempts}")
        
        return session
    
    async def find_available_port(
        self,
        service_name: str,
        original_port: int,
        strategy: PortConflictStrategy = PortConflictStrategy.HYBRID,
        max_attempts: int = None
    ) -> Tuple[Optional[int], PortConflictSession]:
        """
        Find an available port using the specified retry strategy.
        
        Args:
            service_name: Name of the service
            original_port: Originally requested port
            strategy: Port selection strategy
            max_attempts: Maximum retry attempts
            
        Returns:
            Tuple of (available_port, session) - port is None if no port found
        """
        session = await self.start_retry_session(service_name, original_port, strategy, max_attempts)
        session.status = RetryStatus.RETRYING
        
        # First check if original port is available
        start_time = time.time()
        available, error = await self.is_port_available(original_port)
        duration_ms = int((time.time() - start_time) * 1000)
        
        attempt = PortRetryAttempt(
            attempt_number=0,
            port=original_port,
            timestamp=datetime.now(),
            error_message=error,
            success=available,
            duration_ms=duration_ms
        )
        session.attempts.append(attempt)
        
        if available:
            session.status = RetryStatus.SUCCESS
            session.successful_port = original_port
            session.end_time = datetime.now()
            session.total_duration_ms = int((session.end_time - session.start_time).total_seconds() * 1000)
            
            if self.verbose:
                print(f"✅ Original port {original_port} available for {service_name}")
            
            return original_port, session
        
        # Generate fallback ports and try each one
        fallback_ports = self._generate_fallback_ports(original_port, service_name, strategy, max_attempts)
        
        if self.verbose:
            print(f"   Trying {len(fallback_ports)} fallback ports: {fallback_ports[:5]}{'...' if len(fallback_ports) > 5 else ''}")
        
        for attempt_num, port in enumerate(fallback_ports, 1):
            start_time = time.time()
            available, error = self.is_port_available(port)
            duration_ms = int((time.time() - start_time) * 1000)
            
            attempt = PortRetryAttempt(
                attempt_number=attempt_num,
                port=port,
                timestamp=datetime.now(),
                error_message=error,
                success=available,
                duration_ms=duration_ms
            )
            session.attempts.append(attempt)
            
            if available:
                session.status = RetryStatus.SUCCESS
                session.successful_port = port
                session.end_time = datetime.now()
                session.total_duration_ms = int((session.end_time - session.start_time).total_seconds() * 1000)
                
                if self.verbose:
                    print(f"✅ Found available port {port} for {service_name} (attempt {attempt_num})")
                
                return port, session
            
            elif self.verbose:
                print(f"   ❌ Port {port} unavailable (attempt {attempt_num})")
        
        # All attempts exhausted
        session.status = RetryStatus.EXHAUSTED
        session.end_time = datetime.now()
        session.total_duration_ms = int((session.end_time - session.start_time).total_seconds() * 1000)
        session.error_message = f"No available port found after {len(session.attempts)} attempts"
        
        if self.verbose:
            print(f"❌ Port retry exhausted for {service_name} - no available ports found")
        
        return None, session
    
    async def monitor_retry_session(self, service_name: str) -> Optional[PortConflictSession]:
        """
        Monitor an active retry session and return its current status.
        
        Args:
            service_name: Name of the service to monitor
            
        Returns:
            PortConflictSession if active, None if not found
        """
        return self.active_sessions.get(service_name)
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about all retry sessions.
        
        Returns:
            Dictionary with retry statistics and metrics
        """
        stats = {
            "total_sessions": len(self.active_sessions),
            "successful_sessions": 0,
            "failed_sessions": 0,
            "active_sessions": 0,
            "average_attempts": 0,
            "average_duration_ms": 0,
            "sessions_by_service": {},
            "port_usage_frequency": {},
            "strategy_success_rates": {}
        }
        
        if not self.active_sessions:
            return stats
        
        total_attempts = 0
        total_duration = 0
        strategy_counts = {}
        strategy_successes = {}
        
        for session in self.active_sessions.values():
            # Count by status
            if session.status == RetryStatus.SUCCESS:
                stats["successful_sessions"] += 1
            elif session.status in [RetryStatus.FAILED, RetryStatus.EXHAUSTED]:
                stats["failed_sessions"] += 1
            elif session.status in [RetryStatus.PENDING, RetryStatus.RETRYING]:
                stats["active_sessions"] += 1
            
            # Service statistics
            if session.service_name not in stats["sessions_by_service"]:
                stats["sessions_by_service"][session.service_name] = {
                    "count": 0,
                    "successful": 0,
                    "average_attempts": 0
                }
            
            service_stats = stats["sessions_by_service"][session.service_name]
            service_stats["count"] += 1
            
            if session.status == RetryStatus.SUCCESS:
                service_stats["successful"] += 1
                if session.successful_port:
                    stats["port_usage_frequency"][session.successful_port] = \
                        stats["port_usage_frequency"].get(session.successful_port, 0) + 1
            
            # Strategy statistics
            strategy_name = session.strategy.value
            strategy_counts[strategy_name] = strategy_counts.get(strategy_name, 0) + 1
            if session.status == RetryStatus.SUCCESS:
                strategy_successes[strategy_name] = strategy_successes.get(strategy_name, 0) + 1
            
            # Totals for averages
            total_attempts += len(session.attempts)
            if session.total_duration_ms:
                total_duration += session.total_duration_ms
            
            service_stats["average_attempts"] = len(session.attempts)
        
        # Calculate averages
        if stats["total_sessions"] > 0:
            stats["average_attempts"] = total_attempts / stats["total_sessions"]
            stats["average_duration_ms"] = total_duration / stats["total_sessions"]
        
        # Strategy success rates
        for strategy, count in strategy_counts.items():
            success_count = strategy_successes.get(strategy, 0)
            stats["strategy_success_rates"][strategy] = {
                "total": count,
                "successful": success_count,
                "success_rate": success_count / count if count > 0 else 0
            }
        
        return stats
    
    def cleanup_session(self, service_name: str) -> bool:
        """
        Clean up a completed retry session.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if session was found and cleaned up
        """
        if service_name in self.active_sessions:
            del self.active_sessions[service_name]
            return True
        return False
    
    def cleanup_all_sessions(self) -> int:
        """
        Clean up all retry sessions.

        Returns:
            Number of sessions cleaned up
        """
        count = len(self.active_sessions)
        self.active_sessions.clear()
        return count


@dataclass
class PortAllocation:
    """Represents a port allocation to a service."""
    service_name: str
    service_type: str  # 'dashboard', 'api', 'clickhouse', 'otel', etc.
    port: int
    allocated_at: datetime
    last_health_check: Optional[datetime] = None
    is_active: bool = True


class PortRegistry:
    """
    Centralized port allocation and management system.

    Prevents port conflicts between Flask dashboard, FastAPI, ClickHouse, OTEL, etc.
    Maintains global registry of all allocated ports with health monitoring.
    """

    _instance: Optional['PortRegistry'] = None
    _lock = threading.Lock()

    def __init__(self):
        # Core port tracking
        self.allocated_ports: Dict[int, PortAllocation] = {}
        self.service_ports: Dict[str, int] = {}  # service_name -> port
        self.reserved_ports: Set[int] = set()

        # Port ranges by service type
        self.service_port_ranges = {
            'dashboard': (8100, 8199),      # Flask dashboard
            'api': (8000, 8099),            # FastAPI API
            'clickhouse': (8200, 8299),     # ClickHouse
            'otel': (4300, 4399),           # OTEL collectors
            'websocket': (8300, 8399),      # WebSocket services
            'auxiliary': (9000, 9999)       # Other services
        }

        # Default ports for services
        self.default_ports = {
            'dashboard': 8110,
            'api': 8000,
            'clickhouse': 8123,
            'otel': 4317,
            'websocket': 8350
        }

        # Thread safety
        self._allocation_lock = threading.Lock()

        # Health monitoring
        self.health_check_interval = 30  # seconds
        self.last_global_health_check = datetime.now()

        # Port conflict manager integration
        self.conflict_manager = PortConflictManager(verbose=True)

    @classmethod
    def get_instance(cls) -> 'PortRegistry':
        """Get singleton instance of PortRegistry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def allocate_port(
        self,
        service_name: str,
        service_type: str,
        preferred_port: Optional[int] = None,
        force_preferred: bool = False
    ) -> Tuple[Optional[int], str]:
        """
        Allocate a port for a service.

        Args:
            service_name: Unique service identifier
            service_type: Type of service (dashboard, api, clickhouse, etc.)
            preferred_port: Desired port number
            force_preferred: If True, fail if preferred port unavailable

        Returns:
            Tuple of (allocated_port, message)
        """
        with self._allocation_lock:
            # Check if service already has a port
            if service_name in self.service_ports:
                existing_port = self.service_ports[service_name]
                allocation = self.allocated_ports.get(existing_port)
                if allocation and allocation.is_active:
                    return existing_port, f"Service {service_name} already allocated port {existing_port}"

            # Determine target port
            target_port = preferred_port or self.default_ports.get(service_type, 8000)

            # Check if preferred port is available
            if self._is_port_allocatable(target_port, service_type):
                allocated_port = self._perform_allocation(service_name, service_type, target_port)
                return allocated_port, f"Allocated preferred port {allocated_port} to {service_name}"

            # If force_preferred is True and preferred port unavailable, fail
            if force_preferred:
                return None, f"Preferred port {target_port} unavailable and force_preferred=True"

            # Find alternative port in service range
            port_range = self.service_port_ranges.get(service_type, (8000, 8999))

            # Try ports in range
            for port in range(port_range[0], port_range[1] + 1):
                if self._is_port_allocatable(port, service_type):
                    allocated_port = self._perform_allocation(service_name, service_type, port)
                    return allocated_port, f"Allocated alternative port {allocated_port} to {service_name}"

            # No ports available in range
            return None, f"No available ports in range {port_range} for service type {service_type}"

    def _is_port_allocatable(self, port: int, service_type: str) -> bool:
        """Check if a port can be allocated."""
        # Check if already allocated
        if port in self.allocated_ports:
            return False

        # Check if reserved
        if port in self.reserved_ports:
            return False

        # Check if actually available on system
        available, _ = self.conflict_manager.is_port_available(port)
        if not available:
            return False

        # Check if in valid range for service type
        port_range = self.service_port_ranges.get(service_type)
        if port_range and not (port_range[0] <= port <= port_range[1]):
            return False

        return True

    def _perform_allocation(self, service_name: str, service_type: str, port: int) -> int:
        """Perform the actual port allocation."""
        allocation = PortAllocation(
            service_name=service_name,
            service_type=service_type,
            port=port,
            allocated_at=datetime.now(),
            is_active=True
        )

        self.allocated_ports[port] = allocation
        self.service_ports[service_name] = port

        return port

    def deallocate_port(self, service_name: str) -> bool:
        """
        Deallocate a port from a service.

        Args:
            service_name: Service identifier

        Returns:
            True if deallocated successfully
        """
        with self._allocation_lock:
            if service_name not in self.service_ports:
                return False

            port = self.service_ports[service_name]

            # Remove from allocations
            if port in self.allocated_ports:
                del self.allocated_ports[port]

            # Remove from service mapping
            del self.service_ports[service_name]

            return True

    def get_service_port(self, service_name: str) -> Optional[int]:
        """Get the allocated port for a service."""
        return self.service_ports.get(service_name)

    def get_all_allocations(self) -> Dict[str, Dict[str, Any]]:
        """Get all current port allocations."""
        with self._allocation_lock:
            allocations = {}
            for service_name, port in self.service_ports.items():
                allocation = self.allocated_ports.get(port)
                if allocation:
                    allocations[service_name] = {
                        'port': port,
                        'service_type': allocation.service_type,
                        'allocated_at': allocation.allocated_at.isoformat(),
                        'is_active': allocation.is_active,
                        'last_health_check': allocation.last_health_check.isoformat() if allocation.last_health_check else None
                    }
            return allocations

    def get_port_conflicts(self) -> Dict[str, Any]:
        """
        Detect and report port conflicts.

        Returns:
            Dictionary with conflict information
        """
        conflicts = {
            'conflicted_services': [],
            'system_conflicts': [],
            'total_conflicts': 0
        }

        for service_name, port in self.service_ports.items():
            available, error = self.conflict_manager.is_port_available(port)
            if not available:
                conflicts['conflicted_services'].append({
                    'service_name': service_name,
                    'port': port,
                    'error': error
                })

        # Check for system-wide conflicts
        all_ports = list(self.allocated_ports.keys())
        for port in all_ports:
            available, error = self.conflict_manager.is_port_available(port)
            if not available:
                conflicts['system_conflicts'].append({
                    'port': port,
                    'allocation': self.allocated_ports[port],
                    'error': error
                })

        conflicts['total_conflicts'] = len(conflicts['conflicted_services']) + len(conflicts['system_conflicts'])
        return conflicts


# Global registry instance
def get_port_registry() -> PortRegistry:
    """Get the global PortRegistry instance."""
    return PortRegistry.get_instance()