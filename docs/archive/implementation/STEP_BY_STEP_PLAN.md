# Context Cleaner Impact Tracking - Step-by-Step Implementation Plan

> **Detailed implementation guide with specific PRs, code examples, and success criteria**

## 🎯 Overview

This document provides the detailed, step-by-step plan for implementing impact tracking and evaluation metrics in Context Cleaner. Each step includes specific code examples, PR strategies, and measurable success criteria.

---

## 📋 Phase 1: Foundation Infrastructure (Weeks 1-3)

### **Step 1: Core Hook Integration System** 
**Target**: Week 1, Days 1-2 | **PR #1**

#### **1.1 Create Hook Integration Manager**

**File**: `src/context_cleaner/collectors/hook_integration.py`
```python
"""
Hook Integration Manager for Context Cleaner Impact Tracking.

Provides performance-safe integration with Claude Code hooks to collect
productivity and context optimization metrics.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class HookExecutionResult:
    """Result of hook execution with performance metrics."""
    success: bool
    execution_time: float
    error: Optional[str] = None
    data_collected: Dict[str, Any] = None

class CircuitBreaker:
    """Circuit breaker pattern for hook reliability."""
    
    def __init__(self, failure_threshold: int = 3, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if hook can be executed based on circuit breaker state."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

class HookIntegrationManager:
    """Manages integration with Claude Code hooks for productivity tracking."""
    
    def __init__(self, config):
        self.config = config
        self.circuit_breaker = CircuitBreaker()
        self.active_session = None
        self.hook_registry = {}
        self.performance_monitor = PerformanceMonitor()
    
    async def register_hook(self, hook_name: str, handler: Callable) -> bool:
        """Register a hook handler with performance monitoring."""
        try:
            wrapped_handler = self._wrap_handler_with_monitoring(handler)
            self.hook_registry[hook_name] = wrapped_handler
            logger.info(f"Registered hook: {hook_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register hook {hook_name}: {e}")
            return False
    
    def _wrap_handler_with_monitoring(self, handler: Callable) -> Callable:
        """Wrap hook handler with performance monitoring and error handling."""
        
        async def monitored_handler(*args, **kwargs) -> HookExecutionResult:
            start_time = time.time()
            
            # Circuit breaker check
            if not self.circuit_breaker.can_execute():
                return HookExecutionResult(
                    success=False,
                    execution_time=0,
                    error="Circuit breaker open"
                )
            
            try:
                # Execute with timeout protection
                result = await asyncio.wait_for(
                    handler(*args, **kwargs),
                    timeout=0.050  # 50ms max execution time
                )
                
                execution_time = time.time() - start_time
                
                # Performance monitoring
                if execution_time > 0.010:  # 10ms warning threshold
                    logger.warning(f"Hook execution took {execution_time:.3f}s")
                
                self.circuit_breaker.record_success()
                self.performance_monitor.record_execution(execution_time)
                
                return HookExecutionResult(
                    success=True,
                    execution_time=execution_time,
                    data_collected=result
                )
                
            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                self.circuit_breaker.record_failure()
                logger.error(f"Hook timeout after {execution_time:.3f}s")
                
                return HookExecutionResult(
                    success=False,
                    execution_time=execution_time,
                    error="Timeout"
                )
                
            except Exception as e:
                execution_time = time.time() - start_time
                self.circuit_breaker.record_failure()
                logger.error(f"Hook execution error: {e}")
                
                return HookExecutionResult(
                    success=False,
                    execution_time=execution_time,
                    error=str(e)
                )
        
        return monitored_handler

class PerformanceMonitor:
    """Monitor hook performance and system impact."""
    
    def __init__(self):
        self.execution_times = []
        self.error_count = 0
        self.total_executions = 0
    
    def record_execution(self, execution_time: float):
        """Record hook execution time for performance analysis."""
        self.execution_times.append(execution_time)
        self.total_executions += 1
        
        # Keep only recent executions for memory efficiency
        if len(self.execution_times) > 1000:
            self.execution_times = self.execution_times[-500:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self.execution_times:
            return {"status": "no_data"}
        
        import statistics
        return {
            "avg_execution_time": statistics.mean(self.execution_times),
            "max_execution_time": max(self.execution_times),
            "min_execution_time": min(self.execution_times),
            "total_executions": self.total_executions,
            "error_count": self.error_count,
            "success_rate": (self.total_executions - self.error_count) / self.total_executions
        }
```

#### **1.2 Create Session Lifecycle Tracker**

