# Component Architecture

> **Detailed breakdown of all Context Cleaner components, their responsibilities, and interactions**

## 📦 Component Overview

Context Cleaner consists of 25+ components organized into logical layers. This document provides detailed information about each component's purpose, interfaces, and dependencies.

## 🏗️ Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │   CLI Commands   │  │   Config Mgmt    │  │  Error Handler│ │
│  │  (Entrypoints)   │  │  (Settings)      │  │  (Logging)    │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘ │
│           │                     │                     │          │
└───────────┼─────────────────────┼─────────────────────┼──────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATION LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Service Orchestrator                        │  │
│  │  • Unified start/stop interface                          │  │
│  │  • Service lifecycle management                          │  │
│  │  • Dependency resolution                                 │  │
│  └────────┬─────────────────────────────────────────────────┘  │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Supervisor (IPC Server)                     │  │
│  │  • Central service coordination                           │  │
│  │  • Unix socket IPC                                        │  │
│  │  • Process registry management                            │  │
│  │  • Service health monitoring                              │  │
│  └────────┬─────────────────────────────────────────────────┘  │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │  Docker Mgmt   │  │  JSONL Watcher │  │  Bridge Service │  │
│  │  (Containers)  │  │  (File Monitor)│  │  (Token API)    │  │
│  └────────┬───────┘  └────────┬───────┘  └────────┬────────┘  │
│           │                   │                    │            │
│  ┌────────▼───────┐  ┌────────▼───────┐  ┌────────▼────────┐  │
│  │   Dashboard    │  │   Watchdog     │  │  Analytics Eng. │  │
│  │   (Web UI)     │  │   (Monitor)    │  │  (Processing)   │  │
│  └────────────────┘  └────────────────┘  └─────────────────┘  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │   ClickHouse   │  │  Process Reg.  │  │  File System    │  │
│  │   (Telemetry)  │  │  (SQLite)      │  │  (Cache/Logs)   │  │
│  └────────────────┘  └────────────────┘  └─────────────────┘  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## 🎯 Core Components

### **1. Service Orchestrator**

**Location**: `src/context_cleaner/core/service_orchestrator.py`

**Purpose**: Unified interface for service lifecycle management

**Responsibilities**:
- Start/stop all services with dependency resolution
- Coordinate startup sequence across multiple services
- Handle graceful shutdown with reverse dependency order
- Provide fallback mechanisms for service operations
- Stream real-time status updates to CLI

**Key Methods**:
```python
class ServiceOrchestrator:
    def start_all_services() -> bool
    def stop_all_services(force: bool = False) -> bool
    def get_service_status() -> Dict[str, ServiceStatus]
    def start_service(service_name: str) -> bool
    def stop_service(service_name: str, force: bool = False) -> bool
```

**Dependencies**:
- Supervisor (for IPC communication)
- Docker Manager (for container services)
- JSONL Watcher (for file monitoring)
- Dashboard Service (for web UI)

**Configuration**:
```python
# Service startup order
STARTUP_ORDER = [
    "supervisor",      # Must start first
    "docker",          # Containers (ClickHouse, OTEL)
    "bridge",          # Token analysis (optional)
    "jsonl_watcher",   # File monitoring
    "dashboard"        # Web UI (depends on all above)
]
```

**Error Handling**:
- Automatic retry with exponential backoff
- Fallback to alternative start methods
- Detailed error logging with context
- User-friendly error messages

---

### **2. Supervisor (IPC Server)**

**Location**: `src/context_cleaner/core/supervisor.py`

**Purpose**: Central coordination service using Unix socket IPC

**Responsibilities**:
- Run as persistent background daemon
- Accept IPC requests from CLI and services
- Manage process registry (SQLite database)
- Coordinate service health checks
- Handle service lifecycle events
- Stream real-time updates to clients

**Key Methods**:
```python
class Supervisor:
    def start() -> bool
    def stop() -> bool
    def register_service(service_info: Dict) -> str
    def unregister_service(service_id: str) -> bool
    def get_all_services() -> List[Dict]
    def health_check(service_id: str) -> ServiceHealth
    def handle_ipc_request(request: IPCRequest) -> IPCResponse
```

