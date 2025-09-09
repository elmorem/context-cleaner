"""
Data Validation

Provides pre-migration validation (file integrity, schema compliance),
post-migration verification (record counts, token totals, data consistency),
cross-validation between JSONL and ClickHouse data, validation reports
with discrepancy analysis, and data quality metrics.

Ensures migration integrity and enables comprehensive validation reporting.
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib

from ..services.token_analysis_bridge import TokenAnalysisBridge
from ..analysis.enhanced_token_counter import EnhancedTokenCounterService
from ..models.token_bridge_models import SessionTokenMetrics
from .jsonl_discovery import JSONLDiscoveryService, JSONLFileInfo
from .data_extraction import DataExtractionEngine

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue found during checks."""

    severity: str  # "error", "warning", "info"
    category: str  # "data_integrity", "count_mismatch", "schema_violation", etc.
    description: str
    context: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "context": self.context,
            "file_path": self.file_path,
            "session_id": self.session_id,
        }


@dataclass
class ValidationResult:
    """Result of migration validation operation."""

    # Validation metadata
    validation_id: str
    validation_type: str  # "pre_migration", "post_migration", "cross_validation"
    start_time: datetime
    end_time: datetime

    # Validation scope
    files_validated: int = 0
    sessions_validated: int = 0
    records_validated: int = 0

    # Validation results
    validation_passed: bool = False
    accuracy_score: float = 0.0

    # Count verification
    source_token_count: Optional[int] = None
    database_token_count: Optional[int] = None
    token_count_variance: Optional[float] = None

    source_session_count: Optional[int] = None
    database_session_count: Optional[int] = None
    session_count_variance: Optional[float] = None

    # Data quality metrics
    integrity_score: float = 0.0
    consistency_score: float = 0.0
    completeness_score: float = 0.0

    # Issues found
    issues: List[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    # Performance metrics
    validation_duration_seconds: float = 0.0
    validation_rate_records_per_second: float = 0.0

    @property
    def overall_score(self) -> float:
        """Calculate overall validation score."""
        return (self.accuracy_score + self.integrity_score + self.consistency_score + self.completeness_score) / 4

    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.error_count += 1
        elif issue.severity == "warning":
            self.warning_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "validation_id": self.validation_id,
            "validation_type": self.validation_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "validation_duration_seconds": self.validation_duration_seconds,
            "validation_passed": self.validation_passed,
            "overall_score": self.overall_score,
            # Scope
            "files_validated": self.files_validated,
            "sessions_validated": self.sessions_validated,
            "records_validated": self.records_validated,
            # Scores
            "accuracy_score": self.accuracy_score,
            "integrity_score": self.integrity_score,
            "consistency_score": self.consistency_score,
            "completeness_score": self.completeness_score,
            # Count verification
            "source_token_count": self.source_token_count,
            "database_token_count": self.database_token_count,
            "token_count_variance": self.token_count_variance,
            "source_session_count": self.source_session_count,
            "database_session_count": self.database_session_count,
            "session_count_variance": self.session_count_variance,
            # Issues
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
            # Performance
            "validation_rate_records_per_second": self.validation_rate_records_per_second,
        }