**File**: `src/context_cleaner/collectors/session_tracker.py`
```python
"""
Session Lifecycle Tracker for Context Cleaner.

Tracks complete development sessions from start to finish,
collecting productivity metrics and context health data.
"""

import time
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import uuid

@dataclass
class SessionMetrics:
    """Core session metrics for productivity analysis."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Context metrics
    initial_context_size: int = 0
    final_context_size: int = 0
    context_size_change: int = 0
    context_health_score: float = 0.0
    
    # Productivity metrics
    optimization_events: int = 0
    tool_usage_count: Dict[str, int] = None
    error_count: int = 0
    task_completion_indicators: int = 0
    
    # Flow metrics
    interruption_count: int = 0
    focused_work_duration: float = 0.0
    productivity_score: float = 0.0
    
    def __post_init__(self):
        if self.tool_usage_count is None:
            self.tool_usage_count = {}

class SessionTracker:
    """Tracks complete development sessions for productivity analysis."""
    
    def __init__(self, storage_manager, config):
        self.storage = storage_manager
        self.config = config
        self.current_session = None
        self.session_start_time = None
        
    async def start_session(self, initial_context: Dict[str, Any]) -> str:
        """Start tracking a new development session."""
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        # Calculate initial context size
        initial_size = len(json.dumps(initial_context, default=str))
        
        self.current_session = SessionMetrics(
            session_id=session_id,
            start_time=start_time,
            initial_context_size=initial_size
        )
        
        self.session_start_time = time.time()
        
        # Store session start event
        await self.storage.store_event('session_start', {
            'session_id': session_id,
            'timestamp': start_time.isoformat(),
            'initial_context_size': initial_size
        })
        
        return session_id
    
    async def end_session(self, final_context: Dict[str, Any], summary: Dict[str, Any] = None) -> SessionMetrics:
        """End the current session and calculate final metrics."""
        if not self.current_session:
            raise ValueError("No active session to end")
        
        end_time = datetime.now(timezone.utc)
        duration = time.time() - self.session_start_time
        
        # Calculate final context size
        final_size = len(json.dumps(final_context, default=str))
        
        # Update session metrics
        self.current_session.end_time = end_time
        self.current_session.duration_seconds = duration
        self.current_session.final_context_size = final_size
        self.current_session.context_size_change = final_size - self.current_session.initial_context_size
        
        # Calculate context health score
        self.current_session.context_health_score = self._calculate_context_health(
            final_size, duration, self.current_session.optimization_events
        )
        
        # Calculate productivity score
        self.current_session.productivity_score = self._calculate_productivity_score(
            duration, self.current_session.task_completion_indicators,
            self.current_session.error_count, self.current_session.focused_work_duration
        )
        
        # Store completed session
        await self.storage.store_session(self.current_session)
        
        # Store session end event
        await self.storage.store_event('session_end', {
            'session_id': self.current_session.session_id,
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration,
            'final_context_size': final_size,
            'productivity_score': self.current_session.productivity_score
        })
        
        completed_session = self.current_session
        self.current_session = None
        self.session_start_time = None
        
        return completed_session
    
    async def record_optimization_event(self, optimization_type: str, impact_metrics: Dict[str, Any]):
        """Record a context optimization event during the session."""
        if not self.current_session:
            return
        
        self.current_session.optimization_events += 1
        
        await self.storage.store_event('optimization_event', {
            'session_id': self.current_session.session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'optimization_type': optimization_type,
            'impact_metrics': impact_metrics
        })
    
    async def record_tool_usage(self, tool_name: str, execution_time: float, success: bool):
        """Record tool usage during the session."""
        if not self.current_session:
            return
        
        # Update tool usage count
        if tool_name not in self.current_session.tool_usage_count:
            self.current_session.tool_usage_count[tool_name] = 0
        self.current_session.tool_usage_count[tool_name] += 1
        
        # Count errors
        if not success:
            self.current_session.error_count += 1
        
        await self.storage.store_event('tool_usage', {
            'session_id': self.current_session.session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tool_name': tool_name,
            'execution_time': execution_time,
            'success': success
        })
    
    def _calculate_context_health(self, context_size: int, session_duration: float, optimizations: int) -> float:
        """Calculate context health score (0-100)."""
        # Base score from context size (smaller is better)
        size_score = max(0, 100 - (context_size / 1000))  # Deduct 1 point per 1K chars
        
        # Adjustment for session duration (longer sessions need more optimizations)
        duration_hours = session_duration / 3600
        expected_optimizations = max(1, int(duration_hours / 2))  # Expected 1 optimization per 2 hours
        optimization_score = min(100, (optimizations / expected_optimizations) * 100)
        
        # Weighted average
        health_score = (size_score * 0.7) + (optimization_score * 0.3)
        
        return round(max(0, min(100, health_score)), 1)
    
    def _calculate_productivity_score(self, duration: float, completions: int, errors: int, focused_time: float) -> float:
        """Calculate productivity score (0-100) based on session metrics."""
        if duration == 0:
            return 0.0
        
        # Base score from task completions
        completion_rate = completions / max(1, duration / 3600)  # Completions per hour
        completion_score = min(100, completion_rate * 20)  # 5 completions/hour = 100 score
        
        # Error penalty
        error_rate = errors / max(1, duration / 3600)  # Errors per hour
        error_penalty = min(50, error_rate * 10)  # Max 50 point penalty
        
        # Focus bonus
        focus_ratio = focused_time / duration if duration > 0 else 0
        focus_bonus = focus_ratio * 20  # Max 20 point bonus
        
        productivity_score = completion_score - error_penalty + focus_bonus
        
        return round(max(0, min(100, productivity_score)), 1)
```