**IPC Protocol**:
```python
# Request format
{
    "action": "start_service" | "stop_service" | "health_check",
    "params": {
        "service_name": str,
        "options": Dict
    },
    "request_id": str
}

# Response format
{
    "status": "success" | "error",
    "data": Any,
    "error": Optional[str],
    "request_id": str
}
```

**Socket Configuration**:
- **Path**: `~/.context_cleaner/supervisor.sock`
- **Permissions**: 0600 (owner read/write only)
- **Protocol**: Unix domain socket
- **Timeout**: 30 seconds default

**Process Registry Schema**:
```sql
CREATE TABLE processes (
    id TEXT PRIMARY KEY,
    service_name TEXT NOT NULL,
    pid INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    status TEXT NOT NULL,
    port INTEGER,
    metadata TEXT
);
```

---

### **3. Docker Manager**

**Location**: `src/context_cleaner/services/docker_manager.py`

**Purpose**: Manage Docker containers (ClickHouse, OpenTelemetry)

**Responsibilities**:
- Start/stop Docker containers
- Verify Docker availability
- Check container health
- Manage container lifecycle
- Handle port allocation
- Clean up orphaned containers

**Key Methods**:
```python
class DockerManager:
    def start_containers() -> bool
    def stop_containers(force: bool = False) -> bool
    def get_container_status() -> Dict[str, ContainerStatus]
    def check_docker_available() -> bool
    def cleanup_orphaned_containers() -> int
```

**Managed Containers**:

1. **ClickHouse**
   - Image: `clickhouse/clickhouse-server:latest`
   - Ports: `8123:8123` (HTTP), `9000:9000` (Native)
   - Volume: `~/.context_cleaner/data/clickhouse`
   - Health Check: HTTP GET to `/ping`

2. **OpenTelemetry Collector**
   - Image: `otel/opentelemetry-collector:latest`
   - Ports: `4317:4317` (gRPC), `4318:4318` (HTTP)
   - Config: `~/.context_cleaner/config/otel-config.yaml`
   - Health Check: HTTP GET to `/health`

**Docker Compose Configuration**:
```yaml
version: '3.8'
services:
  clickhouse:
    container_name: context_cleaner_clickhouse
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:8123/ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  otel-collector:
    container_name: context_cleaner_otel
    restart: unless-stopped
    depends_on:
      clickhouse:
        condition: service_healthy
```

**Fallback Mechanisms**:
1. Check Docker availability
2. Try `docker compose up`
3. Try `docker-compose up` (legacy)
4. Try individual `docker run` commands
5. Report error with installation instructions

---

### **4. JSONL Watcher**

**Location**: `src/context_cleaner/services/jsonl_watcher.py`

**Purpose**: Monitor Claude Code session files for real-time telemetry

**Responsibilities**:
- Watch `~/.claude/sessions/` directory
- Detect new/modified `.jsonl` files
- Parse conversation data
- Extract token metrics
- Send telemetry to OpenTelemetry Collector
- Deduplicate messages
- Handle backpressure

**Key Methods**:
```python
class JSONLWatcher:
    def start() -> bool
    def stop() -> bool
    def watch_directory(path: str) -> None
    def process_file(file_path: str) -> List[Message]
    def send_telemetry(data: Dict) -> bool
```

**File Monitoring**:
- **Library**: `watchdog` (cross-platform)
- **Events**: File created, modified, moved
- **Debounce**: 1 second (avoid duplicate processing)
- **Backpressure**: Max 5 concurrent files, 1000 message queue

**Message Parsing**:
```python
# JSONL message format
{
    "type": "message",
    "role": "user" | "assistant",
    "content": str | List[ContentBlock],
    "tokens": {
        "input": int,
        "output": int,
        "cache_creation": int,
        "cache_read": int
    },
    "timestamp": str
}
```

**Deduplication Strategy**:
- Hash message content (SHA-256)
- Store last 10,000 message hashes in memory
- TTL: 1 hour per hash
- Persist hash cache to disk every 5 minutes

**Error Handling**:
- Skip malformed JSONL lines
- Log parsing errors with line number
- Continue processing remaining lines
- Report statistics (processed, skipped, errors)

---

### **5. Bridge Service (Token Analysis)**

**Location**: `src/context_cleaner/services/bridge_service.py`

**Purpose**: Connect to Anthropic API for accurate token counting

