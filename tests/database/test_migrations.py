"""
Tests for Database Migration Framework.

Comprehensive test suite for migration management, version tracking,
rollback operations, and batch processing for Enhanced Token Analysis Bridge.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Any

from src.context_cleaner.database.migrations import (
    Migration,
    MigrationManager,
    MigrationRecord,
    MigrationStatus,
    MigrationDirection,
    InitialSchemaMigration,
    PerformanceOptimizationMigration,
)
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class TestMigrationRecord:
    """Test suite for MigrationRecord dataclass."""

    def test_migration_record_creation(self):
        """Test MigrationRecord creation."""
        record = MigrationRecord(
            migration_id="test_001",
            version="1.0",
            name="Test Migration",
            direction=MigrationDirection.FORWARD,
            status=MigrationStatus.SUCCESS,
            started_at=datetime.now(),
            checksum="abc123",
        )

        assert record.migration_id == "test_001"
        assert record.version == "1.0"
        assert record.name == "Test Migration"
        assert record.direction == MigrationDirection.FORWARD
        assert record.status == MigrationStatus.SUCCESS
        assert record.checksum == "abc123"
        assert record.batch_size == 1000
        assert record.records_processed == 0

    def test_migration_record_to_clickhouse(self):
        """Test conversion to ClickHouse record format."""
        started_at = datetime(2023, 1, 1, 12, 0, 0)
        completed_at = datetime(2023, 1, 1, 12, 5, 30)

        record = MigrationRecord(
            migration_id="test_001",
            version="1.0",
            name="Test Migration",
            direction=MigrationDirection.FORWARD,
            status=MigrationStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
            checksum="abc123",
            batch_size=500,
            records_processed=1000,
            execution_time_seconds=330.5,
        )

        clickhouse_record = record.to_clickhouse_record()

        assert clickhouse_record["migration_id"] == "test_001"
        assert clickhouse_record["version"] == "1.0"
        assert clickhouse_record["name"] == "Test Migration"
        assert clickhouse_record["direction"] == "forward"
        assert clickhouse_record["status"] == "success"
        assert clickhouse_record["started_at"] == "2023-01-01 12:00:00"
        assert clickhouse_record["completed_at"] == "2023-01-01 12:05:30"
        assert clickhouse_record["checksum"] == "abc123"
        assert clickhouse_record["batch_size"] == 500
        assert clickhouse_record["records_processed"] == 1000
        assert clickhouse_record["execution_time_seconds"] == 330.5


class MockMigration(Migration):
    """Mock migration for testing."""

    def __init__(self, migration_id: str = "mock_001", should_succeed: bool = True):
        super().__init__(migration_id, "1.0", "Mock Migration", "Test migration")
        self.should_succeed = should_succeed
        self.forward_called = False
        self.backward_called = False
        self.validate_called = False

    async def forward(self, client: ClickHouseClient, batch_size: int = 1000) -> Dict[str, Any]:
        """Mock forward migration."""
        self.forward_called = True
        if self.should_succeed:
            return {"success": True, "records_processed": 100}
        else:
            return {"success": False, "errors": ["Mock forward error"]}

    async def backward(self, client: ClickHouseClient, batch_size: int = 1000) -> Dict[str, Any]:
        """Mock backward migration."""
        self.backward_called = True
        if self.should_succeed:
            return {"success": True, "records_processed": 50}
        else:
            return {"success": False, "errors": ["Mock backward error"]}

    async def validate(self, client: ClickHouseClient) -> Dict[str, Any]:
        """Mock validation."""
        self.validate_called = True
        return {
            "can_execute": self.should_succeed,
            "warnings": [] if self.should_succeed else ["Mock validation warning"],
            "requirements_met": True,
        }


class TestMigration:
    """Test suite for Migration base class."""

    def test_migration_initialization(self):
        """Test Migration base class initialization."""
        migration = MockMigration("test_001")

        assert migration.migration_id == "test_001"
        assert migration.version == "1.0"
        assert migration.name == "Mock Migration"
        assert migration.description == "Test migration"
        assert len(migration.checksum) == 16  # SHA256 truncated to 16 chars

    def test_migration_checksum_calculation(self):
        """Test migration checksum calculation."""
        migration1 = MockMigration("test_001")
        migration2 = MockMigration("test_001")
        migration3 = MockMigration("test_002")

        # Same migrations should have same checksum
        assert migration1.checksum == migration2.checksum

        # Different migrations should have different checksums
        assert migration1.checksum != migration3.checksum

    async def test_migration_forward_success(self):
        """Test successful forward migration."""
        migration = MockMigration(should_succeed=True)
        client = AsyncMock()

        result = await migration.forward(client, batch_size=500)

        assert result["success"] is True
        assert migration.forward_called is True

    async def test_migration_forward_failure(self):
        """Test failed forward migration."""
        migration = MockMigration(should_succeed=False)
        client = AsyncMock()

        result = await migration.forward(client, batch_size=500)

        assert result["success"] is False
        assert len(result["errors"]) > 0

    async def test_migration_backward_success(self):
        """Test successful backward migration."""
        migration = MockMigration(should_succeed=True)
        client = AsyncMock()

        result = await migration.backward(client, batch_size=500)

        assert result["success"] is True
        assert migration.backward_called is True

    async def test_migration_validate(self):
        """Test migration validation."""
        migration = MockMigration(should_succeed=True)
        client = AsyncMock()

        result = await migration.validate(client)

        assert result["can_execute"] is True
        assert migration.validate_called is True


class TestInitialSchemaMigration:
    """Test suite for InitialSchemaMigration."""

    @pytest.fixture
    def migration(self):
        """Create InitialSchemaMigration instance."""
        return InitialSchemaMigration()

    @pytest.fixture
    def mock_client(self):
        """Create mock ClickHouse client."""
        client = AsyncMock()
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        return client

    def test_initial_migration_properties(self, migration):
        """Test InitialSchemaMigration properties."""
        assert migration.migration_id == "001_initial_schema"
        assert migration.version == "1.0"
        assert "Enhanced Token Analysis Schema" in migration.name
        assert migration.description != ""

    async def test_initial_migration_forward_success(self, migration, mock_client):
        """Test successful initial schema creation."""
        mock_client.execute_query.return_value = []

        result = await migration.forward(mock_client, batch_size=1000)

        assert result["success"] is True
        assert len(result["tables_created"]) == 3
        assert len(result["errors"]) == 0

        # Should have called execute_query for tables, indexes, and views
        assert mock_client.execute_query.call_count > 10  # Tables + indexes + views

    async def test_initial_migration_forward_with_errors(self, migration, mock_client):
        """Test initial schema creation with some errors."""
        # First few calls succeed, then some fail
        mock_client.execute_query.side_effect = [
            [],  # Table 1 success
            Exception("Table 2 failed"),  # Table 2 fails
            [],  # Table 3 success
        ] + [
            [] for _ in range(20)
        ]  # Remaining calls succeed

        result = await migration.forward(mock_client, batch_size=1000)

        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Table 2 failed" in str(result["errors"])

    async def test_initial_migration_backward_success(self, migration, mock_client):
        """Test successful schema rollback."""
        mock_client.execute_query.return_value = []

        result = await migration.backward(mock_client, batch_size=1000)

        assert result["success"] is True
        assert len(result["tables_dropped"]) == 3
        assert len(result["views_dropped"]) == 4

        # Should have called DROP statements
        drop_calls = [call for call in mock_client.execute_query.call_args_list if "DROP" in str(call)]
        assert len(drop_calls) > 0

    async def test_initial_migration_validate_clean_database(self, migration, mock_client):
        """Test validation against clean database."""
        mock_client.execute_query.return_value = []  # No existing tables

        result = await migration.validate(mock_client)

        assert result["can_execute"] is True
        assert len(result["conflicts"]) == 0

    async def test_initial_migration_validate_with_conflicts(self, migration, mock_client):
        """Test validation with existing conflicting tables."""
        mock_client.execute_query.return_value = [{"name": "enhanced_token_summaries"}, {"name": "other_table"}]

        result = await migration.validate(mock_client)

        assert result["can_execute"] is True  # Can still execute but with warnings
        assert len(result["conflicts"]) > 0
        assert len(result["warnings"]) > 0

    async def test_initial_migration_validate_access_error(self, migration, mock_client):
        """Test validation with database access error."""
        mock_client.execute_query.side_effect = Exception("Access denied")

        result = await migration.validate(mock_client)

        assert result["can_execute"] is False
        assert "Access denied" in str(result["warnings"])


class TestPerformanceOptimizationMigration:
    """Test suite for PerformanceOptimizationMigration."""

    @pytest.fixture
    def migration(self):
        """Create PerformanceOptimizationMigration instance."""
        return PerformanceOptimizationMigration()

    @pytest.fixture
    def mock_client(self):
        """Create mock ClickHouse client."""
        client = AsyncMock()
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        return client

    def test_performance_migration_properties(self, migration):
        """Test PerformanceOptimizationMigration properties."""
        assert migration.migration_id == "002_performance_optimization"
        assert migration.version == "1.1"
        assert "Performance Optimization" in migration.name

    async def test_performance_migration_forward_success(self, migration, mock_client):
        """Test successful performance optimization."""
        mock_client.execute_query.return_value = []

        result = await migration.forward(mock_client, batch_size=1000)

        assert result["success"] is True
        assert len(result["optimizations_applied"]) > 0
        assert len(result["errors"]) == 0

        # Should have executed multiple optimization queries
        assert mock_client.execute_query.call_count > 3

    async def test_performance_migration_backward_success(self, migration, mock_client):
        """Test successful performance optimization rollback."""
        mock_client.execute_query.return_value = []

        result = await migration.backward(mock_client, batch_size=1000)

        assert result["success"] is True
        assert len(result["optimizations_removed"]) > 0

        # Should have executed DROP INDEX statements
        drop_calls = [call for call in mock_client.execute_query.call_args_list if "DROP INDEX" in str(call)]
        assert len(drop_calls) > 0

    async def test_performance_migration_validate_ready(self, migration, mock_client):
        """Test validation when tables are ready for optimization."""
        mock_client.execute_query.side_effect = [
            [
                {"name": "enhanced_token_summaries"},
                {"name": "enhanced_token_details"},
                {"name": "enhanced_analysis_metadata"},
            ],  # SHOW TABLES
            [{"table": "enhanced_token_summaries", "total_rows": 2000000, "size": "1GB"}],  # Table sizes
        ]

        result = await migration.validate(mock_client)

        assert result["can_execute"] is True
        assert len(result["warnings"]) > 0  # Should warn about large tables


class TestMigrationManager:
    """Test suite for MigrationManager."""

    @pytest.fixture
    def mock_client(self):
        """Create mock ClickHouse client."""
        client = AsyncMock()
        client.database = "test_otel"
        client.execute_query = AsyncMock(return_value=[])
        client.bulk_insert = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def manager(self, mock_client):
        """Create MigrationManager instance."""
        mgr = MigrationManager(mock_client)
        # Clear built-in migrations for cleaner testing
        mgr.migrations.clear()
        mgr.migration_order.clear()
        return mgr

    def test_manager_initialization(self, mock_client):
        """Test MigrationManager initialization."""
        manager = MigrationManager(mock_client)

        assert manager.client == mock_client
        assert len(manager.migrations) == 2  # Two built-in migrations
        assert len(manager.migration_order) == 2
        assert "001_initial_schema" in manager.migrations
        assert "002_performance_optimization" in manager.migrations

    def test_register_migration(self, manager):
        """Test migration registration."""
        migration = MockMigration("test_001")

        manager.register_migration(migration)

        assert "test_001" in manager.migrations
        assert "test_001" in manager.migration_order
        assert manager.migrations["test_001"] == migration

    def test_register_duplicate_migration(self, manager):
        """Test registering duplicate migration."""
        migration1 = MockMigration("test_001")
        migration2 = MockMigration("test_001")

        manager.register_migration(migration1)
        manager.register_migration(migration2)

        # Should have only one entry in order
        assert manager.migration_order.count("test_001") == 1
        # But should update the migration
        assert manager.migrations["test_001"] == migration2

    async def test_initialize_migration_tracking(self, manager, mock_client):
        """Test migration tracking table initialization."""
        await manager.initialize_migration_tracking()

        mock_client.execute_query.assert_called_once()
        call_args = mock_client.execute_query.call_args[0][0]
        assert "CREATE TABLE" in call_args
        assert "schema_migrations" in call_args

    async def test_get_applied_migrations_success(self, manager, mock_client):
        """Test retrieval of applied migrations."""
        mock_client.execute_query.return_value = [
            {
                "migration_id": "001_initial_schema",
                "version": "1.0",
                "name": "Initial Schema",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:00:00Z",
                "completed_at": "2023-01-01T12:05:00Z",
                "error_message": "",
                "checksum": "abc123",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 300.0,
            }
        ]

        applied = await manager.get_applied_migrations()

        assert len(applied) == 1
        assert applied[0].migration_id == "001_initial_schema"
        assert applied[0].status == MigrationStatus.SUCCESS
        assert applied[0].direction == MigrationDirection.FORWARD

    async def test_get_applied_migrations_empty(self, manager, mock_client):
        """Test retrieval when no migrations applied."""
        mock_client.execute_query.return_value = []

        applied = await manager.get_applied_migrations()

        assert len(applied) == 0

    async def test_get_applied_migrations_error(self, manager, mock_client):
        """Test retrieval with database error."""
        mock_client.execute_query.side_effect = Exception("Database error")

        applied = await manager.get_applied_migrations()

        assert len(applied) == 0  # Should handle error gracefully

    async def test_get_pending_migrations(self, manager, mock_client):
        """Test retrieval of pending migrations."""
        # Register test migrations
        manager.register_migration(MockMigration("test_001"))
        manager.register_migration(MockMigration("test_002"))
        manager.register_migration(MockMigration("test_003"))

        # Mock that test_001 is already applied
        mock_client.execute_query.return_value = [
            {
                "migration_id": "test_001",
                "version": "1.0",
                "name": "Test 1",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:00:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "abc123",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            }
        ]

        pending = await manager.get_pending_migrations()

        assert len(pending) == 2
        assert pending[0].migration_id == "test_002"
        assert pending[1].migration_id == "test_003"

    async def test_migrate_up_success(self, manager, mock_client):
        """Test successful forward migration."""
        # Register successful migrations
        migration1 = MockMigration("test_001", should_succeed=True)
        migration2 = MockMigration("test_002", should_succeed=True)
        manager.register_migration(migration1)
        manager.register_migration(migration2)

        # Mock no applied migrations
        mock_client.execute_query.return_value = []

        result = await manager.migrate_up()

        assert result["success"] is True
        assert len(result["migrations_applied"]) == 2
        assert len(result["migrations_failed"]) == 0
        assert result["total_execution_time"] > 0

        # Verify migrations were called
        assert migration1.forward_called is True
        assert migration2.forward_called is True

    async def test_migrate_up_with_failure(self, manager, mock_client):
        """Test forward migration with failure."""
        # Register migrations - second one fails
        migration1 = MockMigration("test_001", should_succeed=True)
        migration2 = MockMigration("test_002", should_succeed=False)
        migration3 = MockMigration("test_003", should_succeed=True)
        manager.register_migration(migration1)
        manager.register_migration(migration2)
        manager.register_migration(migration3)

        # Mock no applied migrations
        mock_client.execute_query.return_value = []

        result = await manager.migrate_up()

        assert result["success"] is False
        assert len(result["migrations_applied"]) == 1  # Only first one applied
        assert len(result["migrations_failed"]) == 1  # Second one failed
        assert len(result["errors"]) > 0

        # Verify only first migration was called (stops on failure)
        assert migration1.forward_called is True
        assert migration2.forward_called is True
        assert migration3.forward_called is False  # Should not be called

    async def test_migrate_up_validation_failure(self, manager, mock_client):
        """Test forward migration with validation failure."""
        # Register migration that fails validation
        migration = MockMigration("test_001", should_succeed=False)
        manager.register_migration(migration)

        mock_client.execute_query.return_value = []

        result = await manager.migrate_up()

        assert result["success"] is False
        assert len(result["migrations_applied"]) == 0
        assert len(result["migrations_failed"]) == 1

        # Migration should not be executed due to validation failure
        assert migration.validate_called is True
        assert migration.forward_called is False

    async def test_migrate_up_with_target(self, manager, mock_client):
        """Test forward migration to specific target."""
        # Register three migrations
        migration1 = MockMigration("test_001", should_succeed=True)
        migration2 = MockMigration("test_002", should_succeed=True)
        migration3 = MockMigration("test_003", should_succeed=True)
        manager.register_migration(migration1)
        manager.register_migration(migration2)
        manager.register_migration(migration3)

        mock_client.execute_query.return_value = []

        # Migrate up to test_002 only
        result = await manager.migrate_up(target_migration="test_002")

        assert result["success"] is True
        assert len(result["migrations_applied"]) == 2

        # Third migration should not be called
        assert migration1.forward_called is True
        assert migration2.forward_called is True
        assert migration3.forward_called is False

    async def test_migrate_down_success(self, manager, mock_client):
        """Test successful backward migration."""
        # Register migrations
        migration1 = MockMigration("test_001", should_succeed=True)
        migration2 = MockMigration("test_002", should_succeed=True)
        migration3 = MockMigration("test_003", should_succeed=True)
        manager.register_migration(migration1)
        manager.register_migration(migration2)
        manager.register_migration(migration3)

        # Mock applied migrations in order
        mock_client.execute_query.return_value = [
            {
                "migration_id": "test_001",
                "version": "1.0",
                "name": "Test 1",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:00:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "abc123",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
            {
                "migration_id": "test_002",
                "version": "1.0",
                "name": "Test 2",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:05:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "def456",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
            {
                "migration_id": "test_003",
                "version": "1.0",
                "name": "Test 3",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:10:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "ghi789",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
        ]

        # Rollback to test_001 (should rollback test_003 and test_002)
        result = await manager.migrate_down("test_001")

        assert result["success"] is True
        assert len(result["migrations_rolled_back"]) == 2
        assert result["migrations_rolled_back"] == ["test_003", "test_002"]

        # Verify backwards calls were made in reverse order
        assert migration3.backward_called is True
        assert migration2.backward_called is True
        assert migration1.backward_called is False  # Target, so not rolled back

    async def test_migrate_down_target_not_found(self, manager, mock_client):
        """Test rollback with target migration not found."""
        migration = MockMigration("test_001")
        manager.register_migration(migration)

        mock_client.execute_query.return_value = []  # No applied migrations

        result = await manager.migrate_down("test_001")

        assert result["success"] is False
        assert "not found" in result["errors"][0]

    async def test_migrate_down_with_failure(self, manager, mock_client):
        """Test rollback with failure."""
        # Register migrations - second rollback fails
        migration1 = MockMigration("test_001", should_succeed=True)
        migration2 = MockMigration("test_002", should_succeed=False)  # Will fail on rollback
        migration3 = MockMigration("test_003", should_succeed=True)
        manager.register_migration(migration1)
        manager.register_migration(migration2)
        manager.register_migration(migration3)

        # Mock all three applied
        mock_client.execute_query.return_value = [
            {
                "migration_id": "test_001",
                "version": "1.0",
                "name": "Test 1",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:00:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "a",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
            {
                "migration_id": "test_002",
                "version": "1.0",
                "name": "Test 2",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:05:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "b",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
            {
                "migration_id": "test_003",
                "version": "1.0",
                "name": "Test 3",
                "direction": "forward",
                "status": "success",
                "started_at": "2023-01-01T12:10:00Z",
                "completed_at": None,
                "error_message": "",
                "checksum": "c",
                "batch_size": 1000,
                "records_processed": 0,
                "execution_time_seconds": 0,
            },
        ]

        result = await manager.migrate_down("test_001")

        assert result["success"] is False
        assert len(result["migrations_rolled_back"]) == 1  # Only test_003 succeeded
        assert len(result["migrations_failed"]) == 1  # test_002 failed

        # First rollback should succeed, second should fail, third should not be attempted
        assert migration3.backward_called is True
        assert migration2.backward_called is True
        assert migration1.backward_called is False

    async def test_get_migration_status(self, manager, mock_client):
        """Test comprehensive migration status retrieval."""
        # Register migrations
        migration1 = MockMigration("test_001")
        migration2 = MockMigration("test_002")
        manager.register_migration(migration1)
        manager.register_migration(migration2)

        # Mock applied migrations
        mock_client.execute_query.side_effect = [
            # Applied migrations
            [
                {
                    "migration_id": "test_001",
                    "version": "1.0",
                    "name": "Test 1",
                    "direction": "forward",
                    "status": "success",
                    "started_at": "2023-01-01T12:00:00Z",
                    "completed_at": None,
                    "error_message": "",
                    "checksum": "abc123",
                    "batch_size": 1000,
                    "records_processed": 0,
                    "execution_time_seconds": 120.5,
                }
            ],
            # Failed migrations
            [
                {
                    "migration_id": "failed_migration",
                    "name": "Failed Test",
                    "error_message": "Something went wrong",
                    "started_at": "2023-01-01T11:00:00Z",
                }
            ],
        ]

        status = await manager.get_migration_status()

        assert status["current_version"] == "1.0"
        assert len(status["applied_migrations"]) == 1
        assert len(status["pending_migrations"]) == 1
        assert len(status["failed_migrations"]) == 1
        assert status["total_migrations"] == 2
        assert status["schema_health"] == "outdated"  # Has pending migrations

        # Check applied migration details
        applied = status["applied_migrations"][0]
        assert applied["id"] == "test_001"
        assert applied["execution_time"] == 120.5

        # Check pending migration details
        pending = status["pending_migrations"][0]
        assert pending["id"] == "test_002"

    async def test_record_migration_status(self, manager, mock_client):
        """Test migration status recording."""
        record = MigrationRecord(
            migration_id="test_001",
            version="1.0",
            name="Test Migration",
            direction=MigrationDirection.FORWARD,
            status=MigrationStatus.SUCCESS,
            started_at=datetime.now(),
            checksum="abc123",
        )

        await manager._record_migration_status(record)

        mock_client.bulk_insert.assert_called_once_with("schema_migrations", [record.to_clickhouse_record()])

    async def test_execute_migration_success(self, manager, mock_client):
        """Test successful migration execution."""
        migration = MockMigration("test_001", should_succeed=True)

        result = await manager._execute_migration(migration, MigrationDirection.FORWARD, 1000)

        assert result["success"] is True
        assert migration.forward_called is True

        # Should have recorded migration status twice (start and end)
        assert mock_client.bulk_insert.call_count == 2

    async def test_execute_migration_failure(self, manager, mock_client):
        """Test failed migration execution."""
        migration = MockMigration("test_001", should_succeed=False)

        result = await manager._execute_migration(migration, MigrationDirection.FORWARD, 1000)

        assert result["success"] is False
        assert len(result["errors"]) > 0

        # Should still record migration status (start and end)
        assert mock_client.bulk_insert.call_count == 2


@pytest.mark.integration
class TestMigrationIntegration:
    """Integration tests for migration framework (require actual ClickHouse)."""

    @pytest.mark.skip(reason="Requires running ClickHouse instance")
    async def test_real_initial_schema_migration(self):
        """Test initial schema migration against real ClickHouse."""
        from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient

        client = ClickHouseClient(database="test_migrations")
        manager = MigrationManager(client)

        try:
            await client.initialize()

            # Test forward migration
            result = await manager.migrate_up(target_migration="001_initial_schema")
            assert result["success"] is True
            assert len(result["migrations_applied"]) == 1

            # Verify tables were created
            tables_result = await client.execute_query("SHOW TABLES FROM test_migrations")
            table_names = [row["name"] for row in tables_result]
            assert "enhanced_token_summaries" in table_names
            assert "enhanced_token_details" in table_names
            assert "enhanced_analysis_metadata" in table_names

            # Test migration status
            status = await manager.get_migration_status()
            assert status["current_version"] == "1.0"
            assert len(status["applied_migrations"]) == 1

            # Test rollback
            rollback_result = await manager.migrate_down("000_initial")
            assert rollback_result["success"] is True

        finally:
            # Cleanup
            try:
                await client.execute_query("DROP DATABASE IF EXISTS test_migrations")
                await client.close()
            except Exception:
                pass
