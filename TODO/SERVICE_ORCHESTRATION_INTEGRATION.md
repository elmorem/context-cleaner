# Service Orchestration Integration Plan

## Executive Summary

**CRITICAL ISSUE**: The Context Cleaner service orchestration system has fundamental integration gaps that prevent proper service lifecycle management. The `stop` command failed to shut down 40+ background processes, requiring manual force termination.

**ROOT CAUSE**: Services can be started through multiple pathways that bypass the service orchestration system, creating "orphaned" processes that cannot be managed centrally.

**OBJECTIVE**: Implement systematic service orchestration integration to ensure ALL Context Cleaner processes are managed through a single, reliable lifecycle management system.

## Current Architecture Problems

### 1. Multiple Service Startup Methods
- **Individual CLI commands**: `dashboard`, `bridge sync` bypass orchestration
- **Direct Python execution**: `python -c` scripts bypass CLI entirely
- **Orchestration bypass flags**: `--no-orchestration` defeats the system
- **Manual background processes**: Services started without registration

### 2. Service Discovery Gaps
- **No process registry**: Orchestrator unaware of manually started services
- **No process tracking**: Cannot discover existing application processes
- **No PID management**: No systematic process ID tracking
- **No port conflict detection**: Multiple services bind to same ports

### 3. Shutdown Mechanism Failures
- **Limited scope**: Stop command only affects orchestrated services
- **No process discovery**: Cannot find manually started processes
- **No force cleanup**: No fallback termination mechanisms
- **Inconsistent behavior**: Partial shutdowns leave system in undefined state

## Detailed Integration Plan

### Phase 1: Centralized Process Registry

#### 1.1 Process Registry Database
**Location**: `src/context_cleaner/services/process_registry.py`

```python
@dataclass
class ProcessEntry:
    pid: int
    command_line: str
    service_type: str  # 'dashboard', 'bridge_sync', 'telemetry'
    start_time: datetime
    port: Optional[int]
    status: str  # 'running', 'stopping', 'stopped'
    parent_orchestrator: Optional[str]
```

**Features**:
- SQLite database for persistence: `~/.context_cleaner/processes.db`
- Atomic operations with file locking
- Automatic cleanup of stale entries
- Cross-session process tracking

#### 1.2 Registry Operations
- `register_process(entry: ProcessEntry)`: Add new process
- `unregister_process(pid: int)`: Remove process entry
- `discover_processes()`: Find all Context Cleaner processes by name/command
- `get_all_processes()`: List all registered processes
- `cleanup_stale_entries()`: Remove entries for dead processes

#### 1.3 Integration Points
- **Service startup**: Every service must register on start
- **Periodic health checks**: Verify process still running
- **Shutdown hooks**: Unregister on clean exit
- **Discovery on startup**: Find existing processes and register them

### Phase 2: Enhanced Service Orchestration

#### 2.1 Service Manager Redesign
**Location**: `src/context_cleaner/services/service_orchestrator.py`

**New Capabilities**:
```python
class EnhancedServiceOrchestrator:
    def discover_existing_services(self) -> List[ProcessEntry]
    def register_external_services(self) -> int
    def force_cleanup_all_services(self) -> bool
    def validate_service_configuration(self) -> List[str]
    def get_comprehensive_status(self) -> ServiceStatus
```

#### 2.2 Service Discovery Engine
- **Process name matching**: Find `context_cleaner` processes
- **Port scanning**: Detect services by bound ports (8080, 8888, etc.)
- **Command line analysis**: Identify service types from args
- **Parent process tracking**: Map child processes to orchestrators

#### 2.3 Health Monitoring Enhancement
- **Process validation**: Verify PIDs still exist
- **Port availability checks**: Ensure services are responsive
- **Resource monitoring**: Track CPU/memory usage
- **Error detection**: Monitor service logs for issues

### Phase 3: Single Entry Point Enforcement

#### 3.1 CLI Command Restrictions
**Deprecated Commands** (Phase out):
- `python -m src.context_cleaner.cli.main dashboard` → Redirect to `run`
- `python -m src.context_cleaner.cli.main bridge sync` → Integrate into `run`
- Direct Python dashboard scripts → Remove entirely

