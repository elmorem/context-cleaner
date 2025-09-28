# Data Explorer Reference

Use this page as a quick reference while building queries in the Data Explorer. All tables live in the `otel` ClickHouse database unless stated otherwise.

## Working With Map Columns

Many telemetry tables store structured metadata inside ClickHouse `Map(String, String)` columns (for example `LogAttributes`). Access values with bracket syntax:

```sql
SELECT
    LogAttributes['user.email'] AS user_email,
    LogAttributes['tool_name'] AS tool,
    LogAttributes['status_code'] AS status
FROM otel.otel_logs
LIMIT 5;
```

Type conversions are often required because map values are strings. Use helpers such as `toInt64OrNull(...)`, `toFloat64OrNull(...)`, or `parseDateTimeBestEffort(...)` when you need numeric or temporal comparisons.

`Timestamp` columns are typically stored as `DateTime64`. Bucket them with `toStartOfInterval(timestamp, INTERVAL 15 MINUTE)` or convert to a `Date` with `toDate(timestamp)`.

---

## Core Tables

### `otel.otel_logs`
Low-level OTEL event stream collected from the agents and services.

| Column | Type | Notes |
| --- | --- | --- |
| `Timestamp` | `DateTime64(9)` | Precise event time. |
| `Body` | `String` | Event type such as `claude_code.api_error` or `tool_decision`. |
| `ServiceName` | `LowCardinality(String)` | Emitting service (dashboard, orchestrator, etc.). |
| `LogAttributes` | `Map(String, String)` | Rich metadata (user email, session id, model, durations, status codes, tool name, etc.). |

**Sample queries**
```sql
-- Count API errors by status code in the last day
SELECT
    LogAttributes['status_code'] AS status_code,
    COUNT(*) AS error_count
FROM otel.otel_logs
WHERE Body = 'claude_code.api_error'
  AND Timestamp >= now() - INTERVAL 24 HOUR
GROUP BY status_code
ORDER BY error_count DESC;
```

```sql
-- Surface long running tool invocations
SELECT
    LogAttributes['tool_name'] AS tool_name,
    AVG(toFloat64OrNull(LogAttributes['duration_ms'])) AS avg_duration_ms,
    COUNT(*) AS runs
FROM otel.otel_logs
WHERE LogAttributes['duration_ms'] IS NOT NULL
  AND Timestamp >= now() - INTERVAL 6 HOUR
GROUP BY tool_name
ORDER BY avg_duration_ms DESC
LIMIT 20;
```

### `otel.claude_message_content`
Parsed conversation messages emitted by Claude.

| Column | Type | Notes |
| --- | --- | --- |
| `session_id` | `String` | Conversation/session identifier. |
| `timestamp` | `DateTime64(3)` | Event timestamp. |
| `role` | `LowCardinality(String)` | `user` or `assistant`. |
| `message_preview` | `String` | Shortened text preview. |
| `input_tokens`, `output_tokens` | `UInt32` | Token counts for the message. |
| `cost_usd` | `Float64` | Monetized cost estimate. |
| `contains_code_blocks`, `contains_file_references` | `Bool` | Auto generated flags. |

**Sample query**
```sql
SELECT
    toStartOfInterval(timestamp, INTERVAL 15 MINUTE) AS window_start,
    SUM(cost_usd) AS total_cost,
    SUM(input_tokens + output_tokens) AS total_tokens
FROM otel.claude_message_content
WHERE timestamp >= now() - INTERVAL 48 HOUR
GROUP BY window_start
ORDER BY window_start;
```

### Session activity (24h)
Identify the busiest conversation sessions over the last day. Replace the `LIMIT` if you need a longer tail or feed the resulting `session_id` into the drilldown query below.

```sql
SELECT
    LogAttributes['session.id'] AS session_id,
    MIN(Timestamp) AS first_seen,
    MAX(Timestamp) AS last_seen,
    COUNT(*) AS event_count
FROM otel.otel_logs
WHERE Timestamp >= now() - INTERVAL 24 HOUR
  AND LogAttributes['session.id'] != ''
GROUP BY session_id
ORDER BY event_count DESC
LIMIT 50;
```

