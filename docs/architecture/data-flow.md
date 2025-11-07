# Data Flow Architecture

> **How data moves through Context Cleaner from collection to visualization**

## 🔄 Complete Data Flow Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                       │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐    │
│  │ Claude Code     │   │  User Commands  │   │  System Events  │    │
│  │ (JSONL Files)   │   │  (CLI Actions)  │   │  (Health, etc)  │    │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘    │
│           │                      │                      │              │
│           │  ~/.claude/          │  CLI Input           │  Internal    │
│           │  sessions/           │                      │              │
│           │  *.jsonl             │                      │              │
│           │                      │                      │              │
└───────────┼──────────────────────┼──────────────────────┼──────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     COLLECTION LAYER                                   │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  JSONL Watcher                                                  │   │
│  │  • Monitors ~/.claude/sessions/                                 │   │
│  │  • Detects new/modified files                                   │   │
│  │  • Parses conversation data                                     │   │
│  │  • Extracts token metrics                                       │   │
│  │  • Deduplicates messages                                        │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
│             ▼ (Raw JSONL data)                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Bridge Service (Optional)                                      │   │
│  │  • Connects to Anthropic API                                    │   │
│  │  • Accurate token counting                                      │   │
│  │  • Historical backfill                                          │   │
│  │  • Enhanced analysis                                            │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
│             ▼ (Enriched token data)                                    │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  OpenTelemetry Collector                                        │   │
│  │  • Receives telemetry data                                      │   │
│  │  • Batch processing                                             │   │
│  │  • Data transformation                                          │   │
│  │  • Protocol conversion                                          │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
└─────────────┼───────────────────────────────────────────────────────────┘
              │
              ▼ (Structured telemetry)
┌───────────────────────────────────────────────────────────────────────┐
│                     STORAGE LAYER                                      │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  ClickHouse Database                                            │   │
│  │                                                                  │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                    │   │
│  │  │   otel_logs      │  │   otel_traces    │                    │   │
│  │  │  • Event logs    │  │  • Spans         │                    │   │
│  │  │  • Attributes    │  │  • Durations     │                    │   │
│  │  └──────────────────┘  └──────────────────┘                    │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                    │   │
│  │  │ claude_message_  │  │ enhanced_token_  │                    │   │
│  │  │     content      │  │     details      │                    │   │
│  │  │  • Conversations │  │  • Token counts  │                    │   │
│  │  │  • Messages      │  │  • File analysis │                    │   │
│  │  └──────────────────┘  └──────────────────┘                    │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
│  ┌──────────▼─────────────────────────────────────────────────────┐   │
│  │  Local File System                                              │   │
│  │  ~/.context_cleaner/data/                                       │   │
│  │  • Cache files                                                  │   │
│  │  • Session indexes                                              │   │
│  │  • Analytics results                                            │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
└─────────────┼───────────────────────────────────────────────────────────┘
              │
              ▼ (Stored data)
┌───────────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                                   │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Analytics Engine                                               │   │
│  │  • Aggregate queries                                            │   │
│  │  • Trend analysis                                               │   │
│  │  • Pattern detection                                            │   │
│  │  • Metric calculations                                          │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
│             ▼ (Processed metrics)                                      │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Visualization Preparation                                      │   │
│  │  • Chart data formatting                                        │   │
│  │  • Time series bucketing                                        │   │
│  │  • Aggregation levels                                           │   │
│  │  • JSON serialization                                           │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
└─────────────┼───────────────────────────────────────────────────────────┘
              │
              ▼ (Visualization data)
┌───────────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                                 │
├───────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Dashboard API Endpoints                                        │   │
│  │  /api/analytics          → Analytics data                       │   │
│  │  /api/telemetry/metrics  → Real-time metrics                    │   │
│  │  /api/conversations      → Message history                      │   │
│  │  /api/health             → System health                        │   │
│  └──────────┬─────────────────────────────────────────────────────┘   │
│             │                                                           │
│             ▼ (JSON API responses)                                     │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Web Dashboard (Browser)                                        │   │
│  │  • Chart.js visualizations                                      │   │
│  │  • Real-time updates (WebSocket)                                │   │
│  │  • Interactive data explorer                                    │   │
│  │  • Tabbed navigation                                            │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└───────────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow Patterns

### **1. Real-Time Telemetry Flow**

```
Claude Code Session
    ↓
JSONL File Updated (~/.claude/sessions/abc123.jsonl)
    ↓
JSONL Watcher Detects Change (inotify/watchdog)
    ↓
Parse New Messages (extract tokens, content, metadata)
    ↓
Send to OpenTelemetry Collector (gRPC protocol)
    ↓
OTEL Collector Batches & Transforms
    ↓
Insert into ClickHouse (otel_logs, claude_message_content)
    ↓
Dashboard Polls for Updates (every 5 seconds)
    ↓
Web UI Displays New Data (< 10 second latency)
```

**Latency**: ~5-10 seconds from file update to dashboard

### **2. Historical Data Migration Flow**

