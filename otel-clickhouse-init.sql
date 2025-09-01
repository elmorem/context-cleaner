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