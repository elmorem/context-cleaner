"""
Tests for Database Initialization.

Test suite for database initialization, validation, and environment
configuration for Enhanced Token Analysis Bridge.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, List, Any

from src.context_cleaner.database.db_init import DatabaseInitializer, InitializationResult, InitializationStatus
from src.context_cleaner.database.clickhouse_schema import ClickHouseSchema
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class TestInitializationResult:
    """Test suite for InitializationResult dataclass."""

    def test_initialization_result_creation(self):
        """Test InitializationResult creation and defaults."""
        result = InitializationResult(status=InitializationStatus.SUCCESS, message="Test successful")

        assert result.status == InitializationStatus.SUCCESS
        assert result.message == "Test successful"
        assert result.tables_created == []
        assert result.indexes_created == []
        assert result.views_created == []
        assert result.errors == []
        assert result.warnings == []
        assert result.execution_time_seconds == 0.0
        assert isinstance(result.timestamp, datetime)

    def test_initialization_result_with_data(self):
        """Test InitializationResult with populated data."""
        result = InitializationResult(
            status=InitializationStatus.PARTIAL_SUCCESS,
            message="Partial success",
            tables_created=["table1", "table2"],
            indexes_created=["idx1", "idx2"],
            views_created=["view1"],
            errors=["error1"],
            warnings=["warning1"],
            execution_time_seconds=10.5,
        )

        assert result.status == InitializationStatus.PARTIAL_SUCCESS
        assert len(result.tables_created) == 2
        assert len(result.indexes_created) == 2
        assert len(result.views_created) == 1
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.execution_time_seconds == 10.5


class TestDatabaseInitializer:
    """Test suite for DatabaseInitializer class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock ClickHouse client."""
        client = AsyncMock(spec=ClickHouseClient)
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        client.health_check = AsyncMock(return_value=True)
        client.initialize = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def initializer(self, mock_client):
        """Create DatabaseInitializer instance."""
        return DatabaseInitializer(
            clickhouse_client=mock_client, database_name="test_otel", environment="testing", dry_run=False
        )

    def test_initializer_creation(self, mock_client):
        """Test DatabaseInitializer creation."""
        initializer = DatabaseInitializer(
            clickhouse_client=mock_client, database_name="test_db", environment="development", dry_run=True
        )

        assert initializer.client == mock_client
        assert initializer.database_name == "test_db"
        assert initializer.environment == "development"
        assert initializer.dry_run is True
        assert isinstance(initializer.schema, ClickHouseSchema)

    def test_initializer_without_client(self):
        """Test DatabaseInitializer creation without explicit client."""
        initializer = DatabaseInitializer(database_name="test_db", environment="testing")

        assert isinstance(initializer.client, ClickHouseClient)
        assert initializer.client.database == "test_db"

    async def test_verify_connection_success(self, initializer, mock_client):
        """Test successful connection verification."""
        mock_client.health_check.return_value = True
        mock_client.execute_query.return_value = [{"version()": "21.8.15.7"}]

        result = await initializer._verify_connection()
        assert result is True

        mock_client.health_check.assert_called_once()
        mock_client.execute_query.assert_called_with("SELECT version()")

    async def test_verify_connection_health_failure(self, initializer, mock_client):
        """Test connection verification with health check failure."""
        mock_client.health_check.return_value = False

        result = await initializer._verify_connection()
        assert result is False

    async def test_verify_connection_query_failure(self, initializer, mock_client):
        """Test connection verification with query failure."""
        mock_client.health_check.return_value = True
        mock_client.execute_query.return_value = []  # Empty result indicates failure

        result = await initializer._verify_connection()
        assert result is False

    async def test_get_existing_tables(self, initializer, mock_client):
        """Test retrieval of existing tables."""
        mock_client.execute_query.return_value = [
            {"name": "table1"},
            {"name": "table2"},
            {"name": "enhanced_token_summaries"},
        ]

        tables = await initializer._get_existing_tables()
        assert tables == ["table1", "table2", "enhanced_token_summaries"]

        mock_client.execute_query.assert_called_with("SHOW TABLES FROM test_otel")

    async def test_get_existing_tables_error(self, initializer, mock_client):
        """Test handling of errors when getting existing tables."""
        mock_client.execute_query.side_effect = Exception("Connection failed")

        tables = await initializer._get_existing_tables()
        assert tables == []

    def test_check_schema_conflicts_no_conflicts(self, initializer):
        """Test schema conflict checking with no conflicts."""
        existing_tables = ["other_table1", "other_table2"]

        conflicts = initializer._check_schema_conflicts(existing_tables, force=False)
        assert conflicts == []

    def test_check_schema_conflicts_with_conflicts(self, initializer):
        """Test schema conflict checking with conflicts."""
        existing_tables = ["enhanced_token_summaries", "other_table"]

        conflicts = initializer._check_schema_conflicts(existing_tables, force=False)
        assert len(conflicts) == 1
        assert "enhanced_token_summaries" in conflicts[0]

    def test_check_schema_conflicts_force_override(self, initializer):
        """Test schema conflict checking with force override."""
        existing_tables = ["enhanced_token_summaries", "enhanced_token_details"]

        conflicts = initializer._check_schema_conflicts(existing_tables, force=True)
        assert conflicts == []

    async def test_create_database_if_needed(self, initializer, mock_client):
        """Test database creation."""
        await initializer._create_database_if_needed()

        expected_query = "CREATE DATABASE IF NOT EXISTS test_otel"
        mock_client.execute_query.assert_called_with(expected_query)

    async def test_create_tables_success(self, initializer, mock_client):
        """Test successful table creation."""
        mock_client.execute_query.return_value = []

        result = await initializer._create_tables(force=False)

        assert result["created"] == ["enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"]
        assert result["errors"] == []

        # Should have called execute_query for each table
        assert mock_client.execute_query.call_count == 3

    async def test_create_tables_with_force(self, initializer, mock_client):
        """Test table creation with force flag."""
        mock_client.execute_query.return_value = []
        initializer.dry_run = False

        result = await initializer._create_tables(force=True)

        # Should have called DROP TABLE statements in addition to CREATE
        assert mock_client.execute_query.call_count == 6  # 3 drops + 3 creates

        # Check that DROP statements were called
        drop_calls = [call for call in mock_client.execute_query.call_args_list if "DROP TABLE" in str(call)]
        assert len(drop_calls) == 3

    async def test_create_tables_dry_run(self, initializer, mock_client):
        """Test table creation in dry run mode."""
        initializer.dry_run = True

        result = await initializer._create_tables(force=False)

        assert result["created"] == ["enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"]
        # Should not have executed any queries in dry run mode
        mock_client.execute_query.assert_not_called()

    async def test_create_tables_with_error(self, initializer, mock_client):
        """Test table creation with errors."""
        mock_client.execute_query.side_effect = [
            None,  # First table succeeds
            Exception("Table creation failed"),  # Second table fails
            None,  # Third table succeeds
        ]

        result = await initializer._create_tables(force=False)

        assert len(result["created"]) == 2  # Two successful
        assert len(result["errors"]) == 1  # One failed
        assert "enhanced_token_details" in result["errors"][0]

    async def test_create_indexes_success(self, initializer, mock_client):
        """Test successful index creation."""
        mock_client.execute_query.return_value = []

        result = await initializer._create_indexes()

        assert len(result["created"]) > 0
        assert result["errors"] == []

        # Should have called execute_query for each index
        assert mock_client.execute_query.call_count > 0

    async def test_create_indexes_with_error(self, initializer, mock_client):
        """Test index creation with errors."""
        mock_client.execute_query.side_effect = Exception("Index creation failed")

        result = await initializer._create_indexes()

        assert len(result["errors"]) > 0
        assert "Index creation failed" in str(result["errors"])

    async def test_create_views_success(self, initializer, mock_client):
        """Test successful view creation."""
        mock_client.execute_query.return_value = []

        result = await initializer._create_views()

        expected_views = ["session_token_summary", "token_trends", "content_category_analysis", "analysis_performance"]
        assert result["created"] == expected_views
        assert result["errors"] == []

        assert mock_client.execute_query.call_count == 4

    async def test_create_views_with_error(self, initializer, mock_client):
        """Test view creation with errors."""
        mock_client.execute_query.side_effect = [
            None,  # First view succeeds
            Exception("View creation failed"),  # Second view fails
            None,  # Third view succeeds
            None,  # Fourth view succeeds
        ]

        result = await initializer._create_views()

        assert len(result["created"]) == 3  # Three successful
        assert len(result["errors"]) == 1  # One failed

    async def test_setup_schema_versioning(self, initializer, mock_client):
        """Test schema versioning setup."""
        mock_client.execute_query.return_value = []

        await initializer._setup_schema_versioning()

        mock_client.execute_query.assert_called_once()
        call_args = mock_client.execute_query.call_args[0][0]
        assert "schema_version" in call_args
        assert "enhanced_token_analysis" in call_args

    async def test_validate_final_schema_success(self, initializer, mock_client):
        """Test successful final schema validation."""
        # Mock existing tables to match expected
        mock_client.execute_query.side_effect = [
            [
                {"name": "enhanced_token_summaries"},
                {"name": "enhanced_token_details"},
                {"name": "enhanced_analysis_metadata"},
            ],  # SHOW TABLES
            [],  # Consistency check 1
            [],  # Consistency check 2
            [],  # Consistency check 3
        ]

        result = await initializer._validate_final_schema()

        assert result["valid"] is True
        assert len(result["warnings"]) == 0

    async def test_validate_final_schema_missing_tables(self, initializer, mock_client):
        """Test final schema validation with missing tables."""
        # Mock missing tables
        mock_client.execute_query.return_value = [{"name": "enhanced_token_summaries"}]  # Only one table exists

        result = await initializer._validate_final_schema()

        assert result["valid"] is False
        assert len(result["warnings"]) >= 2  # Two missing tables
        assert any("Missing table" in warning for warning in result["warnings"])


class TestFullInitialization:
    """Test suite for complete initialization workflow."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client for full initialization testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        client.health_check = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def initializer(self, mock_client):
        """Create initializer for full testing."""
        return DatabaseInitializer(
            clickhouse_client=mock_client, database_name="test_otel", environment="testing", dry_run=False
        )

    async def test_initialize_database_success(self, initializer, mock_client):
        """Test successful full database initialization."""
        # Mock all sub-operations to succeed
        mock_client.health_check.return_value = True
        mock_client.execute_query.return_value = []

        # Mock existing tables check to return empty (clean slate)
        with patch.object(initializer, "_get_existing_tables", return_value=[]):
            result = await initializer.initialize_database()

        assert result.status == InitializationStatus.SUCCESS
        assert "successfully" in result.message.lower()
        assert len(result.tables_created) == 3
        assert len(result.errors) == 0
        assert result.execution_time_seconds > 0

    async def test_initialize_database_connection_failure(self, initializer, mock_client):
        """Test initialization with connection failure."""
        mock_client.health_check.return_value = False

        result = await initializer.initialize_database()

        assert result.status == InitializationStatus.CONNECTION_FAILED
        assert "connection" in result.message.lower()

    async def test_initialize_database_schema_conflicts(self, initializer, mock_client):
        """Test initialization with schema conflicts."""
        mock_client.health_check.return_value = True

        # Mock existing tables that conflict
        with patch.object(initializer, "_get_existing_tables", return_value=["enhanced_token_summaries"]):
            result = await initializer.initialize_database(force=False)

        assert result.status == InitializationStatus.VALIDATION_FAILED
        assert "conflicts" in result.message.lower()
        assert len(result.warnings) > 0

    async def test_initialize_database_with_force(self, initializer, mock_client):
        """Test initialization with force flag to override conflicts."""
        mock_client.health_check.return_value = True
        mock_client.execute_query.return_value = []

        # Mock existing tables that would conflict
        with patch.object(initializer, "_get_existing_tables", return_value=["enhanced_token_summaries"]):
            result = await initializer.initialize_database(force=True)

        assert result.status == InitializationStatus.SUCCESS
        assert len(result.tables_created) == 3

    async def test_initialize_database_partial_success(self, initializer, mock_client):
        """Test initialization with partial success (some errors)."""
        mock_client.health_check.return_value = True

        # Mock some operations to fail
        mock_client.execute_query.side_effect = [
            [],  # Database creation succeeds
            None,  # First table succeeds
            Exception("Table creation failed"),  # Second table fails
            None,  # Third table succeeds
            # ... other operations succeed
        ] + [
            [] for _ in range(20)
        ]  # Remaining calls succeed

        with patch.object(initializer, "_get_existing_tables", return_value=[]):
            result = await initializer.initialize_database()

        assert result.status == InitializationStatus.PARTIAL_SUCCESS
        assert len(result.errors) > 0
        assert len(result.tables_created) > 0  # Some tables were created

    async def test_initialize_database_dry_run(self, initializer, mock_client):
        """Test initialization in dry run mode."""
        initializer.dry_run = True
        mock_client.health_check.return_value = True

        with patch.object(initializer, "_get_existing_tables", return_value=[]):
            result = await initializer.initialize_database()

        assert result.status == InitializationStatus.SUCCESS
        # In dry run, we shouldn't execute actual queries
        # The exact call count depends on verification queries only
        assert mock_client.execute_query.call_count <= 2  # Health check and version check only

    async def test_initialize_database_exception_handling(self, initializer, mock_client):
        """Test initialization exception handling."""
        mock_client.health_check.side_effect = Exception("Unexpected error")

        result = await initializer.initialize_database()

        assert result.status == InitializationStatus.FAILED
        assert "Unexpected error" in result.message
        assert len(result.errors) > 0


