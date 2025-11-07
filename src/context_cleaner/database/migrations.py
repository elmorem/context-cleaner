"""
Database Migration Framework for Enhanced Token Analysis Bridge.

Provides schema version tracking, forward/backward migration support,
migration validation, and rollback capabilities with batch processing
for large datasets.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import hashlib
import json

from .clickhouse_schema import ClickHouseSchema, SchemaVersion
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PARTIAL = "partial"


class MigrationDirection(Enum):
    """Migration direction."""

    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass
class MigrationRecord:
    """Record of migration execution in database."""

    migration_id: str
    version: str
    name: str
    direction: MigrationDirection
    status: MigrationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    checksum: str = ""
    batch_size: int = 1000
    records_processed: int = 0
    execution_time_seconds: float = 0.0

    def to_clickhouse_record(self) -> Dict[str, Any]:
        """Convert to ClickHouse record format."""
        return {
            "migration_id": self.migration_id,
            "version": self.version,
            "name": self.name,
            "direction": self.direction.value,
            "status": self.status.value,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": (
                self.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.completed_at
                else None
            ),
            "error_message": self.error_message or "",
            "checksum": self.checksum,
            "batch_size": self.batch_size,
            "records_processed": self.records_processed,
            "execution_time_seconds": self.execution_time_seconds,
        }


class Migration(ABC):
    """Base class for database migrations."""

    def __init__(
        self, migration_id: str, version: str, name: str, description: str = ""
    ):
        self.migration_id = migration_id
        self.version = version
        self.name = name
        self.description = description
        self.checksum = self._calculate_checksum()

    @abstractmethod
    async def forward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute forward migration.

        Args:
            client: ClickHouse client
            batch_size: Batch size for processing

        Returns:
            Migration result dictionary
        """
        pass

    @abstractmethod
    async def backward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute backward migration (rollback).

        Args:
            client: ClickHouse client
            batch_size: Batch size for processing

        Returns:
            Migration result dictionary
        """
        pass

    @abstractmethod
    async def validate(self, client: ClickHouseClient) -> Dict[str, Any]:
        """
        Validate migration can be safely executed.

        Args:
            client: ClickHouse client

        Returns:
            Validation result dictionary
        """
        pass

    def _calculate_checksum(self) -> str:
        """Calculate checksum for migration integrity."""
        content = f"{self.migration_id}:{self.version}:{self.name}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class InitialSchemaMigration(Migration):
    """Initial schema creation migration."""

    def __init__(self):
        super().__init__(
            migration_id="001_initial_schema",
            version="1.0",
            name="Create Enhanced Token Analysis Schema",
            description="Create initial tables, indexes, and views for enhanced token analysis",
        )
        self.schema = ClickHouseSchema()

    async def forward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Create initial schema."""
        result = {
            "success": True,
            "tables_created": [],
            "indexes_created": [],
            "views_created": [],
            "errors": [],
        }

        try:
            # Create tables
            schemas = self.schema.get_table_schemas(client.database)
            table_order = [
                "enhanced_token_summaries",
                "enhanced_token_details",
                "enhanced_analysis_metadata",
            ]

            for table_name in table_order:
                try:
                    await client.execute_query(schemas[table_name].create_sql)
                    result["tables_created"].append(table_name)
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    error_msg = f"Failed to create table {table_name}: {e}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)

            # Create indexes
            for table_name in table_order:
                index_sqls = self.schema.get_index_sql(table_name, client.database)
                for i, index_sql in enumerate(index_sqls):
                    try:
                        await client.execute_query(index_sql)
                        result["indexes_created"].append(f"{table_name}_idx_{i}")
                    except Exception as e:
                        error_msg = f"Failed to create index for {table_name}: {e}"
                        result["errors"].append(error_msg)
                        logger.error(error_msg)

            # Create views
            for view_name in self.schema.VIEWS.keys():
                try:
                    view_sql = self.schema.get_view_sql(view_name, client.database)
                    await client.execute_query(view_sql)
                    result["views_created"].append(view_name)
                    logger.info(f"Created view: {view_name}")
                except Exception as e:
                    error_msg = f"Failed to create view {view_name}: {e}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)

            if result["errors"]:
                result["success"] = False

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Migration failed: {e}")

        return result

    async def backward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Drop initial schema."""
        result = {
            "success": True,
            "tables_dropped": [],
            "views_dropped": [],
            "errors": [],
        }

        try:
            # Drop views first
            for view_name in self.schema.VIEWS.keys():
                try:
                    drop_sql = f"DROP VIEW IF EXISTS {client.database}.{view_name}"
                    await client.execute_query(drop_sql)
                    result["views_dropped"].append(view_name)
                except Exception as e:
                    result["errors"].append(f"Failed to drop view {view_name}: {e}")

            # Drop tables in reverse order
            table_order = [
                "enhanced_analysis_metadata",
                "enhanced_token_details",
                "enhanced_token_summaries",
            ]
            for table_name in table_order:
                try:
                    drop_sql = f"DROP TABLE IF EXISTS {client.database}.{table_name}"
                    await client.execute_query(drop_sql)
                    result["tables_dropped"].append(table_name)
                except Exception as e:
                    result["errors"].append(f"Failed to drop table {table_name}: {e}")

            if result["errors"]:
                result["success"] = False

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Rollback failed: {e}")

        return result

    async def validate(self, client: ClickHouseClient) -> Dict[str, Any]:
        """Validate initial schema migration."""
        validation = {
            "can_execute": True,
            "warnings": [],
            "requirements_met": True,
            "disk_space_sufficient": True,
            "conflicts": [],
        }

        try:
            # Check for existing tables
            existing_tables_query = f"SHOW TABLES FROM {client.database}"
            existing_tables_result = await client.execute_query(existing_tables_query)
            existing_tables = [row["name"] for row in existing_tables_result]

            expected_tables = set(self.schema.get_table_schemas().keys())
            conflicts = [table for table in existing_tables if table in expected_tables]

            if conflicts:
                validation["conflicts"] = conflicts
                validation["warnings"].append(
                    f"Existing tables will be affected: {', '.join(conflicts)}"
                )

            # Check database permissions
            try:
                await client.execute_query("SELECT 1")
                validation["requirements_met"] = True
            except Exception as e:
                validation["requirements_met"] = False
                validation["can_execute"] = False
                validation["warnings"].append(f"Database access issue: {e}")

        except Exception as e:
            validation["can_execute"] = False
            validation["warnings"].append(f"Validation failed: {e}")

        return validation


class PerformanceOptimizationMigration(Migration):
    """Migration for performance optimizations."""

    def __init__(self):
        super().__init__(
            migration_id="002_performance_optimization",
            version="1.1",
            name="Performance Optimization",
            description="Add additional indexes and optimize table settings for 2.7B token dataset",
        )

    async def forward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Apply performance optimizations."""
        result = {"success": True, "optimizations_applied": [], "errors": []}

        try:
            # Add skip indexes for large dataset optimization
            skip_indexes = [
                f"ALTER TABLE {client.database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_session_id_bloom session_id TYPE bloom_filter(0.01) GRANULARITY 8192",
                f"ALTER TABLE {client.database}.enhanced_token_summaries ADD INDEX IF NOT EXISTS idx_content_categories_map content_categories TYPE bloom_filter(0.1) GRANULARITY 8192",
                f"ALTER TABLE {client.database}.enhanced_token_details ADD INDEX IF NOT EXISTS idx_file_path_ngram file_path TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 8192",
            ]

            for index_sql in skip_indexes:
                try:
                    await client.execute_query(index_sql)
                    result["optimizations_applied"].append(
                        index_sql.split("ADD INDEX")[1].split("TYPE")[0].strip()
                    )
                except Exception as e:
                    result["errors"].append(f"Failed to add skip index: {e}")

            # Optimize table settings for large datasets
            settings_updates = [
                f"ALTER TABLE {client.database}.enhanced_token_summaries MODIFY SETTING merge_with_ttl_timeout = 86400",
                f"ALTER TABLE {client.database}.enhanced_token_details MODIFY SETTING merge_with_ttl_timeout = 86400",
            ]

            for setting_sql in settings_updates:
                try:
                    await client.execute_query(setting_sql)
                    result["optimizations_applied"].append(
                        "table_settings_optimization"
                    )
                except Exception as e:
                    result["errors"].append(f"Failed to update table settings: {e}")

            if result["errors"]:
                result["success"] = False

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Performance optimization failed: {e}")

        return result

    async def backward(
        self, client: ClickHouseClient, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Remove performance optimizations."""
        result = {"success": True, "optimizations_removed": [], "errors": []}

        try:
            # Remove skip indexes
            drop_indexes = [
                f"ALTER TABLE {client.database}.enhanced_token_summaries DROP INDEX IF EXISTS idx_session_id_bloom",
                f"ALTER TABLE {client.database}.enhanced_token_summaries DROP INDEX IF EXISTS idx_content_categories_map",
                f"ALTER TABLE {client.database}.enhanced_token_details DROP INDEX IF EXISTS idx_file_path_ngram",
            ]

            for drop_sql in drop_indexes:
                try:
                    await client.execute_query(drop_sql)
                    result["optimizations_removed"].append(
                        drop_sql.split("DROP INDEX")[1].strip()
                    )
                except Exception as e:
                    result["errors"].append(f"Failed to drop skip index: {e}")

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Performance optimization rollback failed: {e}")

        return result

    async def validate(self, client: ClickHouseClient) -> Dict[str, Any]:
        """Validate performance optimization migration."""
        validation = {
            "can_execute": True,
            "warnings": [],
            "table_sizes_acceptable": True,
            "indexes_ready": True,
        }

        try:
            # Check table exists
            tables_query = f"SHOW TABLES FROM {client.database} LIKE 'enhanced_token_%'"
            tables_result = await client.execute_query(tables_query)

            if len(tables_result) < 3:
                validation["can_execute"] = False
                validation["warnings"].append(
                    "Required tables not found - run initial migration first"
                )

            # Check current table sizes for optimization feasibility
            size_query = f"""
            SELECT table, sum(rows) as total_rows, formatReadableSize(sum(bytes_on_disk)) as size
            FROM system.parts 
            WHERE database = '{client.database}' AND table LIKE 'enhanced_token_%' AND active = 1
            GROUP BY table
            """

            size_result = await client.execute_query(size_query)
            for row in size_result:
                if row["total_rows"] > 1000000:  # Large table threshold
                    validation["warnings"].append(
                        f"Table {row['table']} has {row['total_rows']} rows - optimization recommended"
                    )

        except Exception as e:
            validation["can_execute"] = False
            validation["warnings"].append(f"Validation failed: {e}")

        return validation


class MigrationManager:
    """
    Migration manager for Enhanced Token Analysis Bridge database.

    Handles migration execution, version tracking, rollback operations,
    and batch processing for large datasets.
    """

    def __init__(self, client: ClickHouseClient):
        """
        Initialize migration manager.

        Args:
            client: ClickHouse client instance
        """
        self.client = client
        self.migrations: Dict[str, Migration] = {}
        self.migration_order: List[str] = []

        # Register built-in migrations
        self._register_builtin_migrations()

    def _register_builtin_migrations(self):
        """Register built-in migrations."""
        initial_migration = InitialSchemaMigration()
        perf_migration = PerformanceOptimizationMigration()

        self.register_migration(initial_migration)
        self.register_migration(perf_migration)

    def register_migration(self, migration: Migration):
        """
        Register a migration.

        Args:
            migration: Migration instance to register
        """
        self.migrations[migration.migration_id] = migration
        if migration.migration_id not in self.migration_order:
            self.migration_order.append(migration.migration_id)

        logger.info(
            f"Registered migration: {migration.migration_id} ({migration.name})"
        )

    async def initialize_migration_tracking(self):
        """Initialize migration tracking table."""
        migration_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.client.database}.schema_migrations (
            migration_id String,
            version String,
            name String,
            direction Enum8('forward' = 1, 'backward' = 2),
            status Enum8('pending' = 1, 'running' = 2, 'success' = 3, 'failed' = 4, 'rolled_back' = 5, 'partial' = 6),
            started_at DateTime64(3),
            completed_at Nullable(DateTime64(3)),
            error_message String DEFAULT '',
            checksum String,
            batch_size UInt32,
            records_processed UInt64,
            execution_time_seconds Float64
        )
        ENGINE = ReplacingMergeTree(started_at)
        PRIMARY KEY (migration_id, direction)
        ORDER BY (migration_id, direction, started_at);
        """

        await self.client.execute_query(migration_table_sql)
        logger.info("Migration tracking table initialized")

    async def get_applied_migrations(self) -> List[MigrationRecord]:
        """Get list of successfully applied migrations."""
        query = f"""
        SELECT * FROM {self.client.database}.schema_migrations 
        WHERE status = 'success' AND direction = 'forward'
        ORDER BY started_at
        """

        try:
            results = await self.client.execute_query(query)
            return [
                MigrationRecord(
                    migration_id=row["migration_id"],
                    version=row["version"],
                    name=row["name"],
                    direction=MigrationDirection(row["direction"]),
                    status=MigrationStatus(row["status"]),
                    started_at=datetime.fromisoformat(
                        row["started_at"].replace("Z", "+00:00")
                    ),
                    completed_at=(
                        datetime.fromisoformat(
                            row["completed_at"].replace("Z", "+00:00")
                        )
                        if row["completed_at"]
                        else None
                    ),
                    error_message=row["error_message"],
                    checksum=row["checksum"],
                    batch_size=row["batch_size"],
                    records_processed=row["records_processed"],
                    execution_time_seconds=row["execution_time_seconds"],
                )
                for row in results
            ]
        except Exception as e:
            logger.warning(f"Could not retrieve applied migrations: {e}")
            return []

    async def get_pending_migrations(
        self, applied_migrations: Optional[List[MigrationRecord]] = None
    ) -> List[Migration]:
        """Get list of migrations that need to be applied."""
        if applied_migrations is None:
            applied_migrations = await self.get_applied_migrations()
        applied_ids = {m.migration_id for m in applied_migrations}

        pending = []
        for migration_id in self.migration_order:
            if migration_id not in applied_ids:
                pending.append(self.migrations[migration_id])

        return pending

    async def migrate_up(
        self, target_migration: Optional[str] = None, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute forward migrations.

        Args:
            target_migration: Stop at this migration (None = apply all)
            batch_size: Batch size for processing

        Returns:
            Migration execution result
        """
        await self.initialize_migration_tracking()

        result = {
            "success": True,
            "migrations_applied": [],
            "migrations_failed": [],
            "total_execution_time": 0.0,
            "errors": [],
        }

        start_time = datetime.now()

        try:
            pending_migrations = await self.get_pending_migrations()

            for idx, migration in enumerate(pending_migrations):
                at_target = (
                    target_migration is not None
                    and migration.migration_id == target_migration
                )

                logger.info(
                    f"Applying migration: {migration.migration_id} ({migration.name})"
                )

                # Validate migration
                validation = await migration.validate(self.client)
                if not validation.get("requirements_met", True):
                    error_msg = (
                        f"Migration {migration.migration_id} validation failed: "
                        f"{validation.get('warnings', [])}"
                    )
                    result["errors"].append(error_msg)
                    result["migrations_failed"].append(migration.migration_id)
                    break

                if not validation.get("can_execute", True):
                    warning_msg = (
                        f"Migration {migration.migration_id} has warnings: "
                        f"{validation.get('warnings', [])}"
                    )
                    result["errors"].append(warning_msg)
                    logger.warning(warning_msg)
                    if idx == len(pending_migrations) - 1:
                        result["migrations_failed"].append(migration.migration_id)
                        if at_target:
                            break
                        continue

                # Execute migration
                migration_result = await self._execute_migration(
                    migration, MigrationDirection.FORWARD, batch_size
                )

                if migration_result["success"]:
                    result["migrations_applied"].append(migration.migration_id)
                    logger.info(
                        f"Successfully applied migration: {migration.migration_id}"
                    )
                    if at_target:
                        break
                else:
                    result["migrations_failed"].append(migration.migration_id)
                    result["errors"].extend(migration_result.get("errors", []))

                    # Stop on first failure to maintain consistency
                    break

            # Update overall result
            if result["migrations_failed"]:
                result["success"] = False

            result["total_execution_time"] = (
                datetime.now() - start_time
            ).total_seconds()

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Migration failed: {e}")
            logger.error(f"Migration execution failed: {e}", exc_info=True)

        return result

    async def migrate_down(
        self, target_migration: str, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Execute backward migrations (rollback).

        Args:
            target_migration: Rollback to this migration
            batch_size: Batch size for processing

        Returns:
            Rollback execution result
        """
        result = {
            "success": True,
            "migrations_rolled_back": [],
            "migrations_failed": [],
            "total_execution_time": 0.0,
            "errors": [],
        }

        start_time = datetime.now()

        try:
            applied_migrations = await self.get_applied_migrations()

            # Find migrations to rollback (in reverse order)
            rollback_migrations = []
            target_found = False

            for migration_record in reversed(applied_migrations):
                if migration_record.migration_id == target_migration:
                    target_found = True
                    break
                rollback_migrations.append(migration_record.migration_id)

            if not target_found:
                result["success"] = False
                result["errors"].append(
                    f"Target migration {target_migration} not found in applied migrations"
                )
                return result

            # Execute rollbacks
            for migration_id in rollback_migrations:
                if migration_id not in self.migrations:
                    result["errors"].append(
                        f"Migration {migration_id} not registered - cannot rollback"
                    )
                    result["migrations_failed"].append(migration_id)
                    continue

                migration = self.migrations[migration_id]
                logger.info(
                    f"Rolling back migration: {migration_id} ({migration.name})"
                )

                # Execute rollback
                migration_result = await self._execute_migration(
                    migration, MigrationDirection.BACKWARD, batch_size
                )

                if migration_result["success"]:
                    result["migrations_rolled_back"].append(migration_id)
                    logger.info(f"Successfully rolled back migration: {migration_id}")
                else:
                    result["migrations_failed"].append(migration_id)
                    result["errors"].extend(migration_result.get("errors", []))
                    break  # Stop on first failure

            if result["migrations_failed"]:
                result["success"] = False

            result["total_execution_time"] = (
                datetime.now() - start_time
            ).total_seconds()

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Rollback failed: {e}")
            logger.error(f"Migration rollback failed: {e}", exc_info=True)

        return result

    async def _execute_migration(
        self, migration: Migration, direction: MigrationDirection, batch_size: int
    ) -> Dict[str, Any]:
        """Execute a single migration in the specified direction."""
        migration_record = MigrationRecord(
            migration_id=migration.migration_id,
            version=migration.version,
            name=migration.name,
            direction=direction,
            status=MigrationStatus.RUNNING,
            started_at=datetime.now(),
            checksum=migration.checksum,
            batch_size=batch_size,
        )

        # Record migration start
        await self._record_migration_status(migration_record)

        try:
            # Execute migration
            if direction == MigrationDirection.FORWARD:
                result = await migration.forward(self.client, batch_size)
            else:
                result = await migration.backward(self.client, batch_size)

            # Update migration record
            migration_record.completed_at = datetime.now()
            migration_record.execution_time_seconds = (
                migration_record.completed_at - migration_record.started_at
            ).total_seconds()

            if result.get("success", False):
                migration_record.status = MigrationStatus.SUCCESS
            else:
                migration_record.status = MigrationStatus.FAILED
                migration_record.error_message = "; ".join(result.get("errors", []))

            # Record final status
            await self._record_migration_status(migration_record)

            return result

        except Exception as e:
            migration_record.status = MigrationStatus.FAILED
            migration_record.error_message = str(e)
            migration_record.completed_at = datetime.now()
            migration_record.execution_time_seconds = (
                migration_record.completed_at - migration_record.started_at
            ).total_seconds()

            await self._record_migration_status(migration_record)

            return {"success": False, "errors": [str(e)]}

    async def _record_migration_status(self, migration_record: MigrationRecord):
        """Record migration status in tracking table."""
        try:
            record_data = [migration_record.to_clickhouse_record()]
            await self.client.bulk_insert("schema_migrations", record_data)
        except Exception as e:
            logger.error(f"Failed to record migration status: {e}")

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get comprehensive migration status."""
        status = {
            "current_version": "unknown",
            "applied_migrations": [],
            "pending_migrations": [],
            "failed_migrations": [],
            "total_migrations": len(self.migrations),
            "schema_health": "unknown",
        }

        try:
            applied = await self.get_applied_migrations()
            pending = await self.get_pending_migrations(applied)

            status["applied_migrations"] = [
                {
                    "id": m.migration_id,
                    "name": m.name,
                    "version": m.version,
                    "applied_at": m.started_at.isoformat(),
                    "execution_time": m.execution_time_seconds,
                }
                for m in applied
            ]

            status["pending_migrations"] = [
                {
                    "id": m.migration_id,
                    "name": m.name,
                    "version": m.version,
                    "description": m.description,
                }
                for m in pending
            ]

            # Get current version from latest applied migration
            if applied:
                status["current_version"] = applied[-1].version

            # Get failed migrations
            failed_query = f"""
            SELECT migration_id, name, error_message, started_at
            FROM {self.client.database}.schema_migrations 
            WHERE status = 'failed'
            ORDER BY started_at DESC
            LIMIT 10
            """

            try:
                failed_results = await self.client.execute_query(failed_query)
                status["failed_migrations"] = failed_results
            except Exception:
                pass

            # Determine schema health
            if not pending and not status["failed_migrations"]:
                status["schema_health"] = "healthy"
            elif pending:
                status["schema_health"] = "outdated"
            else:
                status["schema_health"] = "error"

        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            status["error"] = str(e)

        return status
