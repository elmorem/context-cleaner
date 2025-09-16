# Context Cleaner Infinite Restart Loop - Comprehensive Fix Plan

**Date**: September 16, 2025
**Status**: Ready for Implementation
**Priority**: Critical - System Stability

## 🔍 Root Cause Analysis

### Problem Summary
The Context Cleaner system experiences infinite restart loops where services continuously restart themselves, preventing stable operation. Through multi-agent analysis, we identified the root cause as a **WebSocket initialization failure cascade**.

### Failure Chain
1. **WebSocket Initialization Fails** → Frontend can't establish real-time connections
2. **UI Components Stuck in Loading State** → Despite APIs working perfectly and returning data
3. **Consistency Checker Detects Mixed States** → `api_working_ui_loading` instead of `consistent`
4. **Services Marked as Unhealthy** → Based on API/UI state mismatch
5. **Automatic Service Restarts Triggered** → Service orchestrator attempts to fix "unhealthy" services
6. **Infinite Restart Cycle** → System never reaches stable state

### Key Evidence
```
🚀 Context Cleaner running at: http://localhost:8110
WARNING: Service dashboard is unhealthy, triggering restart #1
💊 HEALTH_INTERNAL: ❌ Service NOT RUNNING - task_status: {'task_cancelled': True}
🔄 MONITOR_ISSUES: Found 15 critical API/UI consistency issues:
   /api/dashboard-metrics: both_failing
   /api/context-window-usage: api_working_ui_loading  ← APIs work but UI loading
   /api/content-search: api_working_ui_loading

WebSocket Errors:
simple_websocket.errors.ConnectionClosed: Connection closed: 1001
engineio/socketio errors causing connection drops
```

## 🎯 Multi-Agent Analysis Summary

### Agent 1: Codebase Architect
- **Finding**: Race conditions in async task lifecycle management
- **Issue**: Aggressive health check timeouts don't account for service startup periods
- **Impact**: Task cancellation issues in service orchestrator

### Agent 2: Senior Code Reviewer
- **Finding**: Race condition in async task supervision with improper exception handling
- **Issue**: Anti-patterns in health check reliability and timing
- **Impact**: Restart loops triggered by false positive health failures

### Agent 3: Frontend TypeScript/React Expert
- **Finding**: **ROOT CAUSE IDENTIFIED** - WebSocket initialization failure
- **Issue**: APIs work perfectly but frontend can't receive real-time updates
- **Impact**: Widgets remain in loading states indefinitely, triggering consistency failures

### Agent 4: General Purpose Investigator
- **Finding**: Missing fallback endpoints `/api/health/detailed` and `/api/realtime/events`
- **Issue**: WebSocket fallback mechanism targets non-existent endpoints
- **Impact**: No graceful degradation when real-time connections fail

## 🚀 Comprehensive Solution Plan

### PHASE 1: IMMEDIATE STABILIZATION (Stop Restart Loops)
**Timeline**: 1-2 hours
**Goal**: Break the infinite restart cycle

#### 1.1 Fix WebSocket Initialization
**Files to Modify**:
- `/src/context_cleaner/dashboard/` (WebSocket client code)
- Dashboard HTML templates with SocketIO initialization

**Changes**:
```javascript
// Add proper WebSocket connection with fallback
const socket = io({
  transports: ['websocket', 'polling'],
  timeout: 20000,
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000
});

// Add connection event handlers
socket.on('connect', () => {
  console.log('🔗 WebSocket connected successfully');
  updateConnectionStatus('connected');
});

socket.on('disconnect', (reason) => {
  console.warn('🔗 WebSocket disconnected:', reason);
  updateConnectionStatus('disconnected');
  // Trigger fallback to API polling
});
```

#### 1.2 Add Missing API Endpoints
**Files to Create/Modify**:
- Dashboard Flask routes for missing endpoints

**Required Endpoints**:
```python
@app.route('/api/health/detailed')
def health_detailed():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": get_service_health_status(),
        "websocket_available": True
    })

@app.route('/api/realtime/events')
def realtime_events():
    return jsonify({
        "events": get_recent_events(),
        "last_update": datetime.utcnow().isoformat(),
        "polling_interval": 5000
    })
```

