# Service Orchestration

> **How Context Cleaner coordinates service lifecycle, dependencies, and state management**

## 🎯 Overview

Service orchestration in Context Cleaner manages the complex lifecycle of 8+ concurrent services, ensuring proper startup order, dependency resolution, graceful shutdown, and robust error handling.

## 🏗️ Orchestration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   USER COMMANDS (CLI)                        │
│  context-cleaner run | stop | restart | status              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              SERVICE ORCHESTRATOR                            │
│  • Unified service control interface                         │
│  • Dependency graph management                               │
│  • State machine for lifecycle                               │
│  • Fallback coordination                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  Supervisor │  │Docker Manager│  │   Dashboard  │
│  (IPC Core) │  │ (Containers) │  │   (Web UI)   │
└─────────────┘  └──────────────┘  └──────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
                ┌────────────────┐
                │Watchdog Monitor│
                │(Auto-recovery) │
                └────────────────┘
```

## 📋 Service Dependency Graph

```
         supervisor (IPC)
               │
      ┌────────┴────────┐
      │                 │
   docker           watchdog
      │                 │
  ┌───┴───┐            │
  │       │            │
clickhouse otel        │
  │       │            │
  └───┬───┘            │
      │                │
  ┌───┴────┬───────────┘
  │        │
bridge  jsonl_watcher
  │        │
  └────┬───┘
       │
   dashboard

Legend:
  │  = Dependency (must start before)
  ┌┘ = Optional dependency
```

**Dependency Rules**:
1. **Supervisor** must start first (provides IPC)
2. **Docker** must start before bridge/jsonl (provides database)
3. **Watchdog** can start anytime (monitors all)
4. **Dashboard** should start last (depends on data sources)

## 🚀 Startup Orchestration

### **Phase 1: Initialization**

```python
def start_all_services() -> bool:
    """
    Orchestrated startup with dependency resolution
    """
    # 1. Pre-flight checks
    validate_configuration()
    check_system_resources()
    cleanup_stale_processes()

    # 2. Initialize process registry
    registry = ProcessRegistry()
    registry.initialize()

    # 3. Create service dependency graph
    graph = build_dependency_graph()
    startup_order = topological_sort(graph)

    # 4. Start services in dependency order
    for service in startup_order:
        success = start_service_with_fallbacks(service)
        if not success and service.required:
            rollback_started_services()
            return False

    # 5. Post-startup validation
    verify_all_services_healthy()

    return True
