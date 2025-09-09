"""
Tests for ClickHouse Schema Implementation.

Comprehensive test suite for database schema creation, validation,
and DDL generation for Enhanced Token Analysis Bridge.
"""

import pytest
import asyncio
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.context_cleaner.database.clickhouse_schema import ClickHouseSchema, SchemaVersion, TableSchema


class TestClickHouseSchema:
    """Test suite for ClickHouseSchema class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.schema = ClickHouseSchema()
        self.test_database = "test_otel"

    def test_current_version(self):
        """Test schema version constants."""
        assert ClickHouseSchema.CURRENT_VERSION == SchemaVersion.CURRENT
        assert SchemaVersion.V1_0 == SchemaVersion.CURRENT

    def test_get_table_schemas(self):
        """Test retrieval of table schema definitions."""
        schemas = self.schema.get_table_schemas(self.test_database)

        # Check all expected tables are present
        expected_tables = {"enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"}
        assert set(schemas.keys()) == expected_tables

        # Verify each schema has required components
        for table_name, schema in schemas.items():
            assert isinstance(schema, TableSchema)
            assert schema.name == table_name
            assert schema.create_sql
            assert isinstance(schema.indexes, list)
            assert schema.description

            # Verify database placeholder is replaced
            assert self.test_database in schema.create_sql
            assert "{database}" not in schema.create_sql

    def test_enhanced_token_summaries_schema(self):
        """Test enhanced_token_summaries table schema."""
        schema = self.schema.get_table_schemas(self.test_database)["enhanced_token_summaries"]

        # Check DDL contains required fields
        required_fields = [
            "analysis_id String",
            "session_id String",
            "timestamp DateTime64(3)",
            "reported_input_tokens UInt64",
            "calculated_total_tokens UInt64",
            "accuracy_ratio Float64",
            "undercount_percentage Float64",
            "content_categories Map(String, UInt64)",
            "validation_status Enum8",
        ]

        for field in required_fields:
            assert field in schema.create_sql

        # Check engine and partitioning
        assert "ENGINE = ReplacingMergeTree" in schema.create_sql
        assert "PARTITION BY toDate(timestamp)" in schema.create_sql
        assert "TTL timestamp + INTERVAL 90 DAY" in schema.create_sql

    def test_enhanced_token_details_schema(self):
        """Test enhanced_token_details table schema."""
        schema = self.schema.get_table_schemas(self.test_database)["enhanced_token_details"]

        # Check file-specific fields
        required_fields = [
            "file_path String",
            "file_hash String",
            "file_size_bytes UInt64",
            "file_total_tokens UInt64",
            "conversation_count UInt32",
        ]

        for field in required_fields:
            assert field in schema.create_sql

        # Check engine and TTL
        assert "ENGINE = MergeTree()" in schema.create_sql
        assert "TTL created_at + INTERVAL 30 DAY" in schema.create_sql

    def test_enhanced_analysis_metadata_schema(self):
        """Test enhanced_analysis_metadata table schema."""
        schema = self.schema.get_table_schemas(self.test_database)["enhanced_analysis_metadata"]

        # Check metadata-specific fields
        required_fields = [
            "execution_timestamp DateTime64(3)",
            "hostname String",
            "python_version String",
            "trigger_source Enum8",
            "execution_mode Enum8",
            "total_execution_time_ms UInt64",
            "errors_detail Array(String)",
        ]

        for field in required_fields:
            assert field in schema.create_sql

        # Check TTL for long-term retention
        assert "TTL execution_timestamp + INTERVAL 365 DAY" in schema.create_sql

    def test_get_create_table_sql(self):
        """Test individual table SQL generation."""
        # Test valid table
        sql = self.schema.get_create_table_sql("enhanced_token_summaries", self.test_database)
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert self.test_database in sql
        assert "enhanced_token_summaries" in sql

        # Test invalid table
        with pytest.raises(ValueError, match="Unknown table"):
            self.schema.get_create_table_sql("nonexistent_table", self.test_database)

    def test_get_index_sql(self):
        """Test index SQL generation."""
        # Test table with indexes
        indexes = self.schema.get_index_sql("enhanced_token_summaries", self.test_database)
        assert len(indexes) > 0

        for index_sql in indexes:
            assert "ALTER TABLE" in index_sql
            assert "ADD INDEX" in index_sql
            assert self.test_database in index_sql
            assert "GRANULARITY 8192" in index_sql

        # Test table without indexes
        indexes = self.schema.get_index_sql("nonexistent_table", self.test_database)
        assert indexes == []

    def test_get_view_sql(self):
        """Test view SQL generation."""
        # Test valid view
        view_sql = self.schema.get_view_sql("session_token_summary", self.test_database)
        assert "CREATE OR REPLACE VIEW" in view_sql
        assert self.test_database in view_sql
        assert "session_token_summary" in view_sql
        assert "enhanced_token_summaries" in view_sql

        # Test invalid view
        with pytest.raises(ValueError, match="Unknown view"):
            self.schema.get_view_sql("nonexistent_view", self.test_database)

    def test_get_all_views_sql(self):
        """Test generation of all view SQL statements."""
        view_sqls = self.schema.get_all_views_sql(self.test_database)

        expected_views = {"session_token_summary", "token_trends", "content_category_analysis", "analysis_performance"}

        assert len(view_sqls) == len(expected_views)

        for view_sql in view_sqls:
            assert "CREATE OR REPLACE VIEW" in view_sql
            assert self.test_database in view_sql

    def test_get_full_schema_sql(self):
        """Test complete schema SQL generation."""
        sql_statements = self.schema.get_full_schema_sql(self.test_database)

        # Check all components are included
        statement_types = [
            "CREATE DATABASE IF NOT EXISTS",  # Database creation
            "CREATE TABLE IF NOT EXISTS",  # Tables
            "ALTER TABLE",  # Indexes
            "CREATE OR REPLACE VIEW",  # Views
        ]

        sql_text = " ".join(sql_statements)
        for stmt_type in statement_types:
            assert stmt_type in sql_text

        # Check proper ordering (database -> tables -> indexes -> views)
        db_index = next(i for i, stmt in enumerate(sql_statements) if "CREATE DATABASE" in stmt)
        table_indices = [i for i, stmt in enumerate(sql_statements) if "CREATE TABLE" in stmt]
        index_indices = [i for i, stmt in enumerate(sql_statements) if "ALTER TABLE" in stmt]
        view_indices = [i for i, stmt in enumerate(sql_statements) if "CREATE OR REPLACE VIEW" in stmt]

        # Verify ordering
        assert db_index < min(table_indices)
        if index_indices:
            assert max(table_indices) < min(index_indices)
        if view_indices:
            assert (max(index_indices) if index_indices else max(table_indices)) < min(view_indices)

    def test_validate_schema_compatibility(self):
        """Test schema compatibility validation."""
        # Test with no existing tables (clean slate)
        issues = self.schema.validate_schema_compatibility([])
        assert len(issues) == 1  # Should warn about missing tables
        assert "Missing required tables" in issues[0]

        # Test with expected tables present
        expected_tables = ["enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"]
        issues = self.schema.validate_schema_compatibility(expected_tables)
        assert issues == []

        # Test with missing tables
        partial_tables = ["enhanced_token_summaries"]
        issues = self.schema.validate_schema_compatibility(partial_tables)
        assert len(issues) > 0
        assert any("Missing required tables" in issue for issue in issues)

        # Test with conflicting tables
        conflicting_tables = ["enhanced_token_summaries", "enhanced_token_legacy", "other_table"]
        issues = self.schema.validate_schema_compatibility(conflicting_tables)
        assert any("Potentially conflicting table" in issue for issue in issues)

    def test_get_schema_version_sql(self):
        """Test schema version tracking SQL."""
        version_sql = self.schema.get_schema_version_sql(self.test_database)

        assert "CREATE TABLE IF NOT EXISTS" in version_sql
        assert "schema_version" in version_sql
        assert "component String" in version_sql
        assert "version String" in version_sql
        assert "INSERT INTO" in version_sql
        assert "enhanced_token_analysis" in version_sql
        assert SchemaVersion.CURRENT.value in version_sql

    def test_get_data_consistency_check_sql(self):
        """Test data consistency check queries."""
        checks = self.schema.get_data_consistency_check_sql(self.test_database)

        expected_checks = {"token_sum_consistency", "accuracy_ratio_bounds", "orphaned_details"}

        assert set(checks.keys()) == expected_checks

        for check_name, check_sql in checks.items():
            assert isinstance(check_sql, str)
            assert "SELECT" in check_sql
            assert self.test_database in check_sql

    def test_get_performance_monitoring_sql(self):
        """Test performance monitoring queries."""
        perf_queries = self.schema.get_performance_monitoring_sql(self.test_database)

        expected_queries = {"table_sizes", "partition_info", "query_performance"}

        assert set(perf_queries.keys()) == expected_queries

        for query_name, query_sql in perf_queries.items():
            assert isinstance(query_sql, str)
            assert "SELECT" in query_sql
            # Most queries should reference the test database
            if query_name != "query_performance":  # This one uses system tables
                assert self.test_database in query_sql


class TestSchemaIntegration:
    """Integration tests for schema components."""

    def test_schema_table_view_relationships(self):
        """Test relationships between tables and views."""
        schema = ClickHouseSchema()
        database = "test_db"

        # Get all table and view definitions
        table_schemas = schema.get_table_schemas(database)
        view_sqls = schema.get_all_views_sql(database)

        # Check that views reference actual tables
        table_names = set(table_schemas.keys())

        for view_sql in view_sqls:
            # Each view should reference at least one table
            references_table = any(table_name in view_sql for table_name in table_names)
            assert references_table, f"View does not reference any known tables: {view_sql[:100]}..."

    def test_index_table_relationships(self):
        """Test that indexes reference actual table columns."""
        schema = ClickHouseSchema()
        database = "test_db"

        # Get table schemas and indexes
        table_schemas = schema.get_table_schemas(database)

        for table_name, table_schema in table_schemas.items():
            indexes = schema.get_index_sql(table_name, database)

            for index_sql in indexes:
                # Index should reference the correct table
                assert f"{database}.{table_name}" in index_sql

                # Index should use proper granularity
                assert "GRANULARITY" in index_sql

    def test_schema_evolution_compatibility(self):
        """Test schema can handle evolution scenarios."""
        schema = ClickHouseSchema()

        # Test that schema version tracking works
        version_sql = schema.get_schema_version_sql("test_db")
        assert "ReplacingMergeTree" in version_sql  # Handles updates

        # Test that tables use appropriate engines for updates
        summaries_sql = schema.get_create_table_sql("enhanced_token_summaries", "test_db")
        assert "ReplacingMergeTree" in summaries_sql  # Supports deduplication

        details_sql = schema.get_create_table_sql("enhanced_token_details", "test_db")
        assert "MergeTree" in details_sql  # Append-only is fine


@pytest.fixture
def mock_clickhouse_client():
    """Create a mock ClickHouse client for testing."""
    client = AsyncMock()
    client.database = "test_otel"
    client.execute_query = AsyncMock(return_value=[])
    return client


class TestSchemaPerformance:
    """Performance-related tests for schema design."""

    def test_table_partitioning_strategy(self):
        """Test that tables use appropriate partitioning."""
        schema = ClickHouseSchema()

        # Time-series tables should be partitioned by date
        summaries_sql = schema.get_create_table_sql("enhanced_token_summaries", "test_db")
        assert "PARTITION BY toDate(timestamp)" in summaries_sql

        details_sql = schema.get_create_table_sql("enhanced_token_details", "test_db")
        assert "PARTITION BY toDate(created_at)" in details_sql

        metadata_sql = schema.get_create_table_sql("enhanced_analysis_metadata", "test_db")
        assert "PARTITION BY toDate(execution_timestamp)" in metadata_sql

    def test_index_optimization_for_queries(self):
        """Test that indexes are optimized for expected query patterns."""
        schema = ClickHouseSchema()

        # Session-based queries
        summaries_indexes = schema.get_index_sql("enhanced_token_summaries", "test_db")
        session_index_found = any("session_id" in idx for idx in summaries_indexes)
        assert session_index_found

        # Token range queries
        token_index_found = any("calculated_total_tokens" in idx for idx in summaries_indexes)
        assert token_index_found

        # Time-based queries
        time_index_found = any("timestamp" in idx for idx in summaries_indexes)
        assert time_index_found

    def test_compression_settings(self):
        """Test that tables use appropriate compression."""
        schema = ClickHouseSchema()
        tables = ["enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"]

        for table_name in tables:
            table_sql = schema.get_create_table_sql(table_name, "test_db")
            assert "compress_on_write = 1" in table_sql
            assert "compression_method" in table_sql

    def test_ttl_policies(self):
        """Test that TTL policies are appropriate for data lifecycle."""
        schema = ClickHouseSchema()

        # Different retention periods for different data types
        summaries_sql = schema.get_create_table_sql("enhanced_token_summaries", "test_db")
        assert "90 DAY" in summaries_sql  # Longer retention for summaries

        details_sql = schema.get_create_table_sql("enhanced_token_details", "test_db")
        assert "30 DAY" in details_sql  # Shorter retention for details

        metadata_sql = schema.get_create_table_sql("enhanced_analysis_metadata", "test_db")
        assert "365 DAY" in metadata_sql  # Longest retention for metadata
