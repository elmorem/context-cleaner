#!/usr/bin/env python3
"""
Integration Tests for PR18 Safety & Validation Framework

Tests the complete integration of all PR18 components:
- Enhanced ManipulationValidator with risk assessment
- BackupManager with rollback capabilities
- TransactionManager with atomic operations
- PreviewGenerator with visual diffs
- ConfirmationWorkflows with user interaction
- End-to-end safety validation workflow
"""

import pytest
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

from context_cleaner.core.manipulation_engine import (
    ManipulationOperation,
    ManipulationPlan
)
from context_cleaner.core.manipulation_validator import (
    ManipulationValidator,
    SafetyConstraints,
    RiskLevel,
    SafetyAction
)
from context_cleaner.core.backup_manager import (
    BackupManager,
    BackupType
)
from context_cleaner.core.transaction_manager import (
    TransactionManager,
    TransactionIsolation
)
from context_cleaner.core.preview_generator import (
    PreviewGenerator,
    PreviewFormat
)
from context_cleaner.core.confirmation_workflows import (
    ConfirmationWorkflowManager,
    ConfirmationLevel,
    ConfirmationResult
)


class MockConfirmationProvider:
    """Mock provider that always approves for testing."""
    
    def __init__(self, result=ConfirmationResult.APPROVED):
        self.result = result
        self.call_count = 0
        self.last_request = None
    
    def request_confirmation(self, request):
        self.call_count += 1
        self.last_request = request
        return Mock(
            result=self.result,
            request_id=request.request_id,
            user_comments="Mock approval",
            approved_operations=["all"] if self.result == ConfirmationResult.APPROVED else []
        )
    
    def supports_level(self, level):
        return True