class TestSchemaValidation:
    """Test suite for existing schema validation."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client for validation testing."""
        client = AsyncMock(spec=ClickHouseClient)
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        client.health_check = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def initializer(self, mock_client):
        """Create initializer for validation testing."""
        return DatabaseInitializer(clickhouse_client=mock_client, database_name="test_otel")

    async def test_validate_existing_schema_compatible(self, initializer, mock_client):
        """Test validation of compatible existing schema."""
        # Mock all expected tables present
        expected_tables = ["enhanced_token_summaries", "enhanced_token_details", "enhanced_analysis_metadata"]

        mock_client.execute_query.side_effect = [
            [{"name": table} for table in expected_tables],  # SHOW TABLES
            [{"version": "1.0"}],  # Schema version query
            [],  # Performance query 1
            [],  # Performance query 2
            [],  # Performance query 3
        ]

        result = await initializer.validate_existing_schema()

        assert result["compatible"] is True
        assert result["schema_version"] == "1.0"
        assert len(result["missing_tables"]) == 0
        assert len(result["compatibility_issues"]) == 0

    async def test_validate_existing_schema_missing_tables(self, initializer, mock_client):
        """Test validation with missing tables."""
        # Mock only some tables present
        mock_client.execute_query.side_effect = [
            [{"name": "enhanced_token_summaries"}],  # Only one table
            [],  # Other queries return empty
            [],
            [],
            [],
        ]

        result = await initializer.validate_existing_schema()

        assert result["compatible"] is False
        assert len(result["missing_tables"]) == 2  # Two missing tables
        assert len(result["recommendations"]) > 0
        assert "initialization" in result["recommendations"][0].lower()

    async def test_validate_existing_schema_connection_failure(self, initializer, mock_client):
        """Test validation with connection failure."""
        mock_client.health_check.return_value = False

        result = await initializer.validate_existing_schema()

        assert result["compatible"] is False
        assert "connect" in result["compatibility_issues"][0].lower()

    async def test_validate_existing_schema_version_tracking(self, initializer, mock_client):
        """Test schema version tracking validation."""
        mock_client.execute_query.side_effect = [
            [
                {"name": "enhanced_token_summaries"},
                {"name": "enhanced_token_details"},
                {"name": "enhanced_analysis_metadata"},
            ],  # All tables present
            [],  # Schema version not found
            [],
            [],
            [],  # Performance queries
        ]

        result = await initializer.validate_existing_schema()

        assert result["schema_version"] == "not_tracked"
        assert any("not being tracked" in rec for rec in result["recommendations"])