### `otel.claude_tool_results`
Structured log of tool executions triggered inside conversations.

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | `DateTime64(3)` | When the tool finished. |
| `tool_name` | `LowCardinality(String)` | Tool identifier (Bash, Search, etc.). |
| `execution_time_ms` | `UInt32` | Execution duration. |
| `success` | `Bool` | True when the tool completed successfully. |
| `tool_input`, `tool_output`, `tool_error` | `String` | Payloads and failures. |
| `session_id`, `message_uuid` | `String` | Conversation linkage. |

**Sample query**
```sql
SELECT
    tool_name,
    COUNT() AS runs,
    AVG(execution_time_ms) AS avg_execution_ms,
    quantile(0.9)(execution_time_ms) AS p90_execution_ms
FROM otel.claude_tool_results
WHERE timestamp >= now() - INTERVAL 7 DAY
GROUP BY tool_name
ORDER BY runs DESC;
```

### `otel.context_rot_metrics`
Real-time metrics emitted by the Context Rot analyzer.

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | `DateTime64(3)` | Measurement timestamp. |
| `session_id` | `String` | Conversation where the analysis ran. |
| `rot_score` | `Float32` | Calculated rot score (0–1). |
| `confidence_score` | `Float32` | Model confidence (0–1). |
| `indicator_breakdown` | `Map(String, Float32)` | Contributing signal weights. |

**Sample query**
```sql
SELECT
    toStartOfInterval(timestamp, INTERVAL 1 HOUR) AS window_start,
    AVG(rot_score) AS avg_rot,
    AVG(confidence_score) AS avg_confidence,
    COUNT() AS samples
FROM otel.context_rot_metrics
WHERE timestamp >= now() - INTERVAL 24 HOUR
GROUP BY window_start
ORDER BY window_start DESC;
```

### `otel.token_usage_summary`
Daily rollups of token consumption per service/category.

| Column | Type | Notes |
| --- | --- | --- |
| `date` | `Date` | Day of aggregation. |
| `service_name` | `String` | Application/service source. |
| `category` | `Array(String)` | Tags describing the workload. |
| `operation_count` | `UInt32` | Number of requests. |
| `total_tokens`, `input_tokens`, `output_tokens`, `cache_tokens` | `Float64` | Token metrics. |

**Sample query**
```sql
SELECT
    date,
    service_name,
    sum(total_tokens) AS total_tokens
FROM otel.token_usage_summary
WHERE date >= today() - 14
GROUP BY date, service_name
ORDER BY date DESC, total_tokens DESC;
```

### `otel.enhanced_token_details`
Detailed per-file/per-repo token analysis generated by the enhanced token counter.

Use when drilling into local cache utilization and undercount detection.

| Column Highlights |
| --- |
| `analysis_id` (String), `file_path` (String), `estimated_tokens` (UInt32), `undercount_ratio` (Float32), `session_id` (String). |

### Session drilldown example
Return the full message history for the most recently active session (adapt the subquery to pick a specific session ID).

```sql
WITH target_session AS (
    SELECT session_id
    FROM otel.claude_message_content
    WHERE session_id != ''
    ORDER BY timestamp DESC
    LIMIT 1
)
SELECT
    timestamp,
    role,
    message_preview,
    input_tokens,
    output_tokens,
    cost_usd
FROM otel.claude_message_content
WHERE session_id = (SELECT session_id FROM target_session)
ORDER BY timestamp ASC
LIMIT 200;
```

---

## Helper Snippets

- Bucket timestamps: `toStartOfInterval(timestamp, INTERVAL 15 MINUTE) AS window_start`
- Extract maps: `LogAttributes['user.email']`, `LogAttributes['tool_name']`
- Safe numeric casts: `toFloat64OrNull(LogAttributes['duration_ms'])`
- Date filters: `timestamp >= now() - INTERVAL 7 DAY`

## Troubleshooting

- If a query returns zero rows, double-check table names (use `SHOW TABLES FROM otel`) and column spellings (`DESCRIBE TABLE otel.<table>`).
- Aggregations without a `LIMIT` may pull large result sets. The API automatically appends `LIMIT 1000` when none is provided.
- The Data Explorer logs every request/response to the dashboard log (`Data Explorer query requested…`), which is useful when validating new queries.
- The reference guide is available from the running dashboard at `/docs/data-explorer-reference` (also linked inside the Data Explorer).
- The reference guide is also available from the running dashboard at `/docs/data-explorer-reference` and via the Data Explorer “Open Reference” button.
