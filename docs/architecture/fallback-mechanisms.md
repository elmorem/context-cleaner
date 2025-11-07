# Fallback Mechanisms & Resilience

> **Complete guide to Context Cleaner's fault tolerance and graceful degradation**

## 🎯 Design Philosophy

Context Cleaner is built with **resilience first**: every critical operation has multiple fallback layers to ensure the system continues functioning even when components fail.

### **Key Principles**

1. **Never Block the User**: Failed operations should degrade gracefully, not hang
2. **Multiple Fallback Layers**: 3-4 fallback strategies for critical paths
3. **Clear Failure Communication**: Users know what failed and why
4. **Automatic Recovery**: System attempts self-healing before human intervention
5. **Fail Open**: Better to provide reduced functionality than to fail completely

## 🛡️ Fallback Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    FALLBACK HIERARCHY                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: Primary Path (Supervisor IPC)                     │
│       ├─ Fast, efficient, feature-complete                   │
│       ├─ Streaming progress updates                          │
│       └─ Process registry integration                        │
│                │                                              │
│                ▼  (Connection Failed)                        │
│  Layer 2: Legacy Orchestrator                                │
│       ├─ Direct process management                           │
│       ├─ Basic progress reporting                            │
│       └─ Process discovery fallback                          │
│                │                                              │
│                ▼  (Orchestrator Issues)                      │
│  Layer 3: Direct Service Control                             │
│       ├─ Individual service commands                         │
│       ├─ Manual Docker control                               │
│       └─ PID-based process management                        │
│                │                                              │
│                ▼  (All Automation Failed)                    │
│  Layer 4: Manual Cleanup                                     │
│       ├─ Bash scripts (stop-context-cleaner.sh)             │
│       ├─ Direct kill commands                                │
│       └─ Manual Docker cleanup                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Service Start Fallbacks

### **1. Supervisor Startup**

```python
# Primary: Start new supervisor
try:
    supervisor = await start_supervisor()
    # Success! Use IPC for all operations
except SupervisorStartFailed:
    # Fallback 1: Check if already running
    if supervisor_socket_exists():
        try:
            existing = connect_to_supervisor()
            # Use existing supervisor
        except ConnectionFailed:
            # Fallback 2: Clean stale socket
            remove_stale_socket()
            supervisor = await start_supervisor()
    else:
        # Fallback 3: Run without supervisor
        use_legacy_orchestrator()
```

**Fallback Layers**:
1. **Primary**: Start fresh supervisor process
2. **Fallback 1**: Connect to existing supervisor
3. **Fallback 2**: Clean stale socket and retry
4. **Fallback 3**: Run with legacy orchestrator only

### **2. Docker Service Startup**

```python
# Primary: Use docker compose
try:
    docker compose up -d
    # Modern, clean approach
except DockerComposeNotFound:
    # Fallback 1: Individual docker run commands
    try:
        docker run clickhouse...
        docker run otel-collector...
    except DockerNotRunning:
        # Fallback 2: Attempt to start Docker daemon
        try:
            start_docker_daemon()
            retry_docker_startup()
        except DockerNotInstalled:
            # Fallback 3: Continue without Docker
            warn_user("Docker unavailable")
            use_file_based_analytics()
```

**Fallback Layers**:
1. **Primary**: Docker Compose orchestration
2. **Fallback 1**: Individual docker run commands
3. **Fallback 2**: Auto-start Docker daemon
4. **Fallback 3**: File-based analytics without ClickHouse

### **3. Dashboard Startup**

```python
# Primary: Gunicorn with production settings
try:
    gunicorn --workers 4 --bind 127.0.0.1:8110
    # Production-ready server
except GunicornNotFound:
    # Fallback 1: Flask development server
    try:
        flask run --port 8110
    except PortInUse:
        # Fallback 2: Auto-select alternative port
        try:
            port = find_available_port(start=8111, end=8120)
            flask run --port {port}
        except NoPortsAvailable:
            # Fallback 3: Disable dashboard
            warn_user("Dashboard unavailable")
            cli_only_mode()
```

**Fallback Layers**:
1. **Primary**: Gunicorn production server
2. **Fallback 1**: Flask development server
3. **Fallback 2**: Alternative port selection
4. **Fallback 3**: CLI-only mode without dashboard

## 🛑 Service Stop Fallbacks

### **1. Graceful Shutdown via Supervisor**