class TestEnvironmentConfiguration:
    """Test suite for environment-specific configuration."""

    def test_get_environment_config_development(self):
        """Test development environment configuration."""
        config = DatabaseInitializer.get_environment_config("development")

        assert config["database_name"] == "otel_dev"
        assert config["host"] == "localhost"
        assert config["port"] == 9000
        assert config["enable_health_monitoring"] is True
        assert config["batch_size"] == 100
        assert config["ttl_days"] == 7

    def test_get_environment_config_testing(self):
        """Test testing environment configuration."""
        config = DatabaseInitializer.get_environment_config("testing")

        assert config["database_name"] == "otel_test"
        assert config["enable_health_monitoring"] is False
        assert config["batch_size"] == 50
        assert config["ttl_days"] == 1

    def test_get_environment_config_production(self):
        """Test production environment configuration."""
        with patch.dict("os.environ", {"CLICKHOUSE_HOST": "prod-host", "CLICKHOUSE_PORT": "8123"}):
            config = DatabaseInitializer.get_environment_config("production")

            assert config["database_name"] == "otel"
            assert config["host"] == "prod-host"
            assert config["port"] == 8123
            assert config["batch_size"] == 1000
            assert config["ttl_days"] == 90

    def test_get_environment_config_unknown(self):
        """Test unknown environment defaults to development."""
        config = DatabaseInitializer.get_environment_config("unknown")

        # Should default to development config
        assert config["database_name"] == "otel_dev"
        assert config["enable_health_monitoring"] is True

    async def test_create_client_from_environment(self):
        """Test creating client from environment configuration."""
        initializer = DatabaseInitializer(database_name="test")

        with patch("src.context_cleaner.database.db_init.ClickHouseClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.initialize = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            client = await initializer.create_client_from_environment("testing")

            # Verify client was created with correct parameters
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["database"] == "otel_test"
            assert call_kwargs["max_connections"] == 2
            assert call_kwargs["enable_health_monitoring"] is False

            # Verify initialization was called
            mock_client.initialize.assert_called_once()


@pytest.mark.integration
class TestDatabaseInitializationIntegration:
    """Integration tests for database initialization (require actual ClickHouse)."""

    @pytest.mark.skip(reason="Requires running ClickHouse instance")
    async def test_real_database_initialization(self):
        """Test initialization against real ClickHouse instance."""
        initializer = DatabaseInitializer(
            database_name="test_enhanced_tokens_init", environment="testing", dry_run=False
        )

        try:
            # Test clean initialization
            result = await initializer.initialize_database(force=True)
            assert result.status == InitializationStatus.SUCCESS
            assert len(result.tables_created) == 3
            assert len(result.views_created) == 4

            # Test validation of created schema
            validation = await initializer.validate_existing_schema()
            assert validation["compatible"] is True
            assert len(validation["missing_tables"]) == 0

        finally:
            # Cleanup - drop test database
            if initializer.client:
                try:
                    await initializer.client.execute_query("DROP DATABASE IF EXISTS test_enhanced_tokens_init")
                    await initializer.client.close()
                except Exception:
                    pass
