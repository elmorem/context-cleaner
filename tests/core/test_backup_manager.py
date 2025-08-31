#!/usr/bin/env python3
"""
Tests for BackupManager

Tests the backup and rollback system including:
- Backup creation and storage
- Backup retrieval and management
- Rollback operations
- Backup metadata and integrity
- Cleanup and retention policies
"""

import pytest
import tempfile
import shutil
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from context_cleaner.core.backup_manager import (
    BackupManager,
    BackupType,
    BackupStatus,
    BackupMetadata,
    BackupEntry,
    RestoreResult,
    create_safety_backup,
    restore_from_backup
)


class TestBackupManager:
    """Test suite for BackupManager."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary directory for backup tests."""
        temp_dir = tempfile.mkdtemp(prefix="backup_test_")
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def backup_manager(self, temp_backup_dir):
        """BackupManager instance for testing."""
        config = {
            'backup_dir': temp_backup_dir,
            'max_memory_backups': 5,
            'retention_days': 7,
            'compress_backups': True
        }
        return BackupManager(config)

    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for backup testing."""
        return {
            "user_message": "Help me debug authentication",
            "todo_item": "Fix login bug in auth module",
            "config_data": {"debug": True, "timeout": 30},
            "large_content": "x" * 1000,  # Large content for compression testing
            "timestamp": datetime.now().isoformat()
        }

    def test_backup_manager_initialization(self, temp_backup_dir):
        """Test BackupManager initialization."""
        config = {
            'backup_dir': temp_backup_dir,
            'max_memory_backups': 10,
            'retention_days': 14,
            'compress_backups': False,
            'auto_cleanup': True
        }
        
        manager = BackupManager(config)
        
        assert str(manager.backup_dir) == temp_backup_dir
        assert manager.max_memory_backups == 10
        assert manager.retention_days == 14
        assert manager.compress_backups is False
        assert manager.auto_cleanup_enabled is True
        assert len(manager.memory_backups) == 0
        assert Path(temp_backup_dir).exists()

    def test_create_backup_full(self, backup_manager, sample_context_data):
        """Test creating a full backup."""
        backup_id = backup_manager.create_backup(
            context_data=sample_context_data,
            backup_type=BackupType.FULL,
            description="Test full backup",
            tags=["test", "full"],
            save_to_disk=True
        )
        
        assert backup_id is not None
        assert backup_id.startswith("full_")
        assert backup_id in backup_manager.memory_backups
        
        # Verify backup entry
        backup_entry = backup_manager.memory_backups[backup_id]
        assert backup_entry.metadata.backup_type == BackupType.FULL
        assert backup_entry.metadata.description == "Test full backup"
        assert "test" in backup_entry.metadata.tags
        assert "full" in backup_entry.metadata.tags
        assert backup_entry.metadata.key_count == len(sample_context_data)
        assert backup_entry.metadata.context_size > 0
        assert len(backup_entry.metadata.checksum) > 0
        
        # Verify data integrity
        assert backup_entry.data == sample_context_data
        
        # Verify file was saved to disk
        assert backup_entry.file_path is not None
        assert Path(backup_entry.file_path).exists()

    def test_create_backup_operation_specific(self, backup_manager, sample_context_data):
        """Test creating operation-specific backup."""
        operation_id = "test-operation-001"
        
        backup_id = backup_manager.create_backup(
            context_data=sample_context_data,
            backup_type=BackupType.OPERATION,
            operation_id=operation_id,
            description="Pre-operation backup",
            save_to_disk=True
        )
        
        assert operation_id in backup_id
        assert backup_id.startswith("operation_")
        
        backup_entry = backup_manager.get_backup(backup_id)
        assert backup_entry.metadata.operation_id == operation_id
        assert backup_entry.metadata.backup_type == BackupType.OPERATION

    def test_create_safety_backup(self, backup_manager, sample_context_data):
        """Test creating safety backup."""
        backup_id = backup_manager.create_backup(
            context_data=sample_context_data,
            backup_type=BackupType.SAFETY,
            operation_id="risky-op-001",
            description="Safety backup before risky operation",
            tags=["safety", "pre-operation"]
        )
        
        assert backup_id.startswith("safety_")
        
        backup_entry = backup_manager.get_backup(backup_id)
        assert backup_entry.metadata.backup_type == BackupType.SAFETY
        assert "safety" in backup_entry.metadata.tags

    def test_backup_compression(self, temp_backup_dir, sample_context_data):
        """Test backup compression functionality."""
        # Test compressed backup
        compressed_manager = BackupManager({
            'backup_dir': temp_backup_dir,
            'compress_backups': True
        })
        
        compressed_id = compressed_manager.create_backup(
            sample_context_data,
            BackupType.FULL,
            save_to_disk=True
        )
        
        compressed_entry = compressed_manager.get_backup(compressed_id)
        assert compressed_entry.metadata.compression_used is True
        assert compressed_entry.file_path.endswith('.json.gz')
        
        # Test uncompressed backup
        uncompressed_manager = BackupManager({
            'backup_dir': temp_backup_dir + "_uncompressed",
            'compress_backups': False
        })
        
        uncompressed_id = uncompressed_manager.create_backup(
            sample_context_data,
            BackupType.FULL,
            save_to_disk=True
        )
        
        uncompressed_entry = uncompressed_manager.get_backup(uncompressed_id)
        assert uncompressed_entry.metadata.compression_used is False
        assert uncompressed_entry.file_path.endswith('.json')

    def test_get_backup_from_memory(self, backup_manager, sample_context_data):
        """Test retrieving backup from memory cache."""
        backup_id = backup_manager.create_backup(
            sample_context_data,
            BackupType.FULL,
            save_to_disk=False  # Only in memory
        )
        
        # Should retrieve from memory
        backup_entry = backup_manager.get_backup(backup_id)
        assert backup_entry is not None
        assert backup_entry.metadata.backup_id == backup_id
        assert backup_entry.data == sample_context_data

    def test_get_backup_from_disk(self, backup_manager, sample_context_data):
        """Test retrieving backup from disk storage."""
        backup_id = backup_manager.create_backup(
            sample_context_data,
            BackupType.FULL,
            save_to_disk=True
        )
        
        # Remove from memory to test disk retrieval
        del backup_manager.memory_backups[backup_id]
        
        # Should load from disk and restore to memory
        backup_entry = backup_manager.get_backup(backup_id)
        assert backup_entry is not None
        assert backup_entry.metadata.backup_id == backup_id
        assert backup_entry.data == sample_context_data
        assert backup_id in backup_manager.memory_backups  # Should be back in memory

    def test_list_backups_all(self, backup_manager, sample_context_data):
        """Test listing all backups."""
        # Create multiple backups
        backup1_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        backup2_id = backup_manager.create_backup(sample_context_data, BackupType.OPERATION, operation_id="op-001")
        backup3_id = backup_manager.create_backup(sample_context_data, BackupType.SAFETY, operation_id="op-002")
        
        all_backups = backup_manager.list_backups()
        
        assert len(all_backups) == 3
        backup_ids = [backup.backup_id for backup in all_backups]
        assert backup1_id in backup_ids
        assert backup2_id in backup_ids
        assert backup3_id in backup_ids

    def test_list_backups_filtered(self, backup_manager, sample_context_data):
        """Test listing backups with filters."""
        # Create backups with different types and tags
        full_id = backup_manager.create_backup(sample_context_data, BackupType.FULL, tags=["manual"])
        op_id = backup_manager.create_backup(sample_context_data, BackupType.OPERATION, 
                                           operation_id="test-op", tags=["auto"])
        safety_id = backup_manager.create_backup(sample_context_data, BackupType.SAFETY, 
                                                operation_id="risky-op", tags=["safety"])
        
        # Filter by backup type
        full_backups = backup_manager.list_backups(backup_type=BackupType.FULL)
        assert len(full_backups) == 1
        assert full_backups[0].backup_id == full_id
        
        # Filter by operation ID
        op_backups = backup_manager.list_backups(operation_id="test-op")
        assert len(op_backups) == 1
        assert op_backups[0].backup_id == op_id
        
        # Filter by tags
        safety_backups = backup_manager.list_backups(tags=["safety"])
        assert len(safety_backups) == 1
        assert safety_backups[0].backup_id == safety_id

    def test_list_backups_age_filter(self, backup_manager, sample_context_data):
        """Test listing backups with age filter."""
        # Create backup
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        
        # Should find recent backup
        recent_backups = backup_manager.list_backups(max_age_days=1)
        assert len(recent_backups) == 1
        assert recent_backups[0].backup_id == backup_id
        
        # Should not find backup older than 0 days (impossible)
        old_backups = backup_manager.list_backups(max_age_days=0)
        assert len(old_backups) == 0

    def test_restore_backup_full(self, backup_manager, sample_context_data):
        """Test full backup restoration."""
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        
        restore_result = backup_manager.restore_backup(backup_id)
        
        assert restore_result.success is True
        assert restore_result.backup_id == backup_id
        assert restore_result.integrity_verified is True
        assert len(restore_result.restored_keys) == len(sample_context_data)
        assert len(restore_result.skipped_keys) == 0
        assert set(restore_result.restored_keys) == set(sample_context_data.keys())

    def test_restore_backup_partial(self, backup_manager, sample_context_data):
        """Test partial backup restoration."""
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        
        # Restore only specific keys
        target_keys = ["user_message", "todo_item"]
        restore_result = backup_manager.restore_backup(backup_id, target_keys=target_keys)
        
        assert restore_result.success is True
        assert len(restore_result.restored_keys) == 2
        assert set(restore_result.restored_keys) == set(target_keys)

    def test_restore_backup_missing_keys(self, backup_manager, sample_context_data):
        """Test restoration with missing keys."""
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        
        # Try to restore keys that don't exist
        target_keys = ["user_message", "nonexistent_key1", "nonexistent_key2"]
        restore_result = backup_manager.restore_backup(backup_id, target_keys=target_keys)
        
        assert restore_result.success is True
        assert len(restore_result.restored_keys) == 1  # Only user_message exists
        assert restore_result.restored_keys[0] == "user_message"
        assert len(restore_result.skipped_keys) == 2
        assert "nonexistent_key1" in restore_result.skipped_keys
        assert "nonexistent_key2" in restore_result.skipped_keys

    def test_restore_backup_not_found(self, backup_manager):
        """Test restoration of non-existent backup."""
        restore_result = backup_manager.restore_backup("nonexistent-backup-id")
        
        assert restore_result.success is False
        assert len(restore_result.error_messages) > 0
        assert "not found" in restore_result.error_messages[0].lower()

    def test_delete_backup(self, backup_manager, sample_context_data):
        """Test backup deletion."""
        backup_id = backup_manager.create_backup(
            sample_context_data, 
            BackupType.FULL,
            save_to_disk=True
        )
        
        # Verify backup exists
        assert backup_id in backup_manager.memory_backups
        backup_entry = backup_manager.get_backup(backup_id)
        assert backup_entry is not None
        file_path = Path(backup_entry.file_path)
        assert file_path.exists()
        
        # Delete backup
        success = backup_manager.delete_backup(backup_id)
        
        assert success is True
        assert backup_id not in backup_manager.memory_backups
        assert not file_path.exists()

    def test_memory_cache_management(self, temp_backup_dir, sample_context_data):
        """Test memory cache size management."""
        # Create manager with small cache
        manager = BackupManager({
            'backup_dir': temp_backup_dir,
            'max_memory_backups': 3
        })
        
        backup_ids = []
        
        # Create more backups than cache can hold
        for i in range(5):
            backup_id = manager.create_backup(
                sample_context_data,
                BackupType.FULL,
                description=f"Backup {i}",
                save_to_disk=True
            )
            backup_ids.append(backup_id)
        
        # Memory should be limited to max size (plus some headroom)
        assert len(manager.memory_backups) <= manager.max_memory_backups + 10
        
        # But all backups should still be retrievable from disk
        for backup_id in backup_ids:
            backup_entry = manager.get_backup(backup_id)
            assert backup_entry is not None

    def test_cleanup_expired_backups(self, backup_manager, sample_context_data):
        """Test cleanup of expired backups."""
        # Create a backup
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        
        # Mock the backup creation time to be old
        backup_entry = backup_manager.get_backup(backup_id)
        old_timestamp = (datetime.now() - timedelta(days=10)).isoformat()
        backup_entry.metadata.creation_timestamp = old_timestamp
        
        # Set short retention period
        backup_manager.retention_days = 5
        backup_manager.auto_cleanup_enabled = True
        
        # Run cleanup
        deleted_count = backup_manager.cleanup_expired_backups()
        
        assert deleted_count == 1
        assert backup_id not in backup_manager.memory_backups

    def test_backup_statistics(self, backup_manager, sample_context_data):
        """Test backup system statistics."""
        # Create various types of backups
        full_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        op_id = backup_manager.create_backup(sample_context_data, BackupType.OPERATION, operation_id="op-001")
        safety_id = backup_manager.create_backup(sample_context_data, BackupType.SAFETY, operation_id="op-002")
        
        stats = backup_manager.get_backup_statistics()
        
        assert stats['total_backups'] == 3
        assert stats['memory_backups'] == 3
        assert stats['disk_backups'] == 0  # Not saved to disk in this test
        assert 'full' in stats['backup_types']
        assert 'operation' in stats['backup_types']
        assert 'safety' in stats['backup_types']
        assert stats['total_size'] > 0
        assert stats['oldest_backup'] is not None
        assert stats['newest_backup'] is not None

    def test_checksum_verification(self, backup_manager, sample_context_data):
        """Test backup checksum verification."""
        backup_id = backup_manager.create_backup(sample_context_data, BackupType.FULL)
        backup_entry = backup_manager.get_backup(backup_id)
        
        # Verify checksum was generated
        assert len(backup_entry.metadata.checksum) == 64  # SHA256 length
        
        # Verify checksum calculation is consistent
        expected_checksum = backup_manager._calculate_checksum(sample_context_data)
        assert backup_entry.metadata.checksum == expected_checksum

    def test_backup_metadata_structure(self, backup_manager, sample_context_data):
        """Test backup metadata structure."""
        backup_id = backup_manager.create_backup(
            sample_context_data,
            BackupType.OPERATION,
            operation_id="meta-test-001",
            description="Metadata test backup",
            tags=["test", "metadata"]
        )
        
        backup_entry = backup_manager.get_backup(backup_id)
        metadata = backup_entry.metadata
        
        # Verify all required fields
        assert isinstance(metadata, BackupMetadata)
        assert metadata.backup_id == backup_id
        assert metadata.backup_type == BackupType.OPERATION
        assert metadata.operation_id == "meta-test-001"
        assert metadata.description == "Metadata test backup"
        assert "test" in metadata.tags
        assert "metadata" in metadata.tags
        assert metadata.context_size > 0
        assert metadata.key_count == len(sample_context_data)
        assert len(metadata.checksum) > 0
        assert isinstance(metadata.compression_used, bool)
        
        # Verify timestamp format
        creation_time = datetime.fromisoformat(metadata.creation_timestamp)
        assert isinstance(creation_time, datetime)

    def test_convenience_functions(self, sample_context_data):
        """Test convenience functions."""
        # Test create_safety_backup
        backup_id = create_safety_backup(
            sample_context_data,
            "convenience-test-001",
            "Convenience function test"
        )
        
        assert backup_id is not None
        assert backup_id.startswith("safety_")
        
        # Test restore_from_backup
        restore_result = restore_from_backup(backup_id)
        
        assert restore_result.success is True
        assert restore_result.backup_id == backup_id
        assert len(restore_result.restored_keys) == len(sample_context_data)

    def test_disk_storage_formats(self, backup_manager, sample_context_data):
        """Test different disk storage formats."""
        # Test compressed storage
        compressed_id = backup_manager.create_backup(
            sample_context_data,
            BackupType.FULL,
            save_to_disk=True
        )
        
        compressed_entry = backup_manager.get_backup(compressed_id)
        compressed_file = Path(compressed_entry.file_path)
        assert compressed_file.exists()
        assert compressed_file.suffix == '.gz'
        
        # Verify file can be read directly
        with gzip.open(compressed_file, 'rt', encoding='utf-8') as f:
            backup_data = json.load(f)
            assert 'metadata' in backup_data
            assert 'data' in backup_data
            assert backup_data['data'] == sample_context_data

    def test_error_handling(self, backup_manager, sample_context_data):
        """Test error handling in backup operations."""
        # Test backup with invalid data
        with pytest.raises(Exception):
            backup_manager._calculate_checksum({"invalid": object()})  # Non-serializable
        
        # Test restore with corrupted backup ID
        restore_result = backup_manager.restore_backup("corrupted-backup-id")
        assert restore_result.success is False
        assert len(restore_result.error_messages) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])