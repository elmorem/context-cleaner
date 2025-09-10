# Dashboard Endpoints Mapping

## Complete Dashboard Tab Structure with API Endpoints

### 📊 **1. OVERVIEW Tab** (`#overview`)

**Widgets:**
- **Total Tokens Analyzed** → `/api/dashboard-metrics` (field: `total_tokens`)
- **Sessions Analyzed** → `/api/dashboard-metrics` (field: `total_sessions`) 
- **Orchestration Success Rate** → `/api/dashboard-metrics` (field: `success_rate`)
- **Active Agents** → `/api/dashboard-metrics` (field: `active_agents`)
- **Context Window Usage Table** → `/api/context-window-usage`

**JavaScript Functions:** `loadOverviewMetrics()`

---

### 💬 **2. CONVERSATIONS Tab** (`#conversations`)

**Widgets:**
- **Conversation Timeline** → `/api/conversation-analytics` 
- **Conversation Analytics** → `/api/conversation-analytics`

**JavaScript Functions:** `loadConversationAnalytics()`, `loadConversationData()`

---

### 📈 **3. TELEMETRY Tab** (`#telemetry`)

**6 Primary Widgets:**
1. **API Error Monitor** (`#error-monitor-widget`) → `/api/telemetry-widget/code-pattern-analysis`
2. **Cost Burn Rate Tracker** (`#cost-tracker-widget`) → `/api/telemetry-widget/conversation-timeline`
3. **Timeout Risk Assessment** (`#timeout-risk-widget`) → `/api/telemetry-widget/content-search-widget`
4. **Tool Usage Optimizer** (`#tool-optimizer-widget`) → `/api/telemetry/tool-analytics`
5. **Model Efficiency Tracker** (`#model-efficiency-widget`) → `/api/telemetry/model-analytics`
6. **Context Rot Meter** (`#context-rot-meter-widget`) → `/api/telemetry-widget/context-rot-meter`

**Additional Widgets:**
- **Error Details** → `/api/telemetry/error-details?hours=24`

**JavaScript Functions:** `loadTelemetryWidgets()`, `loadTelemetryData()`

---

### 🤖 **4. ORCHESTRATION Tab** (`#orchestration`)

**3 Primary Widgets:**
1. **Orchestration System Status** (`#orchestration-status-widget`) → `/api/dashboard-metrics`
2. **Agent Utilization Monitor** (`#agent-utilization-widget`) → `/api/dashboard-metrics`
3. **ML Workflow Performance** (`#workflow-performance-widget`) → `/api/dashboard-metrics`

**JavaScript Functions:** `loadOrchestrationWidgets()`

---

### 🔍 **5. ANALYTICS Tab** (`#analytics`)

**High Priority Analytics Widgets:**
- **Conversation Timeline** → `/api/telemetry-widget/conversation-timeline`
- **Code Pattern Analysis** → `/api/telemetry-widget/code-pattern-analysis`  
- **Content Search Interface** → `/api/telemetry-widget/content-search-widget`
- **Context Health Metrics** → `/api/analytics/context-health`
- **Performance Trends** → `/api/analytics/performance-trends`

**JavaScript Functions:** `loadAnalyticsWidgets()`

---

### ⚡ **6. PERFORMANCE Tab** (`#performance`)

**Widgets:**
- **Context Health Widget** (`#context-health-widget`) → `/api/analytics/context-health`
- **Performance Trends** → `/api/analytics/performance-trends`
- **JSONL Processing Status** → `/api/jsonl-processing-status`

**JavaScript Functions:** `loadPerformanceWidgets()`

---

### 🔎 **7. DATA EXPLORER Tab** (`#data-explorer`)

**Widgets:**
- **SQL Query Interface** → `/api/data-explorer/query` (POST method)
- **Content Search** → `/api/content-search` (POST method)
- **Code Patterns** → `/api/code-patterns-analytics`

**JavaScript Functions:** `loadDataExplorerWidgets()`

---

## **API Endpoints Summary**

**Working Endpoints (15 total tested):**
1. `/api/dashboard-metrics` ✅
2. `/api/context-window-usage` ✅
3. `/api/conversation-analytics` ✅
4. `/api/code-patterns-analytics` ✅
5. `/api/content-search` ✅
6. `/api/analytics/context-health` ✅
7. `/api/analytics/performance-trends` ✅
8. `/api/data-explorer/query` ✅
9. `/api/jsonl-processing-status` ✅
10. `/api/telemetry-widget/code-pattern-analysis` ✅
11. `/api/telemetry-widget/content-search-widget` ✅
12. `/api/telemetry-widget/conversation-timeline` ✅
13. `/api/telemetry/error-details?hours=24` ✅
14. `/api/telemetry/model-analytics` ✅
15. `/api/telemetry/tool-analytics` ✅

**Additional Endpoints Found in Frontend:**
16. `/api/telemetry-widget/context-rot-meter`

---

## **Problem Analysis**

### **Root Issue:** ClickHouse Circuit Breaker
- APIs are returning `{"status": "error", "alerts": ["Error: Circuit breaker is open due to consecutive failures"]}` 
- This happens because ClickHouse database is not available (Docker daemon not running)
- Frontend widgets are designed to show "Loading..." when they receive error responses instead of displaying the error or showing empty states

### **Widget Loading Issues by Tab:**

**📈 Telemetry Tab** (Most affected):
- 6 widgets all showing "Loading..." because telemetry endpoints depend on ClickHouse
- Error Monitor, Cost Tracker, Timeout Risk, Tool Optimizer, Model Efficiency, Context Rot Meter

**🤖 Orchestration Tab**:
- 3 widgets showing "Loading..." but using `/api/dashboard-metrics` which should work
- Issue may be in JavaScript error handling or widget ID targeting

**🔍 Analytics Tab**:
- High priority widgets showing "Loading..." 
- Mix of telemetry endpoints (ClickHouse dependent) and analytics endpoints

---

## **API/UI Mismatch Root Causes:**

1. **ClickHouse Database Unavailable** → Circuit breaker tripped → API errors → "Loading..." states
2. **Frontend Error Handling** → Widgets show "Loading..." instead of error messages or empty states
3. **JavaScript Widget Loading** → Some functions may have incorrect endpoint mappings
4. **Duplicate Element IDs** → JavaScript may be targeting wrong elements

**Next Steps:**
1. Start ClickHouse/Docker services OR modify APIs to work without ClickHouse
2. Update frontend error handling to show meaningful messages instead of "Loading..."
3. Verify all widget→endpoint mappings are correct
4. Fix any duplicate ID issues preventing proper updates