#### 1.3 Reduce Consistency Checker Sensitivity
**File**: `/src/context_cleaner/services/api_ui_consistency_checker.py`

**Changes**:
```python
# Increase failure tolerance
self.max_consecutive_failures = 10  # Was 3
self.startup_grace_period = 60      # New: 60 second grace period
self.check_interval = 45            # Was 30, give more time

# Add startup grace period check
def is_monitoring_healthy(self) -> bool:
    # Don't fail during startup grace period
    if hasattr(self, 'start_time'):
        if time.time() - self.start_time < self.startup_grace_period:
            return True

    # Be more tolerant of api_working_ui_loading states
    if self.consecutive_failures >= self.max_consecutive_failures:
        # Check if issues are just UI loading (not critical)
        recent_issues = self.get_recent_issues()
        if all('ui_loading' in issue.status for issue in recent_issues):
            self.logger.info("🔄 UI loading states detected, not marking as unhealthy")
            return True  # Don't restart for UI loading issues
```

### PHASE 2: STRUCTURAL IMPROVEMENTS (Prevent Recurrence)
**Timeline**: 2-4 hours
**Goal**: Fix underlying race conditions and improve reliability

#### 2.1 Fix Async Task Lifecycle Management
**File**: `/src/context_cleaner/services/service_orchestrator.py`

**Changes**:
```python
async def start_consistency_checker(self, dashboard_port: int) -> bool:
    try:
        # Add proper task lifecycle management
        self.consistency_checker = APIUIConsistencyChecker(
            config=self.config,
            dashboard_host="127.0.0.1",
            dashboard_port=dashboard_port
        )

        # Create task with proper exception handling
        async def start_with_lifecycle_management():
            try:
                await self.consistency_checker.start_monitoring()
            except asyncio.CancelledError:
                self.logger.info("✅ Consistency checker cancelled gracefully")
                raise  # Re-raise to properly handle cancellation
            except Exception as e:
                self.logger.error(f"❌ Consistency checker failed: {e}")
                # Don't mark as failed immediately - allow restart

        # Store task reference for proper cleanup
        self.consistency_checker_task = asyncio.create_task(
            start_with_lifecycle_management()
        )

        # Add proper task completion callback
        def on_task_done(task):
            if task.cancelled():
                self.logger.info("Consistency checker task cancelled")
                return

            try:
                exception = task.exception()
                if exception:
                    self.logger.error(f"Consistency checker task failed: {exception}")
                    # Schedule restart after delay, not immediately
                    asyncio.create_task(self._delayed_restart_consistency_checker())
            except:
                pass  # Task was cancelled

        self.consistency_checker_task.add_done_callback(on_task_done)

        # Wait a moment to ensure task is running before returning success
        await asyncio.sleep(1)
        return True

    except Exception as e:
        self.logger.error(f"Failed to start consistency checker: {e}")
        return False

async def _delayed_restart_consistency_checker(self):
    """Restart consistency checker after a delay to avoid rapid restart loops"""
    await asyncio.sleep(30)  # Wait 30 seconds before restart
    # Implement restart logic here
```

#### 2.2 Improve Health Check Reliability
**File**: `/src/context_cleaner/services/service_orchestrator.py`

**Changes**:
```python
def _check_consistency_checker_health(self) -> bool:
    """Enhanced health check with better timing and logic"""

    if not self.consistency_checker:
        return False

    # Don't check health immediately after startup
    if hasattr(self, 'consistency_checker_start_time'):
        startup_age = time.time() - self.consistency_checker_start_time
        if startup_age < 60:  # Grace period
            self.logger.debug(f"💊 Consistency checker in startup grace period ({startup_age:.1f}s)")
            return True

    # Check if monitoring is healthy (with tolerance for temporary issues)
    if hasattr(self.consistency_checker, 'is_monitoring_healthy'):
        is_healthy = self.consistency_checker.is_monitoring_healthy()

        # Add hysteresis - don't restart on single health check failure
        if not is_healthy:
            if not hasattr(self, '_health_failure_count'):
                self._health_failure_count = 0
            self._health_failure_count += 1

            # Only restart after multiple consecutive failures
            if self._health_failure_count >= 3:
                self.logger.warning(f"💊 Consistency checker unhealthy after {self._health_failure_count} checks")
                return False
            else:
                self.logger.info(f"💊 Temporary health check failure {self._health_failure_count}/3")
                return True  # Give it another chance
        else:
            # Reset failure count on success
            self._health_failure_count = 0

        return is_healthy

    return True  # Default to healthy if we can't check
```