```
User Runs: context-cleaner migration migrate-historical
    ↓
Discovery: Scan ~/.claude/sessions/ (find all .jsonl files)
    ↓
Checkpoint: Create resumeable checkpoint file
    ↓
For Each File:
    ├─ Parse JSONL (line by line)
    ├─ Extract conversations & messages
    ├─ Build token metrics
    ├─ Insert batch into ClickHouse (1000 records)
    └─ Update checkpoint
    ↓
Validation: Verify data integrity
    ↓
Complete: Report statistics (files, messages, tokens)
```

**Performance**: ~1000 messages/second, resumeable on failure

### **3. Analytics Query Flow**

```
User Opens Dashboard Tab
    ↓
Browser Requests: GET /api/analytics/effectiveness
    ↓
Dashboard API Handler
    ↓
Check Cache (LRU cache, 5-minute TTL)
    ├─ Cache Hit: Return cached data
    └─ Cache Miss: Query ClickHouse
        ↓
        SQL Query: Aggregate by time bucket
        ↓
        Process Results: Calculate metrics
        ↓
        Store in Cache
        ↓
        Return JSON Response
    ↓
Browser Renders Chart (Chart.js)
```

**Response Time**: <100ms (cached), <500ms (uncached)

### **4. Token Analysis Flow**

```
JSONL File Contains Message
    ↓
Extract Content & Metadata
    ↓
Check if Enhanced Analysis Enabled
    ├─ YES (API key configured)
    │   ↓
    │   Send to Anthropic API: POST /v1/messages/count_tokens
    │   ↓
    │   Receive Accurate Token Count
    │   ↓
    │   Store Enhanced Metrics (input_tokens, cache_tokens, etc)
    │
    └─ NO (fallback mode)
        ↓
        Use Heuristic Estimation (~90% accurate)
        ↓
        Store Estimated Metrics
    ↓
Store in enhanced_token_details Table
    ↓
Available for Analytics Queries
```

**API Calls**: Rate-limited, batched when possible

## 🔐 Data Transformation & Sanitization

### **JSONL Parsing**

```python
# Raw JSONL format
{"type": "message", "role": "user", "content": "...", "tokens": {...}}

# Transformed for ClickHouse
{
    "session_id": "abc123",
    "timestamp": 1704067200,
    "role": "user",
    "message_preview": "First 200 chars...",
    "input_tokens": 1500,
    "output_tokens": 0,
    "cost_usd": 0.0225,
    "contains_code_blocks": true,
    "contains_file_references": false
}
```

### **Token Metrics Extraction**

```python
# From JSONL usage field
usage = {
    "input_tokens": 1500,
    "cache_creation_input_tokens": 800,
    "cache_read_input_tokens": 700,
    "output_tokens": 300
}

# Transformed for storage
{
    "total_tokens": 1500,
    "input_tokens": 1500,
    "cache_tokens": 700,
    "output_tokens": 300,
    "estimated_cost": 0.0225
}
```

## 📈 Data Retention & Lifecycle

### **ClickHouse TTL Policies**

```sql
-- otel_logs: 72 hour retention
ALTER TABLE otel.otel_logs
MODIFY TTL timestamp + INTERVAL 72 HOUR;

-- enhanced_token_details: No automatic deletion
-- (user-controlled via privacy commands)

-- claude_message_content: 30 day retention
ALTER TABLE otel.claude_message_content
MODIFY TTL timestamp + INTERVAL 30 DAY;
```

### **Cache Lifecycle**

```python
# LRU Cache in Dashboard
cache = LRUCache(maxsize=1000, ttl=300)  # 5 minutes

# File System Cache
cache_dir = ~/.context_cleaner/data/cache/
retention = 7 days  # Automatically cleaned by cleanup task
```

## 🚦 Data Flow Control

### **Backpressure Handling**

```python
# JSONL Watcher with backpressure
async def process_files(files):
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent
    async with semaphore:
        for file in files:
            await process_jsonl(file)
            # Yield control if queue full
            if queue.qsize() > 1000:
                await asyncio.sleep(1)
```

### **Batch Processing**

```python
# ClickHouse batch inserts
BATCH_SIZE = 1000
buffer = []

for message in messages:
    buffer.append(message)
    if len(buffer) >= BATCH_SIZE:
        clickhouse.insert_batch(buffer)
        buffer.clear()
```

## 🔍 Query Optimization

### **Indexing Strategy**

```sql
-- Primary indexes
PRIMARY KEY (timestamp, session_id)

-- Skip indexes for fast filtering
INDEX idx_session_id session_id TYPE bloom_filter GRANULARITY 1
INDEX idx_event_type Body TYPE set(100) GRANULARITY 1

-- Projection for common aggregations
PROJECTION daily_stats (
    SELECT
        toDate(timestamp) as date,
        count() as events,
        sum(input_tokens) as total_tokens
    GROUP BY date
)
```

### **Query Patterns**

```sql
-- Fast: Uses projection
SELECT date, sum(total_tokens)
FROM claude_message_content
GROUP BY toDate(timestamp);

-- Fast: Uses skip index
SELECT * FROM otel_logs
WHERE session_id = 'abc123';

-- Slow: Full scan (use carefully)
SELECT * FROM otel_logs
WHERE Body LIKE '%error%';
```

---

**Next**: [Component Architecture](components.md) for detailed component information

*See also: [Database Layer](database.md) for ClickHouse schema details*