**Responsibilities**:
- Authenticate with Anthropic API
- Send messages for token analysis
- Store enhanced token metrics
- Handle rate limiting
- Support historical backfill
- Provide fallback to heuristic estimation

**Key Methods**:
```python
class BridgeService:
    def start() -> bool
    def stop() -> bool
    def analyze_tokens(content: str) -> TokenMetrics
    def backfill_historical(days: int) -> BackfillResult
    def validate_api_key() -> bool
    def get_sync_status() -> SyncStatus
```

**API Integration**:
```python
# Anthropic API endpoint
POST https://api.anthropic.com/v1/messages/count_tokens

# Request
{
    "model": "claude-sonnet-4-5-20250929",
    "messages": [
        {"role": "user", "content": "..."}
    ]
}

# Response
{
    "input_tokens": 1500,
    "cache_creation_input_tokens": 800,
    "cache_read_input_tokens": 700
}
```

**Rate Limiting**:
- Max 50 requests/minute (API limit)
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Queue overflow: Fall back to estimation
- Priority: Real-time > Backfill

**Token Storage**:
```sql
-- Enhanced token metrics table
CREATE TABLE enhanced_token_details (
    session_id TEXT,
    message_id TEXT,
    timestamp DateTime,
    input_tokens UInt32,
    output_tokens UInt32,
    cache_creation_tokens UInt32,
    cache_read_tokens UInt32,
    cache_hit_rate Float32,
    estimated_cost Float32,
    api_analyzed BOOLEAN
) ENGINE = MergeTree()
ORDER BY (timestamp, session_id);
```

**Fallback Estimation**:
When API unavailable, use heuristic:
```python
def estimate_tokens(text: str) -> int:
    # Conservative estimation (~90% accurate)
    # 1 token ≈ 4 characters for English text
    return len(text) // 4
```

---

### **6. Dashboard Service**

**Location**: `src/context_cleaner/dashboard/`

**Purpose**: Web-based visualization and control interface

**Responsibilities**:
- Serve web UI (HTML, CSS, JavaScript)
- Provide REST API for data access
- Handle WebSocket connections for real-time updates
- Render analytics charts (Chart.js)
- Manage user preferences
- Support export functionality

**Key Components**:

1. **Web Server** (`dashboard_server.py`):
   ```python
   class DashboardServer:
       def start(port: int = 8110) -> bool
       def stop() -> bool
       def handle_request(request: Request) -> Response
   ```

2. **API Endpoints** (`api/routes.py`):
   ```python
   # Analytics endpoints
   GET /api/analytics/effectiveness
   GET /api/analytics/trends
   GET /api/analytics/forecasts

   # Telemetry endpoints
   GET /api/telemetry/metrics
   GET /api/telemetry/sessions
   GET /api/telemetry/messages

   # Control endpoints
   POST /api/services/start
   POST /api/services/stop
   GET /api/health
   ```

3. **WebSocket Handler** (`websocket_handler.py`):
   ```python
   class WebSocketHandler:
       def on_connect(client: WebSocketClient)
       def on_disconnect(client: WebSocketClient)
       def broadcast_update(data: Dict)
   ```

**Frontend Stack**:
- **Framework**: Vanilla JavaScript (no framework)
- **Charts**: Chart.js 3.x
- **Styling**: Custom CSS with CSS Grid
- **Build**: No build step (production-ready static files)

**Data Refresh**:
- **Analytics**: 5-second polling interval
- **Health Status**: 10-second polling interval
- **WebSocket**: Real-time push for events
- **Cache**: LRU with 5-minute TTL

**Port Management**:
```python
DEFAULT_PORT = 8110
FALLBACK_PORTS = [8111, 8112, 8113, 8114, 8115, 8116, 8117, 8118, 8119, 8120]

def find_available_port() -> int:
    for port in [DEFAULT_PORT] + FALLBACK_PORTS:
        if is_port_available(port):
            return port
    raise NoPortAvailableError()
```

---

### **7. Watchdog Service**

**Location**: `src/context_cleaner/core/watchdog.py`

**Purpose**: Monitor service health and perform auto-recovery

**Responsibilities**:
- Periodic health checks (every 30 seconds)
- Detect service failures
- Attempt automatic restart
- Implement exponential backoff
- Report persistent failures
- Maintain service uptime metrics