```python
# Primary: Supervisor streaming shutdown
try:
    async for progress in supervisor.shutdown_services():
        print_progress(progress)
    # Coordinated, dependency-aware shutdown
except SupervisorUnavailable:
    # Fallback 1: Orchestrator shutdown
    try:
        orchestrator.stop_all_services()
    except OrchestrationFailed:
        # Fallback 2: Process discovery
        try:
            processes = discover_context_cleaner_processes()
            for proc in processes:
                proc.terminate(timeout=5)
        except DiscoveryFailed:
            # Fallback 3: Manual cleanup script
            try:
                subprocess.run(["bash", "stop-context-cleaner.sh"])
            except ScriptNotFound:
                # Fallback 4: User guidance
                print_manual_cleanup_instructions()
```

**Fallback Layers**:
1. **Primary**: Supervisor streaming shutdown with dependency handling
2. **Fallback 1**: Legacy orchestrator with basic shutdown
3. **Fallback 2**: Process discovery and termination
4. **Fallback 3**: Bash cleanup script
5. **Fallback 4**: Manual instructions to user

### **2. Container Shutdown**

```python
# Primary: Docker compose down
try:
    docker compose down --timeout 10
except ComposeUnavailable:
    # Fallback 1: Individual container stops
    try:
        docker stop clickhouse-otel otel-collector
    except ContainerNotFound:
        # Fallback 2: Force kill containers
        try:
            docker kill clickhouse-otel otel-collector
        except DockerDaemonDown:
            # Fallback 3: Containers already stopped
            log("Containers not running")
```

**Fallback Layers**:
1. **Primary**: Docker Compose graceful shutdown
2. **Fallback 1**: Individual container stops
3. **Fallback 2**: Force kill containers
4. **Fallback 3**: Accept already-stopped state

## 📊 Data Access Fallbacks

### **1. Analytics Data Retrieval**

```python
# Primary: ClickHouse query
try:
    data = clickhouse.query("SELECT * FROM otel_logs")
    # Fast, structured data
except ClickHouseUnavailable:
    # Fallback 1: Local file cache
    try:
        data = load_from_cache("analytics.cache")
    except CacheCorrupted:
        # Fallback 2: Parse JSONL files directly
        try:
            data = parse_jsonl_sessions()
        except NoJSONLFiles:
            # Fallback 3: Empty state with message
            return EmptyAnalytics(message="No data available")
```

**Fallback Layers**:
1. **Primary**: ClickHouse database query
2. **Fallback 1**: Local file cache
3. **Fallback 2**: Direct JSONL parsing
4. **Fallback 3**: Empty state with clear messaging

### **2. Token Analysis**

```python
# Primary: Enhanced token analysis via API
try:
    analysis = anthropic_api.count_tokens(content)
    # Accurate, official counts
except APIKeyMissing:
    # Fallback 1: Estimated token counting
    try:
        analysis = estimate_tokens_heuristic(content)
        # ~90% accurate estimation
    except:
        # Fallback 2: Character-based rough estimate
        analysis = len(content) // 4  # Very rough
```

**Fallback Layers**:
1. **Primary**: Anthropic API official token counting
2. **Fallback 1**: Heuristic estimation (90% accuracy)
3. **Fallback 2**: Character-based approximation

## 🔌 IPC Communication Fallbacks

### **1. Supervisor Connection**

```python
# Primary: Unix socket connection
try:
    socket = connect_unix_socket("/var/run/context-cleaner/supervisor.sock")
    # Fast, reliable IPC
except SocketNotFound:
    # Fallback 1: TCP socket (if configured)
    try:
        socket = connect_tcp("localhost", 5555)
    except TCPConnectionRefused:
        # Fallback 2: Retry with backoff
        for attempt in range(3):
            time.sleep(2 ** attempt)
            try:
                socket = connect_unix_socket(...)
                break
            except:
                continue
        else:
            # Fallback 3: Direct method calls
            use_direct_orchestrator_calls()
```

**Fallback Layers**:
1. **Primary**: Unix socket IPC
2. **Fallback 1**: TCP socket alternative
3. **Fallback 2**: Retry with exponential backoff
4. **Fallback 3**: Direct orchestrator method calls

## 🏥 Health Check Fallbacks

### **1. Service Health Verification**

```python
# Primary: Comprehensive health check
try:
    health = await service.health_check()
    # Full status including metrics
except HealthCheckTimeout:
    # Fallback 1: Simple ping test
    try:
        health = service.ping()
        # Basic up/down status
    except PingFailed:
        # Fallback 2: Process existence check
        try:
            health = process_exists(service.pid)
        except:
            # Fallback 3: Assume unhealthy
            health = HealthStatus.UNKNOWN
```

