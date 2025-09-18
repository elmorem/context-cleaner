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
from typing import List, Dict, Optional, Tuple, Any
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