#!/usr/bin/env python3
"""
Backup and Rollback Manager

Provides comprehensive backup and rollback capabilities for context manipulation operations:
- Automatic backup creation before risky operations
- Multiple backup strategies (full, incremental, operation-specific)
- Rollback operations with integrity verification
- Backup metadata and version management
- Cleanup and retention policies

Integrates with ManipulationValidator and ManipulationEngine for safe operations.
"""

import json
import logging
import hashlib
import gzip
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from copy import deepcopy
from enum import Enum

logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Types of backups that can be created."""
    FULL = "full"  # Complete context backup
    INCREMENTAL = "incremental"  # Only changed keys
    OPERATION = "operation"  # Specific to an operation
    SAFETY = "safety"  # Created before risky operations


class BackupStatus(Enum):
    """Status of backup operations."""
    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORING = "restoring"
    EXPIRED = "expired"


@dataclass
class BackupMetadata:
    """Metadata for a backup."""
    
    backup_id: str  # Unique identifier
    backup_type: BackupType
    creation_timestamp: str
    context_size: int  # Size of original context in characters
    key_count: int  # Number of keys in backup
    checksum: str  # Data integrity checksum
    compression_used: bool  # Whether backup is compressed
    operation_id: Optional[str] = None  # Associated operation if any
    description: str = ""  # Human-readable description
    tags: List[str] = None  # Searchable tags
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class BackupEntry:
    """A complete backup entry with data and metadata."""
    
    metadata: BackupMetadata
    data: Dict[str, Any]  # The backed-up context data
    file_path: Optional[str] = None  # Path to backup file if stored on disk


@dataclass
class RestoreResult:
    """Result of a backup restore operation."""
    
    success: bool
    backup_id: str
    restored_keys: List[str]
    skipped_keys: List[str]  # Keys that couldn't be restored
    integrity_verified: bool
    restore_timestamp: str
    error_messages: List[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []


class BackupManager:
    """
    Comprehensive Backup and Rollback Manager
    
    Manages context backups with multiple strategies and rollback capabilities.
    Provides automatic backup creation, retention policies, and integrity verification.
    """
    
    DEFAULT_BACKUP_DIR = "context_backups"
    MAX_MEMORY_BACKUPS = 50  # Max backups to keep in memory
    DEFAULT_RETENTION_DAYS = 30  # Default backup retention period
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize backup manager with configuration."""
        self.config = config or {}
        
        # Backup storage configuration
        self.backup_dir = Path(self.config.get('backup_dir', self.DEFAULT_BACKUP_DIR))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory backup cache (for recent/frequently accessed backups)
        self.memory_backups: Dict[str, BackupEntry] = {}
        
        # Configuration
        self.max_memory_backups = self.config.get('max_memory_backups', self.MAX_MEMORY_BACKUPS)
        self.retention_days = self.config.get('retention_days', self.DEFAULT_RETENTION_DAYS)
        self.compress_backups = self.config.get('compress_backups', True)
        self.auto_cleanup_enabled = self.config.get('auto_cleanup', True)
        
        logger.info(f"BackupManager initialized with backup_dir: {self.backup_dir}")

    def _generate_backup_id(self, backup_type: BackupType, operation_id: Optional[str] = None) -> str:
        """Generate unique backup ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        type_prefix = backup_type.value
        
        if operation_id:
            return f"{type_prefix}_{operation_id}_{timestamp}"
        else:
            return f"{type_prefix}_{timestamp}"

    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for data integrity verification."""
        # Create deterministic string representation
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _get_backup_file_path(self, backup_id: str, compressed: bool = False) -> Path:
        """Get file path for backup storage."""
        extension = ".json.gz" if compressed else ".json"
        return self.backup_dir / f"{backup_id}{extension}"

    def _save_backup_to_disk(self, backup_entry: BackupEntry) -> bool:
        """Save backup to disk storage."""
        try:
            file_path = self._get_backup_file_path(
                backup_entry.metadata.backup_id, 
                backup_entry.metadata.compression_used
            )
            
            # Convert metadata to dict with enum serialization
            metadata_dict = asdict(backup_entry.metadata)
            metadata_dict['backup_type'] = backup_entry.metadata.backup_type.value  # Convert enum to string
            
            backup_data = {
                'metadata': metadata_dict,
                'data': backup_entry.data
            }
            
            if backup_entry.metadata.compression_used:
                # Save compressed
                with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                    json.dump(backup_data, f, separators=(',', ':'))
            else:
                # Save uncompressed
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2)
            
            backup_entry.file_path = str(file_path)
            logger.info(f"Backup {backup_entry.metadata.backup_id} saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save backup to disk: {e}")
            return False

    def _load_backup_from_disk(self, backup_id: str) -> Optional[BackupEntry]:
        """Load backup from disk storage."""
        try:
            # Try compressed first, then uncompressed
            for compressed in [True, False]:
                file_path = self._get_backup_file_path(backup_id, compressed)
                if file_path.exists():
                    if compressed:
                        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                            backup_data = json.load(f)
                    else:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            backup_data = json.load(f)
                    
                    # Reconstruct BackupEntry
                    metadata = BackupMetadata(**backup_data['metadata'])
                    # Convert string enums back to enum instances
                    metadata.backup_type = BackupType(metadata.backup_type)
                    
                    backup_entry = BackupEntry(
                        metadata=metadata,
                        data=backup_data['data'],
                        file_path=str(file_path)
                    )
                    
                    logger.info(f"Backup {backup_id} loaded from {file_path}")
                    return backup_entry
            
            logger.warning(f"Backup {backup_id} not found on disk")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load backup from disk: {e}")
            return None

    def _manage_memory_cache(self) -> None:
        """Manage in-memory backup cache size."""
        if len(self.memory_backups) > self.max_memory_backups:
            # Remove oldest backups from memory (but keep on disk)
            sorted_backups = sorted(
                self.memory_backups.items(),
                key=lambda x: x[1].metadata.creation_timestamp
            )
            
            # Remove oldest entries
            excess_count = len(self.memory_backups) - self.max_memory_backups + 10  # Remove 10 extra for headroom
            for backup_id, _ in sorted_backups[:excess_count]:
                logger.debug(f"Removing backup {backup_id} from memory cache")
                del self.memory_backups[backup_id]

    def create_backup(
        self,
        context_data: Dict[str, Any],
        backup_type: BackupType = BackupType.FULL,
        operation_id: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        save_to_disk: bool = True
    ) -> str:
        """Create a backup of context data."""
        backup_start = datetime.now()
        
        try:
            # Generate backup metadata
            backup_id = self._generate_backup_id(backup_type, operation_id)
            context_copy = deepcopy(context_data)
            
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=backup_type,
                creation_timestamp=backup_start.isoformat(),
                context_size=sum(len(str(v)) for v in context_data.values()),
                key_count=len(context_data),
                checksum=self._calculate_checksum(context_data),
                compression_used=self.compress_backups,
                operation_id=operation_id,
                description=description or f"{backup_type.value} backup",
                tags=tags or []
            )
            
            backup_entry = BackupEntry(metadata=metadata, data=context_copy)
            
            # Save to memory cache
            self.memory_backups[backup_id] = backup_entry
            self._manage_memory_cache()
            
            # Save to disk if requested
            if save_to_disk:
                success = self._save_backup_to_disk(backup_entry)
                if not success:
                    logger.warning(f"Failed to save backup {backup_id} to disk, but kept in memory")
            
            execution_time = (datetime.now() - backup_start).total_seconds()
            logger.info(f"Created backup {backup_id} in {execution_time:.3f}s ({metadata.context_size} chars)")
            
            return backup_id
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    def get_backup(self, backup_id: str) -> Optional[BackupEntry]:
        """Retrieve a backup by ID."""
        # Check memory cache first
        if backup_id in self.memory_backups:
            return self.memory_backups[backup_id]
        
        # Try loading from disk
        backup_entry = self._load_backup_from_disk(backup_id)
        if backup_entry:
            # Add back to memory cache
            self.memory_backups[backup_id] = backup_entry
            self._manage_memory_cache()
            
        return backup_entry

    def list_backups(
        self, 
        backup_type: Optional[BackupType] = None,
        operation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        max_age_days: Optional[int] = None
    ) -> List[BackupMetadata]:
        """List available backups with optional filtering."""
        try:
            all_backups = []
            cutoff_date = None
            
            if max_age_days is not None:
                cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            # Include memory backups
            for backup_entry in self.memory_backups.values():
                all_backups.append(backup_entry.metadata)
            
            # Include disk backups (scan backup directory)
            if self.backup_dir.exists():
                for backup_file in self.backup_dir.glob("*.json*"):
                    backup_id = backup_file.stem
                    if backup_id.endswith('.json'):  # Remove .json from .json.gz files
                        backup_id = backup_id[:-5]
                    
                    # Skip if already in memory
                    if backup_id in self.memory_backups:
                        continue
                    
                    # Try to load metadata only (lightweight)
                    backup_entry = self._load_backup_from_disk(backup_id)
                    if backup_entry:
                        all_backups.append(backup_entry.metadata)
            
            # Apply filters
            filtered_backups = []
            for metadata in all_backups:
                # Filter by backup type
                if backup_type and metadata.backup_type != backup_type:
                    continue
                    
                # Filter by operation ID
                if operation_id and metadata.operation_id != operation_id:
                    continue
                    
                # Filter by tags
                if tags and not any(tag in metadata.tags for tag in tags):
                    continue
                    
                # Filter by age
                if cutoff_date:
                    backup_date = datetime.fromisoformat(metadata.creation_timestamp)
                    if backup_date < cutoff_date:
                        continue
                
                filtered_backups.append(metadata)
            
            # Sort by creation time (newest first)
            filtered_backups.sort(key=lambda x: x.creation_timestamp, reverse=True)
            
            return filtered_backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def restore_backup(
        self,
        backup_id: str,
        target_keys: Optional[List[str]] = None,
        verify_integrity: bool = True
    ) -> RestoreResult:
        """Restore context data from a backup."""
        restore_start = datetime.now()
        
        try:
            # Get backup data
            backup_entry = self.get_backup(backup_id)
            if not backup_entry:
                return RestoreResult(
                    success=False,
                    backup_id=backup_id,
                    restored_keys=[],
                    skipped_keys=[],
                    integrity_verified=False,
                    restore_timestamp=restore_start.isoformat(),
                    error_messages=[f"Backup {backup_id} not found"]
                )
            
            # Verify integrity if requested
            integrity_verified = True
            if verify_integrity:
                current_checksum = self._calculate_checksum(backup_entry.data)
                if current_checksum != backup_entry.metadata.checksum:
                    logger.error(f"Integrity check failed for backup {backup_id}")
                    integrity_verified = False
                    return RestoreResult(
                        success=False,
                        backup_id=backup_id,
                        restored_keys=[],
                        skipped_keys=[],
                        integrity_verified=False,
                        restore_timestamp=restore_start.isoformat(),
                        error_messages=["Backup integrity check failed"]
                    )
            
            # Restore data
            restored_keys = []
            skipped_keys = []
            
            if target_keys is None:
                # Restore all keys
                target_keys = list(backup_entry.data.keys())
            
            for key in target_keys:
                if key in backup_entry.data:
                    restored_keys.append(key)
                else:
                    skipped_keys.append(key)
                    logger.warning(f"Key '{key}' not found in backup {backup_id}")
            
            # Create restored context data
            restored_data = {}
            for key in restored_keys:
                restored_data[key] = deepcopy(backup_entry.data[key])
            
            execution_time = (datetime.now() - restore_start).total_seconds()
            logger.info(f"Restored backup {backup_id} in {execution_time:.3f}s ({len(restored_keys)} keys)")
            
            return RestoreResult(
                success=True,
                backup_id=backup_id,
                restored_keys=restored_keys,
                skipped_keys=skipped_keys,
                integrity_verified=integrity_verified,
                restore_timestamp=restore_start.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return RestoreResult(
                success=False,
                backup_id=backup_id,
                restored_keys=[],
                skipped_keys=[],
                integrity_verified=False,
                restore_timestamp=restore_start.isoformat(),
                error_messages=[f"Restore error: {e}"]
            )

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup from both memory and disk."""
        try:
            success = True
            
            # Remove from memory
            if backup_id in self.memory_backups:
                del self.memory_backups[backup_id]
                logger.debug(f"Removed backup {backup_id} from memory")
            
            # Remove from disk
            for compressed in [True, False]:
                file_path = self._get_backup_file_path(backup_id, compressed)
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted backup file: {file_path}")
                    break
            else:
                logger.warning(f"Backup file for {backup_id} not found on disk")
                success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_id}: {e}")
            return False

    def cleanup_expired_backups(self) -> int:
        """Clean up expired backups based on retention policy."""
        if not self.auto_cleanup_enabled:
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            backups_to_delete = []
            
            # Find expired backups
            all_backups = self.list_backups()
            for metadata in all_backups:
                backup_date = datetime.fromisoformat(metadata.creation_timestamp)
                if backup_date < cutoff_date:
                    backups_to_delete.append(metadata.backup_id)
            
            # Delete expired backups
            deleted_count = 0
            for backup_id in backups_to_delete:
                if self.delete_backup(backup_id):
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired backups")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired backups: {e}")
            return 0

    def get_backup_statistics(self) -> Dict[str, Any]:
        """Get backup system statistics."""
        try:
            all_backups = self.list_backups()
            
            stats = {
                'total_backups': len(all_backups),
                'memory_backups': len(self.memory_backups),
                'disk_backups': len(all_backups) - len(self.memory_backups),
                'backup_types': {},
                'total_size': 0,
                'oldest_backup': None,
                'newest_backup': None
            }
            
            if all_backups:
                # Calculate type distribution and sizes
                for metadata in all_backups:
                    backup_type = metadata.backup_type.value
                    stats['backup_types'][backup_type] = stats['backup_types'].get(backup_type, 0) + 1
                    stats['total_size'] += metadata.context_size
                
                # Find oldest and newest
                sorted_by_date = sorted(all_backups, key=lambda x: x.creation_timestamp)
                stats['oldest_backup'] = sorted_by_date[0].creation_timestamp
                stats['newest_backup'] = sorted_by_date[-1].creation_timestamp
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get backup statistics: {e}")
            return {}


# Convenience functions
def create_safety_backup(context_data: Dict[str, Any], operation_id: str, description: str = "") -> str:
    """Convenience function to create a safety backup before risky operations."""
    manager = BackupManager()
    return manager.create_backup(
        context_data=context_data,
        backup_type=BackupType.SAFETY,
        operation_id=operation_id,
        description=description or f"Safety backup before operation {operation_id}",
        tags=["safety", "pre-operation"]
    )


def restore_from_backup(backup_id: str, target_keys: Optional[List[str]] = None) -> RestoreResult:
    """Convenience function to restore from a backup."""
    manager = BackupManager()
    return manager.restore_backup(backup_id, target_keys)


if __name__ == "__main__":
    # Test backup system
    print("Testing Backup Manager...")
    
    # Test context data
    test_context = {
        "important_data": "This is critical information",
        "temp_data": "This is temporary",
        "config": {"setting1": "value1", "setting2": "value2"}
    }
    
    manager = BackupManager()
    
    # Create backup
    backup_id = manager.create_backup(test_context, BackupType.FULL, description="Test backup")
    print(f"✅ Created backup: {backup_id}")
    
    # List backups
    backups = manager.list_backups()
    print(f"📋 Found {len(backups)} backups")
    
    # Restore backup
    restore_result = manager.restore_backup(backup_id)
    print(f"🔄 Restore result: {'SUCCESS' if restore_result.success else 'FAILED'}")
    print(f"   Restored keys: {len(restore_result.restored_keys)}")
    
    # Statistics
    stats = manager.get_backup_statistics()
    print(f"📊 Backup statistics: {stats}")