**Migration Strategy**:
1. Add deprecation warnings to standalone commands
2. Redirect standalone commands to orchestrated versions
3. Remove standalone command support entirely

#### 3.2 Mandatory Orchestration Integration
**Remove Bypass Options**:
- `--no-orchestration` flag → Remove entirely
- Direct service imports → Add orchestration checks
- Background script execution → Require registration

#### 3.3 Unified Service Startup
**Single Command**: `python -m src.context_cleaner.cli run`
- Starts ALL required services through orchestration
- Registers all processes in central registry
- Provides unified configuration
- Handles service dependencies

### Phase 4: Robust Shutdown Implementation

#### 4.1 Enhanced Stop Command
**Location**: `src/context_cleaner/cli/commands/stop.py`

**New Shutdown Process**:
1. **Graceful shutdown**: Send SIGTERM to registered processes
2. **Process discovery**: Find any unregistered Context Cleaner processes
3. **Force termination**: SIGKILL processes that don't respond
4. **Registry cleanup**: Remove all process entries
5. **Verification**: Confirm no processes remain

#### 4.2 Shutdown Verification
```python
def verify_complete_shutdown() -> ShutdownStatus:
    """Verify all Context Cleaner processes are terminated"""
    remaining = discover_context_cleaner_processes()
    if remaining:
        return ShutdownStatus.INCOMPLETE
    return ShutdownStatus.COMPLETE
```

#### 4.3 Container Management Integration
- **Context Cleaner containers**: Stop application-specific containers
- **Docker daemon preservation**: Leave system Docker running
- **Container tagging**: Identify Context Cleaner containers
- **Cleanup verification**: Ensure containers fully stopped

### Phase 5: Service Dependencies and Coordination

#### 5.1 Service Dependency Graph
```python
SERVICE_DEPENDENCIES = {
    'clickhouse': [],  # Base dependency
    'telemetry_collector': ['clickhouse'],
    'bridge_sync': ['clickhouse', 'telemetry_collector'],
    'dashboard': ['clickhouse', 'telemetry_collector']
}
```

#### 5.2 Coordinated Startup
- **Dependency resolution**: Start services in correct order
- **Health verification**: Ensure dependencies ready before dependents
- **Failure handling**: Cascade failure detection and recovery
- **Timeout management**: Prevent indefinite startup delays

#### 5.3 Service Communication
- **Status broadcasting**: Services report health to orchestrator
- **Configuration sharing**: Centralized config distribution
- **Event coordination**: Service lifecycle event notifications

## Implementation Checks and Validations

### Check 1: Process Registry Integrity
```bash
# Verify registry tracks all processes
python -m src.context_cleaner.cli run &
sleep 5
python -m src.context_cleaner.cli debug list-processes
# Should show: dashboard, bridge_sync, telemetry_collector
```

### Check 2: Discovery Engine Accuracy  
```bash
# Start services manually, verify discovery
python -m src.context_cleaner.cli.main dashboard --port 9999 &
python -m src.context_cleaner.cli debug discover-services
# Should find the manual dashboard process
```

### Check 3: Complete Shutdown Verification
```bash
# Start services, ensure complete shutdown
python -m src.context_cleaner.cli run &
sleep 10
python -m src.context_cleaner.cli stop
ps aux | grep context_cleaner | grep -v grep
# Should show: NO processes (exit code 1)
```

### Check 4: Service Dependency Validation
```bash
# Verify services start in correct order
python -m src.context_cleaner.cli run --verbose
# Should show: clickhouse → telemetry → bridge/dashboard
```

## Comprehensive Test Suite

### Unit Tests
- **Process Registry**: CRUD operations, concurrency, persistence
- **Service Discovery**: Process matching, port scanning, command parsing
- **Orchestrator**: Startup/shutdown sequences, health monitoring
- **CLI Integration**: Command routing, parameter validation

