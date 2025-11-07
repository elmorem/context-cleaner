# Context Cleaner Architecture

> **Comprehensive architecture documentation for Context Cleaner v0.3.0**

## 📖 Documentation Index

### **Core Architecture**
- [System Overview](system-overview.md) - High-level architecture and design principles
- [Component Architecture](components.md) - Detailed component breakdown and responsibilities
- [Data Flow](data-flow.md) - How data moves through the system
- [Service Orchestration](orchestration.md) - Service lifecycle and coordination

### **Key Systems**
- [Supervisor & IPC](supervisor-ipc.md) - Process supervision and inter-process communication
- [Telemetry System](telemetry.md) - OpenTelemetry integration and data collection
- [Dashboard System](dashboard.md) - Web interface and API architecture
- [Database Layer](database.md) - ClickHouse integration and schema

### **Resilience & Safety**
- [Fallback Mechanisms](fallback-mechanisms.md) - Graceful degradation and error handling
- [Circuit Breakers](circuit-breakers.md) - Protection against cascading failures
- [Health Monitoring](health-monitoring.md) - Watchdog and health check systems

### **Integration Points**
- [CLI Integration](cli-integration.md) - Command-line interface architecture
- [File System Integration](filesystem.md) - JSONL processing and cache management
- [Docker Integration](docker.md) - Container management and lifecycle

## 🏗️ Quick Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONTEXT CLEANER v0.3.0                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │     CLI      │  │  Dashboard   │  │   Telemetry  │         │
│  │   Interface  │  │    (Web)     │  │  Collection  │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                  │
│         └─────────┬────────┴──────────────────┘                 │
│                   │                                              │
│         ┌─────────▼─────────┐                                   │
│         │   ORCHESTRATOR    │◄──────────┐                       │
│         │ (Service Manager) │            │                       │
│         └────────┬──────────┘            │                       │
│                  │              ┌────────▼────────┐              │
│         ┌────────▼────────┐    │   SUPERVISOR    │              │
│         │   Services      │    │  (IPC/Registry) │              │
│         │  ├─ Docker      │    └────────┬────────┘              │
│         │  ├─ JSONL       │             │                        │
│         │  ├─ Bridge      │    ┌────────▼────────┐              │
│         │  └─ Dashboard   │    │    WATCHDOG     │              │
│         └────────┬────────┘    │ (Auto-restart)  │              │
│                  │              └─────────────────┘              │
│         ┌────────▼────────┐                                      │
│         │   ClickHouse    │◄──── JSONL Files                    │
│         │   (Database)    │                                      │
│         └─────────────────┘                                      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## 🎯 Key Design Principles

### **1. Resilience First**
- Multiple fallback layers for every critical operation
- Graceful degradation when components fail
- Circuit breakers prevent cascading failures
- Health monitoring with automatic recovery

### **2. Local-Only Processing**
- All data stays on your machine
- No external network requests
- Privacy-first architecture
- Complete user control

### **3. Performance Safety**
- <10ms overhead for hooks
- <100ms for dashboard operations
- Circuit breakers for expensive operations
- Resource limits and monitoring

### **4. Modular Design**
- Independent components with clear interfaces
- Loose coupling between services
- Easy to test and maintain
- Extensible architecture

### **5. Developer Experience**
- Clear error messages
- Comprehensive logging
- Easy debugging
- Well-documented APIs

## 🚀 Getting Started

- **New to the architecture?** Start with [System Overview](system-overview.md)
- **Want to understand services?** Read [Component Architecture](components.md)
- **Need to debug issues?** Check [Fallback Mechanisms](fallback-mechanisms.md)
- **Building integrations?** See [CLI Integration](cli-integration.md)

## 📊 System Statistics

- **Components**: 25+ independent services
- **Fallback Layers**: 3-4 per critical operation
- **Health Checks**: 15+ monitoring points
- **API Endpoints**: 30+ dashboard routes
- **Docker Services**: 2 (ClickHouse, OpenTelemetry)
- **Background Services**: 5+ (JSONL, Bridge, Watchdog, etc.)

---

**Context Cleaner Architecture Documentation v0.3.0**

*Last Updated: January 2025*
