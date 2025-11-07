"""
ClickHouse Schema Implementation for Enhanced Token Analysis Bridge.

This module provides comprehensive DDL definitions, indexes, views, and schema
management for storing 2.768B tokens of enhanced token analysis results.
Optimized for high-volume writes and analytical queries.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SchemaVersion(Enum):
    """Schema version enumeration for migration tracking."""

    V1_0 = "1.0"
    CURRENT = V1_0


@dataclass
class TableSchema:
    """Schema definition for a ClickHouse table."""

    name: str
    create_sql: str
    indexes: List[str]
    views: List[str] = None
    description: str = ""


class ClickHouseSchema:
    """
    ClickHouse schema manager for Enhanced Token Analysis Bridge.

    Provides DDL generation, schema validation, and optimization settings
    for storing token analysis results in ClickHouse database.
    """

    CURRENT_VERSION = SchemaVersion.CURRENT
    DATABASE_NAME = "otel"

    # Core table schemas
    ENHANCED_TOKEN_SUMMARIES_TABLE = """
    CREATE TABLE IF NOT EXISTS {database}.enhanced_token_summaries (
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
        token_calculation_confidence Float32 DEFAULT 1.0,
        
        -- Content analysis metadata
        files_processed UInt32,
        total_conversations UInt32 DEFAULT 0,
        total_messages UInt64 DEFAULT 0,
        
        -- Content categorization (using Map for flexible categories)
        content_categories Map(String, UInt64),
        message_types Map(String, UInt64),
        
        -- Processing performance metrics
        processing_duration_ms UInt32,
        memory_usage_mb Float32 DEFAULT 0.0,
        analysis_version String DEFAULT '1.0',
        
        -- Data lineage and validation
        source_files_hash String DEFAULT '',
        data_checksum String DEFAULT '',
        validation_status Enum8('validated' = 1, 'warning' = 2, 'error' = 3) DEFAULT 'validated',
        validation_notes String DEFAULT '',
        
        -- Temporal tracking
        created_at DateTime64(3) DEFAULT now64(3),
        updated_at DateTime64(3) DEFAULT now64(3)
    ) 
    ENGINE = ReplacingMergeTree(updated_at)
    PRIMARY KEY (session_id, analysis_id)
    ORDER BY (session_id, analysis_id, timestamp)
    PARTITION BY toDate(timestamp)
    TTL timestamp + INTERVAL 90 DAY
    SETTINGS index_granularity = 4096,
             index_granularity_bytes = 10485760,
             compress_on_write = 1,
             compression_method = 'lz4',
             merge_with_ttl_timeout = 86400,
             max_suspicious_broken_parts = 10;
    """

    ENHANCED_TOKEN_DETAILS_TABLE = """
    CREATE TABLE IF NOT EXISTS {database}.enhanced_token_details (
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
        processing_status Enum8('success' = 1, 'warning' = 2, 'error' = 3) DEFAULT 'success',
        error_message String DEFAULT '',
        
        -- Temporal tracking
        created_at DateTime64(3) DEFAULT now64(3)
    )
    ENGINE = MergeTree()
    PRIMARY KEY (analysis_id, session_id, file_path)
    ORDER BY (analysis_id, session_id, file_path)
    PARTITION BY toDate(created_at)
    TTL created_at + INTERVAL 30 DAY
    SETTINGS index_granularity = 4096,
             index_granularity_bytes = 10485760,
             compress_on_write = 1,
             compression_method = 'lz4',
             merge_with_ttl_timeout = 86400,
             max_suspicious_broken_parts = 10;
    """

    ENHANCED_ANALYSIS_METADATA_TABLE = """
    CREATE TABLE IF NOT EXISTS {database}.enhanced_analysis_metadata (
        -- Analysis execution tracking
        analysis_id String,
        execution_timestamp DateTime64(3),
        
        -- System environment
        hostname String,
        python_version String,
        analysis_version String,
        
        -- Execution context
        trigger_source Enum8('manual' = 1, 'scheduled' = 2, 'dashboard' = 3, 'api' = 4) DEFAULT 'manual',
        execution_mode Enum8('full' = 1, 'incremental' = 2, 'validation' = 3) DEFAULT 'full',
        
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
    SETTINGS index_granularity = 4096,
             index_granularity_bytes = 10485760,
             compress_on_write = 1,
             compression_method = 'lz4',
             merge_with_ttl_timeout = 86400,
             max_suspicious_broken_parts = 10;
    """

    # High-performance index definitions optimized for 2.768B tokens
    INDEXES = {
        "enhanced_token_summaries": [
            # Primary performance indexes with optimized granularity
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_session_timestamp (session_id, timestamp) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_total_tokens (calculated_total_tokens) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_accuracy (accuracy_ratio, undercount_percentage) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_timestamp (timestamp) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_validation_status (validation_status) TYPE set(0) GRANULARITY 4096;",
            # High-performance indexes for common dashboard queries
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_session_analysis (session_id, analysis_id) TYPE bloom_filter(0.01) GRANULARITY 2048;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_token_range (calculated_total_tokens, timestamp) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_processing_performance (processing_duration_ms, files_processed) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_cost_analysis (reported_input_tokens, reported_output_tokens, accuracy_ratio) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_analysis_version (analysis_version, timestamp) TYPE bloom_filter(0.01) GRANULARITY 2048;",
        ],
        "enhanced_token_details": [
            # Optimized indexes for file-level analysis
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_file_path (file_path) TYPE bloom_filter(0.01) GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_file_tokens (file_total_tokens) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_processing_status (processing_status) TYPE set(0) GRANULARITY 4096;",
            # Performance indexes for file analysis queries
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_analysis_file (analysis_id, file_path) TYPE bloom_filter(0.01) GRANULARITY 2048;",
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_file_size_tokens (file_size_bytes, file_total_tokens) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_conversation_metrics (conversation_count, message_count) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_file_processing_time (processing_duration_ms, processing_order) TYPE minmax GRANULARITY 4096;",
        ],
        "enhanced_analysis_metadata": [
            # Metadata analysis performance indexes
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_trigger_source (trigger_source) TYPE set(0) GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_execution_mode (execution_mode) TYPE set(0) GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_validation_passed (validation_passed) TYPE set(0) GRANULARITY 4096;",
            # Performance monitoring indexes
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_performance_metrics (total_execution_time_ms, peak_memory_usage_mb) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_execution_results (files_processed, files_scanned, error_count) TYPE minmax GRANULARITY 4096;",
            "ALTER TABLE {database}.enhanced_analysis_metadata ADD INDEX IF NOT EXISTS idx_analysis_timestamp (analysis_id, execution_timestamp) TYPE bloom_filter(0.01) GRANULARITY 2048;",
        ],
    }

    # Materialized views for dashboard consumption
    VIEWS = {
        "session_token_summary": """
        CREATE OR REPLACE VIEW {database}.session_token_summary AS
        SELECT 
            session_id,
            analysis_id,
            timestamp,
            calculated_total_tokens,
            accuracy_ratio,
            files_processed,
            processing_duration_ms,
            validation_status,
            created_at
        FROM {database}.enhanced_token_summaries
        WHERE validation_status = 'validated'
        ORDER BY timestamp DESC;
        """,
        "token_trends": """
        CREATE OR REPLACE VIEW {database}.token_trends AS
        SELECT 
            toDate(timestamp) as date,
            count() as analyses_count,
            sum(calculated_total_tokens) as daily_tokens,
            avg(accuracy_ratio) as avg_accuracy,
            max(processing_duration_ms) as max_processing_time,
            uniq(session_id) as unique_sessions
        FROM {database}.enhanced_token_summaries
        WHERE validation_status = 'validated'
        GROUP BY toDate(timestamp)
        ORDER BY date DESC;
        """,
        "content_category_analysis": """
        CREATE OR REPLACE VIEW {database}.content_category_analysis AS
        SELECT 
            session_id,
            analysis_id, 
            timestamp,
            content_categories,
            message_types,
            calculated_total_tokens,
            files_processed
        FROM {database}.enhanced_token_summaries
        WHERE length(content_categories) > 0
          AND validation_status = 'validated'
        ORDER BY calculated_total_tokens DESC;
        """,
        "analysis_performance": """
        CREATE OR REPLACE VIEW {database}.analysis_performance AS
        SELECT 
            analysis_version,
            avg(processing_duration_ms) as avg_duration,
            avg(memory_usage_mb) as avg_memory,
            count() as executions,
            sum(files_processed) as total_files,
            avg(accuracy_ratio) as avg_accuracy,
            min(timestamp) as first_execution,
            max(timestamp) as last_execution
        FROM {database}.enhanced_token_summaries
        WHERE timestamp >= now() - INTERVAL 30 DAY
          AND validation_status = 'validated'
        GROUP BY analysis_version
        ORDER BY avg_duration ASC;
        """,
    }

    @classmethod
    def get_table_schemas(cls, database: str = DATABASE_NAME) -> Dict[str, TableSchema]:
        """
        Get all table schema definitions.

        Args:
            database: Target database name

        Returns:
            Dictionary mapping table names to schema definitions
        """
        return {
            "enhanced_token_summaries": TableSchema(
                name="enhanced_token_summaries",
                create_sql=cls.ENHANCED_TOKEN_SUMMARIES_TABLE.format(database=database),
                indexes=cls.INDEXES["enhanced_token_summaries"],
                views=[
                    "session_token_summary",
                    "token_trends",
                    "content_category_analysis",
                    "analysis_performance",
                ],
                description="Primary table storing session-level token summaries from Enhanced Token Analysis",
            ),
            "enhanced_token_details": TableSchema(
                name="enhanced_token_details",
                create_sql=cls.ENHANCED_TOKEN_DETAILS_TABLE.format(database=database),
                indexes=cls.INDEXES["enhanced_token_details"],
                views=[],
                description="Detail table storing file-level token breakdowns for detailed analysis",
            ),
            "enhanced_analysis_metadata": TableSchema(
                name="enhanced_analysis_metadata",
                create_sql=cls.ENHANCED_ANALYSIS_METADATA_TABLE.format(
                    database=database
                ),
                indexes=cls.INDEXES["enhanced_analysis_metadata"],
                views=[],
                description="Metadata table tracking analysis execution and system performance",
            ),
        }

    @classmethod
    def get_create_table_sql(
        cls, table_name: str, database: str = DATABASE_NAME
    ) -> str:
        """
        Get CREATE TABLE SQL for specific table.

        Args:
            table_name: Name of table to create
            database: Target database name

        Returns:
            CREATE TABLE SQL statement

        Raises:
            ValueError: If table_name is not recognized
        """
        schemas = cls.get_table_schemas(database)
        if table_name not in schemas:
            raise ValueError(
                f"Unknown table: {table_name}. Available tables: {list(schemas.keys())}"
            )

        return schemas[table_name].create_sql

    @classmethod
    def get_index_sql(cls, table_name: str, database: str = DATABASE_NAME) -> List[str]:
        """
        Get index creation SQL statements for specific table.

        Args:
            table_name: Name of table
            database: Target database name

        Returns:
            List of CREATE INDEX SQL statements
        """
        if table_name not in cls.INDEXES:
            return []

        return [idx.format(database=database) for idx in cls.INDEXES[table_name]]

    @classmethod
    def get_view_sql(cls, view_name: str, database: str = DATABASE_NAME) -> str:
        """
        Get view creation SQL for specific view.

        Args:
            view_name: Name of view to create
            database: Target database name

        Returns:
            CREATE VIEW SQL statement

        Raises:
            ValueError: If view_name is not recognized
        """
        if view_name not in cls.VIEWS:
            raise ValueError(
                f"Unknown view: {view_name}. Available views: {list(cls.VIEWS.keys())}"
            )

        return cls.VIEWS[view_name].format(database=database)

    @classmethod
    def get_all_views_sql(cls, database: str = DATABASE_NAME) -> List[str]:
        """
        Get all view creation SQL statements.

        Args:
            database: Target database name

        Returns:
            List of CREATE VIEW SQL statements
        """
        return [cls.get_view_sql(view_name, database) for view_name in cls.VIEWS.keys()]

    @classmethod
    def get_full_schema_sql(cls, database: str = DATABASE_NAME) -> List[str]:
        """
        Get complete schema creation SQL in dependency order.

        Args:
            database: Target database name

        Returns:
            List of SQL statements to create complete schema
        """
        sql_statements = []

        # 1. Create database if it doesn't exist
        sql_statements.append(f"CREATE DATABASE IF NOT EXISTS {database};")

        # 2. Create tables in dependency order
        table_order = [
            "enhanced_token_summaries",
            "enhanced_token_details",
            "enhanced_analysis_metadata",
        ]
        for table_name in table_order:
            sql_statements.append(cls.get_create_table_sql(table_name, database))

        # 3. Create indexes
        for table_name in table_order:
            sql_statements.extend(cls.get_index_sql(table_name, database))

        # 4. Create views
        sql_statements.extend(cls.get_all_views_sql(database))

        return sql_statements

    @classmethod
    def validate_schema_compatibility(cls, existing_tables: List[str]) -> List[str]:
        """
        Validate compatibility with existing database schema.

        Args:
            existing_tables: List of existing table names in database

        Returns:
            List of compatibility issues or warnings
        """
        issues = []
        expected_tables = set(cls.get_table_schemas().keys())
        existing_set = set(existing_tables)

        # Check for missing tables
        missing_tables = expected_tables - existing_set
        if missing_tables:
            issues.append(f"Missing required tables: {', '.join(missing_tables)}")

        # Check for unexpected tables that might conflict
        conflicting_prefixes = ["enhanced_token_", "enhanced_analysis_"]
        for table in existing_set:
            if any(table.startswith(prefix) for prefix in conflicting_prefixes):
                if table not in expected_tables:
                    issues.append(f"Potentially conflicting table found: {table}")

        return issues

    @classmethod
    def get_schema_version_sql(cls, database: str = DATABASE_NAME) -> str:
        """
        Get SQL to create or update schema version tracking.

        Args:
            database: Target database name

        Returns:
            SQL statement to track schema version
        """
        return f"""
        CREATE TABLE IF NOT EXISTS {database}.schema_version (
            component String,
            version String,
            applied_at DateTime64(3) DEFAULT now64(3),
            applied_by String DEFAULT 'system'
        )
        ENGINE = ReplacingMergeTree(applied_at)
        PRIMARY KEY (component, version)
        ORDER BY (component, version);
        
        INSERT INTO {database}.schema_version (component, version) 
        VALUES ('enhanced_token_analysis', '{cls.CURRENT_VERSION.value}');
        """

    @classmethod
    def get_data_consistency_check_sql(
        cls, database: str = DATABASE_NAME
    ) -> Dict[str, str]:
        """
        Get SQL queries for data consistency validation.

        Args:
            database: Target database name

        Returns:
            Dictionary of check names to SQL queries
        """
        return {
            "token_sum_consistency": f"""
            SELECT 
                session_id,
                analysis_id,
                (reported_input_tokens + reported_output_tokens + 
                 reported_cache_creation_tokens + reported_cache_read_tokens) as calculated_sum,
                calculated_total_tokens,
                abs(calculated_total_tokens - 
                    (reported_input_tokens + reported_output_tokens + 
                     reported_cache_creation_tokens + reported_cache_read_tokens)) as difference
            FROM {database}.enhanced_token_summaries
            WHERE abs(calculated_total_tokens - 
                      (reported_input_tokens + reported_output_tokens + 
                       reported_cache_creation_tokens + reported_cache_read_tokens)) > 1000
            ORDER BY difference DESC
            LIMIT 100;
            """,
            "accuracy_ratio_bounds": f"""
            SELECT 
                session_id,
                analysis_id,
                accuracy_ratio,
                undercount_percentage
            FROM {database}.enhanced_token_summaries
            WHERE accuracy_ratio < 0 OR accuracy_ratio > 2.0
               OR undercount_percentage < 0 OR undercount_percentage > 200
            ORDER BY accuracy_ratio DESC;
            """,
            "orphaned_details": f"""
            SELECT d.analysis_id, d.session_id, count() as detail_count
            FROM {database}.enhanced_token_details d
            LEFT JOIN {database}.enhanced_token_summaries s 
            ON d.analysis_id = s.analysis_id AND d.session_id = s.session_id
            WHERE s.analysis_id IS NULL
            GROUP BY d.analysis_id, d.session_id
            ORDER BY detail_count DESC;
            """,
        }

    @classmethod
    def get_performance_monitoring_sql(
        cls, database: str = DATABASE_NAME
    ) -> Dict[str, str]:
        """
        Get SQL queries for performance monitoring.

        Args:
            database: Target database name

        Returns:
            Dictionary of monitoring queries
        """
        return {
            "table_sizes": f"""
            SELECT 
                table,
                formatReadableSize(total_bytes) as size,
                rows,
                parts,
                formatReadableSize(total_bytes / rows) as avg_row_size
            FROM system.parts
            WHERE database = '{database}' 
              AND table LIKE 'enhanced_%'
              AND active = 1
            ORDER BY total_bytes DESC;
            """,
            "partition_info": f"""
            SELECT 
                table,
                partition,
                count() as parts_count,
                sum(rows) as total_rows,
                formatReadableSize(sum(data_compressed_bytes)) as compressed_size,
                min(min_date) as min_date,
                max(max_date) as max_date
            FROM system.parts
            WHERE database = '{database}' 
              AND table LIKE 'enhanced_%'
              AND active = 1
            GROUP BY table, partition
            ORDER BY table, partition DESC;
            """,
            "query_performance": f"""
            SELECT 
                query_kind,
                count() as query_count,
                avg(query_duration_ms) as avg_duration_ms,
                max(query_duration_ms) as max_duration_ms,
                avg(read_rows) as avg_read_rows,
                avg(read_bytes) as avg_read_bytes
            FROM system.query_log
            WHERE query LIKE '%enhanced_token_%'
              AND event_date >= today() - 7
              AND type = 'QueryFinish'
            GROUP BY query_kind
            ORDER BY avg_duration_ms DESC;
            """,
        }
