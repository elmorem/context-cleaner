"""
Historical Data Migration Package

This package provides comprehensive tools for migrating Enhanced Token Analysis
historical data from JSONL files to ClickHouse database. Addresses the critical
2.768 billion token data loss issue by enabling one-time historical backfill
and ongoing incremental synchronization.

Components:
- JSONL Discovery Service: Filesystem scanning and file inventory
- Data Extraction Engine: JSONL parsing and data transformation
- Migration Engine: Orchestrates complete migration workflow
- Progress Tracking: Real-time monitoring and checkpointing
- Data Validation: Pre/post-migration verification
- CLI Commands: Complete command-line interface for migration operations
"""

from .jsonl_discovery import JSONLDiscoveryService, FileDiscoveryResult, JSONLFileInfo
from .data_extraction import DataExtractionEngine, ExtractionResult
from .migration_engine import MigrationEngine, MigrationResult
from .progress_tracker import ProgressTracker, MigrationProgress
from .validation import MigrationValidator, ValidationResult

__all__ = [
    "JSONLDiscoveryService",
    "FileDiscoveryResult",
    "JSONLFileInfo",
    "DataExtractionEngine",
    "ExtractionResult",
    "MigrationEngine",
    "MigrationResult",
    "ProgressTracker",
    "MigrationProgress",
    "MigrationValidator",
    "ValidationResult",
]