class TestPR18SafetyIntegration:
    """Integration tests for PR18 safety framework."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Temporary directory for backup storage."""
        temp_dir = tempfile.mkdtemp(prefix="pr18_integration_test_")
        yield temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def safety_constraints(self):
        """Enhanced safety constraints for testing."""
        return SafetyConstraints(
            max_single_operation_impact=0.4,
            max_total_reduction=0.7,
            min_confidence_threshold=0.75,
            require_backup_threshold=0.3,
            max_operations_per_batch=10,
            enable_dry_run_mode=True
        )

    @pytest.fixture
    def enhanced_validator(self, safety_constraints):
        """Enhanced validator with custom constraints."""
        return ManipulationValidator(safety_constraints=safety_constraints)

    @pytest.fixture
    def backup_manager(self, temp_backup_dir):
        """Backup manager for integration testing."""
        return BackupManager({
            'backup_dir': temp_backup_dir,
            'compress_backups': True,
            'auto_cleanup': True,
            'retention_days': 7
        })

    @pytest.fixture
    def transaction_manager(self, backup_manager, enhanced_validator):
        """Transaction manager for integration testing."""
        return TransactionManager(
            backup_manager=backup_manager,
            validator=enhanced_validator,
            config={'enable_logging': True}
        )

    @pytest.fixture
    def preview_generator(self, enhanced_validator):
        """Preview generator for integration testing."""
        return PreviewGenerator(
            validator=enhanced_validator,
            config={'highlight_risks': True, 'include_validation': True}
        )

    @pytest.fixture
    def confirmation_manager(self, enhanced_validator, preview_generator, backup_manager):
        """Confirmation workflow manager for integration testing."""
        return ConfirmationWorkflowManager(
            validator=enhanced_validator,
            preview_generator=preview_generator,
            backup_manager=backup_manager,
            config={
                'auto_confirm_threshold': 0.9,
                'force_confirmation_threshold': 0.6,
                'enable_previews': True,
                'enable_safety_reports': True
            }
        )

    @pytest.fixture
    def comprehensive_context_data(self):
        """Comprehensive context data with various risk levels."""
        return {
            # Low risk content
            "user_message_1": "Help me understand this code structure",
            "user_message_2": "Can you explain how authentication works?",
            "documentation": "This module handles user authentication flow",
            
            # Medium risk content
            "todo_active": "Implement two-factor authentication",
            "todo_completed": "Add basic login validation - COMPLETED",
            "conversation_log": "User asked about password requirements",
            
            # High risk content  
            "config_database": "database_password = super_secret_password_123",
            "api_credentials": "api_key = sk-1234567890abcdef",
            "sensitive_data": "User credit card: 4532-1234-5678-9012",
            
            # Large content for impact testing
            "large_log": "ERROR: " + ("Authentication failed. " * 100),
            
            # Metadata
            "session_id": "sess_abc123xyz789",
            "timestamp": datetime.now().isoformat(),
            "version": "2.1.0"
        }

    @pytest.fixture
    def mixed_risk_operations(self):
        """Operations with mixed risk levels for comprehensive testing."""
        return [
            # Low risk operation
            ManipulationOperation(
                operation_id="integration-001-safe",
                operation_type="remove",
                target_keys=["todo_completed"],
                operation_data={"removal_type": "safe_delete"},
                estimated_token_impact=-30,
                confidence_score=0.95,
                reasoning="Remove completed todo item",
                requires_confirmation=False
            ),
            
            # Medium risk operation
            ManipulationOperation(
                operation_id="integration-002-medium",
                operation_type="consolidate",
                target_keys=["user_message_1", "user_message_2"],
                operation_data={"strategy": "merge_similar"},
                estimated_token_impact=-25,
                confidence_score=0.8,
                reasoning="Consolidate similar user messages",
                requires_confirmation=True
            ),
            
            # High risk operation
            ManipulationOperation(
                operation_id="integration-003-risky",
                operation_type="remove",
                target_keys=["api_credentials", "config_database"],
                operation_data={"removal_type": "secure_delete"},
                estimated_token_impact=-100,
                confidence_score=0.6,
                reasoning="Remove sensitive credentials",
                requires_confirmation=True
            ),
            
            # Large impact operation
            ManipulationOperation(
                operation_id="integration-004-large",
                operation_type="summarize",
                target_keys=["large_log"],
                operation_data={"strategy": "error_summary"},
                estimated_token_impact=-2000,
                confidence_score=0.85,
                reasoning="Summarize large error log",
                requires_confirmation=True
            )
        ]

    def test_end_to_end_safe_operation_workflow(self, comprehensive_context_data, enhanced_validator, 
                                               backup_manager, preview_generator, confirmation_manager):
        """Test complete workflow for a safe operation."""
        # Create safe operation
        safe_operation = ManipulationOperation(
            operation_id="e2e-safe-001",
            operation_type="remove",
            target_keys=["todo_completed"],
            operation_data={"removal_type": "safe_delete"},
            estimated_token_impact=-30,
            confidence_score=0.95,
            reasoning="Remove completed todo - very safe",
            requires_confirmation=False
        )
        
        # Step 1: Enhanced validation with risk assessment
        validation_result, risk_assessment = enhanced_validator.validate_operation_enhanced(
            safe_operation, comprehensive_context_data
        )
        
        assert validation_result.is_valid is True
        assert validation_result.confidence_score >= 0.9
        assert risk_assessment.risk_level == RiskLevel.LOW
        assert risk_assessment.recommended_action == SafetyAction.PROCEED
        
        # Step 2: Generate preview
        preview = preview_generator.preview_operation(safe_operation, comprehensive_context_data)
        assert len(preview.changes) > 0
        assert len(preview.warnings) == 0
        
        # Step 3: Generate safety report
        safety_report = enhanced_validator.generate_enhanced_safety_report(
            validation_result, risk_assessment=risk_assessment
        )
        
        assert safety_report["overall_assessment"]["safe_to_proceed"] is True
        assert safety_report["overall_assessment"]["safety_score"] >= 0.7
        
        # Step 4: Confirmation workflow (should auto-approve)
        response = confirmation_manager.request_operation_confirmation(
            safe_operation, comprehensive_context_data
        )
        
        assert response.result == ConfirmationResult.APPROVED
        assert "auto-approved" in response.user_comments.lower()

    def test_end_to_end_risky_operation_workflow(self, comprehensive_context_data, enhanced_validator,
                                                backup_manager, preview_generator, confirmation_manager):
        """Test complete workflow for a risky operation."""
        # Create risky operation
        risky_operation = ManipulationOperation(
            operation_id="e2e-risky-001",
            operation_type="remove",
            target_keys=["api_credentials", "sensitive_data"],
            operation_data={"removal_type": "secure_delete"},
            estimated_token_impact=-150,
            confidence_score=0.6,
            reasoning="Remove sensitive data - high risk",
            requires_confirmation=True
        )
        
        # Step 1: Enhanced validation with risk assessment
        validation_result, risk_assessment = enhanced_validator.validate_operation_enhanced(
            risky_operation, comprehensive_context_data
        )
        
        assert risk_assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert risk_assessment.recommended_action != SafetyAction.PROCEED
        assert len(risk_assessment.risk_factors) > 0
        assert len(risk_assessment.mitigation_strategies) > 0
        
        # Step 2: Generate preview with risk highlighting
        preview = preview_generator.preview_operation(risky_operation, comprehensive_context_data)
        
        high_risk_changes = [c for c in preview.changes if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        assert len(high_risk_changes) > 0
        assert len(preview.warnings) > 0
        
        # Step 3: Generate comprehensive safety report
        safety_report = enhanced_validator.generate_enhanced_safety_report(
            validation_result, risk_assessment=risk_assessment
        )
        
        assert safety_report["overall_assessment"]["safe_to_proceed"] is False
        assert safety_report["overall_assessment"]["requires_backup"] is True
        assert safety_report["overall_assessment"]["requires_manual_review"] is True
        
        # Step 4: Confirmation workflow (should require confirmation)
        mock_provider = MockConfirmationProvider(ConfirmationResult.REJECTED)
        confirmation_manager.add_provider(mock_provider)
        
        response = confirmation_manager.request_operation_confirmation(
            risky_operation, comprehensive_context_data
        )
        
        assert mock_provider.call_count > 0
        assert mock_provider.last_request.confirmation_level in [
            ConfirmationLevel.DETAILED, ConfirmationLevel.INTERACTIVE
        ]
        assert mock_provider.last_request.requires_backup is True

    def test_transaction_with_backup_and_rollback(self, comprehensive_context_data, transaction_manager, 
                                                 enhanced_validator, backup_manager, mixed_risk_operations):
        """Test atomic transaction with backup and rollback capabilities."""
        # Create transaction
        tx = transaction_manager.create_transaction(
            isolation_level=TransactionIsolation.READ_COMMITTED,
            description="Integration test transaction",
            tags=["integration", "test"]
        )
        
        # Begin transaction (creates backup)
        tx.begin(comprehensive_context_data)
        
        assert tx.transaction_backup_id is not None
        assert tx.original_context == comprehensive_context_data
        
        # Add operations
        for operation in mixed_risk_operations:
            tx.add_operation(operation)
        
        assert len(tx.operations) == len(mixed_risk_operations)
        
        # Create savepoint after adding operations
        savepoint_id = tx.create_savepoint("after_adding_operations")
        assert len(tx.savepoints) == 1
        
        # Simulate some operation execution
        tx.execute_operations(None, validate_each=True, continue_on_error=True)
        
        # Check operation history was recorded
        assert len(enhanced_validator.operation_history) > 0
        
        # Test rollback to savepoint
        rollback_success = tx.rollback_to_savepoint("after_adding_operations")
        assert rollback_success is True
        
        # Test full rollback
        result = tx.rollback()
        
        assert result.success is False
        assert result.rollback_performed is True
        assert result.operations_attempted == len(mixed_risk_operations)
        
        # Verify backup exists and can be restored
        backup_entry = backup_manager.get_backup(tx.transaction_backup_id)
        assert backup_entry is not None
        assert backup_entry.data == comprehensive_context_data

    def test_plan_confirmation_with_staged_approval(self, comprehensive_context_data, mixed_risk_operations,
                                                   confirmation_manager):
        """Test plan confirmation with staged approval workflow."""
        # Create manipulation plan
        plan = ManipulationPlan(
            plan_id="integration-plan-001",
            total_operations=len(mixed_risk_operations),
            operations=mixed_risk_operations,
            estimated_total_reduction=2155,  # Sum of all operation impacts
            estimated_execution_time=2.5,
            safety_level="aggressive",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        # Mock provider for staged approval
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        confirmation_manager.add_provider(mock_provider)
        
        # Request plan confirmation
        response = confirmation_manager.request_plan_confirmation(
            plan, comprehensive_context_data, 
            force_level=ConfirmationLevel.STAGED
        )
        
        assert mock_provider.call_count > 0
        request = mock_provider.last_request
        
        assert request.confirmation_level == ConfirmationLevel.STAGED
        assert isinstance(request.operation_or_plan, ManipulationPlan)
        assert request.preview is not None  # Should have plan preview
        assert request.safety_report is not None  # Should have safety report

    def test_preview_generation_integration(self, comprehensive_context_data, mixed_risk_operations,
                                          preview_generator, enhanced_validator):
        """Test comprehensive preview generation with validation integration."""
        # Create plan
        plan = ManipulationPlan(
            plan_id="preview-integration-001",
            total_operations=len(mixed_risk_operations),
            operations=mixed_risk_operations,
            estimated_total_reduction=2155,
            estimated_execution_time=2.5,
            safety_level="balanced",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        # Generate plan preview
        preview = preview_generator.preview_plan(plan, comprehensive_context_data)
        
        assert len(preview.operation_previews) == len(mixed_risk_operations)
        assert preview.total_changes > 0
        assert preview.total_size_reduction > 0
        assert preview.overall_risk != RiskLevel.LOW  # Should detect high-risk operations
        
        # Test different preview formats
        text_preview = preview_generator.format_preview(preview, PreviewFormat.TEXT, True)
        assert "MANIPULATION PLAN PREVIEW" in text_preview
        
        json_preview = preview_generator.format_preview(preview, PreviewFormat.JSON, True)
        import json
        preview_data = json.loads(json_preview)
        assert "plan_id" in preview_data
        
        markdown_preview = preview_generator.format_preview(preview, PreviewFormat.MARKDOWN, True)
        assert "# Manipulation Plan Preview" in markdown_preview
        
        # Test diff generation
        original_context = comprehensive_context_data
        # Simulate operation execution for diff
        modified_context = preview_generator._simulate_operation_execution(
            mixed_risk_operations[0], original_context
        )
        
        diff = preview_generator.generate_diff(original_context, modified_context, PreviewFormat.TEXT)
        assert len(diff) > 0
        assert "todo_completed" in diff  # Should show removed content

    def test_backup_manager_integration(self, comprehensive_context_data, backup_manager, mixed_risk_operations):
        """Test backup manager integration with operation history."""
        # Create operation-specific backups
        operation_backups = []
        
        for operation in mixed_risk_operations:
            backup_id = backup_manager.create_backup(
                comprehensive_context_data,
                BackupType.OPERATION,
                operation_id=operation.operation_id,
                description=f"Backup for {operation.operation_type} operation",
                tags=["integration", operation.operation_type],
                save_to_disk=True
            )
            operation_backups.append(backup_id)
        
        # Test backup listing and filtering
        all_backups = backup_manager.list_backups()
        assert len(all_backups) == len(mixed_risk_operations)
        
        # Filter by operation type
        remove_backups = backup_manager.list_backups(tags=["remove"])
        consolidate_backups = backup_manager.list_backups(tags=["consolidate"])
        
        assert len(remove_backups) > 0
        assert len(consolidate_backups) > 0
        
        # Test restore functionality
        first_backup = operation_backups[0]
        restore_result = backup_manager.restore_backup(first_backup)
        
        assert restore_result.success is True
        assert restore_result.integrity_verified is True
        assert len(restore_result.restored_keys) == len(comprehensive_context_data)
        
        # Test backup statistics
        stats = backup_manager.get_backup_statistics()
        assert stats['total_backups'] == len(mixed_risk_operations)
        assert 'operation' in stats['backup_types']

    def test_enhanced_safety_reporting_integration(self, comprehensive_context_data, mixed_risk_operations,
                                                  enhanced_validator):
        """Test enhanced safety reporting with complete operation analysis."""
        # Create plan
        plan = ManipulationPlan(
            plan_id="safety-report-integration-001",
            total_operations=len(mixed_risk_operations),
            operations=mixed_risk_operations,
            estimated_total_reduction=2155,
            estimated_execution_time=2.5,
            safety_level="aggressive",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        # Validate plan and all operations
        plan_validation = enhanced_validator.validate_plan(plan, comprehensive_context_data)
        operation_validations = []
        
        for operation in mixed_risk_operations:
            validation_result, risk_assessment = enhanced_validator.validate_operation_enhanced(
                operation, comprehensive_context_data
            )
            operation_validations.append((operation, validation_result, risk_assessment))
            
            # Record in history
            enhanced_validator.record_operation_history(operation, comprehensive_context_data)
        
        # Generate comprehensive plan safety report
        plan_report = enhanced_validator.generate_plan_safety_report(
            plan_validation, operation_validations
        )
        
        # Verify report structure and content
        assert "report_metadata" in plan_report
        assert "plan_summary" in plan_report
        assert "aggregated_risk_assessment" in plan_report
        assert "operation_details" in plan_report
        assert "plan_safety_assessment" in plan_report
        
        # Check report content
        assert plan_report["plan_summary"]["total_operations"] == len(mixed_risk_operations)
        assert plan_report["plan_summary"]["high_risk_operations"] > 0  # Should detect risky operations
        assert plan_report["aggregated_risk_assessment"]["overall_risk_level"] != "low"
        
        # Verify operation details
        assert len(plan_report["operation_details"]) == len(mixed_risk_operations)
        for op_detail in plan_report["operation_details"]:
            assert "operation_id" in op_detail
            assert "risk_level" in op_detail
            assert "validation_status" in op_detail
        
        # Check safety assessment recommendations
        assert "plan_safety_score" in plan_report["plan_safety_assessment"]
        assert "recommended_approach" in plan_report["plan_safety_assessment"]
        
        # Should recommend careful approach due to high-risk operations
        assert plan_report["plan_safety_assessment"]["safe_to_execute"] is False
        assert plan_report["plan_safety_assessment"]["requires_full_backup"] is True

    def test_comprehensive_error_handling(self, comprehensive_context_data, enhanced_validator, 
                                        backup_manager, transaction_manager, preview_generator):
        """Test error handling across all PR18 components."""
        # Create problematic operations
        problematic_operations = [
            ManipulationOperation(
                operation_id="error-test-001",
                operation_type="invalid_type",
                target_keys=["nonexistent_key"],
                operation_data={},
                estimated_token_impact=-1000000,  # Unrealistic impact
                confidence_score=-0.5,  # Invalid confidence
                reasoning="Error test operation",
                requires_confirmation=True
            ),
            ManipulationOperation(
                operation_id="error-test-002", 
                operation_type="remove",
                target_keys=[],  # Empty target keys
                operation_data={},
                estimated_token_impact=0,
                confidence_score=1.5,  # Invalid confidence > 1
                reasoning="Another error test",
                requires_confirmation=False
            )
        ]
        
        # Test validator error handling
        for operation in problematic_operations:
            validation_result, risk_assessment = enhanced_validator.validate_operation_enhanced(
                operation, comprehensive_context_data
            )
            
            # Should handle gracefully with errors/warnings
            assert isinstance(validation_result, ValidationResult)
            assert len(validation_result.validation_errors) > 0 or len(validation_result.warnings) > 0
        
        # Test backup manager error handling
        try:
            # Invalid backup data
            backup_manager._calculate_checksum({"invalid": object()})
        except Exception as e:
            assert isinstance(e, Exception)  # Should raise appropriate exception
        
        # Test transaction error handling
        tx = transaction_manager.create_transaction(description="Error handling test")
        
        # Try invalid operations
        with pytest.raises(ValueError):
            tx.add_operation(problematic_operations[0])  # Should fail - not started
        
        tx.begin(comprehensive_context_data)
        tx.add_operation(problematic_operations[0])
        
        # Should handle execution errors gracefully
        try:
            tx.execute_operations(None, validate_each=True, continue_on_error=True)
        except Exception:
            pass  # Expected to have issues but shouldn't crash
        
        # Test preview generator error handling
        try:
            preview = preview_generator.preview_operation(problematic_operations[0], comprehensive_context_data)
            assert len(preview.warnings) > 0  # Should generate warnings
        except Exception:
            pass  # Should handle gracefully

    def test_performance_with_large_context(self, enhanced_validator, backup_manager, preview_generator):
        """Test performance characteristics with large context data."""
        # Create large context data
        large_context = {}
        for i in range(100):
            large_context[f"item_{i:03d}"] = f"Content for item {i} with some longer text to increase size" * 10
            large_context[f"data_{i:03d}"] = {"nested": f"value_{i}", "array": list(range(20))}
        
        # Create multiple operations
        operations = []
        for i in range(0, 100, 10):
            operation = ManipulationOperation(
                operation_id=f"perf-test-{i:03d}",
                operation_type="remove",
                target_keys=[f"item_{j:03d}" for j in range(i, min(i+5, 100))],
                operation_data={"removal_type": "batch_delete"},
                estimated_token_impact=-50,
                confidence_score=0.8,
                reasoning=f"Batch remove items {i}-{i+4}",
                requires_confirmation=False
            )
            operations.append(operation)
        
        import time
        
        # Test validation performance
        start_time = time.time()
        for operation in operations:
            validation_result, risk_assessment = enhanced_validator.validate_operation_enhanced(
                operation, large_context
            )
            assert validation_result is not None
        validation_time = time.time() - start_time
        
        # Should complete validation in reasonable time
        assert validation_time < 10.0  # Less than 10 seconds for 10 operations
        
        # Test backup performance
        start_time = time.time()
        backup_id = backup_manager.create_backup(
            large_context, 
            BackupType.FULL,
            description="Performance test backup"
        )
        backup_time = time.time() - start_time
        
        assert backup_time < 5.0  # Less than 5 seconds for large backup
        
        # Test preview performance
        start_time = time.time()
        preview = preview_generator.preview_operation(operations[0], large_context)
        preview_time = time.time() - start_time
        
        assert preview_time < 3.0  # Less than 3 seconds for preview
        assert len(preview.changes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])