**Fallback Layers**:
1. **Primary**: Comprehensive health check with metrics
2. **Fallback 1**: Simple ping/pong test
3. **Fallback 2**: Process existence verification
4. **Fallback 3**: Conservative "unknown" status

## 🔄 Auto-Recovery Mechanisms

### **1. Watchdog Auto-Restart**

```python
class WatchdogRecovery:
    def __init__(self):
        self.max_restart_attempts = 3
        self.restart_backoff = [1, 5, 15]  # seconds

    async def monitor_service(self, service):
        attempt = 0
        while attempt < self.max_restart_attempts:
            if not await service.is_healthy():
                # Restart with backoff
                await asyncio.sleep(self.restart_backoff[attempt])
                try:
                    await service.restart()
                    # Success! Reset counter
                    attempt = 0
                except RestartFailed:
                    attempt += 1
                    if attempt >= self.max_restart_attempts:
                        # Give up, notify user
                        alert_user(f"{service.name} failed repeatedly")
                        break
```

**Strategy**:
- **Attempt 1**: Restart after 1 second
- **Attempt 2**: Restart after 5 seconds
- **Attempt 3**: Restart after 15 seconds
- **After 3 failures**: Alert user and give up

### **2. Circuit Breaker Pattern**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = timeout
        self.last_failure = None
        self.state = "CLOSED"  # CLOSED -> OPEN -> HALF_OPEN -> CLOSED

    async def call(self, func):
        if self.state == "OPEN":
            if time.time() - self.last_failure < self.timeout:
                # Circuit still open, fail fast
                raise CircuitBreakerOpen("Service unavailable")
            else:
                # Try to close circuit
                self.state = "HALF_OPEN"

        try:
            result = await func()
            # Success! Close circuit
            self.failures = 0
            self.state = "CLOSED"
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.state = "OPEN"
            raise
```

**States**:
- **CLOSED**: Normal operation, requests go through
- **OPEN**: Too many failures, fail fast to prevent cascading
- **HALF_OPEN**: Testing if service recovered

## 📝 Fallback Examples by Scenario

### **Scenario 1: User Starts System, Docker Not Installed**

```
1. CLI: context-cleaner run
2. Orchestrator: Attempt Docker Compose
3. FALLBACK: Docker not found
4. Orchestrator: Skip Docker services
5. CONTINUE: Start dashboard with file-based analytics
6. USER SEES: "Docker unavailable, using file-based analytics"
7. RESULT: System works, but no ClickHouse integration
```

### **Scenario 2: Supervisor Socket Stale**

```
1. CLI: context-cleaner stop
2. Orchestrator: Attempt supervisor connection
3. FALLBACK: Socket exists but no response
4. Orchestrator: Remove stale socket
5. FALLBACK: Use legacy shutdown method
6. Orchestrator: Direct process termination
7. RESULT: Services stopped successfully
```

### **Scenario 3: Dashboard Port Conflict**

```
1. Orchestrator: Start dashboard on 8110
2. FALLBACK: Port 8110 in use
3. Orchestrator: Try port 8111
4. FALLBACK: Port 8111 in use
5. Orchestrator: Try port 8112
6. SUCCESS: Dashboard starts on 8112
7. USER SEES: "Dashboard running on http://localhost:8112"
```

### **Scenario 4: ClickHouse Crashes During Operation**

```
1. Dashboard: Query analytics data
2. DATABASE: ClickHouse connection refused
3. FALLBACK: Load from local cache
4. CACHE: Serve slightly stale data
5. WATCHDOG: Detect ClickHouse down
6. RECOVERY: Restart ClickHouse container
7. WATCHDOG: Verify container healthy
8. RESULT: Dashboard works throughout, automatic recovery
```

## 🎯 Fallback Best Practices

### **1. Always Have a Fallback**
Every critical operation should have at least 2-3 fallback strategies.

### **2. Fail Fast When Appropriate**
Don't retry indefinitely. Circuit breakers prevent cascading failures.

### **3. Communicate Clearly**
Tell users what failed and what fallback is being used.

### **4. Log Everything**
All fallback activations should be logged for debugging.

### **5. Test Fallbacks**
Regularly test that fallback mechanisms actually work.

---

**Next**: [Component Architecture](components.md) for detailed component breakdown

*See also: [Health Monitoring](health-monitoring.md) for monitoring systems*