### Integration Tests  
- **Multi-service lifecycle**: Start → Health → Stop → Verify
- **Failure recovery**: Service crashes, dependency failures
- **Concurrency**: Multiple orchestrators, race conditions
- **Cross-session**: Registry persistence across restarts

### System Tests
- **Full stack validation**: Complete application lifecycle
- **Performance impact**: Orchestration overhead measurement
- **Resource cleanup**: Memory leaks, file descriptor limits
- **Error propagation**: Failure modes and error reporting

### Load Tests
- **Service scaling**: Multiple dashboard instances
- **Registry performance**: High-frequency process registration
- **Shutdown timing**: Large numbers of processes

## Monitoring and Observability

### Service Health Dashboard
- **Process status**: Real-time service health visualization
- **Resource usage**: CPU, memory, network per service
- **Error rates**: Service failure frequency and patterns
- **Performance metrics**: Startup/shutdown timing

### Alerting System
- **Service failures**: Immediate notification of service crashes
- **Resource limits**: Warnings for high resource usage
- **Orchestration errors**: Registry corruption, discovery failures
- **Cleanup issues**: Processes that fail to terminate

### Logging Integration
- **Structured logging**: JSON format with service correlation IDs
- **Log aggregation**: Centralized logging for all services
- **Debug tracing**: Request tracing across service boundaries
- **Audit trail**: Service lifecycle event logging

## Migration Strategy

### Phase 1: Registry Implementation (Week 1)
- Implement process registry database
- Add discovery engine
- Create debug commands for validation

### Phase 2: Orchestrator Enhancement (Week 2)  
- Integrate registry with orchestrator
- Add service discovery to startup
- Implement enhanced health monitoring

### Phase 3: CLI Consolidation (Week 3)
- Add deprecation warnings to standalone commands
- Redirect commands to orchestrated versions
- Update documentation

### Phase 4: Shutdown Robustness (Week 4)
- Implement enhanced stop command
- Add force cleanup mechanisms
- Create shutdown verification

### Phase 5: Testing and Validation (Week 5)
- Comprehensive test suite implementation
- Performance benchmarking
- Documentation updates

## Success Criteria

### Functional Requirements
- ✅ **Single startup method**: Only `run` command starts services
- ✅ **Complete shutdown**: `stop` command terminates ALL processes
- ✅ **Process discovery**: Find and register existing services
- ✅ **Health monitoring**: Detect and restart failed services
- ✅ **Dependency management**: Services start in correct order

### Performance Requirements
- ✅ **Startup time**: < 30 seconds for full service stack
- ✅ **Shutdown time**: < 10 seconds for graceful termination
- ✅ **Registry overhead**: < 1% CPU impact
- ✅ **Memory footprint**: < 50MB additional memory usage

### Reliability Requirements
- ✅ **Zero orphaned processes**: No processes survive stop command
- ✅ **Cross-session persistence**: Registry survives application restarts
- ✅ **Error recovery**: Automatic restart of failed services
- ✅ **Graceful degradation**: Partial service failures don't crash system

## Risk Assessment and Mitigation

### High Risk: Registry Corruption
- **Mitigation**: SQLite WAL mode, backup/restore mechanisms
- **Detection**: Registry validation on startup
- **Recovery**: Automatic registry rebuild from process discovery

### Medium Risk: Service Discovery Failures
- **Mitigation**: Multiple discovery methods (PID, port, name)
- **Detection**: Cross-validation of discovery results  
- **Recovery**: Manual process registration override

### Low Risk: Performance Degradation
- **Mitigation**: Async operations, caching, lazy loading
- **Detection**: Performance monitoring and alerting
- **Recovery**: Registry optimization, cleanup procedures

## Conclusion

This comprehensive service orchestration integration plan addresses all identified gaps in the Context Cleaner service management system. Implementation will ensure reliable, centralized control of all application processes with robust startup, monitoring, and shutdown capabilities.

The plan prioritizes backward compatibility during migration while establishing a foundation for scalable service management. Success will be measured by zero orphaned processes, reliable service lifecycle management, and comprehensive observability of all system components.