**Key Methods**:
```python
class WatchdogService:
    def start() -> bool
    def stop() -> bool
    def register_service(service: Service) -> None
    def check_health(service_id: str) -> HealthStatus
    def attempt_recovery(service_id: str) -> bool
```

**Health Check Protocol**:
```python
# Health check interface
class HealthCheckable:
    def health_check() -> HealthStatus

# Health status
@dataclass
class HealthStatus:
    is_healthy: bool
    response_time_ms: float
    error: Optional[str]
    last_check: datetime
    consecutive_failures: int
```

**Recovery Strategy**:
1. **Attempt 1**: Graceful restart (1-second delay)
2. **Attempt 2**: Force restart (5-second delay)
3. **Attempt 3**: Full cleanup + restart (15-second delay)
4. **Failure**: Mark as failed, notify user, disable auto-restart

**Circuit Breaker**:
```python
class CircuitBreaker:
    CLOSED: Normal operation
    OPEN: Failures detected, auto-recovery disabled
    HALF_OPEN: Testing recovery after cooldown

    # Thresholds
    FAILURE_THRESHOLD = 3
    COOLDOWN_PERIOD = 60  # seconds
    SUCCESS_THRESHOLD = 2  # to close circuit
```

**Uptime Tracking**:
```python
# Service uptime metrics
{
    "service_id": "dashboard",
    "total_uptime_seconds": 86400,
    "availability_percentage": 99.95,
    "total_restarts": 2,
    "last_restart": "2025-01-07T10:30:00",
    "consecutive_healthy_checks": 2880
}
```

---

### **8. Analytics Engine**

**Location**: `src/context_cleaner/analytics/`

**Purpose**: Process and analyze productivity data

**Responsibilities**:
- Aggregate metrics from ClickHouse
- Calculate productivity scores
- Detect patterns and trends
- Generate forecasts
- Identify anomalies
- Produce recommendations

**Key Components**:

1. **Effectiveness Analyzer** (`effectiveness_analyzer.py`):
   ```python
   class EffectivenessAnalyzer:
       def calculate_success_rate(sessions: List) -> float
       def estimate_time_saved(sessions: List) -> float
       def analyze_strategy_performance(sessions: List) -> Dict
   ```

2. **Trend Analyzer** (`trend_analyzer.py`):
   ```python
   class TrendAnalyzer:
       def detect_trends(metrics: List[float]) -> TrendAnalysis
       def forecast_productivity(history: List) -> Forecast
       def identify_patterns(sessions: List) -> PatternReport
   ```

3. **Anomaly Detector** (`anomaly_detector.py`):
   ```python
   class AnomalyDetector:
       def detect_statistical_anomalies(data: List) -> List[Anomaly]
       def detect_behavioral_anomalies(sessions: List) -> List[Anomaly]
   ```

**Productivity Score Calculation**:
```python
def calculate_productivity_score(session: Session) -> float:
    """
    Score range: 0-100

    Factors:
    - Context optimization impact (40%)
    - User satisfaction rating (30%)
    - Time saved estimate (20%)
    - Session success rate (10%)
    """
    optimization_score = session.improvement * 0.4
    satisfaction_score = (session.rating / 5.0) * 30
    time_score = min(session.time_saved / 60, 1.0) * 20
    success_score = (1.0 if session.success else 0.0) * 10

    return optimization_score + satisfaction_score + time_score + success_score
```

**Forecast Algorithm**:
- **Method**: Exponential smoothing (Holt-Winters)
- **Seasonality**: Daily and weekly patterns
- **Confidence**: 95% confidence intervals
- **Horizon**: 7-30 days ahead

---

### **9. Process Registry**

**Location**: `src/context_cleaner/core/registry.py`

**Purpose**: Track all Context Cleaner processes and services

