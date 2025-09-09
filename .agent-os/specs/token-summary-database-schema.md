# Token Summary Database Schema Specification

**Version**: 1.0  
**Status**: DRAFT  
**Priority**: CRITICAL  
**Created**: 2025-09-09  

## Executive Summary

This specification defines the ClickHouse database schema for storing Enhanced Token Analysis results. The schema supports storing token summaries for 2.768 billion tokens from JSONL analysis while maintaining optimal query performance for dashboard consumption and analytics.

## Schema Overview

The token summary schema consists of three primary tables designed for different data access patterns:

1. **`enhanced_token_summaries`** - Session-level token aggregations
2. **`enhanced_token_details`** - File-level token breakdowns  
3. **`enhanced_analysis_metadata`** - Analysis execution metadata

## Table Specifications

### Primary Table: enhanced_token_summaries

**Purpose**: Store session-level token summaries from Enhanced Token Analysis

```sql
CREATE TABLE IF NOT EXISTS enhanced_token_summaries (
    -- Primary identifiers
    analysis_id String,
    session_id String,
    timestamp DateTime64(3) DEFAULT now64(3),
    
    -- Token counts (core metrics from enhanced analysis)
    reported_input_tokens UInt64,
    reported_output_tokens UInt64, 
    reported_cache_creation_tokens UInt64,
    reported_cache_read_tokens UInt64,
    calculated_total_tokens UInt64,
    
    -- Analysis accuracy metrics
    accuracy_ratio Float64,
    undercount_percentage Float64,
    token_calculation_confidence Float32,
    
    -- Content analysis metadata
    files_processed UInt32,
    total_conversations UInt32,
    total_messages UInt64,
    
    -- Content categorization (using Map for flexible categories)
    content_categories Map(String, UInt64),
    message_types Map(String, UInt64),
    
    -- Processing performance metrics
    processing_duration_ms UInt32,
    memory_usage_mb Float32,
    analysis_version String,
    
    -- Data lineage and validation
    source_files_hash String,
    data_checksum String,
    validation_status Enum8('validated' = 1, 'warning' = 2, 'error' = 3),
    validation_notes String,
    
    -- Temporal tracking
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) 
ENGINE = ReplacingMergeTree(updated_at)
PRIMARY KEY (session_id, analysis_id)
ORDER BY (session_id, analysis_id, timestamp)
PARTITION BY toDate(timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
```

**Indexes for Query Optimization**:
```sql
-- Index for session-based queries
ALTER TABLE enhanced_token_summaries ADD INDEX idx_session_timestamp (session_id, timestamp) TYPE minmax GRANULARITY 8192;

-- Index for token count range queries  
ALTER TABLE enhanced_token_summaries ADD INDEX idx_total_tokens (calculated_total_tokens) TYPE minmax GRANULARITY 8192;

-- Index for accuracy analysis queries
ALTER TABLE enhanced_token_summaries ADD INDEX idx_accuracy (accuracy_ratio, undercount_percentage) TYPE minmax GRANULARITY 8192;

-- Index for time-series analytics
ALTER TABLE enhanced_token_summaries ADD INDEX idx_timestamp (timestamp) TYPE minmax GRANULARITY 8192;
```

### Detail Table: enhanced_token_details

**Purpose**: Store file-level token breakdowns for detailed analysis

```sql
CREATE TABLE IF NOT EXISTS enhanced_token_details (
    -- Link to summary record
    analysis_id String,
    session_id String,
    
    -- File identification
    file_path String,
    file_hash String,
    file_size_bytes UInt64,
    file_modified_at DateTime64(3),
    
    -- File-level token metrics
    file_input_tokens UInt64,
    file_output_tokens UInt64,
    file_cache_creation_tokens UInt64, 
    file_cache_read_tokens UInt64,
    file_total_tokens UInt64,
    
    -- Content structure metrics
    conversation_count UInt32,
    message_count UInt64,
    tool_usage_count UInt32,
    
    -- File processing metadata
    processing_order UInt16,
    processing_duration_ms UInt32,
    processing_status Enum8('success' = 1, 'warning' = 2, 'error' = 3),
    error_message String,
    
    -- Temporal tracking
    created_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PRIMARY KEY (analysis_id, session_id, file_path)
ORDER BY (analysis_id, session_id, file_path)
PARTITION BY toDate(created_at)
TTL created_at + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;
```

### Metadata Table: enhanced_analysis_metadata

**Purpose**: Track analysis execution metadata and system performance