class MigrationValidator:
    """
    Comprehensive validation service for migration operations.

    Provides pre-migration validation, post-migration verification,
    cross-validation between source and target systems, and detailed
    validation reporting with discrepancy analysis.
    """

    def __init__(
        self,
        bridge_service: Optional[TokenAnalysisBridge] = None,
        enhanced_counter: Optional[EnhancedTokenCounterService] = None,
        discovery_service: Optional[JSONLDiscoveryService] = None,
        extraction_engine: Optional[DataExtractionEngine] = None,
        # Validation thresholds
        token_variance_threshold: float = 0.1,  # 0.1% variance allowed
        session_variance_threshold: float = 1.0,  # 1% variance allowed
        integrity_threshold: float = 95.0,  # 95% integrity required
        consistency_threshold: float = 90.0,  # 90% consistency required
    ):
        self.bridge_service = bridge_service or TokenAnalysisBridge()
        self.enhanced_counter = enhanced_counter or EnhancedTokenCounterService()
        self.discovery_service = discovery_service or JSONLDiscoveryService()
        self.extraction_engine = extraction_engine or DataExtractionEngine()

        # Thresholds
        self.token_variance_threshold = token_variance_threshold
        self.session_variance_threshold = session_variance_threshold
        self.integrity_threshold = integrity_threshold
        self.consistency_threshold = consistency_threshold

        logger.info("Migration validator initialized")

    async def validate_pre_migration(
        self,
        source_directories: List[str],
        check_file_integrity: bool = True,
        check_schema_compliance: bool = True,
        check_access_permissions: bool = True,
    ) -> ValidationResult:
        """
        Validate source data before migration.

        Args:
            source_directories: Directories containing JSONL files
            check_file_integrity: Verify file integrity and readability
            check_schema_compliance: Check JSONL schema compliance
            check_access_permissions: Verify file access permissions

        Returns:
            ValidationResult with pre-migration validation status
        """
        start_time = datetime.now()
        validation_id = f"pre_migration_{start_time.strftime('%Y%m%d_%H%M%S')}"

        result = ValidationResult(
            validation_id=validation_id,
            validation_type="pre_migration",
            start_time=start_time,
            end_time=start_time,
        )

        logger.info("Starting pre-migration validation...")

        try:
            # Discover files
            discovery_result = await self.discovery_service.discover_files(
                search_paths=source_directories, sort_by="modified_desc"
            )

            result.files_validated = discovery_result.total_files_found

            if discovery_result.total_files_found == 0:
                result.add_issue(
                    ValidationIssue(
                        severity="error",
                        category="data_availability",
                        description="No JSONL files found in source directories",
                        context={"directories": source_directories},
                    )
                )
                result.validation_passed = False
                return result

            # File integrity checks
            if check_file_integrity:
                await self._validate_file_integrity(discovery_result.processing_manifest, result)

            # Schema compliance checks
            if check_schema_compliance:
                await self._validate_schema_compliance(discovery_result.processing_manifest, result)

            # Access permission checks
            if check_access_permissions:
                await self._validate_access_permissions(discovery_result.processing_manifest, result)

            # Calculate scores
            result.integrity_score = self._calculate_integrity_score(result)
            result.completeness_score = self._calculate_completeness_score(discovery_result, result)

            # Determine if validation passed
            result.validation_passed = result.error_count == 0 and result.integrity_score >= self.integrity_threshold

            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()

            logger.info(f"Pre-migration validation complete: {'PASSED' if result.validation_passed else 'FAILED'}")
            return result

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="error",
                    category="validation_error",
                    description=f"Pre-migration validation failed: {str(e)}",
                )
            )
            result.validation_passed = False
            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()
            logger.error(f"Pre-migration validation failed: {e}")
            return result

    async def validate_migration_integrity(
        self,
        sample_size: int = 100,
        full_validation: bool = False,
        tolerance: float = 0.001,
        verify_counts: bool = True,
    ) -> ValidationResult:
        """
        Validate migrated data integrity against source analysis.

        Args:
            sample_size: Number of sessions to validate (if not full)
            full_validation: Validate all migrated data
            tolerance: Acceptable variance in token counts
            verify_counts: Verify token and session counts

        Returns:
            ValidationResult with detailed validation metrics
        """
        start_time = datetime.now()
        validation_id = f"post_migration_{start_time.strftime('%Y%m%d_%H%M%S')}"

        result = ValidationResult(
            validation_id=validation_id,
            validation_type="post_migration",
            start_time=start_time,
            end_time=start_time,
        )

        logger.info(f"Starting post-migration validation (sample_size={sample_size}, full={full_validation})...")

        try:
            # Count verification
            if verify_counts:
                await self._verify_token_counts(result, tolerance)
                await self._verify_session_counts(result, tolerance)

            # Data integrity checks
            await self._validate_database_integrity(result, sample_size, full_validation)

            # Cross-validation with source data
            await self._cross_validate_with_source(result, sample_size)

            # Calculate final scores
            result.accuracy_score = self._calculate_accuracy_score(result)
            result.consistency_score = self._calculate_consistency_score(result)

            # Determine if validation passed
            result.validation_passed = (
                result.error_count == 0
                and result.overall_score >= 85.0  # 85% overall score threshold
                and (result.token_count_variance is None or result.token_count_variance <= tolerance * 100)
            )

            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()

            if result.validation_duration_seconds > 0:
                result.validation_rate_records_per_second = (
                    result.records_validated / result.validation_duration_seconds
                )

            logger.info(f"Post-migration validation complete: {'PASSED' if result.validation_passed else 'FAILED'}")
            return result

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="error",
                    category="validation_error",
                    description=f"Post-migration validation failed: {str(e)}",
                )
            )
            result.validation_passed = False
            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()
            logger.error(f"Post-migration validation failed: {e}")
            return result

    async def cross_validate_data(
        self,
        source_directories: List[str],
        sample_sessions: Optional[List[str]] = None,
        deep_validation: bool = False,
    ) -> ValidationResult:
        """
        Cross-validate data between source JSONL files and database.

        Args:
            source_directories: Source directories for comparison
            sample_sessions: Specific sessions to validate
            deep_validation: Perform detailed content validation

        Returns:
            ValidationResult with cross-validation results
        """
        start_time = datetime.now()
        validation_id = f"cross_validation_{start_time.strftime('%Y%m%d_%H%M%S')}"

        result = ValidationResult(
            validation_id=validation_id,
            validation_type="cross_validation",
            start_time=start_time,
            end_time=start_time,
        )

        logger.info("Starting cross-validation between source and database...")

        try:
            # Get enhanced analysis from source
            source_analysis = await self.enhanced_counter.analyze_comprehensive_token_usage()

            # Get database statistics
            database_stats = await self._get_database_statistics()

            # Compare overall counts
            result.source_token_count = source_analysis.total_calculated_tokens
            result.database_token_count = database_stats.get("total_tokens", 0)

            if result.source_token_count > 0:
                variance = (
                    abs(result.database_token_count - result.source_token_count) / result.source_token_count * 100
                )
                result.token_count_variance = variance

                if variance > self.token_variance_threshold:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="count_mismatch",
                            description=f"Token count variance {variance:.3f}% exceeds threshold {self.token_variance_threshold}%",
                            context={
                                "source_tokens": result.source_token_count,
                                "database_tokens": result.database_token_count,
                                "variance_percent": variance,
                            },
                        )
                    )

            # Session-level validation
            if sample_sessions:
                await self._validate_specific_sessions(sample_sessions, result, deep_validation)
            else:
                await self._validate_random_sessions(
                    source_analysis, result, sample_size=50, deep_validation=deep_validation
                )

            # Calculate scores
            result.accuracy_score = self._calculate_accuracy_score(result)
            result.consistency_score = self._calculate_consistency_score(result)
            result.integrity_score = self._calculate_integrity_score(result)

            result.validation_passed = result.error_count == 0 and result.overall_score >= 85.0

            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()

            logger.info(f"Cross-validation complete: {'PASSED' if result.validation_passed else 'FAILED'}")
            return result

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="error", category="validation_error", description=f"Cross-validation failed: {str(e)}"
                )
            )
            result.validation_passed = False
            result.end_time = datetime.now()
            result.validation_duration_seconds = (result.end_time - result.start_time).total_seconds()
            logger.error(f"Cross-validation failed: {e}")
            return result

    async def _validate_file_integrity(self, files: List[JSONLFileInfo], result: ValidationResult):
        """Validate file integrity and readability."""
        for file_info in files:
            try:
                # Check if file exists and is readable
                file_path = Path(file_info.path)
                if not file_path.exists():
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="file_access",
                            description="File does not exist",
                            file_path=file_info.path,
                        )
                    )
                    continue

                if not file_path.is_file():
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="file_access",
                            description="Path is not a file",
                            file_path=file_info.path,
                        )
                    )
                    continue

                # Check file size
                if file_info.size_bytes == 0:
                    result.add_issue(
                        ValidationIssue(
                            severity="warning",
                            category="file_integrity",
                            description="File is empty",
                            file_path=file_info.path,
                        )
                    )

                # Verify file hash if available
                if file_info.file_hash:
                    current_hash = await self._calculate_file_hash(file_info.path)
                    if current_hash != file_info.file_hash:
                        result.add_issue(
                            ValidationIssue(
                                severity="error",
                                category="file_integrity",
                                description="File hash mismatch - file may be corrupted",
                                file_path=file_info.path,
                                context={"expected_hash": file_info.file_hash, "actual_hash": current_hash},
                            )
                        )

            except Exception as e:
                result.add_issue(
                    ValidationIssue(
                        severity="error",
                        category="file_access",
                        description=f"File integrity check failed: {str(e)}",
                        file_path=file_info.path,
                    )
                )

    async def _validate_schema_compliance(self, files: List[JSONLFileInfo], result: ValidationResult):
        """Validate JSONL schema compliance."""
        for file_info in files[:10]:  # Sample first 10 files
            try:
                line_count = 0
                async with asyncio.timeout(30):  # 30 second timeout per file
                    with open(file_info.path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if line_count >= 100:  # Check first 100 lines
                                break

                            line = line.strip()
                            if not line:
                                continue

                            try:
                                entry = json.loads(line)

                                # Basic schema validation
                                if not isinstance(entry, dict):
                                    result.add_issue(
                                        ValidationIssue(
                                            severity="error",
                                            category="schema_violation",
                                            description=f"Invalid JSON structure at line {line_num}",
                                            file_path=file_info.path,
                                            context={"line_number": line_num},
                                        )
                                    )

                                # Check for required fields (flexible approach)
                                if not any(key in entry for key in ["type", "message", "content", "data"]):
                                    result.add_issue(
                                        ValidationIssue(
                                            severity="warning",
                                            category="schema_compliance",
                                            description=f"Entry missing common fields at line {line_num}",
                                            file_path=file_info.path,
                                            context={"line_number": line_num, "available_keys": list(entry.keys())},
                                        )
                                    )

                                line_count += 1

                            except json.JSONDecodeError as e:
                                result.add_issue(
                                    ValidationIssue(
                                        severity="error",
                                        category="schema_violation",
                                        description=f"Invalid JSON at line {line_num}: {str(e)}",
                                        file_path=file_info.path,
                                        context={"line_number": line_num},
                                    )
                                )

            except Exception as e:
                result.add_issue(
                    ValidationIssue(
                        severity="error",
                        category="schema_validation",
                        description=f"Schema validation failed: {str(e)}",
                        file_path=file_info.path,
                    )
                )

    async def _validate_access_permissions(self, files: List[JSONLFileInfo], result: ValidationResult):
        """Validate file access permissions."""
        for file_info in files:
            try:
                file_path = Path(file_info.path)

                # Check read permission
                if not file_path.stat().st_mode & 0o400:  # Read permission for owner
                    result.add_issue(
                        ValidationIssue(
                            severity="warning",
                            category="file_permissions",
                            description="File may not be readable",
                            file_path=file_info.path,
                        )
                    )

                # Try to actually read the file
                try:
                    with open(file_path, "r") as f:
                        f.read(100)  # Read first 100 chars
                except PermissionError:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="file_permissions",
                            description="Permission denied when reading file",
                            file_path=file_info.path,
                        )
                    )

            except Exception as e:
                result.add_issue(
                    ValidationIssue(
                        severity="warning",
                        category="file_permissions",
                        description=f"Permission check failed: {str(e)}",
                        file_path=file_info.path,
                    )
                )

    async def _verify_token_counts(self, result: ValidationResult, tolerance: float):
        """Verify token counts between source and database."""
        try:
            # Get source token count from enhanced analysis
            source_analysis = await self.enhanced_counter.analyze_comprehensive_token_usage()
            result.source_token_count = source_analysis.total_calculated_tokens

            # Get database token count
            database_stats = await self._get_database_statistics()
            result.database_token_count = database_stats.get("total_tokens", 0)

            if result.source_token_count > 0:
                variance = abs(result.database_token_count - result.source_token_count) / result.source_token_count
                result.token_count_variance = variance * 100

                if variance > tolerance:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="count_mismatch",
                            description=f"Token count variance {variance*100:.3f}% exceeds tolerance {tolerance*100:.3f}%",
                            context={
                                "source_tokens": result.source_token_count,
                                "database_tokens": result.database_token_count,
                                "variance_percent": variance * 100,
                            },
                        )
                    )
                else:
                    logger.info(f"Token count verification passed: {variance*100:.3f}% variance")

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="error",
                    category="count_verification",
                    description=f"Token count verification failed: {str(e)}",
                )
            )

    async def _verify_session_counts(self, result: ValidationResult, tolerance: float):
        """Verify session counts between source and database."""
        try:
            # Get source session count
            source_analysis = await self.enhanced_counter.analyze_comprehensive_token_usage()
            result.source_session_count = source_analysis.total_sessions_analyzed

            # Get database session count
            database_stats = await self._get_database_statistics()
            result.database_session_count = database_stats.get("total_sessions", 0)

            if result.source_session_count > 0:
                variance = (
                    abs(result.database_session_count - result.source_session_count) / result.source_session_count
                )
                result.session_count_variance = variance * 100

                if variance > tolerance:
                    result.add_issue(
                        ValidationIssue(
                            severity="warning",
                            category="count_mismatch",
                            description=f"Session count variance {variance*100:.1f}% exceeds tolerance {tolerance*100:.1f}%",
                            context={
                                "source_sessions": result.source_session_count,
                                "database_sessions": result.database_session_count,
                                "variance_percent": variance * 100,
                            },
                        )
                    )
                else:
                    logger.info(f"Session count verification passed: {variance*100:.1f}% variance")

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="warning",
                    category="count_verification",
                    description=f"Session count verification failed: {str(e)}",
                )
            )

    async def _validate_database_integrity(self, result: ValidationResult, sample_size: int, full_validation: bool):
        """Validate database data integrity."""
        try:
            # Get sample sessions from database
            query = """
            SELECT session_id, calculated_total_tokens, total_reported_tokens, 
                   accuracy_ratio, undercount_percentage
            FROM otel.enhanced_token_summaries
            {} 
            ORDER BY created_at DESC
            """.format(
                "" if full_validation else f"LIMIT {sample_size}"
            )

            sessions = await self.bridge_service.clickhouse_client.execute_query(query)
            result.sessions_validated = len(sessions)

            for session in sessions:
                session_id = session.get("session_id")

                # Validate token counts
                calculated_tokens = session.get("calculated_total_tokens", 0)
                reported_tokens = session.get("total_reported_tokens", 0)

                if calculated_tokens <= 0:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="data_integrity",
                            description="Session has zero or negative calculated tokens",
                            session_id=session_id,
                            context={"calculated_tokens": calculated_tokens},
                        )
                    )

                if reported_tokens < 0:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="data_integrity",
                            description="Session has negative reported tokens",
                            session_id=session_id,
                            context={"reported_tokens": reported_tokens},
                        )
                    )

                # Validate accuracy ratio
                accuracy_ratio = session.get("accuracy_ratio", 0)
                if accuracy_ratio < 0 or accuracy_ratio > 10:  # Allow up to 10x ratio
                    result.add_issue(
                        ValidationIssue(
                            severity="warning",
                            category="data_quality",
                            description=f"Unusual accuracy ratio: {accuracy_ratio}",
                            session_id=session_id,
                            context={"accuracy_ratio": accuracy_ratio},
                        )
                    )

                result.records_validated += 1

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="error",
                    category="database_validation",
                    description=f"Database integrity validation failed: {str(e)}",
                )
            )

    async def _cross_validate_with_source(self, result: ValidationResult, sample_size: int):
        """Cross-validate a sample of database records with source data."""
        try:
            # This is a placeholder for more detailed cross-validation
            # In a full implementation, we would:
            # 1. Sample sessions from database
            # 2. Re-analyze corresponding source files
            # 3. Compare results

            # For now, perform basic consistency checks
            logger.info(f"Cross-validation with source data (sample_size={sample_size})")

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="warning",
                    category="cross_validation",
                    description=f"Cross-validation with source failed: {str(e)}",
                )
            )

    async def _validate_specific_sessions(
        self, session_ids: List[str], result: ValidationResult, deep_validation: bool
    ):
        """Validate specific sessions in detail."""
        for session_id in session_ids:
            try:
                # Get session from database
                db_session = await self.bridge_service.get_session_metrics(session_id)

                if not db_session:
                    result.add_issue(
                        ValidationIssue(
                            severity="error",
                            category="data_missing",
                            description="Session not found in database",
                            session_id=session_id,
                        )
                    )
                    continue

                # Validate session data
                validation_errors = db_session.validate()
                for error in validation_errors:
                    result.add_issue(
                        ValidationIssue(
                            severity="error", category="data_validation", description=error, session_id=session_id
                        )
                    )

                result.sessions_validated += 1

            except Exception as e:
                result.add_issue(
                    ValidationIssue(
                        severity="error",
                        category="session_validation",
                        description=f"Session validation failed: {str(e)}",
                        session_id=session_id,
                    )
                )

    async def _validate_random_sessions(
        self, source_analysis, result: ValidationResult, sample_size: int, deep_validation: bool
    ):
        """Validate a random sample of sessions."""
        try:
            # Get random sessions from source analysis
            source_sessions = list(source_analysis.sessions.keys())
            if len(source_sessions) > sample_size:
                import random

                source_sessions = random.sample(source_sessions, sample_size)

            await self._validate_specific_sessions(source_sessions, result, deep_validation)

        except Exception as e:
            result.add_issue(
                ValidationIssue(
                    severity="warning",
                    category="random_validation",
                    description=f"Random session validation failed: {str(e)}",
                )
            )

    async def _get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics for validation."""
        try:
            query = """
            SELECT 
                COUNT(*) as total_sessions,
                SUM(calculated_total_tokens) as total_tokens,
                AVG(accuracy_ratio) as avg_accuracy_ratio,
                AVG(undercount_percentage) as avg_undercount_percentage
            FROM otel.enhanced_token_summaries
            """

            results = await self.bridge_service.clickhouse_client.execute_query(query)
            if results:
                return results[0]

        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")

        return {}

    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _calculate_accuracy_score(self, result: ValidationResult) -> float:
        """Calculate accuracy score based on validation results."""
        if result.token_count_variance is None:
            return 100.0

        # Score decreases with variance
        variance_penalty = min(result.token_count_variance * 10, 50)  # Max 50% penalty
        return max(0, 100 - variance_penalty)

    def _calculate_integrity_score(self, result: ValidationResult) -> float:
        """Calculate integrity score based on validation issues."""
        base_score = 100.0

        # Penalty for errors and warnings
        error_penalty = result.error_count * 10  # 10 points per error
        warning_penalty = result.warning_count * 2  # 2 points per warning

        return max(0, base_score - error_penalty - warning_penalty)

    def _calculate_consistency_score(self, result: ValidationResult) -> float:
        """Calculate consistency score based on data consistency checks."""
        # Placeholder implementation
        # In a full implementation, this would analyze consistency issues
        consistency_issues = len(
            [issue for issue in result.issues if issue.category in ["data_consistency", "count_mismatch"]]
        )
        penalty = consistency_issues * 5
        return max(0, 100 - penalty)

    def _calculate_completeness_score(self, discovery_result, validation_result: ValidationResult) -> float:
        """Calculate completeness score based on data availability."""
        if discovery_result.total_files_found == 0:
            return 0.0

        # Score based on proportion of healthy files
        healthy_files = len(discovery_result.healthy_files)
        completeness = (healthy_files / discovery_result.total_files_found) * 100

        return completeness