```

### **Startup Sequence (Detailed)**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Pre-Flight Checks (5-10 seconds)                    │
├─────────────────────────────────────────────────────────────┤
│ • Check if services already running                         │
│ • Validate config file exists and is valid                  │
│ • Verify required directories exist                         │
│ • Check Docker availability (if using containers)           │
│ • Verify sufficient disk space (>100MB)                     │
│ • Check port availability (8110)                            │
│ • Clean up any stale process registry entries               │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Start Supervisor (1-2 seconds)                      │
├─────────────────────────────────────────────────────────────┤
│ 1. Create Unix socket: ~/.context_cleaner/supervisor.sock   │
│ 2. Set permissions: chmod 0600                              │
│ 3. Initialize SQLite registry database                      │
│ 4. Start IPC listener thread                                │
│ 5. Register supervisor in process registry                  │
│ 6. Wait for socket to be ready (max 5 seconds)              │
│                                                              │
│ Fallback: If socket creation fails:                         │
│   → Try alternate path: /tmp/context_cleaner_supervisor.sock│
│   → Try TCP socket on 127.0.0.1:9999                        │
│   → Continue without supervisor (degraded mode)             │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Start Docker Services (30-60 seconds)               │
├─────────────────────────────────────────────────────────────┤
│ 3a. Docker Manager Initialization                           │
│     • Verify Docker daemon accessible                       │
│     • Load docker-compose.yml configuration                 │
│     • Check for existing containers                         │
│                                                              │
│ 3b. Start ClickHouse Container                              │
│     • docker compose up clickhouse -d                       │
│     • Wait for health check (HTTP GET /ping)                │
│     • Initialize database schema                            │
│     • Create tables: otel_logs, claude_message_content      │
│     • Max wait: 45 seconds                                  │
│                                                              │
│ 3c. Start OpenTelemetry Collector                           │
│     • docker compose up otel-collector -d                   │
│     • Wait for gRPC port 4317 ready                         │
│     • Verify connection to ClickHouse                       │
│     • Max wait: 30 seconds                                  │
│                                                              │
│ Fallback: If Docker unavailable:                            │
│   → Use local SQLite database                               │
│   → Disable telemetry features                              │
│   → Continue with file-based analytics only                 │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Start Bridge Service (2-5 seconds) [OPTIONAL]       │
├─────────────────────────────────────────────────────────────┤
│ 1. Check for Anthropic API key in environment               │
│ 2. If present:                                              │
│    • Validate API key (test request)                        │
│    • Initialize rate limiter (50 req/min)                   │
│    • Connect to ClickHouse for storage                      │
│    • Register with supervisor                               │
│ 3. If absent:                                               │
│    • Skip bridge service                                    │
│    • Use heuristic token estimation instead                 │
│                                                              │
│ Status: Service startup continues without bridge            │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Start JSONL Watcher (1-2 seconds)                   │
├─────────────────────────────────────────────────────────────┤
│ 1. Verify Claude sessions directory exists                  │
│    • Default: ~/.claude/sessions/                           │
│    • Create if missing                                      │
│ 2. Scan for existing JSONL files                            │
│    • Build initial file index                               │
│    • Calculate baseline metrics                             │
│ 3. Initialize watchdog file monitor                         │
│    • Set up inotify/FSEvents handlers                       │
│    • Configure debounce (1 second)                          │
│ 4. Start file processing queue                              │
│    • Max 5 concurrent files                                 │
│    • Backpressure: 1000 message queue                       │
│ 5. Register with supervisor                                 │
│                                                              │
│ Fallback: If directory unavailable:                         │
│   → Disable real-time monitoring                            │
│   → Support manual file processing only                     │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: Start Dashboard (2-5 seconds)                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Find available port                                      │
│    • Try default: 8110                                      │
│    • Fallback ports: 8111-8120                              │
│ 2. Initialize Flask application                             │
│    • Load templates and static files                        │
│    • Configure routes (15+ endpoints)                       │
│    • Set up WebSocket handler                               │
│ 3. Start web server (Gunicorn)                              │
│    • Bind to 127.0.0.1:<port>                               │
│    • Worker count: 1 (single process)                       │
│ 4. Initialize LRU cache                                     │
│    • Max size: 1000 items                                   │
│    • TTL: 5 minutes                                         │
│ 5. Open browser (if configured)                             │
│ 6. Register with supervisor                                 │
│                                                              │
│ Fallback: If port unavailable:                              │
│   → Try next port in fallback list                          │
│   → Report final URL to user                                │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: Start Watchdog (1 second)                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Register all started services                            │
│ 2. Initialize circuit breakers (one per service)            │
│ 3. Start health check timer (30-second interval)            │
│ 4. Enable auto-recovery mechanisms                          │
│ 5. Register with supervisor                                 │
│                                                              │
│ Monitoring begins immediately                               │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: Post-Startup Validation (2-3 seconds)               │
├─────────────────────────────────────────────────────────────┤
│ 1. Verify all required services are healthy                 │
│ 2. Check inter-service connectivity                         │
│    • Dashboard can reach ClickHouse                         │
│    • JSONL Watcher can send to OTEL                         │
│    • Supervisor can communicate with all services           │
│ 3. Generate startup report                                  │
│    • List running services with PIDs                        │
│    • Display dashboard URL                                  │
│    • Show any warnings or degraded features                 │
│ 4. Mark startup as complete in registry                     │
│                                                              │
│ Total startup time: 40-90 seconds (typical: 50 seconds)     │
└─────────────────────────────────────────────────────────────┘
```

### **Startup Output (CLI)**

```bash
$ context-cleaner run

🚀 Starting Context Cleaner...

✓ Pre-flight checks passed
✓ Supervisor started (PID: 12345, Socket: ~/.context_cleaner/supervisor.sock)
✓ Docker services starting...
  ✓ ClickHouse (Container: context_cleaner_clickhouse, Port: 8123)
  ✓ OpenTelemetry Collector (Container: context_cleaner_otel, Port: 4317)
⚠ Bridge service skipped (no API key configured)
✓ JSONL Watcher started (Monitoring: ~/.claude/sessions/)
✓ Dashboard started (URL: http://127.0.0.1:8110)
✓ Watchdog started (Health checks: every 30s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Context Cleaner is running!

📊 Dashboard: http://127.0.0.1:8110
📁 Data Directory: ~/.context_cleaner/data
🔍 Monitoring: ~/.claude/sessions/

Press Ctrl+C to stop all services
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Opening dashboard in browser...]
```

