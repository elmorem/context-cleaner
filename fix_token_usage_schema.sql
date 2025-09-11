-- Fix token_usage_summary schema
-- Replace materialized view with proper table to support DELETE operations

-- Drop the existing materialized view (if exists)
DROP VIEW IF EXISTS otel.token_usage_summary;

-- Create proper table for token usage summary
CREATE TABLE IF NOT EXISTS otel.token_usage_summary (
    date Date,
    service_name String,
    category Array(String),
    operation_count UInt32,
    total_tokens Float64,
    input_tokens Float64,
    output_tokens Float64,
    cache_tokens Float64
) ENGINE = MergeTree()
PARTITION BY date
ORDER BY (date, service_name);

-- Grant permissions if needed
-- GRANT INSERT, SELECT, DELETE ON otel.token_usage_summary TO default;
