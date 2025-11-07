"""
Database Initialization for Enhanced Token Analysis Bridge.

Provides database and table creation, validation, and environment-specific
configuration for the ClickHouse Enhanced Token Analysis schema.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import os
import socket

from .clickhouse_schema import ClickHouseSchema, SchemaVersion
from ..telemetry.clients.clickhouse_client import ClickHouseClient, ConnectionStatus
from ..telemetry.context_rot.config import get_config

logger = logging.getLogger(__name__)


class InitializationStatus(Enum):
    """Database initialization status."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
    CONNECTION_FAILED = "connection_failed"


@dataclass
class InitializationResult:
    """Result of database initialization operation."""

    status: InitializationStatus
    message: str
    tables_created: List[str] = None
    indexes_created: List[str] = None
    views_created: List[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    execution_time_seconds: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.tables_created is None:
            self.tables_created = []
        if self.indexes_created is None:
            self.indexes_created = []
        if self.views_created is None:
            self.views_created = []
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.timestamp is None:
            self.timestamp = datetime.now()


class DatabaseInitializer:
    """
    Database initialization manager for Enhanced Token Analysis Bridge.

    Handles database creation, schema deployment, validation, and environment
    configuration for development, testing, and production environments.
    """

    def __init__(
        self,
        clickhouse_client: Optional[ClickHouseClient] = None,
        database_name: str = "otel",
        environment: str = "development",
        dry_run: bool = False,
    ):
        """
        Initialize database initializer.

        Args:
            clickhouse_client: ClickHouse client instance
            database_name: Target database name
            environment: Environment type (development, testing, production)
            dry_run: If True, only validate without making changes
        """
        self.client = clickhouse_client or ClickHouseClient(database=database_name)
        self.database_name = database_name
        self.environment = environment
        self.dry_run = dry_run
        self.schema = ClickHouseSchema()
        self._last_connection_failure_reason: Optional[str] = None
        self._last_connection_failure_detail: Optional[str] = None

        logger.info(
            f"Initialized DatabaseInitializer for {environment} environment "
            f"(database: {database_name}, dry_run: {dry_run})"
        )

    async def initialize_database(self, force: bool = False) -> InitializationResult:
        """
        Initialize complete database schema.

        Args:
            force: If True, recreate existing tables

        Returns:
            Initialization result with status and details
        """
        start_time = datetime.now()
        result = InitializationResult(
            status=InitializationStatus.FAILED, message="Initialization not started"
        )

        try:
            logger.info(
                f"Starting database initialization (force={force}, dry_run={self.dry_run})"
            )

            # Step 1: Verify connection
            self._last_connection_failure_reason = None
            self._last_connection_failure_detail = None
            connection_ok = await self._verify_connection()
            if (
                not connection_ok
                and self._last_connection_failure_reason == "version_query_empty"
            ):
                # Attempt lightweight probe before failing hard
                connection_ok = await self._basic_connection_probe()
                if connection_ok:
                    logger.warning(
                        "Version check failed but basic probe succeeded; continuing initialization"
                    )

            if not connection_ok:
                reason = self._last_connection_failure_reason
                detail = self._last_connection_failure_detail

                if reason == "exception":
                    result.status = InitializationStatus.FAILED
                    error_message = detail or "Unknown connection error"
                    result.message = (
                        f"Initialization failed with exception: {error_message}"
                    )
                    result.errors.append(error_message)
                else:
                    result.status = InitializationStatus.CONNECTION_FAILED
                    result.message = detail or "Failed to establish database connection"

                return result

            # Step 2: Check existing schema
            existing_tables = await self._get_existing_tables()
            schema_conflicts = self._check_schema_conflicts(existing_tables, force)

            if schema_conflicts and not force:
                result.status = InitializationStatus.VALIDATION_FAILED
                result.message = (
                    f"Schema conflicts detected: {', '.join(schema_conflicts)}"
                )
                result.warnings.extend(schema_conflicts)
                return result

            # Step 3: Create database if needed
            if not self.dry_run:
                await self._create_database_if_needed()

            # Step 4: Create tables
            tables_result = await self._create_tables(force)
            result.tables_created = tables_result["created"]
            result.errors.extend(tables_result["errors"])

            # Step 5: Create indexes
            indexes_result = await self._create_indexes()
            result.indexes_created = indexes_result["created"]
            result.errors.extend(indexes_result["errors"])

            # Step 6: Create views
            views_result = await self._create_views()
            result.views_created = views_result["created"]
            result.errors.extend(views_result["errors"])

            # Step 7: Set up schema versioning
            if not self.dry_run:
                await self._setup_schema_versioning()

            # Step 8: Validate final state
            validation_result = await self._validate_final_schema()
            if not validation_result["valid"]:
                result.warnings.extend(validation_result["warnings"])

            # Determine final status
            if result.errors:
                if (
                    result.tables_created
                    or result.indexes_created
                    or result.views_created
                ):
                    result.status = InitializationStatus.PARTIAL_SUCCESS
                    result.message = (
                        f"Partial success: {len(result.errors)} errors occurred"
                    )
                else:
                    result.status = InitializationStatus.FAILED
                    result.message = (
                        f"Initialization failed: {len(result.errors)} errors"
                    )
            else:
                result.status = InitializationStatus.SUCCESS
                result.message = "Database initialization completed successfully"

            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time_seconds = execution_time

            logger.info(
                f"Database initialization completed: {result.status.value} "
                f"in {execution_time:.2f}s"
            )

            return result

        except Exception as e:
            result.status = InitializationStatus.FAILED
            result.message = f"Initialization failed with exception: {e}"
            result.errors.append(str(e))
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            return result

    async def _verify_connection(self, *, require_version: bool = True) -> bool:
        """Verify ClickHouse connection is working."""
        try:
            if hasattr(self.client, "initialize"):
                await self.client.initialize()

            health_check = await self.client.health_check()
            if not health_check:
                logger.error("Health check failed during connection verification")
                self._last_connection_failure_reason = "health_check_failed"
                self._last_connection_failure_detail = (
                    "Health check failed during connection verification"
                )
                return False

            if require_version:
                # Test basic query capability
                result = await self.client.execute_query("SELECT version()")
                if not result:
                    logger.error("Version query failed during connection verification")
                    self._last_connection_failure_reason = "version_query_empty"
                    self._last_connection_failure_detail = (
                        "Version query returned no results"
                    )
                    return False

                version = result[0].get("version()", "unknown")
                logger.info(f"Successfully connected to ClickHouse version: {version}")
            else:
                logger.info(
                    "Successfully completed lightweight connection verification"
                )
            self._last_connection_failure_reason = None
            self._last_connection_failure_detail = None
            return True

        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            self._last_connection_failure_reason = "exception"
            self._last_connection_failure_detail = str(e)
            return False

    async def _basic_connection_probe(self) -> bool:
        """Fallback probe to verify ClickHouse connectivity when detailed checks fail."""
        try:
            probe_result = await self.client.health_check()
            if probe_result:
                self._last_connection_failure_reason = None
                self._last_connection_failure_detail = None
                return True
            self._last_connection_failure_reason = "probe_failed"
            self._last_connection_failure_detail = "Basic connection probe failed"
            return False
        except Exception as exc:
            logger.error(f"Basic connection probe failed: {exc}")
            self._last_connection_failure_reason = "probe_failed"
            self._last_connection_failure_detail = str(exc)
            return False

    async def _get_existing_tables(self) -> List[str]:
        """Get list of existing tables in the database."""
        try:
            query = f"SHOW TABLES FROM {self.database_name}"
            results = await self.client.execute_query(query)
            return [row["name"] for row in results]
        except Exception as e:
            logger.warning(f"Could not retrieve existing tables: {e}")
            return []

    def _check_schema_conflicts(
        self, existing_tables: List[str], force: bool
    ) -> List[str]:
        """Check for schema conflicts with existing tables."""
        conflicts = []
        expected_tables = set(self.schema.get_table_schemas().keys())

        for table in existing_tables:
            if table in expected_tables and not force:
                conflicts.append(f"Table '{table}' already exists")

        return conflicts

    async def _create_database_if_needed(self):
        """Create database if it doesn't exist."""
        try:
            query = f"CREATE DATABASE IF NOT EXISTS {self.database_name}"
            await self.client.execute_query(query)
            logger.info(f"Ensured database '{self.database_name}' exists")
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            raise

    async def _create_tables(self, force: bool) -> Dict[str, Any]:
        """Create all tables in the schema."""
        result = {"created": [], "errors": []}
        schemas = self.schema.get_table_schemas(self.database_name)

        # Create tables in dependency order
        table_order = [
            "enhanced_token_summaries",
            "enhanced_token_details",
            "enhanced_analysis_metadata",
        ]

        for table_name in table_order:
            try:
                if table_name not in schemas:
                    result["errors"].append(f"Unknown table schema: {table_name}")
                    continue

                schema = schemas[table_name]

                # Drop table if force is enabled
                if force and not self.dry_run:
                    drop_query = (
                        f"DROP TABLE IF EXISTS {self.database_name}.{table_name}"
                    )
                    await self.client.execute_query(drop_query)
                    logger.info(f"Dropped existing table: {table_name}")

                # Create table
                if not self.dry_run:
                    await self.client.execute_query(schema.create_sql)

                result["created"].append(table_name)
                logger.info(
                    f"{'[DRY RUN] ' if self.dry_run else ''}Created table: {table_name}"
                )

            except Exception as e:
                error_msg = f"Failed to create table {table_name}: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)

        return result

    async def _create_indexes(self) -> Dict[str, Any]:
        """Create all indexes for optimal query performance."""
        result = {"created": [], "errors": []}

        for table_name in self.schema.INDEXES.keys():
            try:
                index_sqls = self.schema.get_index_sql(table_name, self.database_name)

                for index_sql in index_sqls:
                    if not self.dry_run:
                        await self.client.execute_query(index_sql)

                    # Extract index name for logging
                    index_name = f"{table_name}_index_{len(result['created'])}"
                    result["created"].append(index_name)

                logger.info(
                    f"{'[DRY RUN] ' if self.dry_run else ''}"
                    f"Created {len(index_sqls)} indexes for {table_name}"
                )

            except Exception as e:
                error_msg = f"Failed to create indexes for {table_name}: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)

        return result

    async def _create_views(self) -> Dict[str, Any]:
        """Create all materialized views for dashboard consumption."""
        result = {"created": [], "errors": []}

        for view_name in self.schema.VIEWS.keys():
            try:
                view_sql = self.schema.get_view_sql(view_name, self.database_name)

                if not self.dry_run:
                    await self.client.execute_query(view_sql)

                result["created"].append(view_name)
                logger.info(
                    f"{'[DRY RUN] ' if self.dry_run else ''}Created view: {view_name}"
                )

            except Exception as e:
                error_msg = f"Failed to create view {view_name}: {e}"
                result["errors"].append(error_msg)
                logger.error(error_msg)

        return result

    async def _setup_schema_versioning(self):
        """Set up schema version tracking."""
        try:
            version_sql = self.schema.get_schema_version_sql(self.database_name)
            await self.client.execute_query(version_sql)
            logger.info("Schema version tracking initialized")
        except Exception as e:
            logger.warning(f"Failed to set up schema versioning: {e}")

    async def _validate_final_schema(self) -> Dict[str, Any]:
        """Validate the final schema state."""
        result = {"valid": True, "warnings": []}

        try:
            # Check all expected tables exist
            existing_tables = await self._get_existing_tables()
            expected_tables = set(self.schema.get_table_schemas().keys())
            missing_tables = expected_tables - set(existing_tables)

            if missing_tables:
                result["valid"] = False
                result["warnings"].extend(
                    [f"Missing table: {table}" for table in missing_tables]
                )

            # Run consistency checks
            if not self.dry_run:
                consistency_checks = self.schema.get_data_consistency_check_sql(
                    self.database_name
                )
                for check_name, check_sql in consistency_checks.items():
                    try:
                        # Run consistency check (will be empty for new database)
                        await self.client.execute_query(check_sql)
                        logger.debug(f"Consistency check '{check_name}' passed")
                    except Exception as e:
                        result["warnings"].append(
                            f"Consistency check '{check_name}' failed: {e}"
                        )

        except Exception as e:
            result["valid"] = False
            result["warnings"].append(f"Schema validation error: {e}")

        return result

    async def validate_existing_schema(self) -> Dict[str, Any]:
        """
        Validate existing schema against expected structure.

        Returns:
            Validation result with compatibility status
        """
        validation_result = {
            "compatible": True,
            "schema_version": "unknown",
            "missing_tables": [],
            "missing_indexes": [],
            "missing_views": [],
            "compatibility_issues": [],
            "recommendations": [],
        }

        try:
            # Check connection
            if not await self._verify_connection(require_version=False):
                validation_result["compatible"] = False
                validation_result["compatibility_issues"].append(
                    "Cannot connect to database"
                )
                return validation_result

            # Get existing tables
            existing_tables = await self._get_existing_tables()
            expected_tables = set(self.schema.get_table_schemas().keys())

            # Check for missing tables
            missing_tables = expected_tables - set(existing_tables)
            validation_result["missing_tables"] = list(missing_tables)

            if missing_tables:
                validation_result["compatible"] = False
                validation_result["recommendations"].append(
                    f"Run database initialization to create missing tables: {', '.join(missing_tables)}"
                )

            # Check schema version
            try:
                version_query = f"SELECT version FROM {self.database_name}.schema_version WHERE component = 'enhanced_token_analysis' ORDER BY applied_at DESC LIMIT 1"
                version_result = await self.client.execute_query(version_query)
                if version_result:
                    validation_result["schema_version"] = version_result[0]["version"]
                else:
                    validation_result["schema_version"] = "not_tracked"
                    validation_result["recommendations"].append(
                        "Schema version is not being tracked"
                    )
            except Exception:
                validation_result["schema_version"] = "unknown"

            # Performance monitoring checks
            perf_queries = self.schema.get_performance_monitoring_sql(
                self.database_name
            )
            for check_name, check_sql in perf_queries.items():
                try:
                    await self.client.execute_query(check_sql)
                except Exception as e:
                    validation_result["compatibility_issues"].append(
                        f"Performance monitoring query '{check_name}' failed: {e}"
                    )

        except Exception as e:
            validation_result["compatible"] = False
            validation_result["compatibility_issues"].append(
                f"Schema validation failed: {e}"
            )

        return validation_result

    @classmethod
    def get_environment_config(cls, environment: str) -> Dict[str, Any]:
        """
        Get environment-specific configuration.

        Args:
            environment: Environment type (development, testing, production)

        Returns:
            Environment configuration dictionary
        """
        # Get centralized configuration for production environment variables
        config = get_config()

        configs = {
            "development": {
                "database_name": "otel_dev",
                "host": "localhost",
                "port": 9000,
                "max_connections": 5,
                "query_timeout": 30,
                "enable_health_monitoring": True,
                "batch_size": 100,
                "ttl_days": 7,
            },
            "testing": {
                "database_name": "otel_test",
                "host": "localhost",
                "port": 9000,
                "max_connections": 2,
                "query_timeout": 10,
                "enable_health_monitoring": False,
                "batch_size": 50,
                "ttl_days": 1,
            },
            "production": {
                "database_name": "otel",
                "host": config.database.clickhouse_host,
                "port": config.database.clickhouse_port,
                "max_connections": 10,
                "query_timeout": 60,
                "enable_health_monitoring": True,
                "batch_size": 1000,
                "ttl_days": 90,
            },
        }

        return configs.get(environment, configs["development"])

    async def create_client_from_environment(
        self, environment: str
    ) -> ClickHouseClient:
        """
        Create ClickHouse client configured for specific environment.

        Args:
            environment: Environment type

        Returns:
            Configured ClickHouse client
        """
        config = self.get_environment_config(environment)

        client = ClickHouseClient(
            host=config["host"],
            port=config["port"],
            database=config["database_name"],
            max_connections=config["max_connections"],
            query_timeout=config["query_timeout"],
            enable_health_monitoring=config["enable_health_monitoring"],
        )

        await client.initialize()
        return client
