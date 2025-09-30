-- Initialize ClickHouse database for OpenTelemetry data
CREATE DATABASE IF NOT EXISTS otel;

-- Create tables for OpenTelemetry traces, metrics, and logs
USE otel;

-- Traces table (spans)
CREATE TABLE IF NOT EXISTS traces (
    timestamp DateTime64(9),
    trace_id String,
    span_id String,
    parent_span_id String,
    operation_name String,
    kind Int8,
    status_code Int8,
    status_message String,
    duration_ns UInt64,
    service_name String,
    service_version String,
    resource_attributes Map(String, String),
    span_attributes Map(String, String),
    events Array(Tuple(
        timestamp DateTime64(9),
        name String,
        attributes Map(String, String)
    )),
    links Array(Tuple(
        trace_id String,
        span_id String,
        attributes Map(String, String)
    ))
) ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (service_name, timestamp, trace_id, span_id)
TTL timestamp + INTERVAL 7 DAY;

-- Metrics table
CREATE TABLE IF NOT EXISTS metrics (
    timestamp DateTime64(9),
    name String,
    description String,
    unit String,
    type String,
    value Float64,
    service_name String,
    service_version String,
    resource_attributes Map(String, String),
    metric_attributes Map(String, String),
    exemplar_trace_id String,
    exemplar_span_id String
) ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (service_name, name, timestamp)
TTL timestamp + INTERVAL 7 DAY;

-- Logs table
CREATE TABLE IF NOT EXISTS logs (
    timestamp DateTime64(9),
    observed_timestamp DateTime64(9),
    severity_text String,
    severity_number Int8,
    body String,
    trace_id String,
    span_id String,
    service_name String,
    service_version String,
    resource_attributes Map(String, String),
    log_attributes Map(String, String),
    flags UInt32
) ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (service_name, timestamp, trace_id, span_id)
TTL timestamp + INTERVAL 7 DAY;

-- Create materialized views for common queries

-- Daily trace summary
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_trace_summary
ENGINE = SummingMergeTree()
PARTITION BY date
ORDER BY (date, service_name, operation_name)
AS SELECT
    toDate(timestamp) as date,
    service_name,
    operation_name,
    count() as span_count,
    avg(duration_ns) as avg_duration_ns,
    quantile(0.95)(duration_ns) as p95_duration_ns,
    quantile(0.99)(duration_ns) as p99_duration_ns
FROM traces
GROUP BY date, service_name, operation_name;

-- Token usage summary (for Claude Code specific analysis)
CREATE MATERIALIZED VIEW IF NOT EXISTS token_usage_summary  
ENGINE = SummingMergeTree()
PARTITION BY date
ORDER BY (date, service_name, category)
AS SELECT
    toDate(timestamp) as date,
    service_name,
    extractAllGroups(operation_name, '(token|input|output|cache)')[1] as category,
    count() as operation_count,
    sum(toFloat64OrZero(span_attributes['tokens'])) as total_tokens,
    sum(toFloat64OrZero(span_attributes['input_tokens'])) as input_tokens,
    sum(toFloat64OrZero(span_attributes['output_tokens'])) as output_tokens,
    sum(toFloat64OrZero(span_attributes['cache_tokens'])) as cache_tokens
FROM traces
WHERE span_attributes['tokens'] != ''
GROUP BY date, service_name, category;

-- ===== COMPLETE JSONL CONTENT STORAGE TABLES =====
-- Tables for storing complete conversation content, file contents, and tool results