```sql
CREATE TABLE IF NOT EXISTS enhanced_analysis_metadata (
    -- Analysis execution tracking
    analysis_id String,
    execution_timestamp DateTime64(3),
    
    -- System environment
    hostname String,
    python_version String,
    analysis_version String,
    
    -- Execution context
    trigger_source Enum8('manual' = 1, 'scheduled' = 2, 'dashboard' = 3, 'api' = 4),
    execution_mode Enum8('full' = 1, 'incremental' = 2, 'validation' = 3),
    
    -- Performance metrics
    total_execution_time_ms UInt64,
    peak_memory_usage_mb Float32,
    files_scanned UInt32,
    files_processed UInt32,
    files_skipped UInt32,
    
    -- Results summary
    total_sessions_found UInt32,
    total_tokens_calculated UInt64,
    average_accuracy_ratio Float64,
    
    -- Error tracking
    error_count UInt16,
    warning_count UInt16,
    errors_detail Array(String),
    warnings_detail Array(String),
    
    -- Data quality metrics
    data_consistency_score Float32,
    validation_passed Boolean,
    
    -- Temporal tracking
    created_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PRIMARY KEY (analysis_id)
ORDER BY (analysis_id, execution_timestamp)
PARTITION BY toDate(execution_timestamp)
TTL execution_timestamp + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;
```

## Schema Design Principles

### Data Modeling Approach

**Session-Centric Design**: Primary table organized around session_id to support common dashboard queries

**Temporal Partitioning**: All tables partitioned by date for efficient time-range queries

**Deduplication Strategy**: ReplacingMergeTree for summaries to handle duplicate analysis runs

**Data Retention**: TTL policies aligned with data governance requirements

### Performance Optimization

#### Partitioning Strategy
```sql
-- Daily partitions for active data
PARTITION BY toDate(timestamp)

-- Monthly partitions for historical data (alternative for large datasets)
-- PARTITION BY toYYYYMM(timestamp)
```

#### Index Strategy
```sql
-- Primary indexes for common access patterns
PRIMARY KEY (session_id, analysis_id)  -- Session-based access
PRIMARY KEY (analysis_id, session_id, file_path)  -- File-based access

-- Secondary indexes for range queries
INDEX idx_token_range (calculated_total_tokens) TYPE minmax
INDEX idx_time_range (timestamp) TYPE minmax
INDEX idx_accuracy_range (accuracy_ratio) TYPE minmax
```

#### Compression Settings
```sql
-- Optimize for analytical workloads
SETTINGS index_granularity = 8192,
         compress_on_write = 1,
         compression_method = 'lz4'
```

### Data Integrity Constraints

#### Field Validation Rules
```sql
-- Token counts must be non-negative
CHECK calculated_total_tokens >= 0
CHECK reported_input_tokens >= 0
CHECK reported_output_tokens >= 0

-- Accuracy ratio must be reasonable (0.0 to 2.0)  
CHECK accuracy_ratio >= 0.0 AND accuracy_ratio <= 2.0

-- Processing metrics must be positive
CHECK processing_duration_ms > 0
CHECK files_processed > 0
```

#### Data Consistency Rules
```sql
-- Total tokens should equal sum of components
CHECK calculated_total_tokens = 
      reported_input_tokens + 
      reported_output_tokens + 
      reported_cache_creation_tokens + 
      reported_cache_read_tokens
```

## Query Patterns and Views

### Dashboard Query Optimized Views

#### Session Summary View
```sql
CREATE VIEW session_token_summary AS
SELECT 
    session_id,
    analysis_id,
    timestamp,
    calculated_total_tokens,
    accuracy_ratio,
    files_processed,
    processing_duration_ms,
    validation_status
FROM enhanced_token_summaries
WHERE validation_status = 'validated'
ORDER BY timestamp DESC;
```

#### Time Series Analytics View  
```sql
CREATE VIEW token_trends AS
SELECT 
    toDate(timestamp) as date,
    count() as analyses_count,
    sum(calculated_total_tokens) as daily_tokens,
    avg(accuracy_ratio) as avg_accuracy,
    max(processing_duration_ms) as max_processing_time
FROM enhanced_token_summaries
GROUP BY toDate(timestamp)
ORDER BY date DESC;
```

#### Content Category Breakdown View
```sql
CREATE VIEW content_category_analysis AS
SELECT 
    session_id,
    analysis_id, 
    timestamp,
    content_categories,
    message_types,
    calculated_total_tokens
FROM enhanced_token_summaries
WHERE length(content_categories) > 0
ORDER BY calculated_total_tokens DESC;
```

### Common Query Patterns

#### Dashboard Token Display Query
```sql
-- Get latest token summary for dashboard
SELECT 
    sum(calculated_total_tokens) as total_tokens,
    count(DISTINCT session_id) as unique_sessions,
    avg(accuracy_ratio) as average_accuracy,
    max(timestamp) as last_updated
FROM enhanced_token_summaries 
WHERE timestamp >= now() - INTERVAL 7 DAY
  AND validation_status = 'validated';
```

#### Session Detail Query  
```sql
-- Get detailed breakdown for specific session
SELECT 
    s.session_id,
    s.calculated_total_tokens,
    s.accuracy_ratio,
    s.files_processed,
    d.file_path,
    d.file_total_tokens,
    d.conversation_count
FROM enhanced_token_summaries s
LEFT JOIN enhanced_token_details d ON s.analysis_id = d.analysis_id
WHERE s.session_id = ?
ORDER BY d.file_total_tokens DESC;
```

#### Performance Analytics Query
```sql
-- Analysis performance tracking
SELECT 
    analysis_version,
    avg(processing_duration_ms) as avg_duration,
    avg(memory_usage_mb) as avg_memory,
    count() as executions,
    sum(files_processed) as total_files
FROM enhanced_token_summaries
WHERE timestamp >= now() - INTERVAL 30 DAY
GROUP BY analysis_version
ORDER BY avg_duration ASC;
```