## 🛑 Shutdown Orchestration

### **Graceful Shutdown Sequence**

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: User-Facing Services (5 seconds timeout)           │
├─────────────────────────────────────────────────────────────┤
│ 1. Stop Dashboard                                           │
│    • Close all WebSocket connections                        │
│    • Finish pending requests (max 2 second wait)            │
│    • Stop Flask/Gunicorn gracefully                         │
│    • Unregister from supervisor                             │
│                                                              │
│ 2. Stop JSONL Watcher                                       │
│    • Stop accepting new file events                         │
│    • Finish processing current files                        │
│    • Flush telemetry queue to OTEL                          │
│    • Close file handles                                     │
│    • Unregister from supervisor                             │
│                                                              │
│ 3. Stop Bridge Service (if running)                         │
│    • Cancel pending API requests                            │
│    • Close Anthropic API connection                         │
│    • Unregister from supervisor                             │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: Infrastructure Services (10 seconds timeout)       │
├─────────────────────────────────────────────────────────────┤
│ 1. Stop Watchdog                                            │
│    • Cancel health check timer                              │
│    • Disable auto-recovery                                  │
│    • Flush uptime metrics                                   │
│    • Unregister from supervisor                             │
│                                                              │
│ 2. Stop Docker Services                                     │
│    • Flush pending telemetry to ClickHouse                  │
│    • docker compose down (graceful)                         │
│    • Wait for containers to stop (max 10 seconds)           │
│    • If timeout: docker compose down --force                │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: Core Services (3 seconds timeout)                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Stop Supervisor                                          │
│    • Close IPC socket                                       │
│    • Flush process registry to disk                         │
│    • Cleanup socket file                                    │
│    • Final status report                                    │
│                                                              │
│ 2. Cleanup                                                  │
│    • Remove PID files                                       │
│    • Close log files                                        │
│    • Release file locks                                     │
│                                                              │
│ Total shutdown time: 10-20 seconds                          │
└─────────────────────────────────────────────────────────────┘
```

### **Shutdown Implementation**

```python
async def stop_all_services(force: bool = False) -> bool:
    """
    Orchestrated shutdown with reverse dependency order
    """
    if force:
        return force_stop_all()

    # Get reverse dependency order
    shutdown_order = reverse_topological_sort(dependency_graph)

    # Phase 1: User-facing services (parallel)
    user_services = ["dashboard", "jsonl_watcher", "bridge"]
    await asyncio.gather(*[
        stop_service_graceful(svc, timeout=5)
        for svc in user_services
    ])

    # Phase 2: Infrastructure services (sequential)
    await stop_service_graceful("watchdog", timeout=3)
    await stop_service_graceful("docker", timeout=10)

    # Phase 3: Core services
    await stop_service_graceful("supervisor", timeout=3)

    # Verify all stopped
    verify_all_services_stopped()

    return True

async def stop_service_graceful(
    service_name: str,
    timeout: int
) -> bool:
    """
    Stop single service with timeout
    """
    try:
        # Send shutdown signal via IPC
        success = await send_shutdown_request(service_name, timeout)

        if not success:
            # Fallback: SIGTERM
            pid = registry.get_pid(service_name)
            os.kill(pid, signal.SIGTERM)

            # Wait for graceful exit
            for _ in range(timeout * 10):
                if not is_process_alive(pid):
                    return True
                await asyncio.sleep(0.1)

            # Force kill if timeout
            os.kill(pid, signal.SIGKILL)

        return True

    except Exception as e:
        log_error(f"Failed to stop {service_name}: {e}")
        return False
```

### **Shutdown Output (CLI)**

```bash
$ context-cleaner stop

🛑 Stopping Context Cleaner services...

Phase 1: User-facing services
  ✓ Dashboard stopped (gracefully)
  ✓ JSONL Watcher stopped (queue flushed)
  ⚠ Bridge service not running

Phase 2: Infrastructure services
  ✓ Watchdog stopped
  ✓ Docker services stopped
    ✓ ClickHouse container stopped
    ✓ OTEL Collector container stopped

Phase 3: Core services
  ✓ Supervisor stopped
  ✓ Cleanup completed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ All services stopped successfully