**Responsibilities**:
- Register new services
- Track service PIDs and ports
- Manage service lifecycle state
- Support process discovery
- Enable safe cleanup
- Prevent orphaned processes

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS processes (
    id TEXT PRIMARY KEY,              -- Unique service ID
    service_name TEXT NOT NULL,       -- Service type (docker, dashboard, etc)
    pid INTEGER NOT NULL,             -- Process ID
    start_time INTEGER NOT NULL,      -- Unix timestamp
    status TEXT NOT NULL,             -- running, stopped, failed
    port INTEGER,                     -- Listening port (if applicable)
    metadata TEXT,                    -- JSON metadata
    last_heartbeat INTEGER,           -- Last health check timestamp
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX idx_service_name ON processes(service_name);
CREATE INDEX idx_status ON processes(status);
CREATE INDEX idx_pid ON processes(pid);
```

**Key Methods**:
```python
class ProcessRegistry:
    def register(service_info: ServiceInfo) -> str
    def unregister(service_id: str) -> bool
    def update_status(service_id: str, status: str) -> bool
    def heartbeat(service_id: str) -> bool
    def get_all() -> List[ServiceInfo]
    def get_by_name(name: str) -> List[ServiceInfo]
    def cleanup_stale(timeout: int = 300) -> int
```

**Service Information**:
```python
@dataclass
class ServiceInfo:
    id: str                    # UUID
    service_name: str          # Type identifier
    pid: int                   # Process ID
    start_time: datetime       # When started
    status: ServiceStatus      # Current state
    port: Optional[int]        # Listening port
    metadata: Dict[str, Any]   # Extra info
    last_heartbeat: datetime   # Health check timestamp
```

**Cleanup Strategy**:
```python
def cleanup_stale_processes(timeout: int = 300) -> int:
    """
    Remove stale process entries:
    1. No heartbeat for 5+ minutes
    2. Process no longer exists (kill -0 fails)
    3. Status marked as 'stopped' but still registered
    """
    stale = find_stale_entries(timeout)
    for entry in stale:
        if not is_process_alive(entry.pid):
            unregister(entry.id)
    return len(stale)
```

---

### **10. Configuration Manager**

**Location**: `src/context_cleaner/config/config_manager.py`

**Purpose**: Centralized configuration management

**Responsibilities**:
- Load configuration from multiple sources
- Validate configuration values
- Provide defaults
- Support environment variable overrides
- Enable runtime configuration updates
- Persist user preferences

**Configuration Sources** (Priority order):
1. Command-line arguments
2. Environment variables (`CONTEXT_CLEANER_*`)
3. User config file (`~/.context_cleaner/config.yaml`)
4. Default config file (`src/config/defaults.yaml`)

**Configuration Schema**:
```yaml
# ~/.context_cleaner/config.yaml

tracking:
  enabled: true
  sampling_rate: 1.0
  session_timeout_minutes: 30
  anonymize_data: true

services:
  dashboard:
    port: 8110
    host: "127.0.0.1"
    auto_open_browser: true

  docker:
    compose_file: "docker-compose.yml"
    startup_timeout_seconds: 120

  supervisor:
    socket_path: "~/.context_cleaner/supervisor.sock"
    ipc_timeout_seconds: 30

  watchdog:
    check_interval_seconds: 30
    max_restart_attempts: 3

data:
  directory: "~/.context_cleaner/data"
  retention_days: 90
  cache_size_mb: 100

telemetry:
  clickhouse_url: "http://localhost:8123"
  otel_endpoint: "http://localhost:4317"
  batch_size: 1000

privacy:
  sanitize_pii: true
  anonymize_paths: true
  exclude_patterns:
    - "*.key"
    - "*.env"
    - "*secret*"

performance:
  max_memory_mb: 50
  max_concurrent_files: 5
  query_cache_ttl_seconds: 300
```

**Key Methods**:
```python
class ConfigManager:
    def load() -> Config
    def get(key: str, default: Any = None) -> Any
    def set(key: str, value: Any) -> None
    def save() -> bool
    def reset() -> None
    def validate() -> List[ValidationError]
```

---

## 🔄 Component Interactions

### **Startup Sequence**

```
1. CLI Command (context-cleaner run)
   ↓
2. ServiceOrchestrator.start_all_services()
   ↓
3. Start Supervisor (IPC server)
   ├─ Create Unix socket
   ├─ Initialize process registry
   └─ Begin accepting connections
   ↓
4. Start Docker Manager
   ├─ Check Docker availability
   ├─ Start ClickHouse container
   ├─ Start OTEL Collector container
   └─ Wait for health checks
   ↓
5. Start Bridge Service (optional)
   ├─ Validate Anthropic API key
   ├─ Connect to API
   └─ Register with supervisor
   ↓
6. Start JSONL Watcher
   ├─ Initialize file monitor
   ├─ Scan existing files
   ├─ Start watching directory
   └─ Register with supervisor
   ↓
7. Start Dashboard
   ├─ Find available port
   ├─ Start web server
   ├─ Open browser (if configured)
   └─ Register with supervisor
   ↓
8. Start Watchdog
   ├─ Register all services
   ├─ Begin health checks
   └─ Enable auto-recovery
```

### **Message Flow (User Request)**

```
User sends message in Claude Code
   ↓
Claude Code appends to ~/.claude/sessions/abc123.jsonl
   ↓
JSONL Watcher detects file change (inotify)
   ↓
Parse new JSONL line → Extract tokens, content, metadata
   ↓
[Optional] Send to Bridge Service for accurate token count
   ↓
Send telemetry to OpenTelemetry Collector (gRPC)
   ↓
OTEL Collector batches and forwards to ClickHouse
   ↓
ClickHouse stores in otel_logs + claude_message_content tables
   ↓
Dashboard polls ClickHouse (every 5 seconds)
   ↓
Dashboard updates charts in web UI
   ↓
User sees updated metrics (< 10 seconds latency)
```

### **Health Check Flow**

```
Watchdog timer triggers (every 30 seconds)
   ↓
For each registered service:
   ├─ Send health check request via Supervisor IPC
   ├─ Measure response time
   ├─ Update service status in registry
   └─ If failure detected:
       ├─ Increment failure counter
       ├─ Check circuit breaker state
       └─ Attempt recovery if threshold reached
   ↓
If recovery needed:
   ├─ Attempt 1: Graceful restart (wait 1s)
   ├─ Attempt 2: Force restart (wait 5s)
   ├─ Attempt 3: Full cleanup + restart (wait 15s)
   └─ If all fail: Mark as failed, open circuit breaker
   ↓
Update uptime metrics
   ↓
Log health check results
```

---

## 📊 Component Statistics

| Component | Lines of Code | Dependencies | Services Started |
|-----------|---------------|--------------|------------------|
| Service Orchestrator | ~800 | 4 | 0 |
| Supervisor | ~1200 | 2 | 1 (itself) |
| Docker Manager | ~600 | 1 (Docker SDK) | 2 (ClickHouse, OTEL) |
| JSONL Watcher | ~900 | 2 (watchdog, asyncio) | 1 |
| Bridge Service | ~700 | 1 (anthropic) | 1 |
| Dashboard | ~2500 | 3 (Flask, Flask-SocketIO) | 1 |
| Watchdog | ~500 | 1 | 1 |
| Analytics Engine | ~1800 | 2 (scipy, numpy) | 0 |
| Process Registry | ~400 | 1 (sqlite3) | 0 |
| Config Manager | ~350 | 1 (PyYAML) | 0 |

**Total**:
- **Lines of Code**: ~9,750 (core components only)
- **Services Managed**: 8 concurrent services
- **Dependencies**: 10 external libraries
- **API Endpoints**: 15+ REST endpoints
- **Database Tables**: 4 primary tables

---

## 🔐 Security Considerations

### **Per-Component Security**

1. **Supervisor**:
   - Unix socket with 0600 permissions (owner-only)
   - Request validation and sanitization
   - Rate limiting on IPC requests
   - Process ownership verification

2. **Dashboard**:
   - Bind to localhost only (127.0.0.1)
   - No authentication (local-only access)
   - CORS disabled
   - CSP headers for XSS protection

3. **Bridge Service**:
   - API key stored encrypted at rest (AES-256)
   - Never log API keys
   - Rate limiting to prevent abuse
   - Validate all API responses

4. **JSONL Watcher**:
   - PII sanitization before storage
   - File permissions validation
   - Path traversal prevention
   - Sandbox file processing

5. **Process Registry**:
   - Database file permissions: 0600
   - SQL injection prevention (parameterized queries)
   - Process ownership validation
   - Cleanup of stale entries

---

**Next**: [Service Orchestration](orchestration.md) for detailed lifecycle management information

*See also: [System Overview](system-overview.md) for high-level architecture*
