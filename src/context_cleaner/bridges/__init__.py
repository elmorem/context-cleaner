"""
Context Cleaner Bridges Module

This module contains bridge services that connect different components of the Context Cleaner system.

Key Bridges:
- TokenAnalysisBridgeService: Bridges enhanced token analysis with ClickHouse database
  Resolves the critical 2.768 billion token data loss issue by transferring JSONL analysis 
  results into the database that the dashboard reads from.

Architecture:
JSONL Files → Enhanced Analysis → Bridge Services → ClickHouse Database → Dashboard
"""

from .token_analysis_bridge import (
    TokenAnalysisBridgeService,
    TokenUsageSummaryRecord, 
    BridgeServiceStats,
    create_token_bridge_service,
    execute_bridge_backfill
)

try:
    from .incremental_sync import (
        IncrementalSyncService,
        FileProcessingState,
        SyncStats,
        create_incremental_sync_service
    )
    _INCREMENTAL_SYNC_AVAILABLE = True
except ImportError:
    _INCREMENTAL_SYNC_AVAILABLE = False

__all__ = [
    'TokenAnalysisBridgeService',
    'TokenUsageSummaryRecord',
    'BridgeServiceStats', 
    'create_token_bridge_service',
    'execute_bridge_backfill'
]

if _INCREMENTAL_SYNC_AVAILABLE:
    __all__.extend([
        'IncrementalSyncService',
        'FileProcessingState',
        'SyncStats',
        'create_incremental_sync_service'
    ])