## Data Migration Strategy

### Schema Evolution Support

#### Version Tracking
```sql
-- Add version tracking for schema evolution
ALTER TABLE enhanced_token_summaries ADD COLUMN schema_version UInt8 DEFAULT 1;
```

#### Backward Compatibility
```sql
-- Support for legacy data during migration
ALTER TABLE enhanced_token_summaries ADD COLUMN legacy_data_source String DEFAULT '';
```

### Migration Scripts

#### Schema Creation Script
```sql
-- Create all tables in dependency order
-- 1. Create enhanced_token_summaries (primary table)
-- 2. Create enhanced_token_details (references summaries)
-- 3. Create enhanced_analysis_metadata (independent)
-- 4. Create indexes and views
```

#### Data Import Script  
```sql
-- Template for importing historical data
INSERT INTO enhanced_token_summaries (
    analysis_id, session_id, timestamp,
    reported_input_tokens, reported_output_tokens,
    calculated_total_tokens, accuracy_ratio,
    files_processed, processing_duration_ms,
    analysis_version
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
```

## Monitoring and Maintenance

### Table Statistics Tracking
```sql
-- Monitor table growth and performance
SELECT 
    table,
    formatReadableSize(total_bytes) as size,
    rows,
    parts
FROM system.parts
WHERE database = 'default' 
  AND table LIKE 'enhanced_token%';
```

### Data Quality Monitoring
```sql
-- Monitor data quality metrics
SELECT 
    validation_status,
    count() as record_count,
    avg(accuracy_ratio) as avg_accuracy,
    min(timestamp) as oldest_record,
    max(timestamp) as newest_record
FROM enhanced_token_summaries
GROUP BY validation_status;
```

### Partition Management
```sql
-- Automated partition cleanup (older than TTL)
SELECT partition, count() as rows_count
FROM system.parts
WHERE table = 'enhanced_token_summaries'
  AND modification_time < now() - INTERVAL 90 DAY
ORDER BY partition;
```

## Security and Access Control

### Role-Based Access

#### Read-Only Dashboard Access
```sql
-- Create role for dashboard queries
CREATE ROLE dashboard_reader;
GRANT SELECT ON enhanced_token_summaries TO dashboard_reader;
GRANT SELECT ON session_token_summary TO dashboard_reader;
GRANT SELECT ON token_trends TO dashboard_reader;
```

#### Bridge Service Access  
```sql
-- Create role for bridge service operations
CREATE ROLE token_bridge_service;
GRANT INSERT, SELECT, UPDATE ON enhanced_token_summaries TO token_bridge_service;
GRANT INSERT, SELECT ON enhanced_token_details TO token_bridge_service;
GRANT INSERT, SELECT ON enhanced_analysis_metadata TO token_bridge_service;
```

#### Administrative Access
```sql
-- Create role for schema management
CREATE ROLE token_schema_admin;
GRANT ALL ON enhanced_token_summaries TO token_schema_admin;
GRANT ALL ON enhanced_token_details TO token_schema_admin;
GRANT ALL ON enhanced_analysis_metadata TO token_schema_admin;
```

### Data Privacy Compliance

**Content Isolation**: Schema stores only aggregate metrics, no conversation content

**Data Retention**: TTL policies ensure data cleanup according to retention policies

**Audit Trail**: All data modifications tracked with timestamps and source attribution

## Testing Strategy

### Schema Validation Tests
- Foreign key relationship integrity
- Data type constraint validation  
- Index performance verification
- Partition pruning effectiveness

### Performance Benchmarks
- Insert performance for 2.7B token backfill
- Query response times for dashboard access patterns
- Concurrent read/write performance
- Storage efficiency and compression ratios

### Data Quality Tests
- Token count accuracy validation
- Duplicate detection and handling
- Data consistency across tables
- ETL process error handling

## Deployment Checklist

### Pre-Deployment
- [ ] ClickHouse cluster health verification
- [ ] Backup existing telemetry database
- [ ] Storage capacity planning (estimate ~500MB for 2.7B tokens)
- [ ] Network connectivity and permissions testing

### Schema Deployment
- [ ] Execute table creation scripts in dependency order
- [ ] Create indexes and materialized views
- [ ] Set up TTL policies and partition management
- [ ] Configure access roles and permissions

### Post-Deployment Validation
- [ ] Verify table structures match specification
- [ ] Test sample data insertion and querying
- [ ] Validate index performance with explain plans
- [ ] Confirm partition and TTL policies are active

### Rollback Plan
- [ ] Schema rollback scripts prepared
- [ ] Data export procedures documented
- [ ] Fallback to enhanced analysis without database storage
- [ ] Recovery procedures for partial deployment failures

---

**Next Steps**:
1. Create `historical-data-migration.md` specification
2. Implement ClickHouse schema creation scripts
3. Set up database roles and permissions
4. Create schema validation test suite
5. Prepare for historical data backfill process