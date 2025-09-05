-- User Baselines Table for Adaptive Context Rot Thresholds - Phase 2
-- This table stores per-user behavioral baselines for personalized threshold calculation

CREATE TABLE IF NOT EXISTS otel.user_baselines (
    user_id String,
    normal_level Float32,              -- User's normal frustration baseline (0.0-1.0)
    variance Float32,                  -- Statistical variance in user behavior  
    session_count UInt32,              -- Number of sessions contributing to baseline
    last_updated DateTime,             -- When baseline was last updated
    confidence Float32,                -- Confidence in baseline accuracy (0.0-1.0)
    avg_session_length Float32,        -- Average session length in minutes
    avg_messages_per_session Float32,  -- Average messages per session
    typical_conversation_flow Float32, -- Typical conversation flow quality (0.0-1.0)
    sensitivity_factor Float32         -- User-specific sensitivity adjustment (0.5-2.0)
) ENGINE = ReplacingMergeTree(last_updated)
PARTITION BY substr(user_id, 1, 2)  -- Partition by first 2 chars of user_id for distribution
ORDER BY user_id
TTL last_updated + INTERVAL 90 DAY DELETE;  -- Auto-cleanup old baselines after 90 days

-- Index for efficient user lookup
CREATE INDEX IF NOT EXISTS idx_user_baselines_user_id ON otel.user_baselines (user_id) TYPE bloom_filter GRANULARITY 1;

-- Materialized view for baseline statistics (optional - for monitoring)
CREATE MATERIALIZED VIEW IF NOT EXISTS otel.baseline_stats AS
SELECT 
    toDate(last_updated) as date,
    count() as total_baselines,
    avg(confidence) as avg_confidence,
    avg(normal_level) as avg_baseline_level,
    avg(variance) as avg_variance,
    countIf(session_count >= 5) as reliable_baselines
FROM otel.user_baselines
GROUP BY date
ORDER BY date DESC;

-- Insert sample data for testing (can be removed in production)
INSERT INTO otel.user_baselines VALUES 
    ('test_user_1', 0.25, 0.15, 10, now(), 0.8, 45.5, 12.3, 0.75, 1.0),
    ('test_user_2', 0.35, 0.25, 8, now(), 0.7, 62.1, 18.7, 0.65, 1.2),
    ('test_user_3', 0.15, 0.10, 15, now(), 0.9, 38.2, 9.4, 0.85, 0.8);