**PR #1 Success Criteria:**
- [ ] Hook integration executes in <10ms consistently
- [ ] Circuit breaker prevents system crashes during errors  
- [ ] Session tracking captures all key lifecycle events
- [ ] Performance monitoring shows <1% CPU overhead
- [ ] All tests pass with >90% coverage
- [ ] Zero impact on Claude Code functionality

### **Step 2: Privacy-First Storage System**
**Target**: Week 1, Days 3-4 | **PR #2**

#### **2.1 Create Encrypted Storage Engine**

**File**: `src/context_cleaner/storage/encrypted_storage.py`
```python
"""
Privacy-First Encrypted Storage for Context Cleaner.

Provides local-only encrypted storage for productivity metrics
with automatic data anonymization and retention policies.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import sqlite3
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class DataAnonymizer:
    """Anonymizes sensitive data before storage."""
    
    SENSITIVE_PATTERNS = [
        # File paths and names
        r'/[a-zA-Z0-9_\-./]+\.py',
        r'/[a-zA-Z0-9_\-./]+\.js',
        r'/[a-zA-Z0-9_\-./]+\.ts',
        # Email addresses
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        # URLs
        r'https?://[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})+',
        # API keys (common patterns)
        r'[a-zA-Z0-9]{32,}',
    ]
    
    def __init__(self):
        self.replacement_map = {}
    
    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize sensitive data while preserving analytical value."""
        if isinstance(data, dict):
            return {key: self.anonymize_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.anonymize_data(item) for item in data]
        elif isinstance(data, str):
            return self._anonymize_string(data)
        else:
            return data
    
    def _anonymize_string(self, text: str) -> str:
        """Anonymize sensitive patterns in strings."""
        # For now, just return length and type info for sensitive data
        if len(text) > 100:  # Potentially sensitive long strings
            return f"<anonymized_text_length_{len(text)}>"
        
        # Check for sensitive patterns
        import re
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                # Generate consistent hash for same content
                hash_key = hashlib.md5(text.encode()).hexdigest()[:8]
                return f"<anonymized_{hash_key}>"
        
        return text

class EncryptedStorage:
    """Encrypted local storage for productivity metrics."""
    
    def __init__(self, storage_path: str, encryption_key: Optional[str] = None):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        if encryption_key:
            key = encryption_key.encode()
        else:
            key = self._generate_or_load_key()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'context_cleaner_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key))
        self.fernet = Fernet(key)
        
        # Initialize database
        self.db_path = self.storage_path / "metrics.db"
        self._initialize_database()
        
        # Initialize anonymizer
        self.anonymizer = DataAnonymizer()
    
    def _generate_or_load_key(self) -> bytes:
        """Generate or load encryption key from secure storage."""
        key_file = self.storage_path / ".encryption_key"
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = os.urandom(32)
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Secure permissions
            return key
    
    def _initialize_database(self):
        """Initialize SQLite database for metrics storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    encrypted_data BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_hash TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    encrypted_data BLOB NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_hash TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
            """)
    
    async def store_session(self, session_data: Dict[str, Any]) -> bool:
        """Store session data with encryption and anonymization."""
        try:
            # Anonymize sensitive data
            anonymized_data = self.anonymizer.anonymize_data(session_data)
            
            # Serialize and encrypt
            json_data = json.dumps(anonymized_data, default=str)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            
            # Generate data hash for integrity verification
            data_hash = hashlib.sha256(json_data.encode()).hexdigest()
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO sessions (session_id, encrypted_data, data_hash)
                    VALUES (?, ?, ?)
                """, (session_data.get('session_id'), encrypted_data, data_hash))
            
            return True
            
        except Exception as e:
            print(f"Error storing session data: {e}")
            return False
    
    async def store_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Store event data with encryption and anonymization."""
        try:
            # Anonymize sensitive data
            anonymized_data = self.anonymizer.anonymize_data(event_data)
            
            # Serialize and encrypt
            json_data = json.dumps(anonymized_data, default=str)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            
            # Generate data hash
            data_hash = hashlib.sha256(json_data.encode()).hexdigest()
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO events (session_id, event_type, encrypted_data, data_hash)
                    VALUES (?, ?, ?, ?)
                """, (event_data.get('session_id'), event_type, encrypted_data, data_hash))
            
            return True
            
        except Exception as e:
            print(f"Error storing event data: {e}")
            return False
    
    async def get_sessions(self, limit: int = 100, days_back: int = 30) -> List[Dict[str, Any]]:
        """Retrieve recent sessions with decryption."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT session_id, encrypted_data, created_at, data_hash
                    FROM sessions
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (cutoff_date, limit))
                
                sessions = []
                for row in cursor.fetchall():
                    try:
                        # Decrypt and deserialize
                        decrypted_data = self.fernet.decrypt(row['encrypted_data'])
                        session_data = json.loads(decrypted_data.decode())
                        
                        # Verify integrity
                        expected_hash = hashlib.sha256(decrypted_data).hexdigest()
                        if expected_hash == row['data_hash']:
                            sessions.append(session_data)
                        else:
                            print(f"Data integrity check failed for session {row['session_id']}")
                    
                    except Exception as e:
                        print(f"Error decrypting session {row['session_id']}: {e}")
                
                return sessions
                
        except Exception as e:
            print(f"Error retrieving sessions: {e}")
            return []
    
    async def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Clean up old data based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            with sqlite3.connect(self.db_path) as conn:
                # Delete old events first (foreign key constraint)
                cursor = conn.execute("""
                    DELETE FROM events WHERE timestamp < ?
                """, (cutoff_date,))
                events_deleted = cursor.rowcount
                
                # Delete old sessions
                cursor = conn.execute("""
                    DELETE FROM sessions WHERE created_at < ?
                """, (cutoff_date,))
                sessions_deleted = cursor.rowcount
                
                # Vacuum database to reclaim space
                conn.execute("VACUUM")
                
                total_deleted = events_deleted + sessions_deleted
                print(f"Cleaned up {total_deleted} old records")
                return total_deleted
                
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            return 0
    
    async def export_all_data(self) -> Dict[str, Any]:
        """Export all data for privacy compliance."""
        try:
            sessions = await self.get_sessions(limit=10000, days_back=365)
            
            # Get all events
            events = []
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT event_type, encrypted_data, timestamp, data_hash
                    FROM events
                    ORDER BY timestamp DESC
                """)
                
                for row in cursor.fetchall():
                    try:
                        decrypted_data = self.fernet.decrypt(row['encrypted_data'])
                        event_data = json.loads(decrypted_data.decode())
                        
                        events.append({
                            'event_type': row['event_type'],
                            'timestamp': row['timestamp'],
                            'data': event_data
                        })
                    except Exception as e:
                        print(f"Error decrypting event: {e}")
            
            return {
                'export_timestamp': datetime.now().isoformat(),
                'sessions': sessions,
                'events': events,
                'total_sessions': len(sessions),
                'total_events': len(events),
                'privacy_notice': 'All data has been processed locally on your machine'
            }
            
        except Exception as e:
            print(f"Error exporting data: {e}")
            return {'error': str(e)}
    
    async def delete_all_data(self) -> bool:
        """Delete all stored data for privacy compliance."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM events")
                conn.execute("DELETE FROM sessions")
                conn.execute("VACUUM")
            
            print("All productivity data has been deleted")
            return True
            
        except Exception as e:
            print(f"Error deleting data: {e}")
            return False
```

**PR #2 Success Criteria:**
- [ ] All data encrypted with AES-256 encryption
- [ ] Sensitive content properly anonymized before storage
- [ ] Data integrity verification with checksums
- [ ] Configurable retention policies working
- [ ] Privacy compliance export/delete functions operational
- [ ] SQLite database performance optimized with indexes

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Copy impact tracking documentation to Context Cleaner repository", "status": "completed", "activeForm": "Copying impact tracking documentation to Context Cleaner repository"}, {"content": "Create comprehensive design documents", "status": "completed", "activeForm": "Creating comprehensive design documents"}, {"content": "Create detailed step-by-step implementation plan", "status": "in_progress", "activeForm": "Creating detailed step-by-step implementation plan"}, {"content": "Establish PR strategy for tracking features", "status": "pending", "activeForm": "Establishing PR strategy for tracking features"}, {"content": "Implement core tracking infrastructure", "status": "pending", "activeForm": "Implementing core tracking infrastructure"}]