-- Complete Message Content Storage
CREATE TABLE IF NOT EXISTS claude_message_content (
    message_uuid String,
    session_id String, 
    timestamp DateTime64(3),
    role LowCardinality(String), -- 'user', 'assistant'
    
    -- FULL MESSAGE CONTENT STORAGE
    message_content String,      -- COMPLETE conversation message (full user prompts, assistant responses)
    message_preview String,      -- First 200 chars for quick access
    message_hash String,         -- SHA-256 for deduplication
    message_length UInt32,       -- Character count
    
    -- Message metadata
    model_name String,
    input_tokens UInt32,
    output_tokens UInt32,
    cost_usd Float64,
    
    -- Content analysis (computed from full content)
    contains_code_blocks Bool MATERIALIZED position(message_content, '```') > 0,
    contains_file_references Bool MATERIALIZED position(message_content, '/') > 0 OR position(message_content, '\\') > 0,
    programming_languages Array(String), -- Detected from content
    
    PRIMARY KEY (message_uuid),
    INDEX idx_session (session_id) TYPE set(100) GRANULARITY 8192,
    INDEX idx_content_hash (message_hash) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_search (message_content) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = MergeTree()
ORDER BY (message_uuid, session_id, timestamp)
PARTITION BY toDate(timestamp)
TTL timestamp + INTERVAL 30 DAY;

-- Complete File Content Storage
CREATE TABLE IF NOT EXISTS claude_file_content (
    file_access_uuid String,
    session_id String,
    message_uuid String, -- Links to the message that accessed this file
    timestamp DateTime64(3),
    
    -- COMPLETE FILE CONTENT STORAGE
    file_path String,
    file_content String,         -- ENTIRE file contents when read by tools
    file_content_hash String,    -- SHA-256 for deduplication 
    file_size UInt32,           -- Size in bytes
    file_extension LowCardinality(String),
    operation_type LowCardinality(String), -- 'read', 'write', 'edit'
    
    -- File analysis (computed from full content)
    file_type LowCardinality(String), -- 'code', 'config', 'data', 'documentation'
    programming_language LowCardinality(String),
    contains_secrets Bool MATERIALIZED position(lower(file_content), 'password') > 0 OR position(lower(file_content), 'api_key') > 0,
    contains_imports Bool MATERIALIZED position(file_content, 'import ') > 0 OR position(file_content, '#include') > 0,
    line_count UInt32 MATERIALIZED length(file_content) - length(replaceAll(file_content, '\n', '')) + 1,
    
    PRIMARY KEY (file_access_uuid),
    INDEX idx_file_path (file_path) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_hash (file_content_hash) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_search (file_content) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = ReplacingMergeTree() -- Use ReplacingMergeTree for file deduplication
ORDER BY (file_access_uuid, file_path, file_content_hash)
PARTITION BY toDate(timestamp)
TTL timestamp + INTERVAL 30 DAY;

-- Complete Tool Results Storage
CREATE TABLE IF NOT EXISTS claude_tool_results (
    tool_result_uuid String,
    session_id String,
    message_uuid String,
    timestamp DateTime64(3),
    
    -- COMPLETE TOOL EXECUTION CONTENT
    tool_name LowCardinality(String),
    tool_input String,          -- COMPLETE tool parameters/commands
    tool_output String,         -- COMPLETE tool output/results/stdout
    tool_error String,          -- Complete error messages/stderr
    
    -- Tool metadata
    execution_time_ms UInt32,
    success Bool,
    exit_code Int32,
    
    -- Content analysis (computed from full output)
    output_size UInt32 MATERIALIZED length(tool_output),
    contains_error Bool MATERIALIZED length(tool_error) > 0,
    output_type LowCardinality(String), -- 'text', 'json', 'binary', 'image'
    is_file_operation Bool MATERIALIZED tool_name IN ('Read', 'Write', 'Edit'),
    is_system_command Bool MATERIALIZED tool_name = 'Bash',
    
    PRIMARY KEY (tool_result_uuid),
    INDEX idx_tool_name (tool_name) TYPE set(50) GRANULARITY 8192,
    INDEX idx_output_search (tool_output) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = MergeTree()
ORDER BY (tool_result_uuid, session_id, timestamp)
PARTITION BY toDate(timestamp)  
TTL timestamp + INTERVAL 30 DAY;