### PHASE 3: ENHANCED MONITORING & LOGGING (Visibility)
**Timeline**: 1-2 hours
**Goal**: Add comprehensive visibility to prevent future issues

#### 3.1 Frontend API Call Logging
**File**: Dashboard JavaScript/TypeScript files

**Changes**:
```javascript
// Add comprehensive API call logging
class DashboardAPILogger {
    constructor() {
        this.requestLog = [];
        this.maxLogEntries = 1000;
    }

    logAPICall(endpoint, method = 'GET', startTime = Date.now()) {
        const entry = {
            timestamp: new Date().toISOString(),
            endpoint,
            method,
            startTime,
            tabContext: this.getCurrentTab(),
            userAction: this.getLastUserAction()
        };

        console.log(`🔗 API Call: ${method} ${endpoint}`, entry);
        this.requestLog.push(entry);

        // Keep log size manageable
        if (this.requestLog.length > this.maxLogEntries) {
            this.requestLog.shift();
        }

        return entry;
    }

    logAPIResponse(entry, response, error = null) {
        const duration = Date.now() - entry.startTime;
        entry.duration = duration;
        entry.status = response?.status || 'error';
        entry.error = error?.message;
        entry.dataReceived = response?.data ? Object.keys(response.data).length : 0;

        console.log(`📊 API Response: ${entry.endpoint} - ${entry.status} (${duration}ms)`, entry);

        // Check for loading state issues
        if (entry.status === 200 && this.isUIStillLoading(entry.endpoint)) {
            console.warn(`⚠️ API Success but UI Loading: ${entry.endpoint}`);
            this.reportUILoadingMismatch(entry);
        }
    }

    getCurrentTab() {
        // Implement tab detection logic
        return document.querySelector('.active-tab')?.textContent || 'unknown';
    }

    getLastUserAction() {
        // Track user interactions
        return this.lastUserAction || 'page_load';
    }

    isUIStillLoading(endpoint) {
        // Check if UI components related to this endpoint are still loading
        const loadingElements = document.querySelectorAll('.loading-state');
        return loadingElements.length > 0;
    }

    reportUILoadingMismatch(entry) {
        // Send alert about API/UI state mismatch
        fetch('/api/internal/ui-loading-mismatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                endpoint: entry.endpoint,
                timestamp: entry.timestamp,
                tab: entry.tabContext,
                duration: entry.duration
            })
        }).catch(console.error);
    }
}

// Initialize logger
const apiLogger = new DashboardAPILogger();

// Wrap fetch calls
const originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
    const entry = apiLogger.logAPICall(url, options.method);

    try {
        const response = await originalFetch(url, options);
        const data = await response.json();
        apiLogger.logAPIResponse(entry, { status: response.status, data });
        return new Response(JSON.stringify(data), response);
    } catch (error) {
        apiLogger.logAPIResponse(entry, null, error);
        throw error;
    }
};
```

#### 3.2 WebSocket Connection Monitoring
**File**: Dashboard WebSocket client code

