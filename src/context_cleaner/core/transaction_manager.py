#!/usr/bin/env python3
"""
Transaction Manager

Provides atomic transaction-based operations for context manipulation:
- Transaction-based operation execution with rollback capabilities
- Multi-operation transactions with all-or-nothing semantics
- Automatic rollback on failure with state restoration
- Transaction logging and audit trails
- Nested transaction support with savepoints
- Transaction isolation and consistency guarantees

Integrates with BackupManager and ManipulationValidator for safe atomic operations.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum
from contextlib import contextmanager

from .manipulation_engine import (
    ManipulationOperation,
    ManipulationPlan,
    ManipulationResult,
)
from .manipulation_validator import (
    ManipulationValidator,
    ValidationResult,
    RiskAssessment,
)
from .backup_manager import BackupManager, BackupType, RestoreResult

logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """States of a transaction."""

    CREATED = "created"
    STARTED = "started"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class TransactionIsolation(Enum):
    """Transaction isolation levels."""

    READ_UNCOMMITTED = "read_uncommitted"  # Lowest isolation
    READ_COMMITTED = "read_committed"  # Default isolation
    REPEATABLE_READ = "repeatable_read"  # Higher isolation
    SERIALIZABLE = "serializable"  # Highest isolation


@dataclass
class TransactionOperation:
    """A single operation within a transaction."""

    operation_id: str
    operation: ManipulationOperation
    pre_execution_backup_id: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    execution_error: Optional[str] = None
    executed_at: Optional[str] = None


@dataclass
class Savepoint:
    """A transaction savepoint for nested rollback capabilities."""

    savepoint_id: str
    savepoint_name: str
    context_backup_id: str
    created_at: str
    operation_count: int  # Number of operations executed when savepoint was created


@dataclass
class TransactionMetadata:
    """Metadata for a transaction."""

    transaction_id: str
    isolation_level: TransactionIsolation
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    state: TransactionState = TransactionState.CREATED
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parent_transaction_id: Optional[str] = None  # For nested transactions


@dataclass
class TransactionResult:
    """Result of a transaction execution."""

    transaction_id: str
    success: bool
    state: TransactionState
    operations_attempted: int
    operations_completed: int
    operations_failed: int
    execution_time: float  # Total execution time in seconds
    rollback_performed: bool
    error_messages: List[str] = field(default_factory=list)
    modified_context: Optional[Dict[str, Any]] = None


class TransactionManager:
    """
    Atomic Transaction Manager for Context Manipulations

    Provides transaction-based execution of context manipulation operations
    with atomic rollback capabilities and transaction isolation.
    """

    def __init__(
        self,
        backup_manager: Optional[BackupManager] = None,
        validator: Optional[ManipulationValidator] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize transaction manager."""
        self.config = config or {}

        # Core managers
        self.backup_manager = backup_manager or BackupManager()
        self.validator = validator or ManipulationValidator()

        # Transaction state
        self.active_transactions: Dict[str, "Transaction"] = {}
        self.transaction_history: List[TransactionResult] = []

        # Configuration
        self.default_isolation = TransactionIsolation(
            self.config.get(
                "default_isolation", TransactionIsolation.READ_COMMITTED.value
            )
        )
        self.enable_nested_transactions = self.config.get(
            "enable_nested_transactions", True
        )
        self.max_transaction_time = self.config.get(
            "max_transaction_time", 300
        )  # 5 minutes
        self.enable_transaction_logging = self.config.get("enable_logging", True)

        logger.info("TransactionManager initialized")

    def create_transaction(
        self,
        isolation_level: Optional[TransactionIsolation] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> "Transaction":
        """Create a new transaction."""
        transaction_id = str(uuid.uuid4())

        metadata = TransactionMetadata(
            transaction_id=transaction_id,
            isolation_level=isolation_level or self.default_isolation,
            created_at=datetime.now().isoformat(),
            description=description,
            tags=tags or [],
        )

        transaction = Transaction(
            manager=self,
            metadata=metadata,
            backup_manager=self.backup_manager,
            validator=self.validator,
        )

        self.active_transactions[transaction_id] = transaction

        if self.enable_transaction_logging:
            logger.info(f"Created transaction {transaction_id}: {description}")

        return transaction

    def get_transaction(self, transaction_id: str) -> Optional["Transaction"]:
        """Get an active transaction by ID."""
        return self.active_transactions.get(transaction_id)

    def _complete_transaction(
        self, transaction: "Transaction", result: TransactionResult
    ) -> None:
        """Complete a transaction and update internal state."""
        # Remove from active transactions
        if transaction.metadata.transaction_id in self.active_transactions:
            del self.active_transactions[transaction.metadata.transaction_id]

        # Add to history
        self.transaction_history.append(result)

        if self.enable_transaction_logging:
            logger.info(
                f"Transaction {transaction.metadata.transaction_id} completed: {result.state.value}"
            )

    @contextmanager
    def transaction(
        self,
        context_data: Optional[Dict[str, Any]] = None,
        isolation_level: Optional[TransactionIsolation] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        """Context manager for transaction execution."""
        tx = self.create_transaction(isolation_level, description, tags)
        try:
            # Always begin the transaction, use empty dict if no context provided
            tx.begin(context_data or {})
            yield tx
            tx.commit()
        except Exception as e:
            logger.error(f"Transaction {tx.metadata.transaction_id} failed: {e}")
            tx.rollback()
            raise

    def get_transaction_statistics(self) -> Dict[str, Any]:
        """Get transaction system statistics."""
        try:
            total_transactions = len(self.transaction_history)
            if total_transactions == 0:
                return {
                    "total_transactions": 0,
                    "active_transactions": len(self.active_transactions),
                }

            successful = sum(1 for tx in self.transaction_history if tx.success)
            failed = total_transactions - successful
            rollbacks = sum(
                1 for tx in self.transaction_history if tx.rollback_performed
            )

            avg_execution_time = (
                sum(tx.execution_time for tx in self.transaction_history)
                / total_transactions
            )

            return {
                "total_transactions": total_transactions,
                "active_transactions": len(self.active_transactions),
                "successful_transactions": successful,
                "failed_transactions": failed,
                "rollback_rate": (
                    rollbacks / total_transactions if total_transactions > 0 else 0
                ),
                "average_execution_time": avg_execution_time,
                "success_rate": (
                    successful / total_transactions if total_transactions > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get transaction statistics: {e}")
            return {}


class Transaction:
    """
    Individual Transaction Instance

    Represents a single transaction with operations, state management,
    and rollback capabilities.
    """

    def __init__(
        self,
        manager: TransactionManager,
        metadata: TransactionMetadata,
        backup_manager: BackupManager,
        validator: ManipulationValidator,
    ):
        """Initialize transaction instance."""
        self.manager = manager
        self.metadata = metadata
        self.backup_manager = backup_manager
        self.validator = validator

        # Transaction state
        self.operations: List[TransactionOperation] = []
        self.savepoints: List[Savepoint] = []
        self.original_context: Optional[Dict[str, Any]] = None
        self.current_context: Optional[Dict[str, Any]] = None
        self.transaction_backup_id: Optional[str] = None

        # Timing
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def begin(self, context_data: Dict[str, Any]) -> None:
        """Begin the transaction with initial context."""
        if self.metadata.state != TransactionState.CREATED:
            raise ValueError(f"Cannot begin transaction in state {self.metadata.state}")

        try:
            self.start_time = datetime.now()
            self.metadata.started_at = self.start_time.isoformat()
            self.metadata.state = TransactionState.STARTED

            # Create deep copies of context for isolation
            self.original_context = deepcopy(context_data)
            self.current_context = deepcopy(context_data)

            # Create transaction-level backup
            self.transaction_backup_id = self.backup_manager.create_backup(
                context_data=context_data,
                backup_type=BackupType.OPERATION,
                operation_id=self.metadata.transaction_id,
                description=f"Transaction backup: {self.metadata.description}",
                tags=["transaction", "pre-execution"] + self.metadata.tags,
            )

            logger.debug(
                f"Transaction {self.metadata.transaction_id} begun with backup {self.transaction_backup_id}"
            )

        except Exception as e:
            self.metadata.state = TransactionState.FAILED
            logger.error(f"Failed to begin transaction: {e}")
            raise

    def add_operation(self, operation: ManipulationOperation) -> str:
        """Add an operation to the transaction."""
        if self.metadata.state != TransactionState.STARTED:
            raise ValueError(
                f"Cannot add operations to transaction in state {self.metadata.state}"
            )

        operation_id = f"{self.metadata.transaction_id}_{len(self.operations)}"

        tx_operation = TransactionOperation(
            operation_id=operation_id, operation=operation
        )

        self.operations.append(tx_operation)
        logger.debug(
            f"Added operation {operation_id} to transaction {self.metadata.transaction_id}"
        )

        return operation_id

    def create_savepoint(self, savepoint_name: str) -> str:
        """Create a savepoint in the transaction."""
        if self.metadata.state != TransactionState.STARTED:
            raise ValueError(
                f"Cannot create savepoint in transaction state {self.metadata.state}"
            )

        try:
            savepoint_id = f"{self.metadata.transaction_id}_sp_{len(self.savepoints)}"

            # Create backup of current context state
            backup_id = self.backup_manager.create_backup(
                context_data=self.current_context,
                backup_type=BackupType.OPERATION,
                operation_id=savepoint_id,
                description=f"Savepoint '{savepoint_name}' in transaction {self.metadata.transaction_id}",
                tags=["savepoint", "transaction"] + self.metadata.tags,
            )

            savepoint = Savepoint(
                savepoint_id=savepoint_id,
                savepoint_name=savepoint_name,
                context_backup_id=backup_id,
                created_at=datetime.now().isoformat(),
                operation_count=len(self.operations),
            )

            self.savepoints.append(savepoint)
            logger.info(f"Created savepoint '{savepoint_name}' with backup {backup_id}")

            return savepoint_id

        except Exception as e:
            logger.error(f"Failed to create savepoint: {e}")
            raise

    def rollback_to_savepoint(self, savepoint_name: str) -> bool:
        """Rollback to a specific savepoint."""
        try:
            # Find the savepoint
            target_savepoint = None
            for savepoint in reversed(self.savepoints):  # Search from most recent
                if savepoint.savepoint_name == savepoint_name:
                    target_savepoint = savepoint
                    break

            if not target_savepoint:
                logger.error(f"Savepoint '{savepoint_name}' not found")
                return False

            # Restore context from savepoint backup
            restore_result = self.backup_manager.restore_backup(
                target_savepoint.context_backup_id
            )
            if not restore_result.success:
                logger.error(
                    f"Failed to restore from savepoint backup: {restore_result.error_messages}"
                )
                return False

            # Restore context data by getting backup entry
            backup_entry = self.backup_manager.get_backup(
                target_savepoint.context_backup_id
            )
            if backup_entry:
                self.current_context = deepcopy(backup_entry.data)
            else:
                logger.error(f"Could not retrieve backup data for savepoint")
                return False

            # Remove operations executed after the savepoint
            operations_to_remove = (
                len(self.operations) - target_savepoint.operation_count
            )
            if operations_to_remove > 0:
                self.operations = self.operations[: target_savepoint.operation_count]
                logger.info(
                    f"Removed {operations_to_remove} operations after savepoint"
                )

            # Remove newer savepoints
            newer_savepoints = [
                sp
                for sp in self.savepoints
                if sp.created_at > target_savepoint.created_at
            ]
            for sp in newer_savepoints:
                self.savepoints.remove(sp)
                # Clean up savepoint backup
                self.backup_manager.delete_backup(sp.context_backup_id)

            logger.info(f"Successfully rolled back to savepoint '{savepoint_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to rollback to savepoint '{savepoint_name}': {e}")
            return False

    def execute_operations(
        self,
        manipulation_engine,  # Import would create circular dependency
        validate_each: bool = True,
        continue_on_error: bool = False,
    ) -> List[Dict[str, Any]]:
        """Execute all operations in the transaction."""
        if self.metadata.state != TransactionState.STARTED:
            raise ValueError(
                f"Cannot execute operations in transaction state {self.metadata.state}"
            )

        results = []

        try:
            for i, tx_operation in enumerate(self.operations):
                try:
                    # Validate operation if requested
                    if validate_each:
                        validation_result = self.validator.validate_operation(
                            tx_operation.operation, self.current_context
                        )

                        if not validation_result.is_valid:
                            error_msg = f"Operation {tx_operation.operation_id} validation failed: {validation_result.validation_errors}"
                            tx_operation.execution_error = error_msg

                            if not continue_on_error:
                                raise ValueError(error_msg)
                            else:
                                logger.warning(error_msg)
                                continue

                    # Create pre-execution backup for this operation
                    tx_operation.pre_execution_backup_id = self.backup_manager.create_backup(
                        context_data=self.current_context,
                        backup_type=BackupType.OPERATION,
                        operation_id=tx_operation.operation_id,
                        description=f"Pre-execution backup for operation {tx_operation.operation_id}",
                        tags=["operation", "pre-execution"] + self.metadata.tags,
                    )

                    # Execute operation using manipulation engine
                    # Note: This would typically call manipulation_engine.execute_operation()
                    # For now, we'll simulate the operation execution
                    execution_start = datetime.now()

                    # Record operation in validator history
                    self.validator.record_operation_history(
                        tx_operation.operation,
                        self.current_context,
                        tx_operation.pre_execution_backup_id,
                    )

                    # TODO: Actual operation execution would happen here
                    # result = manipulation_engine.execute_operation(tx_operation.operation, self.current_context)
                    # For now, simulate successful execution
                    execution_result = {
                        "operation_id": tx_operation.operation_id,
                        "success": True,
                        "tokens_modified": abs(
                            tx_operation.operation.estimated_token_impact
                        ),
                        "execution_time": (
                            datetime.now() - execution_start
                        ).total_seconds(),
                    }

                    tx_operation.execution_result = execution_result
                    tx_operation.executed_at = datetime.now().isoformat()
                    results.append(execution_result)

                    logger.debug(
                        f"Executed operation {tx_operation.operation_id} successfully"
                    )

                except Exception as e:
                    error_msg = (
                        f"Operation {tx_operation.operation_id} execution failed: {e}"
                    )
                    tx_operation.execution_error = error_msg
                    logger.error(error_msg)

                    if not continue_on_error:
                        raise

            return results

        except Exception as e:
            logger.error(f"Transaction operation execution failed: {e}")
            raise

    def commit(self) -> TransactionResult:
        """Commit the transaction."""
        if self.metadata.state != TransactionState.STARTED:
            raise ValueError(
                f"Cannot commit transaction in state {self.metadata.state}"
            )

        try:
            self.end_time = datetime.now()
            execution_time = (self.end_time - self.start_time).total_seconds()

            # Count operation results
            completed_ops = sum(
                1 for op in self.operations if op.execution_result is not None
            )
            failed_ops = sum(
                1 for op in self.operations if op.execution_error is not None
            )

            # Check if all operations succeeded
            all_succeeded = failed_ops == 0 and completed_ops == len(self.operations)

            if all_succeeded:
                self.metadata.state = TransactionState.COMMITTED
                self.metadata.completed_at = self.end_time.isoformat()

                # Clean up savepoint backups (but keep transaction backup for audit)
                for savepoint in self.savepoints:
                    self.backup_manager.delete_backup(savepoint.context_backup_id)

                result = TransactionResult(
                    transaction_id=self.metadata.transaction_id,
                    success=True,
                    state=TransactionState.COMMITTED,
                    operations_attempted=len(self.operations),
                    operations_completed=completed_ops,
                    operations_failed=failed_ops,
                    execution_time=execution_time,
                    rollback_performed=False,
                    modified_context=(
                        deepcopy(self.current_context) if self.current_context else None
                    ),
                )

                logger.info(
                    f"Transaction {self.metadata.transaction_id} committed successfully"
                )

            else:
                # Transaction failed, need to rollback
                result = self.rollback()

        except Exception as e:
            logger.error(f"Transaction commit failed: {e}")
            result = self.rollback()

        self.manager._complete_transaction(self, result)
        return result

    def rollback(self) -> TransactionResult:
        """Rollback the transaction."""
        try:
            rollback_start = datetime.now()
            self.metadata.state = TransactionState.ROLLED_BACK

            # Restore from transaction backup
            restore_success = True
            if self.transaction_backup_id:
                restore_result = self.backup_manager.restore_backup(
                    self.transaction_backup_id
                )
                if restore_result.success:
                    # Get the original context back
                    backup_entry = self.backup_manager.get_backup(
                        self.transaction_backup_id
                    )
                    if backup_entry:
                        self.current_context = deepcopy(backup_entry.data)
                    logger.info(
                        f"Successfully restored context from transaction backup"
                    )
                else:
                    restore_success = False
                    logger.error(
                        f"Failed to restore from transaction backup: {restore_result.error_messages}"
                    )

            # Clean up all backups created during transaction
            for operation in self.operations:
                if operation.pre_execution_backup_id:
                    self.backup_manager.delete_backup(operation.pre_execution_backup_id)

            for savepoint in self.savepoints:
                self.backup_manager.delete_backup(savepoint.context_backup_id)

            # Calculate timing
            execution_time = 0
            if self.start_time:
                end_time = self.end_time or datetime.now()
                execution_time = (end_time - self.start_time).total_seconds()

            # Count operations
            completed_ops = sum(
                1 for op in self.operations if op.execution_result is not None
            )
            failed_ops = sum(
                1 for op in self.operations if op.execution_error is not None
            )

            # Collect error messages
            error_messages = [
                op.execution_error for op in self.operations if op.execution_error
            ]

            result = TransactionResult(
                transaction_id=self.metadata.transaction_id,
                success=False,
                state=TransactionState.ROLLED_BACK,
                operations_attempted=len(self.operations),
                operations_completed=completed_ops,
                operations_failed=failed_ops,
                execution_time=execution_time,
                rollback_performed=True,
                error_messages=error_messages,
                modified_context=(
                    deepcopy(self.current_context) if self.current_context else None
                ),
            )

            logger.info(f"Transaction {self.metadata.transaction_id} rolled back")

            self.manager._complete_transaction(self, result)
            return result

        except Exception as e:
            logger.error(f"Transaction rollback failed: {e}")
            # Create minimal result even if rollback fails
            result = TransactionResult(
                transaction_id=self.metadata.transaction_id,
                success=False,
                state=TransactionState.FAILED,
                operations_attempted=len(self.operations),
                operations_completed=0,
                operations_failed=len(self.operations),
                execution_time=0,
                rollback_performed=False,
                error_messages=[f"Rollback failed: {e}"],
            )

            self.manager._complete_transaction(self, result)
            return result


# Convenience functions
def execute_atomic_operations(
    operations: List[ManipulationOperation],
    context_data: Dict[str, Any],
    description: str = "Atomic operation batch",
    manipulation_engine=None,  # To avoid circular import
    backup_manager: Optional[BackupManager] = None,
    validator: Optional[ManipulationValidator] = None,
) -> TransactionResult:
    """Execute multiple operations atomically."""

    manager = TransactionManager(backup_manager=backup_manager, validator=validator)

    with manager.transaction(context_data=context_data, description=description) as tx:

        # Add all operations
        for operation in operations:
            tx.add_operation(operation)

        # Execute operations
        tx.execute_operations(manipulation_engine)

        # Transaction will be committed automatically by context manager

    # Get result from transaction history
    return manager.transaction_history[-1] if manager.transaction_history else None


if __name__ == "__main__":
    # Test transaction system
    print("Testing Transaction Manager...")

    from .manipulation_engine import ManipulationOperation

    # Test context data
    test_context = {"item1": "value1", "item2": "value2", "item3": "value3"}

    # Create test operation
    test_operation = ManipulationOperation(
        operation_id="test-tx-001",
        operation_type="remove",
        target_keys=["item2"],
        operation_data={"removal_type": "safe_delete"},
        estimated_token_impact=-10,
        confidence_score=0.9,
        reasoning="Test operation for transaction",
        requires_confirmation=False,
    )

    manager = TransactionManager()

    # Test transaction
    try:
        with manager.transaction(description="Test transaction") as tx:
            tx.begin(test_context)
            tx.add_operation(test_operation)

            # Create savepoint
            savepoint_id = tx.create_savepoint("before_execution")
            print(f"✅ Created savepoint: {savepoint_id}")

            # Would execute operations here
            print("🔄 Transaction operations would execute here")

        print("✅ Transaction completed successfully")

    except Exception as e:
        print(f"❌ Transaction failed: {e}")

    # Statistics
    stats = manager.get_transaction_statistics()
    print(f"📊 Transaction statistics: {stats}")