📊 Session Summary:
  • Uptime: 2h 34m 18s
  • Messages Processed: 1,247
  • Dashboard Requests: 89
  • Health Checks: 308 (all passed)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🔄 Service State Machine

Each service follows a well-defined state machine:

```
        [UNINITIALIZED]
               │
               ▼
         [STARTING]
          │      │
          │      └─────────► [FAILED]
          ▼                      ▲
       [RUNNING] ◄───────┐       │
          │              │       │
          │         [RECOVERING] │
          │              │       │
          └──────────────┘       │
          │                      │
          ▼                      │
      [STOPPING]                 │
          │                      │
          ├──────────────────────┘
          ▼
       [STOPPED]

State Transitions:
  UNINITIALIZED → STARTING: User runs start command
  STARTING → RUNNING: Service starts successfully
  STARTING → FAILED: Service fails to start
  RUNNING → RECOVERING: Watchdog detects failure
  RECOVERING → RUNNING: Auto-recovery succeeds
  RECOVERING → FAILED: Auto-recovery fails
  RUNNING → STOPPING: User runs stop command
  STOPPING → STOPPED: Service stops successfully
  STOPPING → FAILED: Service fails to stop gracefully
  FAILED → STARTING: Manual restart attempt
```

### **State Transitions Implementation**

```python
class ServiceState(Enum):
    UNINITIALIZED = "uninitialized"
    STARTING = "starting"
    RUNNING = "running"
    RECOVERING = "recovering"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"

class ServiceStateMachine:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.state = ServiceState.UNINITIALIZED
        self.state_history: List[Tuple[ServiceState, datetime]] = []

    def transition(self, new_state: ServiceState, reason: str = "") -> bool:
        """
        Attempt state transition with validation
        """
        if not self._is_valid_transition(self.state, new_state):
            log_warning(f"Invalid transition: {self.state} → {new_state}")
            return False

        old_state = self.state
        self.state = new_state
        self.state_history.append((new_state, datetime.now()))

        log_info(f"{self.service_name}: {old_state} → {new_state} ({reason})")
        self._emit_state_change_event(old_state, new_state)

        return True

    def _is_valid_transition(self, from_state: ServiceState, to_state: ServiceState) -> bool:
        """
        Validate state transition according to state machine
        """
        valid_transitions = {
            ServiceState.UNINITIALIZED: [ServiceState.STARTING],
            ServiceState.STARTING: [ServiceState.RUNNING, ServiceState.FAILED],
            ServiceState.RUNNING: [ServiceState.RECOVERING, ServiceState.STOPPING],
            ServiceState.RECOVERING: [ServiceState.RUNNING, ServiceState.FAILED],
            ServiceState.STOPPING: [ServiceState.STOPPED, ServiceState.FAILED],
            ServiceState.STOPPED: [],
            ServiceState.FAILED: [ServiceState.STARTING],
        }

        return to_state in valid_transitions.get(from_state, [])
```

## 🎛️ Service Control Interface

### **IPC-Based Control**

```python
class ServiceControl:
    """
    Unified service control via Supervisor IPC
    """

    async def start_service(self, service_name: str, options: Dict = None) -> bool:
        """
        Start a service via supervisor
        """
        request = {
            "action": "start_service",
            "params": {
                "service_name": service_name,
                "options": options or {}
            }
        }

        response = await self.supervisor_ipc.send_request(request)

        if response["status"] == "success":
            log_info(f"Service {service_name} started successfully")
            return True
        else:
            log_error(f"Failed to start {service_name}: {response['error']}")
            return False

    async def stop_service(self, service_name: str, force: bool = False) -> bool:
        """
        Stop a service via supervisor
        """
        request = {
            "action": "stop_service",
            "params": {
                "service_name": service_name,
                "force": force
            }
        }

        response = await self.supervisor_ipc.send_request(request, timeout=30)
        return response["status"] == "success"

    async def restart_service(self, service_name: str) -> bool:
        """
        Restart a service (stop then start)
        """
        await self.stop_service(service_name, force=False)
        await asyncio.sleep(2)  # Brief pause
        return await self.start_service(service_name)

    async def get_service_status(self, service_name: str) -> ServiceStatus:
        """
        Query service status via supervisor
        """
        request = {
            "action": "get_status",
            "params": {"service_name": service_name}
        }

        response = await self.supervisor_ipc.send_request(request)
        return ServiceStatus(**response["data"])
```

