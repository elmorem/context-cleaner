#!/usr/bin/env python3
"""
Tests for TransactionManager

Tests the transaction-based atomic operations including:
- Transaction creation and lifecycle
- Operation execution within transactions
- Rollback and commit functionality
- Savepoints and nested rollbacks
- Transaction isolation and consistency
"""

import pytest
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

from context_cleaner.core.transaction_manager import (
    TransactionManager,
    Transaction,
    TransactionState,
    TransactionIsolation,
    TransactionResult,
    TransactionMetadata,
    TransactionOperation,
    Savepoint,
    execute_atomic_operations
)
from context_cleaner.core.manipulation_engine import ManipulationOperation
from context_cleaner.core.manipulation_validator import ManipulationValidator
from context_cleaner.core.backup_manager import BackupManager


class TestTransactionManager:
    """Test suite for TransactionManager."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary directory for transaction tests."""
        temp_dir = tempfile.mkdtemp(prefix="transaction_test_")
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def backup_manager(self, temp_backup_dir):
        """BackupManager instance for transaction testing."""
        return BackupManager({'backup_dir': temp_backup_dir})

    @pytest.fixture
    def validator(self):
        """ManipulationValidator instance for transaction testing."""
        # Use more lenient constraints for testing
        return ManipulationValidator({
            'max_operation_impact': 0.8,  # Allow up to 80% impact for tests
            'max_total_reduction': 0.9,   # Allow up to 90% reduction for tests
            'min_confidence': 0.1         # Lower confidence requirement for tests
        })

    @pytest.fixture
    def transaction_manager(self, backup_manager, validator):
        """TransactionManager instance for testing."""
        return TransactionManager(
            backup_manager=backup_manager,
            validator=validator
        )

    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for transaction testing."""
        return {
            "message_1": "First message content",
            "message_2": "Second message content",
            "todo_1": "Complete authentication module",
            "todo_2": "Write comprehensive tests",
            "config": {"debug": True, "timeout": 30},
            "timestamp": datetime.now().isoformat()
        }

    @pytest.fixture
    def sample_operations(self):
        """Sample manipulation operations for testing."""
        op1 = ManipulationOperation(
            operation_id="tx-test-001",
            operation_type="remove",
            target_keys=["message_2"],
            operation_data={"removal_type": "safe_delete"},
            estimated_token_impact=-25,
            confidence_score=0.9,
            reasoning="Remove duplicate message",
            requires_confirmation=False
        )
        
        op2 = ManipulationOperation(
            operation_id="tx-test-002",
            operation_type="consolidate",
            target_keys=["todo_1", "todo_2"],
            operation_data={"strategy": "merge_similar"},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Consolidate related todos",
            requires_confirmation=False
        )
        
        return [op1, op2]

    def test_transaction_manager_initialization(self, backup_manager, validator):
        """Test TransactionManager initialization."""
        config = {
            'default_isolation': TransactionIsolation.SERIALIZABLE.value,
            'enable_nested_transactions': False,
            'max_transaction_time': 600,
            'enable_logging': True
        }
        
        manager = TransactionManager(
            backup_manager=backup_manager,
            validator=validator,
            config=config
        )
        
        assert manager.backup_manager is backup_manager
        assert manager.validator is validator
        assert manager.default_isolation == TransactionIsolation.SERIALIZABLE
        assert manager.enable_nested_transactions is False
        assert manager.max_transaction_time == 600
        assert manager.enable_transaction_logging is True
        assert len(manager.active_transactions) == 0
        assert len(manager.transaction_history) == 0

    def test_create_transaction(self, transaction_manager):
        """Test transaction creation."""
        transaction = transaction_manager.create_transaction(
            isolation_level=TransactionIsolation.READ_COMMITTED,
            description="Test transaction",
            tags=["test", "unit_test"]
        )
        
        assert isinstance(transaction, Transaction)
        assert transaction.metadata.isolation_level == TransactionIsolation.READ_COMMITTED
        assert transaction.metadata.description == "Test transaction"
        assert "test" in transaction.metadata.tags
        assert "unit_test" in transaction.metadata.tags
        assert transaction.metadata.state == TransactionState.CREATED
        assert transaction.metadata.transaction_id in transaction_manager.active_transactions

    def test_transaction_context_manager(self, transaction_manager, sample_context_data):
        """Test transaction context manager."""
        with transaction_manager.transaction(context_data=sample_context_data, description="Context manager test") as tx:
            assert isinstance(tx, Transaction)
            assert tx.metadata.state == TransactionState.STARTED
            
            # Add a simple operation
            test_op = ManipulationOperation(
                operation_id="context-test-001",
                operation_type="remove",
                target_keys=["message_2"],
                operation_data={},
                estimated_token_impact=-25,
                confidence_score=0.9,
                reasoning="Context manager test",
                requires_confirmation=False
            )
            
            tx.add_operation(test_op)
            
            # Execute the operation without validation (just testing context manager mechanics)
            results = tx.execute_operations(manipulation_engine=None, validate_each=False)
            assert len(results) == 1
            
        # Transaction should be automatically committed
        assert tx.metadata.state == TransactionState.COMMITTED

    def test_transaction_lifecycle_success(self, transaction_manager, sample_context_data, sample_operations):
        """Test successful transaction lifecycle."""
        tx = transaction_manager.create_transaction(description="Lifecycle test")
        
        # Begin transaction
        tx.begin(sample_context_data)
        assert tx.metadata.state == TransactionState.STARTED
        assert tx.original_context == sample_context_data
        assert tx.current_context == sample_context_data
        assert tx.transaction_backup_id is not None
        
        # Add operations
        for operation in sample_operations:
            op_id = tx.add_operation(operation)
            assert op_id.startswith(tx.metadata.transaction_id)
        
        assert len(tx.operations) == 2
        
        # Execute operations
        execution_results = tx.execute_operations(manipulation_engine=None, validate_each=True)
        assert len(execution_results) == 2
        
        # Commit transaction
        result = tx.commit()
        
        assert isinstance(result, TransactionResult)
        assert result.success is True
        assert result.state == TransactionState.COMMITTED
        assert result.operations_attempted == 2
        assert result.rollback_performed is False
        assert tx.metadata.state == TransactionState.COMMITTED

    def test_transaction_rollback(self, transaction_manager, sample_context_data, sample_operations):
        """Test transaction rollback."""
        tx = transaction_manager.create_transaction(description="Rollback test")
        
        tx.begin(sample_context_data)
        
        for operation in sample_operations:
            tx.add_operation(operation)
        
        # Simulate failure and rollback
        result = tx.rollback()
        
        assert isinstance(result, TransactionResult)
        assert result.success is False
        assert result.state == TransactionState.ROLLED_BACK
        assert result.rollback_performed is True
        assert tx.metadata.state == TransactionState.ROLLED_BACK

    def test_savepoints_creation(self, transaction_manager, sample_context_data, sample_operations):
        """Test savepoint creation and management."""
        tx = transaction_manager.create_transaction(description="Savepoint test")
        tx.begin(sample_context_data)
        
        # Add first operation
        tx.add_operation(sample_operations[0])
        
        # Create savepoint
        savepoint_id = tx.create_savepoint("after_first_operation")
        
        assert savepoint_id is not None
        assert len(tx.savepoints) == 1
        
        savepoint = tx.savepoints[0]
        assert isinstance(savepoint, Savepoint)
        assert savepoint.savepoint_name == "after_first_operation"
        assert savepoint.operation_count == 1
        assert savepoint.context_backup_id is not None
        
        # Add second operation
        tx.add_operation(sample_operations[1])
        
        # Create another savepoint
        savepoint2_id = tx.create_savepoint("after_second_operation")
        
        assert len(tx.savepoints) == 2
        assert tx.savepoints[1].operation_count == 2

    def test_rollback_to_savepoint(self, transaction_manager, sample_context_data, sample_operations):
        """Test rollback to specific savepoint."""
        tx = transaction_manager.create_transaction(description="Savepoint rollback test")
        tx.begin(sample_context_data)
        
        # Add first operation and create savepoint
        tx.add_operation(sample_operations[0])
        savepoint_id = tx.create_savepoint("checkpoint_1")
        
        # Add second operation
        tx.add_operation(sample_operations[1])
        assert len(tx.operations) == 2
        
        # Rollback to savepoint
        success = tx.rollback_to_savepoint("checkpoint_1")
        
        assert success is True
        assert len(tx.operations) == 1  # Should have only first operation
        assert len(tx.savepoints) == 1  # Newer savepoints should be removed

    def test_rollback_to_nonexistent_savepoint(self, transaction_manager, sample_context_data):
        """Test rollback to non-existent savepoint."""
        tx = transaction_manager.create_transaction(description="Invalid savepoint test")
        tx.begin(sample_context_data)
        
        # Try to rollback to non-existent savepoint
        success = tx.rollback_to_savepoint("nonexistent_savepoint")
        
        assert success is False

    def test_operation_execution_simulation(self, transaction_manager, sample_context_data, sample_operations):
        """Test operation execution within transaction."""
        tx = transaction_manager.create_transaction(description="Execution test")
        tx.begin(sample_context_data)
        
        for operation in sample_operations:
            tx.add_operation(operation)
        
        # Execute operations (mocked)
        results = tx.execute_operations(
            manipulation_engine=None,  # Will be simulated
            validate_each=True,
            continue_on_error=False
        )
        
        assert len(results) == len(sample_operations)
        
        # Check that all operations have results
        for tx_operation in tx.operations:
            assert tx_operation.execution_result is not None
            assert tx_operation.executed_at is not None
            assert tx_operation.pre_execution_backup_id is not None

    def test_operation_validation_during_execution(self, transaction_manager, sample_context_data):
        """Test operation validation during execution."""
        # Create operation that will fail validation
        invalid_operation = ManipulationOperation(
            operation_id="invalid-test-001",
            operation_type="remove",
            target_keys=["nonexistent_key"],  # Key doesn't exist
            operation_data={},
            estimated_token_impact=-100,
            confidence_score=0.3,  # Low confidence
            reasoning="Invalid operation for testing",
            requires_confirmation=True
        )
        
        tx = transaction_manager.create_transaction(description="Validation test")
        tx.begin(sample_context_data)
        tx.add_operation(invalid_operation)
        
        # Should raise exception due to validation failure
        with pytest.raises(ValueError):
            tx.execute_operations(
                manipulation_engine=None,
                validate_each=True,
                continue_on_error=False
            )

    def test_operation_validation_continue_on_error(self, transaction_manager, sample_context_data):
        """Test operation execution continuing on validation errors."""
        # Create mix of valid and invalid operations
        valid_operation = ManipulationOperation(
            operation_id="valid-test-001",
            operation_type="remove",
            target_keys=["message_2"],
            operation_data={},
            estimated_token_impact=-25,
            confidence_score=0.9,
            reasoning="Valid operation",
            requires_confirmation=False
        )
        
        invalid_operation = ManipulationOperation(
            operation_id="invalid-test-001",
            operation_type="remove",
            target_keys=["nonexistent_key"],
            operation_data={},
            estimated_token_impact=-100,
            confidence_score=0.3,
            reasoning="Invalid operation",
            requires_confirmation=True
        )
        
        tx = transaction_manager.create_transaction(description="Continue on error test")
        tx.begin(sample_context_data)
        tx.add_operation(valid_operation)
        tx.add_operation(invalid_operation)
        
        # Should continue execution despite invalid operation
        results = tx.execute_operations(
            manipulation_engine=None,
            validate_each=True,
            continue_on_error=True
        )
        
        assert len(results) == 1  # Only valid operation executed
        assert tx.operations[0].execution_result is not None
        assert tx.operations[1].execution_error is not None

    def test_transaction_statistics(self, transaction_manager, sample_context_data, sample_operations):
        """Test transaction system statistics."""
        # Initially no transactions
        stats = transaction_manager.get_transaction_statistics()
        assert stats['total_transactions'] == 0
        assert stats['active_transactions'] == 0
        
        # Create and complete a successful transaction
        tx1 = transaction_manager.create_transaction(description="Stats test 1")
        tx1.begin(sample_context_data)
        for operation in sample_operations:
            tx1.add_operation(operation)
        tx1.execute_operations(manipulation_engine=None)
        tx1.commit()
        
        # Create and rollback a failed transaction
        tx2 = transaction_manager.create_transaction(description="Stats test 2")
        tx2.begin(sample_context_data)
        tx2.add_operation(sample_operations[0])
        tx2.rollback()
        
        # Get updated statistics
        stats = transaction_manager.get_transaction_statistics()
        
        assert stats['total_transactions'] == 2
        assert stats['active_transactions'] == 0  # Both completed
        assert stats['successful_transactions'] == 1
        assert stats['failed_transactions'] == 1
        assert stats['rollback_rate'] == 0.5  # 1 out of 2 rolled back
        assert stats['success_rate'] == 0.5  # 1 out of 2 successful
        assert 'average_execution_time' in stats

    def test_transaction_isolation_levels(self, transaction_manager):
        """Test different transaction isolation levels."""
        # Test each isolation level
        for isolation_level in TransactionIsolation:
            tx = transaction_manager.create_transaction(
                isolation_level=isolation_level,
                description=f"Isolation test: {isolation_level.value}"
            )
            
            assert tx.metadata.isolation_level == isolation_level

    def test_transaction_cleanup_on_completion(self, transaction_manager, sample_context_data):
        """Test transaction cleanup when completed."""
        tx = transaction_manager.create_transaction(description="Cleanup test")
        tx_id = tx.metadata.transaction_id
        
        # Transaction should be in active list
        assert tx_id in transaction_manager.active_transactions
        
        tx.begin(sample_context_data)
        result = tx.commit()
        
        # Transaction should be removed from active list and added to history
        assert tx_id not in transaction_manager.active_transactions
        assert len(transaction_manager.transaction_history) == 1
        assert transaction_manager.transaction_history[0] == result

    def test_transaction_metadata_structure(self, transaction_manager):
        """Test transaction metadata structure."""
        tx = transaction_manager.create_transaction(
            isolation_level=TransactionIsolation.READ_COMMITTED,
            description="Metadata structure test",
            tags=["test", "metadata"]
        )
        
        metadata = tx.metadata
        assert isinstance(metadata, TransactionMetadata)
        assert metadata.transaction_id is not None
        assert metadata.isolation_level == TransactionIsolation.READ_COMMITTED
        assert metadata.created_at is not None
        assert metadata.description == "Metadata structure test"
        assert "test" in metadata.tags
        assert "metadata" in metadata.tags
        assert metadata.state == TransactionState.CREATED
        assert metadata.started_at is None  # Not started yet
        assert metadata.completed_at is None  # Not completed yet

    def test_transaction_operation_structure(self, transaction_manager, sample_context_data, sample_operations):
        """Test transaction operation structure."""
        tx = transaction_manager.create_transaction(description="Operation structure test")
        tx.begin(sample_context_data)
        
        operation_id = tx.add_operation(sample_operations[0])
        
        assert len(tx.operations) == 1
        
        tx_operation = tx.operations[0]
        assert isinstance(tx_operation, TransactionOperation)
        assert tx_operation.operation_id == operation_id
        assert tx_operation.operation == sample_operations[0]
        assert tx_operation.pre_execution_backup_id is None  # Not executed yet
        assert tx_operation.execution_result is None
        assert tx_operation.execution_error is None
        assert tx_operation.executed_at is None

    def test_convenience_function_execute_atomic_operations(self, sample_context_data, sample_operations, backup_manager, validator):
        """Test convenience function for atomic operations."""
        result = execute_atomic_operations(
            operations=sample_operations,
            context_data=sample_context_data,
            description="Convenience function test",
            manipulation_engine=None,
            backup_manager=backup_manager,
            validator=validator
        )
        
        assert isinstance(result, TransactionResult)
        assert result.success is True
        assert result.operations_attempted == len(sample_operations)

    def test_transaction_error_handling(self, transaction_manager, sample_context_data):
        """Test transaction error handling."""
        tx = transaction_manager.create_transaction(description="Error handling test")
        
        # Try to add operation before beginning transaction
        with pytest.raises(ValueError):
            tx.add_operation(ManipulationOperation(
                operation_id="error-test-001",
                operation_type="remove",
                target_keys=["key"],
                operation_data={},
                estimated_token_impact=-10,
                confidence_score=0.9,
                reasoning="Error test",
                requires_confirmation=False
            ))
        
        # Try to create savepoint before beginning transaction
        with pytest.raises(ValueError):
            tx.create_savepoint("invalid_savepoint")
        
        # Try to execute operations before beginning transaction
        with pytest.raises(ValueError):
            tx.execute_operations(None)
        
        # Try to commit before beginning transaction
        with pytest.raises(ValueError):
            tx.commit()

    def test_transaction_state_transitions(self, transaction_manager, sample_context_data):
        """Test transaction state transitions."""
        tx = transaction_manager.create_transaction(description="State transition test")
        
        # Initial state
        assert tx.metadata.state == TransactionState.CREATED
        
        # Begin transaction
        tx.begin(sample_context_data)
        assert tx.metadata.state == TransactionState.STARTED
        
        # Commit transaction
        result = tx.commit()
        assert tx.metadata.state == TransactionState.COMMITTED
        assert result.state == TransactionState.COMMITTED

    def test_transaction_state_transitions_rollback(self, transaction_manager, sample_context_data):
        """Test transaction state transitions with rollback."""
        tx = transaction_manager.create_transaction(description="Rollback state test")
        
        tx.begin(sample_context_data)
        assert tx.metadata.state == TransactionState.STARTED
        
        # Rollback transaction
        result = tx.rollback()
        assert tx.metadata.state == TransactionState.ROLLED_BACK
        assert result.state == TransactionState.ROLLED_BACK

    def test_transaction_backup_integration(self, transaction_manager, sample_context_data, sample_operations):
        """Test transaction integration with backup system."""
        tx = transaction_manager.create_transaction(description="Backup integration test")
        tx.begin(sample_context_data)
        
        # Transaction should create a backup
        assert tx.transaction_backup_id is not None
        
        # Backup should exist in backup manager
        backup_entry = transaction_manager.backup_manager.get_backup(tx.transaction_backup_id)
        assert backup_entry is not None
        assert backup_entry.data == sample_context_data
        
        # Add operation and execute
        tx.add_operation(sample_operations[0])
        tx.execute_operations(None)
        
        # Operation should have pre-execution backup
        tx_operation = tx.operations[0]
        assert tx_operation.pre_execution_backup_id is not None
        
        # Pre-execution backup should exist
        pre_backup = transaction_manager.backup_manager.get_backup(tx_operation.pre_execution_backup_id)
        assert pre_backup is not None


class TestTransactionEnums:
    """Test transaction enum values."""

    def test_transaction_state_enum(self):
        """Test TransactionState enum values."""
        assert TransactionState.CREATED.value == "created"
        assert TransactionState.STARTED.value == "started"
        assert TransactionState.COMMITTED.value == "committed"
        assert TransactionState.ROLLED_BACK.value == "rolled_back"
        assert TransactionState.FAILED.value == "failed"

    def test_transaction_isolation_enum(self):
        """Test TransactionIsolation enum values."""
        assert TransactionIsolation.READ_UNCOMMITTED.value == "read_uncommitted"
        assert TransactionIsolation.READ_COMMITTED.value == "read_committed"
        assert TransactionIsolation.REPEATABLE_READ.value == "repeatable_read"
        assert TransactionIsolation.SERIALIZABLE.value == "serializable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])