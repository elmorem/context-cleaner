# System Overview

> **High-level architecture and design principles for Context Cleaner v0.3.0**

## 🎯 System Purpose

Context Cleaner is a **privacy-first productivity tracking and context optimization** system for AI-assisted development. It provides:

1. **Real-time telemetry collection** from Claude Code sessions
2. **Comprehensive analytics** on token usage and productivity
3. **Interactive dashboard** for insights and optimization
4. **Historical data migration** from JSONL cache files
5. **Automated health monitoring** and service management

## 🏗️ Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          USER INTERACTIONS                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │
│  │     CLI     │   │  Web Browser │   │   Claude    │   │  File       │ │
│  │  Commands   │   │  (Dashboard) │   │    Code     │   │  System     │ │
│  └──────┬──────┘   └──────┬───────┘   └──────┬──────┘   └──────┬──────┘ │
│         │                  │                   │                  │        │
└─────────┼──────────────────┼───────────────────┼──────────────────┼────────┘
          │                  │                   │                  │
┌─────────▼──────────────────▼───────────────────▼──────────────────▼────────┐
│                        APPLICATION LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      CLI ENTRY POINT                               │    │
│  │  (context_cleaner.cli.main)                                        │    │
│  │  ├─ run          ← Start all services                              │    │
│  │  ├─ stop         ← Shutdown services                               │    │
│  │  ├─ analytics    ← Advanced analytics commands                     │    │
│  │  ├─ debug        ← Process registry diagnostics                    │    │
│  │  └─ ...          ← 20+ commands total                              │    │
│  └──────┬─────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         │  INITIATES                                                         │
│         ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                  SERVICE ORCHESTRATOR                              │    │
│  │  (services.service_orchestrator.py)                                │    │
│  │                                                                     │    │
│  │  Responsibilities:                                                  │    │
│  │  • Manage service lifecycle (start/stop/restart)                   │    │
│  │  • Coordinate dependencies between services                        │    │
│  │  • Health monitoring and auto-recovery                             │    │
│  │  • Port conflict resolution                                        │    │
│  │  • Process discovery and cleanup                                   │    │
│  │  • Fallback to legacy methods if supervisor unavailable            │    │
│  └──────┬──────────────────┬──────────────────┬──────────────────────┘    │
│         │                  │                  │                            │
│         │  SPAWNS          │  COMMUNICATES    │  REGISTERS                 │
│         ▼                  ▼                  ▼                            │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐                 │
│  │  SUPERVISOR │   │   WATCHDOG  │   │  PROCESS REGISTRY│                 │
│  │  (IPC)      │   │  (Monitor)  │   │   (Tracking)     │                 │
│  └──────┬──────┘   └──────┬──────┘   └──────┬───────────┘                 │
│         │                  │                  │                             │
└─────────┼──────────────────┼──────────────────┼─────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────────────────────┐
│                        SERVICE LAYER                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   DOCKER     │  │    JSONL     │  │    BRIDGE    │  │   DASHBOARD  │   │
│  │   SERVICES   │  │   PROCESSOR  │  │   SERVICE    │  │   (Web API)  │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │           │
│    ┌────▼────┐      ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼───────┐  │
│    │ ClickH. │      │Parse Cache  │   │Token Analy. │   │Flask/Gunicorn│  │
│    │  OTEL   │      │Monitor New  │   │Historical   │   │WebSocket RT  │  │
│    └────┬────┘      └──────┬──────┘   └──────┬──────┘   └──────┬───────┘  │
│         │                  │                  │                  │           │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │                  │
┌─────────▼──────────────────▼──────────────────▼──────────────────▼───────────┐
│                        DATA LAYER                                             │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                      ClickHouse Database                            │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │     │
│  │  │  otel_logs   │  │ otel_traces  │  │ otel_metrics │              │     │
│  │  │  otel_spans  │  │token_details │  │conversations │              │     │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                      File System Storage                            │     │
│  │  ~/.claude/sessions/*.jsonl        (Source data)                    │     │
│  │  ~/.context_cleaner/data/          (Local analytics)                │     │
│  │  ~/.context_cleaner/telemetry/     (Docker configs)                 │     │
│  │  /var/run/context-cleaner/         (Process registry)               │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Service Lifecycle

### **1. Startup Sequence**

```
User runs: context-cleaner run
       │
       ▼
1. CLI Entry Point (main.py)
   ├─ Parse arguments
   ├─ Load configuration
   └─ Create ServiceOrchestrator
       │
       ▼
2. Service Orchestrator
   ├─ Check for existing supervisor
   ├─ Start supervisor (if not running)
   ├─ Register with process registry
   └─ Begin service startup
       │
       ▼
3. Supervisor (IPC)
   ├─ Listen on Unix socket
   ├─ Initialize service registry
   └─ Start watchdog monitoring
       │
       ▼
4. Docker Services
   ├─ Check Docker daemon status
   ├─ Start ClickHouse container
   ├─ Start OTEL collector container
   └─ Wait for health checks
       │
       ▼
5. Application Services
   ├─ Start JSONL processor
   ├─ Start bridge service
   └─ Start dashboard (Gunicorn)
       │
       ▼
6. Monitoring & Health
   ├─ Watchdog starts monitoring
   ├─ Health checks every 30s
   └─ Auto-restart on failures
       │
       ▼
7. Ready State
   ├─ Dashboard accessible
   ├─ Telemetry collecting
   └─ System healthy
```

### **2. Shutdown Sequence**

```
User runs: context-cleaner stop
       │
       ▼
1. CLI Entry Point
   ├─ Connect to supervisor (if available)
   ├─ Fallback to orchestrator if needed
   └─ Begin graceful shutdown
       │
       ▼
2. Graceful Service Shutdown
   ├─ Stop accepting new requests
   ├─ Wait for in-flight operations
   └─ Shutdown in reverse dependency order:
       │
       ├─ 1. Dashboard (web interface)
       ├─ 2. Bridge service
       ├─ 3. JSONL processor
       ├─ 4. OTEL collector
       ├─ 5. ClickHouse database
       └─ 6. Supervisor & watchdog
       │
       ▼
3. Cleanup & Registry
   ├─ Remove process registry entries
   ├─ Clean up PID files
   ├─ Close network ports
   └─ Log final status
```

## 🧩 Core Components

### **1. Service Orchestrator** (`services/service_orchestrator.py`)

**Purpose**: Central service lifecycle manager

**Responsibilities**:
- Start/stop/restart services in correct order
- Manage service dependencies
- Port conflict resolution
- Health monitoring coordination
- Process discovery and cleanup
- Fallback to legacy methods

**Key Features**:
- Async/await pattern for non-blocking operations
- Timeout handling for all operations
- Circuit breakers for expensive checks
- Process registry integration
- Streaming progress updates

### **2. Supervisor** (`services/service_supervisor.py`)

**Purpose**: Long-running IPC daemon for service coordination

**Responsibilities**:
- Inter-process communication (Unix sockets)
- Service state management
- Command routing to services
- Streaming shutdown progress
- Registry synchronization

**Key Features**:
- Unix socket communication
- JSON-based protocol
- Non-blocking event loop
- Graceful shutdown coordination
- Fallback when unavailable

### **3. Watchdog** (`services/service_watchdog.py`)

**Purpose**: Automatic health monitoring and recovery

**Responsibilities**:
- Periodic health checks (every 30s)
- Automatic service restart on failures
- Restart backoff strategy (3 attempts)
- Heartbeat monitoring
- Health status reporting

**Key Features**:
- Configurable check intervals
- Exponential backoff on restarts
- Maximum restart attempts
- Health check timeouts
- Status streaming to supervisor

### **4. Process Registry** (`services/process_registry.py`)

**Purpose**: Track all Context Cleaner processes

**Responsibilities**:
- Register running services
- Track PIDs and metadata
- Process discovery
- Stale entry cleanup
- Health status tracking

**Key Features**:
- SQLite-based storage
- Cross-platform support
- Atomic operations
- Query capabilities
- Automatic cleanup

### **5. Dashboard** (`dashboard/comprehensive_health_dashboard.py`)

**Purpose**: Web interface for monitoring and control

**Responsibilities**:
- Real-time metrics visualization
- Analytics and insights
- Service control interface
- Data explorer (SQL queries)
- System health monitoring

**Key Features**:
- Flask + Gunicorn stack
- WebSocket for real-time updates
- Chart.js visualizations
- Tabbed navigation
- API endpoints

### **6. JSONL Processor** (`services/jsonl_watcher.py`)

**Purpose**: Process Claude Code cache files

**Responsibilities**:
- Monitor ~/.claude/sessions/
- Parse JSONL conversation files
- Extract token metrics
- Store in ClickHouse
- Incremental processing

**Key Features**:
- File system watching
- Parallel processing
- Error recovery
- Deduplication
- Progress tracking

### **7. Bridge Service** (`bridges/`)

**Purpose**: Enhanced token analysis integration

**Responsibilities**:
- Connect to Anthropic API
- Accurate token counting
- Historical data backfill
- Real-time synchronization
- Data validation

**Key Features**:
- API key management
- Rate limiting
- Retry logic
- Progress checkpoints
- Error handling

## 🔐 Security & Privacy

### **Local-Only Processing**
- **No external data transmission** except optional Anthropic API for token counting
- All analytics stay on your machine
- File system permissions enforced
- Process isolation via user context

### **Data Protection**
- PID files with 0600 permissions
- Unix sockets with restricted access
- Process registry per-user isolation
- No network exposure except localhost dashboard

### **Resource Limits**
- Memory limits per service
- CPU usage monitoring
- Disk space checks
- Connection pooling

## ⚡ Performance Characteristics

### **Startup Time**
- Cold start: 5-10 seconds
- Warm start: 2-3 seconds (supervisor running)
- Docker services: 3-5 seconds
- Application services: 1-2 seconds

### **Resource Usage**
- Memory: ~200-300MB total
- CPU: <5% idle, <20% during analysis
- Disk: <100MB (excluding ClickHouse data)
- Network: Localhost only

### **Response Times**
- Dashboard page load: <500ms
- API calls: <100ms
- Health checks: <50ms
- Process registry queries: <10ms

---

**Next**: [Component Architecture](components.md) - Detailed breakdown of each component

*For fallback mechanisms, see [Fallback Mechanisms](fallback-mechanisms.md)*
