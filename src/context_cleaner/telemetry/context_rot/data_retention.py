"""
Data Retention and Cleanup Policies for Context Rot Meter.

This module implements comprehensive data retention policies to ensure
GDPR compliance, privacy protection, and efficient storage management.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import json

from .health_monitor import get_health_monitor, HealthStatus

logger = logging.getLogger(__name__)


class RetentionPolicy(Enum):
    """Data retention policy types."""

    GDPR_STRICT = "gdpr_strict"  # 30 days maximum
    PRIVACY_FOCUSED = "privacy_focused"  # 90 days maximum
    ANALYTICS_BALANCED = "analytics_balanced"  # 180 days maximum
    RESEARCH_EXTENDED = "research_extended"  # 365 days maximum


class DataCategory(Enum):
    """Categories of data with different retention requirements."""

    PII_SENSITIVE = "pii_sensitive"  # User messages, personal data
    ANALYTICS_METRICS = "analytics_metrics"  # Rot scores, aggregated metrics
    SYSTEM_LOGS = "system_logs"  # Error logs, system events
    USER_PREFERENCES = "user_preferences"  # Thresholds, settings
    AUDIT_RECORDS = "audit_records"  # Security, compliance logs


@dataclass
class RetentionRule:
    """Defines retention rules for specific data categories."""

    category: DataCategory
    policy: RetentionPolicy
    retention_days: int
    archive_days: Optional[int]  # Days before archiving (if supported)
    anonymize_after_days: Optional[int]  # Days before anonymization
    hard_delete_days: int  # Days before permanent deletion
    requires_user_consent: bool = False
    description: str = ""


@dataclass
class CleanupResult:
    """Results of a cleanup operation."""

    category: DataCategory
    records_processed: int
    records_deleted: int
    records_anonymized: int
    records_archived: int
    storage_freed_mb: float
    execution_time_seconds: float
    errors: List[str]


class DataRetentionManager:
    """Manages data retention policies and cleanup operations."""

    def __init__(
        self,
        clickhouse_client,
        default_policy: RetentionPolicy = RetentionPolicy.PRIVACY_FOCUSED,
    ):
        self.clickhouse_client = clickhouse_client
        self.default_policy = default_policy
        self.retention_rules = self._initialize_retention_rules()
        self.health_monitor = get_health_monitor()
        self._cleanup_in_progress = False

        # Performance tracking
        self._last_cleanup_time = None
        self._cleanup_history = []

    def _initialize_retention_rules(self) -> Dict[DataCategory, RetentionRule]:
        """Initialize default retention rules based on policy."""
        base_rules = {
            RetentionPolicy.GDPR_STRICT: {
                DataCategory.PII_SENSITIVE: RetentionRule(
                    category=DataCategory.PII_SENSITIVE,
                    policy=RetentionPolicy.GDPR_STRICT,
                    retention_days=7,
                    anonymize_after_days=3,
                    hard_delete_days=30,
                    requires_user_consent=False,
                    description="GDPR strict: PII deleted within 30 days",
                ),
                DataCategory.ANALYTICS_METRICS: RetentionRule(
                    category=DataCategory.ANALYTICS_METRICS,
                    policy=RetentionPolicy.GDPR_STRICT,
                    retention_days=14,
                    anonymize_after_days=7,
                    hard_delete_days=30,
                    description="GDPR strict: Analytics data anonymized and deleted quickly",
                ),
                DataCategory.SYSTEM_LOGS: RetentionRule(
                    category=DataCategory.SYSTEM_LOGS,
                    policy=RetentionPolicy.GDPR_STRICT,
                    retention_days=30,
                    hard_delete_days=30,
                    description="GDPR strict: System logs retained 30 days",
                ),
                DataCategory.USER_PREFERENCES: RetentionRule(
                    category=DataCategory.USER_PREFERENCES,
                    policy=RetentionPolicy.GDPR_STRICT,
                    retention_days=30,
                    hard_delete_days=30,
                    requires_user_consent=True,
                    description="GDPR strict: User preferences deleted on request",
                ),
                DataCategory.AUDIT_RECORDS: RetentionRule(
                    category=DataCategory.AUDIT_RECORDS,
                    policy=RetentionPolicy.GDPR_STRICT,
                    retention_days=30,
                    hard_delete_days=30,
                    description="GDPR strict: Audit records retained 30 days minimum",
                ),
            },
            RetentionPolicy.PRIVACY_FOCUSED: {
                DataCategory.PII_SENSITIVE: RetentionRule(
                    category=DataCategory.PII_SENSITIVE,
                    policy=RetentionPolicy.PRIVACY_FOCUSED,
                    retention_days=30,
                    anonymize_after_days=14,
                    hard_delete_days=90,
                    description="Privacy focused: PII anonymized after 2 weeks",
                ),
                DataCategory.ANALYTICS_METRICS: RetentionRule(
                    category=DataCategory.ANALYTICS_METRICS,
                    policy=RetentionPolicy.PRIVACY_FOCUSED,
                    retention_days=60,
                    anonymize_after_days=30,
                    hard_delete_days=90,
                    description="Privacy focused: Analytics anonymized monthly",
                ),
                DataCategory.SYSTEM_LOGS: RetentionRule(
                    category=DataCategory.SYSTEM_LOGS,
                    policy=RetentionPolicy.PRIVACY_FOCUSED,
                    retention_days=90,
                    hard_delete_days=90,
                    description="Privacy focused: System logs 90 days",
                ),
                DataCategory.USER_PREFERENCES: RetentionRule(
                    category=DataCategory.USER_PREFERENCES,
                    policy=RetentionPolicy.PRIVACY_FOCUSED,
                    retention_days=180,
                    hard_delete_days=180,
                    requires_user_consent=True,
                    description="Privacy focused: Preferences retained 6 months with consent",
                ),
                DataCategory.AUDIT_RECORDS: RetentionRule(
                    category=DataCategory.AUDIT_RECORDS,
                    policy=RetentionPolicy.PRIVACY_FOCUSED,
                    retention_days=90,
                    hard_delete_days=90,
                    description="Privacy focused: Audit records 90 days",
                ),
            },
            RetentionPolicy.ANALYTICS_BALANCED: {
                DataCategory.PII_SENSITIVE: RetentionRule(
                    category=DataCategory.PII_SENSITIVE,
                    policy=RetentionPolicy.ANALYTICS_BALANCED,
                    retention_days=90,
                    anonymize_after_days=30,
                    hard_delete_days=180,
                    description="Balanced: PII anonymized after 30 days for analytics",
                ),
                DataCategory.ANALYTICS_METRICS: RetentionRule(
                    category=DataCategory.ANALYTICS_METRICS,
                    policy=RetentionPolicy.ANALYTICS_BALANCED,
                    retention_days=120,
                    anonymize_after_days=90,
                    archive_days=60,
                    hard_delete_days=180,
                    description="Balanced: Analytics archived after 60 days",
                ),
                DataCategory.SYSTEM_LOGS: RetentionRule(
                    category=DataCategory.SYSTEM_LOGS,
                    policy=RetentionPolicy.ANALYTICS_BALANCED,
                    retention_days=180,
                    archive_days=90,
                    hard_delete_days=180,
                    description="Balanced: System logs archived after 90 days",
                ),
                DataCategory.USER_PREFERENCES: RetentionRule(
                    category=DataCategory.USER_PREFERENCES,
                    policy=RetentionPolicy.ANALYTICS_BALANCED,
                    retention_days=365,
                    hard_delete_days=365,
                    requires_user_consent=True,
                    description="Balanced: User preferences retained 1 year",
                ),
                DataCategory.AUDIT_RECORDS: RetentionRule(
                    category=DataCategory.AUDIT_RECORDS,
                    policy=RetentionPolicy.ANALYTICS_BALANCED,
                    retention_days=180,
                    hard_delete_days=180,
                    description="Balanced: Audit records 6 months",
                ),
            },
            RetentionPolicy.RESEARCH_EXTENDED: {
                DataCategory.PII_SENSITIVE: RetentionRule(
                    category=DataCategory.PII_SENSITIVE,
                    policy=RetentionPolicy.RESEARCH_EXTENDED,
                    retention_days=30,  # Still short for PII
                    anonymize_after_days=14,
                    hard_delete_days=90,
                    description="Research: PII still anonymized quickly for privacy",
                ),
                DataCategory.ANALYTICS_METRICS: RetentionRule(
                    category=DataCategory.ANALYTICS_METRICS,
                    policy=RetentionPolicy.RESEARCH_EXTENDED,
                    retention_days=365,
                    anonymize_after_days=180,
                    archive_days=120,
                    hard_delete_days=365,
                    description="Research: Analytics retained 1 year for research",
                ),
                DataCategory.SYSTEM_LOGS: RetentionRule(
                    category=DataCategory.SYSTEM_LOGS,
                    policy=RetentionPolicy.RESEARCH_EXTENDED,
                    retention_days=365,
                    archive_days=180,
                    hard_delete_days=365,
                    description="Research: Extended system logs for analysis",
                ),
                DataCategory.USER_PREFERENCES: RetentionRule(
                    category=DataCategory.USER_PREFERENCES,
                    policy=RetentionPolicy.RESEARCH_EXTENDED,
                    retention_days=365,
                    hard_delete_days=365,
                    requires_user_consent=True,
                    description="Research: Extended preference retention",
                ),
                DataCategory.AUDIT_RECORDS: RetentionRule(
                    category=DataCategory.AUDIT_RECORDS,
                    policy=RetentionPolicy.RESEARCH_EXTENDED,
                    retention_days=365,
                    hard_delete_days=365,
                    description="Research: Extended audit retention",
                ),
            },
        }

        return base_rules.get(
            self.default_policy, base_rules[RetentionPolicy.PRIVACY_FOCUSED]
        )

    def get_retention_rule(self, category: DataCategory) -> RetentionRule:
        """Get retention rule for data category."""
        return self.retention_rules.get(category, self._get_default_rule(category))

    def _get_default_rule(self, category: DataCategory) -> RetentionRule:
        """Get default retention rule if none specified."""
        return RetentionRule(
            category=category,
            policy=self.default_policy,
            retention_days=90,
            hard_delete_days=90,
            description=f"Default rule for {category.value}",
        )

    async def execute_retention_policy(
        self, category: DataCategory = None, dry_run: bool = False
    ) -> List[CleanupResult]:
        """Execute retention policy for specified category or all categories."""
        if self._cleanup_in_progress:
            raise RuntimeError("Cleanup operation already in progress")

        self._cleanup_in_progress = True
        start_time = time.time()
        results = []

        try:
            # Record cleanup start
            component_monitor = self.health_monitor.get_component_monitor(
                "data_retention"
            )
            component_monitor.heartbeat()

            categories_to_process = [category] if category else list(DataCategory)

            for cat in categories_to_process:
                rule = self.get_retention_rule(cat)

                logger.info(
                    f"Executing retention policy for {cat.value} (dry_run={dry_run})"
                )

                try:
                    result = await self._cleanup_category(rule, dry_run)
                    results.append(result)

                    # Record successful operation
                    operation_time = time.time() - start_time
                    component_monitor.record_operation(
                        f"cleanup_{cat.value}", operation_time * 1000, success=True
                    )

                except Exception as e:
                    error_msg = f"Cleanup failed for {cat.value}: {str(e)}"
                    logger.error(error_msg)

                    # Record failed operation
                    component_monitor.record_error(error_msg)

                    # Create error result
                    error_result = CleanupResult(
                        category=cat,
                        records_processed=0,
                        records_deleted=0,
                        records_anonymized=0,
                        records_archived=0,
                        storage_freed_mb=0.0,
                        execution_time_seconds=0.0,
                        errors=[error_msg],
                    )
                    results.append(error_result)

            # Update cleanup history
            self._last_cleanup_time = datetime.now()
            self._cleanup_history.append(
                {
                    "timestamp": self._last_cleanup_time,
                    "results": results,
                    "dry_run": dry_run,
                }
            )

            # Keep only last 100 cleanup records
            if len(self._cleanup_history) > 100:
                self._cleanup_history = self._cleanup_history[-100:]

            return results

        finally:
            self._cleanup_in_progress = False

    async def _cleanup_category(
        self, rule: RetentionRule, dry_run: bool
    ) -> CleanupResult:
        """Clean up data for specific category based on retention rule."""
        start_time = time.time()
        result = CleanupResult(
            category=rule.category,
            records_processed=0,
            records_deleted=0,
            records_anonymized=0,
            records_archived=0,
            storage_freed_mb=0.0,
            execution_time_seconds=0.0,
            errors=[],
        )

        try:
            # Determine table and columns based on category
            table_config = self._get_table_config(rule.category)

            if not table_config:
                result.errors.append(
                    f"No table configuration for category {rule.category.value}"
                )
                return result

            # Step 1: Anonymize old data (if rule specifies)
            if rule.anonymize_after_days:
                anonymize_count = await self._anonymize_old_data(
                    table_config, rule.anonymize_after_days, dry_run
                )
                result.records_anonymized = anonymize_count

            # Step 2: Archive data (if rule specifies)
            if rule.archive_days:
                archive_count = await self._archive_old_data(
                    table_config, rule.archive_days, dry_run
                )
                result.records_archived = archive_count

            # Step 3: Delete data past hard delete threshold
            delete_count, storage_freed = await self._delete_old_data(
                table_config, rule.hard_delete_days, dry_run
            )
            result.records_deleted = delete_count
            result.storage_freed_mb = storage_freed

            # Step 4: Count total processed
            total_count = await self._count_category_records(table_config)
            result.records_processed = total_count

        except Exception as e:
            error_msg = f"Category cleanup error: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg)

        finally:
            result.execution_time_seconds = time.time() - start_time

        return result

    def _get_table_config(self, category: DataCategory) -> Optional[Dict[str, Any]]:
        """Get database table configuration for data category."""
        configs = {
            DataCategory.PII_SENSITIVE: {
                "table": "otel.context_rot_metrics",
                "timestamp_column": "timestamp",
                "pii_columns": ["user_message", "file_paths"],
                "user_id_column": "session_id",
            },
            DataCategory.ANALYTICS_METRICS: {
                "table": "otel.context_rot_metrics",
                "timestamp_column": "timestamp",
                "anonymize_columns": ["session_id"],
                "user_id_column": "session_id",
            },
            DataCategory.SYSTEM_LOGS: {
                "table": "otel.system_logs",
                "timestamp_column": "timestamp",
                "anonymize_columns": ["user_id", "session_id"],
            },
            DataCategory.USER_PREFERENCES: {
                "table": "otel.user_baselines",
                "timestamp_column": "last_updated",
                "user_id_column": "user_id",
            },
            DataCategory.AUDIT_RECORDS: {
                "table": "otel.audit_log",
                "timestamp_column": "timestamp",
                "anonymize_columns": ["user_id", "session_id"],
            },
        }

        return configs.get(category)

    async def _anonymize_old_data(
        self, table_config: Dict[str, Any], days_old: int, dry_run: bool
    ) -> int:
        """Anonymize data older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        table = table_config["table"]
        timestamp_col = table_config["timestamp_column"]

        # Count records to anonymize
        count_query = f"""
        SELECT COUNT(*) as count
        FROM {table}
        WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        count_result = await self.clickhouse_client.execute_query(count_query)
        record_count = count_result[0]["count"] if count_result else 0

        if record_count == 0 or dry_run:
            logger.info(
                f"Would anonymize {record_count} records in {table} (dry_run={dry_run})"
            )
            return record_count

        # Anonymize PII columns
        pii_columns = table_config.get("pii_columns", [])
        anonymize_columns = table_config.get("anonymize_columns", [])

        updates = []
        for col in pii_columns:
            updates.append(f"{col} = '[ANONYMIZED]'")

        for col in anonymize_columns:
            updates.append(f"{col} = concat('anon_', cityHash64({col}))")

        if updates:
            anonymize_query = f"""
            ALTER TABLE {table} 
            UPDATE {', '.join(updates)}
            WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
            """

            await self.clickhouse_client.execute_query(anonymize_query)
            logger.info(f"Anonymized {record_count} records in {table}")

        return record_count

    async def _archive_old_data(
        self, table_config: Dict[str, Any], days_old: int, dry_run: bool
    ) -> int:
        """Archive data older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        table = table_config["table"]
        timestamp_col = table_config["timestamp_column"]
        archive_table = f"{table}_archive"

        # Count records to archive
        count_query = f"""
        SELECT COUNT(*) as count
        FROM {table}
        WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        count_result = await self.clickhouse_client.execute_query(count_query)
        record_count = count_result[0]["count"] if count_result else 0

        if record_count == 0 or dry_run:
            logger.info(
                f"Would archive {record_count} records from {table} (dry_run={dry_run})"
            )
            return record_count

        # Create archive table if it doesn't exist (copy structure)
        create_archive_query = f"""
        CREATE TABLE IF NOT EXISTS {archive_table} AS {table} ENGINE = MergeTree()
        ORDER BY {timestamp_col}
        """

        await self.clickhouse_client.execute_query(create_archive_query)

        # Insert into archive
        archive_query = f"""
        INSERT INTO {archive_table}
        SELECT * FROM {table}
        WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        await self.clickhouse_client.execute_query(archive_query)

        # Delete from main table
        delete_query = f"""
        ALTER TABLE {table} 
        DELETE WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        await self.clickhouse_client.execute_query(delete_query)

        logger.info(f"Archived {record_count} records from {table} to {archive_table}")
        return record_count

    async def _delete_old_data(
        self, table_config: Dict[str, Any], days_old: int, dry_run: bool
    ) -> Tuple[int, float]:
        """Delete data older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        table = table_config["table"]
        timestamp_col = table_config["timestamp_column"]

        # Count records and estimate storage before deletion
        count_query = f"""
        SELECT 
            COUNT(*) as count,
            sum(length(toString(*))) as estimated_bytes
        FROM {table}
        WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        count_result = await self.clickhouse_client.execute_query(count_query)
        if not count_result:
            return 0, 0.0

        record_count = count_result[0]["count"]
        estimated_bytes = count_result[0].get("estimated_bytes", 0)
        storage_freed_mb = estimated_bytes / (1024 * 1024) if estimated_bytes else 0

        if record_count == 0 or dry_run:
            logger.info(
                f"Would delete {record_count} records from {table}, freeing ~{storage_freed_mb:.2f}MB (dry_run={dry_run})"
            )
            return record_count, storage_freed_mb

        # Delete old records
        delete_query = f"""
        ALTER TABLE {table} 
        DELETE WHERE {timestamp_col} < '{cutoff_date.isoformat()}'
        """

        await self.clickhouse_client.execute_query(delete_query)

        logger.info(
            f"Deleted {record_count} records from {table}, freed ~{storage_freed_mb:.2f}MB"
        )
        return record_count, storage_freed_mb

    async def _count_category_records(self, table_config: Dict[str, Any]) -> int:
        """Count total records in category table."""
        table = table_config["table"]

        try:
            count_query = f"SELECT COUNT(*) as count FROM {table}"
            result = await self.clickhouse_client.execute_query(count_query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to count records in {table}: {e}")
            return 0

    async def get_retention_status(self) -> Dict[str, Any]:
        """Get current data retention status and statistics."""
        status = {
            "policy": self.default_policy.value,
            "last_cleanup": (
                self._last_cleanup_time.isoformat() if self._last_cleanup_time else None
            ),
            "cleanup_in_progress": self._cleanup_in_progress,
            "categories": {},
            "storage_summary": {
                "total_records": 0,
                "estimated_storage_mb": 0.0,
                "oldest_record": None,
                "newest_record": None,
            },
        }

        # Get status for each category
        for category in DataCategory:
            rule = self.get_retention_rule(category)
            table_config = self._get_table_config(category)

            if table_config:
                try:
                    # Get category statistics
                    stats_query = f"""
                    SELECT 
                        COUNT(*) as count,
                        min({table_config['timestamp_column']}) as oldest,
                        max({table_config['timestamp_column']}) as newest,
                        sum(length(toString(*))) as estimated_bytes
                    FROM {table_config['table']}
                    """

                    stats_result = await self.clickhouse_client.execute_query(
                        stats_query
                    )

                    if stats_result:
                        stats = stats_result[0]
                        category_stats = {
                            "retention_days": rule.retention_days,
                            "hard_delete_days": rule.hard_delete_days,
                            "record_count": stats["count"],
                            "oldest_record": stats["oldest"],
                            "newest_record": stats["newest"],
                            "estimated_storage_mb": (
                                stats.get("estimated_bytes", 0) or 0
                            )
                            / (1024 * 1024),
                            "table": table_config["table"],
                        }

                        status["categories"][category.value] = category_stats

                        # Update totals
                        status["storage_summary"]["total_records"] += stats["count"]
                        status["storage_summary"][
                            "estimated_storage_mb"
                        ] += category_stats["estimated_storage_mb"]

                        # Update oldest/newest across all categories
                        if stats["oldest"]:
                            if (
                                not status["storage_summary"]["oldest_record"]
                                or stats["oldest"]
                                < status["storage_summary"]["oldest_record"]
                            ):
                                status["storage_summary"]["oldest_record"] = stats[
                                    "oldest"
                                ]

                        if stats["newest"]:
                            if (
                                not status["storage_summary"]["newest_record"]
                                or stats["newest"]
                                > status["storage_summary"]["newest_record"]
                            ):
                                status["storage_summary"]["newest_record"] = stats[
                                    "newest"
                                ]

                except Exception as e:
                    logger.error(f"Failed to get stats for {category.value}: {e}")
                    status["categories"][category.value] = {
                        "error": str(e),
                        "retention_days": rule.retention_days,
                        "hard_delete_days": rule.hard_delete_days,
                    }

        return status

    async def request_user_data_deletion(
        self, user_id: str, category: DataCategory = None
    ) -> Dict[str, Any]:
        """Handle user request for data deletion (GDPR right to erasure)."""
        logger.info(f"Processing data deletion request for user {user_id}")

        deletion_results = []
        categories_to_delete = [category] if category else list(DataCategory)

        for cat in categories_to_delete:
            table_config = self._get_table_config(cat)
            if not table_config or "user_id_column" not in table_config:
                continue

            try:
                user_col = table_config["user_id_column"]
                table = table_config["table"]

                # Count user records
                count_query = f"""
                SELECT COUNT(*) as count
                FROM {table}
                WHERE {user_col} = '{user_id}'
                """

                count_result = await self.clickhouse_client.execute_query(count_query)
                record_count = count_result[0]["count"] if count_result else 0

                if record_count > 0:
                    # Delete user records
                    delete_query = f"""
                    ALTER TABLE {table}
                    DELETE WHERE {user_col} = '{user_id}'
                    """

                    await self.clickhouse_client.execute_query(delete_query)

                    deletion_results.append(
                        {
                            "category": cat.value,
                            "table": table,
                            "records_deleted": record_count,
                        }
                    )

                    logger.info(
                        f"Deleted {record_count} records for user {user_id} in {cat.value}"
                    )

            except Exception as e:
                error_msg = (
                    f"Failed to delete {cat.value} data for user {user_id}: {str(e)}"
                )
                logger.error(error_msg)
                deletion_results.append(
                    {"category": cat.value, "error": error_msg, "records_deleted": 0}
                )

        return {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "results": deletion_results,
            "total_records_deleted": sum(
                r.get("records_deleted", 0) for r in deletion_results
            ),
        }

    def get_cleanup_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent cleanup operation history."""
        return self._cleanup_history[-limit:] if self._cleanup_history else []


# Global data retention manager instance
_retention_manager: Optional[DataRetentionManager] = None


def get_retention_manager(
    clickhouse_client=None, policy: RetentionPolicy = RetentionPolicy.PRIVACY_FOCUSED
) -> DataRetentionManager:
    """Get global data retention manager instance."""
    global _retention_manager
    if _retention_manager is None and clickhouse_client:
        _retention_manager = DataRetentionManager(clickhouse_client, policy)
    return _retention_manager