**Changes**:
```javascript
class WebSocketConnectionMonitor {
    constructor(socket) {
        this.socket = socket;
        this.connectionHistory = [];
        this.setupEventLogging();
    }

    setupEventLogging() {
        this.socket.on('connect', () => {
            const event = {
                type: 'connect',
                timestamp: new Date().toISOString(),
                transport: this.socket.io.engine.transport.name,
                sessionId: this.socket.id
            };
            console.log('🔗 WebSocket Connected:', event);
            this.connectionHistory.push(event);
            this.updateConnectionStatus('connected');
        });

        this.socket.on('disconnect', (reason) => {
            const event = {
                type: 'disconnect',
                timestamp: new Date().toISOString(),
                reason,
                sessionId: this.socket.id,
                duration: this.getConnectionDuration()
            };
            console.warn('🔗 WebSocket Disconnected:', event);
            this.connectionHistory.push(event);
            this.updateConnectionStatus('disconnected');

            // Report connection issues
            if (reason !== 'io client disconnect') {
                this.reportConnectionIssue(event);
            }
        });

        this.socket.on('connect_error', (error) => {
            const event = {
                type: 'connect_error',
                timestamp: new Date().toISOString(),
                error: error.message,
                transport: this.socket.io.engine?.transport?.name || 'unknown'
            };
            console.error('🔗 WebSocket Connection Error:', event);
            this.connectionHistory.push(event);
            this.updateConnectionStatus('error');
        });
    }

    updateConnectionStatus(status) {
        // Update UI connection indicator
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.className = `connection-status ${status}`;
            indicator.textContent = status.toUpperCase();
        }

        // Enable/disable real-time features based on connection
        this.toggleRealtimeFeatures(status === 'connected');
    }

    toggleRealtimeFeatures(enabled) {
        const realtimeElements = document.querySelectorAll('[data-realtime]');
        realtimeElements.forEach(el => {
            if (enabled) {
                el.classList.remove('realtime-disabled');
            } else {
                el.classList.add('realtime-disabled');
                // Fall back to API polling for these elements
                this.enableAPIPollingFallback(el);
            }
        });
    }

    enableAPIPollingFallback(element) {
        const endpoint = element.dataset.endpoint;
        if (endpoint && !element.dataset.pollingActive) {
            element.dataset.pollingActive = 'true';
            console.log(`🔄 Enabling API polling fallback for ${endpoint}`);

            // Start polling this endpoint
            const pollInterval = setInterval(async () => {
                if (this.socket.connected) {
                    // WebSocket reconnected, stop polling
                    clearInterval(pollInterval);
                    element.dataset.pollingActive = 'false';
                    return;
                }

                try {
                    const response = await fetch(endpoint);
                    const data = await response.json();
                    // Update element with fresh data
                    this.updateElementWithData(element, data);
                } catch (error) {
                    console.error(`Polling fallback failed for ${endpoint}:`, error);
                }
            }, 5000); // Poll every 5 seconds
        }
    }
}
```

#### 3.3 Backend Service Health Logging
**File**: `/src/context_cleaner/services/service_orchestrator.py`

**Changes**:
```python
class ServiceHealthLogger:
    def __init__(self, logger):
        self.logger = logger
        self.health_history = []
        self.service_metrics = {}

    def log_health_check(self, service_name: str, health_result: bool, details: dict = None):
        """Log detailed health check results"""
        health_event = {
            'timestamp': datetime.utcnow().isoformat(),
            'service': service_name,
            'healthy': health_result,
            'details': details or {},
            'consecutive_failures': self.get_consecutive_failures(service_name)
        }

        self.health_history.append(health_event)

        # Keep last 1000 events
        if len(self.health_history) > 1000:
            self.health_history.pop(0)

        # Log with appropriate level
        if health_result:
            self.logger.debug(f"💚 Health Check PASS: {service_name}", extra=health_event)
        else:
            self.logger.warning(f"💔 Health Check FAIL: {service_name}", extra=health_event)

        # Track metrics
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = {
                'total_checks': 0,
                'failed_checks': 0,
                'last_failure': None,
                'uptime_start': datetime.utcnow()
            }

        metrics = self.service_metrics[service_name]
        metrics['total_checks'] += 1

        if not health_result:
            metrics['failed_checks'] += 1
            metrics['last_failure'] = datetime.utcnow()

        # Calculate failure rate
        failure_rate = metrics['failed_checks'] / metrics['total_checks']

        if failure_rate > 0.1:  # More than 10% failure rate
            self.logger.error(f"🚨 High failure rate for {service_name}: {failure_rate:.1%}")
```

