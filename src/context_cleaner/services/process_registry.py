"""
Centralized Process Registry for Context Cleaner Service Orchestration

This module implements a SQLite-based process registry that tracks all Context Cleaner
processes across sessions, enabling comprehensive service lifecycle management and
preventing orphaned processes.

Key Features:
- Persistent SQLite database with WAL mode for reliability
- Cross-session process tracking 
- Atomic operations with file locking
- Process discovery and validation
- Automatic cleanup of stale entries
- Enhanced process metadata with architectural recommendations
"""

import os
import sqlite3
import psutil
import platform
import logging
import threading
import time
import re
import subprocess
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager
import fcntl
import json

logger = logging.getLogger(__name__)


@dataclass
class ProcessEntry:
    """Enhanced process entry with comprehensive metadata for service tracking."""
    
    # Core identification
    pid: int
    command_line: str
    service_type: str  # 'dashboard', 'bridge_sync', 'telemetry_collector', etc.
    
    # Lifecycle tracking
    start_time: datetime
    registration_time: datetime
    last_health_check: Optional[datetime] = None
    status: str = 'running'  # 'running', 'stopping', 'stopped', 'failed'
    
    # Network and resource tracking
    port: Optional[int] = None
    host: str = '127.0.0.1'
    
    # Orchestration metadata
    parent_orchestrator: Optional[str] = None
    session_id: str = ''
    user_id: str = ''
    
    # Enhanced architectural fields (from code architect recommendations)
    host_identifier: str = ''
    resource_limits: Optional[str] = None  # JSON string of resource constraints
    restart_policy: str = 'manual'  # 'manual', 'always', 'on-failure', 'unless-stopped'
    health_check_config: Optional[str] = None  # JSON string of health check config
    last_health_status: bool = True
    registration_source: str = 'orchestrator'  # 'orchestrator', 'discovery', 'manual'
    
    # Process metadata
    working_directory: str = ''
    environment_vars: Optional[str] = None  # JSON string of relevant env vars
    process_group_id: Optional[int] = None
    parent_pid: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper datetime serialization."""
        data = asdict(self)
        
        # Convert datetime objects to ISO format strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessEntry':
        """Create ProcessEntry from dictionary with datetime parsing."""
        # Convert ISO format strings back to datetime objects
        datetime_fields = ['start_time', 'registration_time', 'last_health_check']
        
        for field in datetime_fields:
            if field in data and data[field] is not None:
                if isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field])
        
        # Filter out database-only fields that aren't part of the ProcessEntry dataclass
        valid_fields = {
            'pid', 'command_line', 'service_type', 'start_time', 'registration_time',
            'last_health_check', 'status', 'port', 'host', 'parent_orchestrator',
            'session_id', 'user_id', 'host_identifier', 'resource_limits',
            'restart_policy', 'health_check_config', 'last_health_status',
            'registration_source', 'working_directory', 'environment_vars',
            'process_group_id', 'parent_pid'
        }
        
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    def is_process_alive(self) -> bool:
        """Check if the process is still running."""
        try:
            process = psutil.Process(self.pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def get_process_info(self) -> Optional[Dict[str, Any]]:
        """Get current process information if still running."""
        try:
            process = psutil.Process(self.pid)
            return {
                'pid': process.pid,
                'name': process.name(),
                'status': process.status(),
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'create_time': datetime.fromtimestamp(process.create_time()),
                'cmdline': process.cmdline(),
                'cwd': process.cwd() if hasattr(process, 'cwd') else None,
                'connections': [conn._asdict() for conn in process.connections()],
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None


class ProcessRegistryDatabase:
    """SQLite-based process registry with reliability and performance optimizations."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the process registry database."""
        self.db_path = db_path or self._get_default_db_path()
        self.lock_file = f"{self.db_path}.lock"
        self._ensure_database_exists()
        self._setup_database()
        
        logger.info(f"Process registry initialized at: {self.db_path}")
    
    def _get_default_db_path(self) -> str:
        """Get the default database path in user's home directory."""
        home_dir = Path.home()
        context_cleaner_dir = home_dir / '.context_cleaner'
        context_cleaner_dir.mkdir(exist_ok=True)
        return str(context_cleaner_dir / 'processes.db')
    
    def _ensure_database_exists(self):
        """Ensure the database file and directory exist."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_database(self):
        """Initialize the database schema with optimizations."""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency and reliability
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=memory")
            
            # Create the processes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processes (
                    pid INTEGER PRIMARY KEY,
                    command_line TEXT NOT NULL,
                    service_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    registration_time TEXT NOT NULL,
                    last_health_check TEXT,
                    status TEXT DEFAULT 'running',
                    port INTEGER,
                    host TEXT DEFAULT '127.0.0.1',
                    parent_orchestrator TEXT,
                    session_id TEXT,
                    user_id TEXT,
                    host_identifier TEXT,
                    resource_limits TEXT,
                    restart_policy TEXT DEFAULT 'manual',
                    health_check_config TEXT,
                    last_health_status BOOLEAN DEFAULT TRUE,
                    registration_source TEXT DEFAULT 'orchestrator',
                    working_directory TEXT,
                    environment_vars TEXT,
                    process_group_id INTEGER,
                    parent_pid INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_service_type ON processes(service_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON processes(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON processes(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registration_source ON processes(registration_source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_port ON processes(port)")
            
            # Create triggers for automatic timestamp updates
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_timestamp 
                AFTER UPDATE ON processes
                BEGIN
                    UPDATE processes SET updated_at = CURRENT_TIMESTAMP WHERE pid = NEW.pid;
                END
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with file locking for atomic operations."""
        lock_fd = None
        try:
            # Acquire file lock for atomic operations
            lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.OperationalError as e:
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if lock_fd is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
    
    def register_process(self, entry: ProcessEntry) -> bool:
        """Register a new process in the registry."""
        try:
            with self._get_connection() as conn:
                # Convert ProcessEntry to database format
                data = entry.to_dict()
                
                # Handle datetime fields
                data['start_time'] = data['start_time'] if isinstance(data['start_time'], str) else entry.start_time.isoformat()
                data['registration_time'] = data['registration_time'] if isinstance(data['registration_time'], str) else entry.registration_time.isoformat()
                
                if entry.last_health_check:
                    data['last_health_check'] = data['last_health_check'] if isinstance(data['last_health_check'], str) else entry.last_health_check.isoformat()
                
                # Insert or replace the process entry
                placeholders = ', '.join(['?' for _ in data.values()])
                columns = ', '.join(data.keys())
                
                conn.execute(f"""
                    INSERT OR REPLACE INTO processes ({columns})
                    VALUES ({placeholders})
                """, list(data.values()))
                
                conn.commit()
                logger.debug(f"Registered process PID {entry.pid} ({entry.service_type})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register process {entry.pid}: {e}")
            return False
    
    def unregister_process(self, pid: int) -> bool:
        """Remove a process from the registry."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM processes WHERE pid = ?", (pid,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Unregistered process PID {pid}")
                    return True
                else:
                    logger.warning(f"Process PID {pid} not found in registry")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to unregister process {pid}: {e}")
            return False
    
    def get_process(self, pid: int) -> Optional[ProcessEntry]:
        """Get a specific process entry by PID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM processes WHERE pid = ?", (pid,)).fetchone()
                
                if row:
                    return ProcessEntry.from_dict(dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Failed to get process {pid}: {e}")
            return None
    
    def get_all_processes(self) -> List[ProcessEntry]:
        """Get all registered processes."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute("SELECT * FROM processes ORDER BY registration_time DESC").fetchall()
                return [ProcessEntry.from_dict(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get all processes: {e}")
            return []
    
    def get_processes_by_type(self, service_type: str) -> List[ProcessEntry]:
        """Get all processes of a specific service type."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM processes WHERE service_type = ? ORDER BY registration_time DESC",
                    (service_type,)
                ).fetchall()
                return [ProcessEntry.from_dict(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get processes by type {service_type}: {e}")
            return []
    
    def get_processes_by_status(self, status: str) -> List[ProcessEntry]:
        """Get all processes with a specific status."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM processes WHERE status = ? ORDER BY registration_time DESC",
                    (status,)
                ).fetchall()
                return [ProcessEntry.from_dict(dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get processes by status {status}: {e}")
            return []
    
    def update_process_status(self, pid: int, status: str, health_status: Optional[bool] = None) -> bool:
        """Update the status and health of a process."""
        try:
            with self._get_connection() as conn:
                if health_status is not None:
                    conn.execute("""
                        UPDATE processes 
                        SET status = ?, last_health_status = ?, last_health_check = ?
                        WHERE pid = ?
                    """, (status, health_status, datetime.now().isoformat(), pid))
                else:
                    conn.execute("""
                        UPDATE processes 
                        SET status = ?
                        WHERE pid = ?
                    """, (status, pid))
                
                conn.commit()
                return conn.total_changes > 0
                
        except Exception as e:
            logger.error(f"Failed to update process {pid} status: {e}")
            return False
    
    def cleanup_stale_entries(self, max_age_hours: int = 24) -> int:
        """Remove entries for processes that no longer exist or are too old."""
        cleaned_count = 0
        
        try:
            with self._get_connection() as conn:
                # Get all processes
                rows = conn.execute("SELECT pid, registration_time FROM processes").fetchall()
                stale_pids = []
                
                cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
                
                for row in rows:
                    pid = row['pid']
                    reg_time_str = row['registration_time']
                    
                    try:
                        reg_time = datetime.fromisoformat(reg_time_str)
                        
                        # Check if process is too old or no longer exists
                        if reg_time < cutoff_time:
                            stale_pids.append(pid)
                            continue
                            
                        # Check if process still exists
                        if not psutil.pid_exists(pid):
                            stale_pids.append(pid)
                            continue
                            
                        # Check if it's a zombie process
                        try:
                            process = psutil.Process(pid)
                            if process.status() == psutil.STATUS_ZOMBIE:
                                stale_pids.append(pid)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            stale_pids.append(pid)
                            
                    except ValueError:
                        # Invalid timestamp format
                        stale_pids.append(pid)
                
                # Remove stale entries
                if stale_pids:
                    placeholders = ', '.join(['?' for _ in stale_pids])
                    cursor = conn.execute(f"DELETE FROM processes WHERE pid IN ({placeholders})", stale_pids)
                    conn.commit()
                    cleaned_count = cursor.rowcount
                    
                    logger.info(f"Cleaned up {cleaned_count} stale process entries")
                
        except Exception as e:
            logger.error(f"Failed to cleanup stale entries: {e}")
        
        return cleaned_count
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the process registry."""
        try:
            with self._get_connection() as conn:
                stats = {}
                
                # Total processes
                stats['total_processes'] = conn.execute("SELECT COUNT(*) FROM processes").fetchone()[0]
                
                # Processes by status
                status_rows = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM processes 
                    GROUP BY status
                """).fetchall()
                stats['by_status'] = {row['status']: row['count'] for row in status_rows}
                
                # Processes by type
                type_rows = conn.execute("""
                    SELECT service_type, COUNT(*) as count 
                    FROM processes 
                    GROUP BY service_type
                """).fetchall()
                stats['by_type'] = {row['service_type']: row['count'] for row in type_rows}
                
                # Database file size
                if os.path.exists(self.db_path):
                    stats['database_size_bytes'] = os.path.getsize(self.db_path)
                
                # Oldest and newest entries
                oldest = conn.execute("SELECT MIN(registration_time) FROM processes").fetchone()[0]
                newest = conn.execute("SELECT MAX(registration_time) FROM processes").fetchone()[0]
                
                stats['oldest_entry'] = oldest
                stats['newest_entry'] = newest
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {}


class ProcessDiscoveryEngine:
    """Engine for discovering existing Context Cleaner processes."""
    
    def __init__(self):
        """Initialize the process discovery engine."""
        # Enhanced patterns to catch ALL Context Cleaner process variations
        self.context_cleaner_patterns = [
            # Original patterns
            'context_cleaner',
            'context-cleaner',
            'python.*context_cleaner',
            'python.*context-cleaner',
            
            # CRITICAL: Direct script invocation patterns (MISSING FROM ORIGINAL)
            'start_context_cleaner',
            'start_context_cleaner_production',
            'python.*start_context_cleaner',
            'python.*start_context_cleaner_production',
            
            # CLI module patterns - catches most common invocation patterns
            'python.*src.context_cleaner.cli',
            'python.*src/context_cleaner/cli',
            'python.*-m.*src.context_cleaner',
            
            # Direct dashboard imports - catches python -c invocations  
            'comprehensivehealthdashboard',
            'comprehensive_health_dashboard',
            'src.context_cleaner.dashboard',
            
            # Bridge service patterns - catches monitoring processes
            'bridge.*sync.*--start-monitoring',
            'context_cleaner.*bridge',
            'bridge.*sync.*interval',
            
            # Shell compound commands - catches delayed execution
            'sleep.*context_cleaner',
            '&&.*context_cleaner',
            'sleep.*start_context_cleaner',
            '&&.*start_context_cleaner',
            
            # Additional CLI patterns that were missed
            'python.*context_cleaner.*dashboard',
            'python.*context_cleaner.*bridge',
            'python.*context_cleaner.*run',
            
            # Environment variable patterns (for PYTHONPATH usage)
            'pythonpath.*context_cleaner',
            'pythonpath.*start_context_cleaner',
        ]
        
        # Expanded known ports covering all discovered active ports
        self.known_ports = {
            # Core dashboard ports (commonly used)
            8080: 'dashboard',
            8888: 'dashboard', 
            8110: 'dashboard',
            
            # Extended dashboard port range (discovered running)
            7777: 'dashboard',
            8050: 'dashboard',
            8055: 'dashboard', 
            8060: 'dashboard',
            8081: 'dashboard',
            8082: 'dashboard',
            8083: 'dashboard',
            8084: 'dashboard',
            8088: 'dashboard',
            8099: 'dashboard',
            8100: 'dashboard',
            8200: 'dashboard',
            8333: 'dashboard',
            9000: 'dashboard',
            9001: 'dashboard', 
            9002: 'dashboard',
            
            # Service ports
            8090: 'telemetry_collector',
            8091: 'bridge_sync',
            4317: 'otel_collector',
            4318: 'otel_collector',
        }
    
    def discover_all_processes(self) -> List[ProcessEntry]:
        """Discover all Context Cleaner processes using multiple methods."""
        discovered = []
        
        # Method 1: Process name and command line discovery
        discovered.extend(self._discover_by_command_line())
        
        # Method 2: Port-based discovery
        discovered.extend(self._discover_by_ports())
        
        # Method 3: Process tree discovery (find children of known processes)
        discovered.extend(self._discover_by_process_tree())
        
        # Method 4: Enhanced shell command discovery (catches compound commands like sleep && python)
        discovered.extend(self._discover_by_shell_commands())
        
        # Deduplicate by PID
        unique_processes = {}
        for process in discovered:
            if process.pid not in unique_processes:
                unique_processes[process.pid] = process
        
        return list(unique_processes.values())
    
    def _discover_by_command_line(self) -> List[ProcessEntry]:
        """Discover processes by analyzing command lines."""
        discovered = []
        
        try:
            for process in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cwd']):
                try:
                    cmdline = ' '.join(process.info['cmdline'] or [])
                    
                    # Check if this looks like a Context Cleaner process
                    if any(pattern in cmdline.lower() for pattern in self.context_cleaner_patterns):
                        service_type = self._determine_service_type(cmdline)
                        
                        # Extract port if present
                        port = self._extract_port_from_cmdline(cmdline)
                        
                        entry = ProcessEntry(
                            pid=process.info['pid'],
                            command_line=cmdline,
                            service_type=service_type,
                            start_time=datetime.fromtimestamp(process.info['create_time']),
                            registration_time=datetime.now(),
                            port=port,
                            working_directory=process.info.get('cwd', ''),
                            registration_source='discovery',
                            host_identifier=platform.node(),
                            status='running'
                        )
                        
                        discovered.append(entry)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Error in command line discovery: {e}")
        
        return discovered
    
    def _discover_by_ports(self) -> List[ProcessEntry]:
        """Discover processes by scanning known ports."""
        discovered = []
        
        try:
            for conn in psutil.net_connections():
                if conn.laddr and conn.laddr.port in self.known_ports:
                    try:
                        if conn.pid:
                            process = psutil.Process(conn.pid)
                            cmdline = ' '.join(process.cmdline())
                            
                            # Verify this is actually a Context Cleaner process
                            if any(pattern in cmdline.lower() for pattern in self.context_cleaner_patterns):
                                service_type = self.known_ports[conn.laddr.port]
                                
                                entry = ProcessEntry(
                                    pid=conn.pid,
                                    command_line=cmdline,
                                    service_type=service_type,
                                    start_time=datetime.fromtimestamp(process.create_time()),
                                    registration_time=datetime.now(),
                                    port=conn.laddr.port,
                                    host=conn.laddr.ip,
                                    working_directory=process.cwd() if hasattr(process, 'cwd') else '',
                                    registration_source='port_discovery',
                                    host_identifier=platform.node(),
                                    status='running'
                                )
                                
                                discovered.append(entry)
                                
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
        except Exception as e:
            logger.error(f"Error in port discovery: {e}")
        
        return discovered
    
    def _discover_by_process_tree(self) -> List[ProcessEntry]:
        """Discover processes by examining process trees."""
        discovered = []
        
        try:
            # Find potential parent processes
            parents = []
            for process in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(process.info['cmdline'] or [])
                    if any(pattern in cmdline.lower() for pattern in self.context_cleaner_patterns):
                        parents.append(process)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Find children of Context Cleaner processes
            for parent in parents:
                try:
                    for child in parent.children(recursive=True):
                        try:
                            cmdline = ' '.join(child.cmdline())
                            service_type = self._determine_service_type(cmdline)
                            
                            entry = ProcessEntry(
                                pid=child.pid,
                                command_line=cmdline,
                                service_type=service_type,
                                start_time=datetime.fromtimestamp(child.create_time()),
                                registration_time=datetime.now(),
                                parent_pid=parent.pid,
                                working_directory=child.cwd() if hasattr(child, 'cwd') else '',
                                registration_source='tree_discovery',
                                host_identifier=platform.node(),
                                status='running'
                            )
                            
                            discovered.append(entry)
                            
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"Error in process tree discovery: {e}")
        
        return discovered
    
    def _discover_by_shell_commands(self) -> List[ProcessEntry]:
        """Enhanced discovery for shell compound commands and direct invocations."""
        discovered = []
        
        try:
            # Look for shell processes that contain Context Cleaner commands
            for process in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cwd']):
                try:
                    # Check if this is a shell process
                    if process.info['name'] not in ['bash', 'sh', 'zsh', 'python', 'python3']:
                        continue
                    
                    cmdline = ' '.join(process.info['cmdline'] or [])
                    cmdline_lower = cmdline.lower()
                    
                    # Enhanced pattern matching for shell commands
                    is_context_cleaner = False
                    for pattern in self.context_cleaner_patterns:
                        if re.search(pattern, cmdline_lower, re.IGNORECASE):
                            is_context_cleaner = True
                            break
                    
                    if not is_context_cleaner:
                        continue
                    
                    # Determine service type with enhanced pattern matching
                    service_type = self._determine_service_type_enhanced(cmdline)
                    
                    # Extract port with enhanced methods
                    port = self._extract_port_from_cmdline(cmdline)
                    
                    entry = ProcessEntry(
                        pid=process.info['pid'],
                        command_line=cmdline,
                        service_type=service_type,
                        start_time=datetime.fromtimestamp(process.info['create_time']),
                        registration_time=datetime.now(),
                        port=port,
                        working_directory=process.info.get('cwd', ''),
                        registration_source='shell_discovery',
                        host_identifier=platform.node(),
                        status='running'
                    )
                    
                    discovered.append(entry)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"Error in shell command discovery: {e}")
        
        return discovered
    
    def _determine_service_type_enhanced(self, cmdline: str) -> str:
        """Enhanced service type determination with expanded patterns."""
        cmdline_lower = cmdline.lower()
        
        # Direct dashboard invocations (most common)
        if 'dashboard' in cmdline_lower:
            return 'dashboard'
        
        # ComprehensiveHealthDashboard direct imports
        if 'comprehensivehealthdashboard' in cmdline_lower:
            return 'dashboard'
        
        # Bridge sync services
        if 'bridge' in cmdline_lower and 'sync' in cmdline_lower:
            return 'bridge_sync'
        
        # Full orchestrator runs
        if 'run' in cmdline_lower and '--dashboard-port' in cmdline_lower:
            return 'orchestrator'
            
        # Telemetry services
        if 'telemetry' in cmdline_lower or 'otel' in cmdline_lower:
            return 'telemetry_collector'
        
        # Sleep compound commands - classify by the python part
        if 'sleep' in cmdline_lower and '&&' in cmdline_lower:
            if 'dashboard' in cmdline_lower:
                return 'dashboard'
            elif 'bridge' in cmdline_lower:
                return 'bridge_sync'
        
        return 'unknown'
    
    def _determine_service_type(self, cmdline: str) -> str:
        """Determine the service type from command line."""
        cmdline_lower = cmdline.lower()
        
        if 'dashboard' in cmdline_lower:
            return 'dashboard'
        elif 'bridge' in cmdline_lower and 'sync' in cmdline_lower:
            return 'bridge_sync'
        elif 'telemetry' in cmdline_lower:
            return 'telemetry_collector'
        elif 'run' in cmdline_lower:
            return 'orchestrator'
        else:
            return 'unknown'
    
    def _extract_port_from_cmdline(self, cmdline: str) -> Optional[int]:
        """Extract port number from command line arguments."""
        import re
        
        # Look for --port XXXX or --dashboard-port XXXX patterns
        port_patterns = [
            r'--port\s+(\d+)',
            r'--dashboard-port\s+(\d+)',
            r'-p\s+(\d+)',
            r':(\d+)',
        ]
        
        for pattern in port_patterns:
            match = re.search(pattern, cmdline)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None


# Global registry instance
_registry = None
_discovery_engine = None


def get_process_registry() -> ProcessRegistryDatabase:
    """Get the global process registry instance."""
    global _registry
    if _registry is None:
        _registry = ProcessRegistryDatabase()
    return _registry


def get_discovery_engine() -> ProcessDiscoveryEngine:
    """Get the global process discovery engine instance."""
    global _discovery_engine
    if _discovery_engine is None:
        _discovery_engine = ProcessDiscoveryEngine()
    return _discovery_engine


def register_current_process(service_type: str, **kwargs) -> bool:
    """Register the current process in the registry."""
    import sys
    
    registry = get_process_registry()
    
    entry = ProcessEntry(
        pid=os.getpid(),
        command_line=' '.join(sys.argv),
        service_type=service_type,
        start_time=datetime.now(),
        registration_time=datetime.now(),
        working_directory=os.getcwd(),
        host_identifier=platform.node(),
        registration_source='self_registration',
        **kwargs
    )
    
    return registry.register_process(entry)


def discover_and_register_processes() -> int:
    """Discover existing processes and register them."""
    registry = get_process_registry()
    discovery = get_discovery_engine()
    
    discovered = discovery.discover_all_processes()
    registered_count = 0
    
    for process in discovered:
        if registry.register_process(process):
            registered_count += 1
    
    logger.info(f"Discovered and registered {registered_count} processes")
    return registered_count