### **Direct Control (Fallback)**

```python
class DirectServiceControl:
    """
    Direct service control when supervisor unavailable
    """

    def start_service_direct(self, service_name: str) -> bool:
        """
        Start service without supervisor (fallback)
        """
        service_config = self.config.get_service_config(service_name)

        if service_name == "docker":
            return self._start_docker_direct()
        elif service_name == "dashboard":
            return self._start_dashboard_direct()
        # ... handle other services

    def _start_docker_direct(self) -> bool:
        """
        Start Docker services directly via CLI
        """
        try:
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
```

## 📊 Service Monitoring

### **Real-Time Status Reporting**

```python
class ServiceMonitor:
    """
    Monitor and report service status in real-time
    """

    async def stream_status_updates(self, output_stream):
        """
        Stream service status to CLI
        """
        while True:
            statuses = await self.get_all_service_statuses()

            for service, status in statuses.items():
                emoji = self._get_status_emoji(status.state)
                output_stream.write(
                    f"{emoji} {service}: {status.state} "
                    f"(PID: {status.pid}, Uptime: {status.uptime})\n"
                )

            await asyncio.sleep(5)

    def _get_status_emoji(self, state: ServiceState) -> str:
        return {
            ServiceState.RUNNING: "✓",
            ServiceState.STARTING: "⏳",
            ServiceState.STOPPING: "🛑",
            ServiceState.FAILED: "✗",
            ServiceState.RECOVERING: "🔄"
        }.get(state, "?")
```

### **Status Dashboard (CLI)**

```bash
$ context-cleaner status

Context Cleaner Service Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Service          Status      PID     Uptime     Health
─────────────────────────────────────────────────────
Supervisor       ✓ Running   12345   2h 15m     100%
Docker Manager   ✓ Running   12346   2h 15m     100%
  ├─ ClickHouse  ✓ Running   12350   2h 15m     100%
  └─ OTEL Coll.  ✓ Running   12351   2h 15m     100%
Bridge Service   ⚠ Disabled  -       -          N/A
JSONL Watcher    ✓ Running   12347   2h 14m     100%
Dashboard        ✓ Running   12348   2h 14m     100%
Watchdog         ✓ Running   12349   2h 14m     100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall System Health: ✓ Healthy

Dashboard: http://127.0.0.1:8110
Last Health Check: 5 seconds ago
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ⚡ Performance Optimization

### **Parallel Service Startup**

Services with no dependencies can start in parallel:

```python
async def start_independent_services() -> Dict[str, bool]:
    """
    Start multiple services in parallel
    """
    # These services have no interdependencies
    independent = ["bridge", "jsonl_watcher"]

    results = await asyncio.gather(*[
        start_service_with_fallbacks(service)
        for service in independent
    ], return_exceptions=True)

    return dict(zip(independent, results))
```

**Timing Comparison**:
- Sequential startup: 50-60 seconds
- Parallel startup: 35-45 seconds
- Improvement: ~30% faster

### **Lazy Service Initialization**

Services can defer expensive initialization:

```python
class LazyService:
    def __init__(self):
        self._initialized = False

    async def ensure_initialized(self):
        if not self._initialized:
            await self._initialize()
            self._initialized = True

    async def _initialize(self):
        # Expensive operations here
        pass

    async def handle_request(self, request):
        await self.ensure_initialized()
        # Process request
```

---

## 🔧 Troubleshooting

### **Common Orchestration Issues**

**1. Service Won't Start**
```bash
# Check supervisor is running
context-cleaner debug list-processes | grep supervisor

# View detailed logs
context-cleaner debug health-check --verbose

# Try manual start
context-cleaner start --service docker --verbose
```

**2. Stuck in Starting State**
```bash
# Force restart
context-cleaner restart --service dashboard --force

# Check for port conflicts
lsof -i :8110

# Clean up stale processes
context-cleaner debug cleanup-stale
```

**3. Partial Shutdown**
```bash
# List remaining processes
context-cleaner debug process-tree

# Force stop all
context-cleaner stop --force

# Manual cleanup if needed
pkill -f "context-cleaner"
```

---

**Next**: [Supervisor IPC](supervisor-ipc.md) for detailed IPC protocol documentation

*See also: [Fallback Mechanisms](fallback-mechanisms.md) for resilience strategies*