### PHASE 4: TESTING & VALIDATION (Ensure Solution Works)
**Timeline**: 1 hour
**Goal**: Verify all fixes resolve the restart loops

#### 4.1 Restart Loop Test
1. **Start Services**: `context-cleaner run`
2. **Monitor for 10 minutes**: Ensure no restart warnings
3. **WebSocket Test**: Verify dashboard real-time updates work
4. **Load Test**: Switch between dashboard tabs, monitor API calls

#### 4.2 Health Check Validation
1. **Consistency Checker**: Should remain healthy for >1 hour
2. **Mixed States**: Should see `consistent` instead of `api_working_ui_loading`
3. **Service Orchestrator**: No "unhealthy service" warnings

#### 4.3 Logging Verification
1. **Frontend Logs**: API calls properly logged in browser console
2. **WebSocket Events**: Connection status changes logged
3. **Backend Health**: Service health events in application logs

## 📊 Success Metrics

### Immediate Success (Phase 1)
- [ ] No service restart warnings for >30 minutes
- [ ] WebSocket connections establish successfully
- [ ] Dashboard loads without indefinite loading states
- [ ] APIs return 200 status with data
- [ ] UI displays fresh data within 30 seconds of service start

### Long-term Success (Phases 2-4)
- [ ] Services remain stable for >24 hours without restarts
- [ ] WebSocket connection success rate >95%
- [ ] API response times <2 seconds
- [ ] Zero false positive health check failures
- [ ] Complete visibility into API/UI data flow

## 🔧 Implementation Notes

### Critical Dependencies
1. **WebSocket Library**: Ensure Flask-SocketIO version compatibility
2. **Port Availability**: Verify dashboard port (8110) is consistently available
3. **Async Task Management**: Python asyncio version and proper exception handling

### Risk Mitigation
1. **Gradual Rollout**: Implement Phase 1 fixes first, validate before proceeding
2. **Rollback Plan**: Keep current service orchestrator logic as backup
3. **Monitoring**: Continuous observation during first 24 hours post-implementation

### Testing Strategy
1. **Unit Tests**: Add tests for new health check logic
2. **Integration Tests**: WebSocket connection and fallback scenarios
3. **Load Tests**: Multiple concurrent dashboard users
4. **Chaos Tests**: Intentional service failures to verify recovery

## 📝 Implementation Checklist

### Phase 1: Immediate Stabilization
- [ ] Add missing API endpoints (`/api/health/detailed`, `/api/realtime/events`)
- [ ] Fix WebSocket initialization with proper fallback
- [ ] Increase consistency checker failure tolerance (3→10)
- [ ] Add startup grace period (60 seconds)
- [ ] Test restart loop elimination

### Phase 2: Structural Improvements
- [ ] Fix async task lifecycle management in service orchestrator
- [ ] Improve health check reliability with hysteresis
- [ ] Add delayed restart logic to prevent rapid cycling
- [ ] Implement proper task cancellation handling
- [ ] Test service stability over extended periods

### Phase 3: Enhanced Monitoring
- [ ] Add comprehensive frontend API call logging
- [ ] Implement WebSocket connection monitoring
- [ ] Create backend service health logging system
- [ ] Add UI loading state detection and reporting
- [ ] Set up alerting for abnormal patterns

### Phase 4: Validation
- [ ] Execute restart loop test (10+ minutes stable)
- [ ] Validate health check accuracy
- [ ] Verify logging completeness
- [ ] Performance testing under load
- [ ] Document operational procedures

## 🎯 Next Steps

1. **Begin Phase 1 Implementation**: Start with WebSocket fixes and missing endpoints
2. **Validate Each Phase**: Don't proceed until current phase is proven stable
3. **Monitor Continuously**: Watch for new patterns or edge cases
4. **Document Lessons Learned**: Update this plan based on implementation experience

---

**Document Version**: 1.0
**Last Updated**: September 16, 2025
**Implementation Status**: Ready to Begin
**Estimated Total Time**: 6-8 hours spread across phases