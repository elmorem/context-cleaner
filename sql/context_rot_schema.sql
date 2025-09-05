-- Context Rot Meter - ClickHouse Schema
-- Production-ready schema for storing context rot metrics

-- Main context rot metrics table
CREATE TABLE IF NOT EXISTS otel.context_rot_metrics (
    timestamp DateTime64(3) DEFAULT now64(),
    session_id String,
    rot_score Float32,
    confidence_score Float32,
    indicator_breakdown Map(String, Float32),
    analysis_version UInt8 DEFAULT 1,
    requires_attention UInt8 DEFAULT 0  -- Using UInt8 as ClickHouse boolean
) ENGINE = MergeTree()
PARTITION BY toDate(timestamp)
ORDER BY (session_id, timestamp)
SETTINGS index_granularity = 8192;

-- Materialized view for real-time aggregations
CREATE MATERIALIZED VIEW IF NOT EXISTS otel.context_rot_realtime AS
SELECT 
    session_id,
    avg(rot_score) as avg_rot_score,
    max(rot_score) as max_rot_score,
    count() as measurement_count,
    sum(requires_attention) as attention_alerts,
    max(timestamp) as last_updated
FROM otel.context_rot_metrics
WHERE timestamp >= now() - INTERVAL 30 MINUTE
GROUP BY session_id;

-- Hourly aggregation table for trend analysis
CREATE TABLE IF NOT EXISTS otel.context_rot_hourly (
    hour DateTime,
    session_id String,
    avg_rot_score Float32,
    max_rot_score Float32,
    min_rot_score Float32,
    measurement_count UInt32,
    attention_alerts UInt32,
    avg_confidence Float32
) ENGINE = MergeTree()
PARTITION BY toDate(hour)
ORDER BY (session_id, hour)
SETTINGS index_granularity = 8192;

-- Materialized view for hourly aggregations
CREATE MATERIALIZED VIEW IF NOT EXISTS otel.context_rot_hourly_mv TO otel.context_rot_hourly AS
SELECT 
    toStartOfHour(timestamp) as hour,
    session_id,
    avg(rot_score) as avg_rot_score,
    max(rot_score) as max_rot_score,
    min(rot_score) as min_rot_score,
    count() as measurement_count,
    sum(requires_attention) as attention_alerts,
    avg(confidence_score) as avg_confidence
FROM otel.context_rot_metrics
GROUP BY hour, session_id;

-- Index for common query patterns
-- Session-based queries
ALTER TABLE otel.context_rot_metrics ADD INDEX IF NOT EXISTS idx_session_time (session_id, timestamp) TYPE minmax GRANULARITY 1;

-- Time-based queries
ALTER TABLE otel.context_rot_metrics ADD INDEX IF NOT EXISTS idx_time_rot (timestamp, rot_score) TYPE minmax GRANULARITY 1;

-- High rot score queries
ALTER TABLE otel.context_rot_metrics ADD INDEX IF NOT EXISTS idx_attention (requires_attention, rot_score) TYPE minmax GRANULARITY 1;

-- TTL for automatic cleanup (keep data for 90 days)
ALTER TABLE otel.context_rot_metrics MODIFY TTL timestamp + INTERVAL 90 DAY;
ALTER TABLE otel.context_rot_hourly MODIFY TTL hour + INTERVAL 90 DAY;

-- Sample queries for validation

-- Get recent context rot for a session
-- SELECT * FROM otel.context_rot_metrics 
-- WHERE session_id = 'your_session_id' 
-- AND timestamp >= now() - INTERVAL 1 HOUR 
-- ORDER BY timestamp DESC;

-- Get sessions with high context rot
-- SELECT session_id, avg(rot_score) as avg_rot, count() as measurements
-- FROM otel.context_rot_metrics 
-- WHERE timestamp >= now() - INTERVAL 24 HOUR
-- GROUP BY session_id
-- HAVING avg_rot > 0.7
-- ORDER BY avg_rot DESC;

-- Get trend analysis
-- SELECT 
--     toHour(timestamp) as hour,
--     avg(rot_score) as avg_rot,
--     max(rot_score) as max_rot,
--     count() as measurements
-- FROM otel.context_rot_metrics
-- WHERE session_id = 'your_session_id'
-- AND timestamp >= now() - INTERVAL 24 HOUR
-- GROUP BY hour
-- ORDER BY hour;

-- System health check
-- SELECT 
--     count() as total_measurements,
--     uniq(session_id) as unique_sessions,
--     avg(rot_score) as global_avg_rot,
--     sum(requires_attention) as total_alerts,
--     min(timestamp) as earliest_measurement,
--     max(timestamp) as latest_measurement
-- FROM otel.context_rot_metrics
-- WHERE timestamp >= now() - INTERVAL 24 HOUR;