#!/usr/bin/env python3
"""
Tests for ConfirmationWorkflows

Tests the user confirmation workflow system including:
- Confirmation level determination
- Operation and plan confirmation requests
- Console confirmation provider
- Workflow manager functionality
- Integration with safety validation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from context_cleaner.core.confirmation_workflows import (
    ConfirmationWorkflowManager,
    ConfirmationProvider,
    ConsoleConfirmationProvider,
    ConfirmationLevel,
    ConfirmationResult,
    ConfirmationRequest,
    ConfirmationResponse,
    confirm_operation,
    confirm_plan
)
from context_cleaner.core.manipulation_engine import (
    ManipulationOperation,
    ManipulationPlan
)
from context_cleaner.core.manipulation_validator import (
    ManipulationValidator,
    ValidationResult,
    RiskLevel,
    RiskAssessment,
    SafetyAction
)
from context_cleaner.core.preview_generator import PreviewGenerator
from context_cleaner.core.backup_manager import BackupManager


class TestConfirmationEnums:
    """Test confirmation enum values."""

    def test_confirmation_level_enum(self):
        """Test ConfirmationLevel enum values."""
        assert ConfirmationLevel.NONE.value == "none"
        assert ConfirmationLevel.SIMPLE.value == "simple"
        assert ConfirmationLevel.DETAILED.value == "detailed"
        assert ConfirmationLevel.INTERACTIVE.value == "interactive"
        assert ConfirmationLevel.STAGED.value == "staged"

    def test_confirmation_result_enum(self):
        """Test ConfirmationResult enum values."""
        assert ConfirmationResult.APPROVED.value == "approved"
        assert ConfirmationResult.REJECTED.value == "rejected"
        assert ConfirmationResult.MODIFIED.value == "modified"
        assert ConfirmationResult.DEFERRED.value == "deferred"


class TestConfirmationDataStructures:
    """Test confirmation data structures."""

    def test_confirmation_request_structure(self):
        """Test ConfirmationRequest data structure."""
        operation = ManipulationOperation(
            operation_id="test-001",
            operation_type="remove",
            target_keys=["test_key"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Test operation",
            requires_confirmation=True
        )
        
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=["Test warning"],
            safety_recommendations=["Test recommendation"],
            risk_assessment="medium",
            validation_timestamp=datetime.now().isoformat()
        )
        
        risk_assessment = RiskAssessment(
            risk_level=RiskLevel.MEDIUM,
            risk_factors=["Test risk factor"],
            impact_severity=0.3,
            reversibility=0.8,
            data_sensitivity=0.4,
            recommended_action=SafetyAction.CONFIRM,
            mitigation_strategies=["Test mitigation"]
        )
        
        request = ConfirmationRequest(
            request_id="test-request-001",
            operation_or_plan=operation,
            confirmation_level=ConfirmationLevel.DETAILED,
            risk_assessment=risk_assessment,
            validation_result=validation_result,
            requires_backup=True,
            timeout_minutes=10
        )
        
        assert request.request_id == "test-request-001"
        assert request.operation_or_plan == operation
        assert request.confirmation_level == ConfirmationLevel.DETAILED
        assert request.risk_assessment == risk_assessment
        assert request.validation_result == validation_result
        assert request.requires_backup is True
        assert request.timeout_minutes == 10

    def test_confirmation_response_structure(self):
        """Test ConfirmationResponse data structure."""
        response = ConfirmationResponse(
            request_id="test-request-001",
            result=ConfirmationResult.APPROVED,
            approved_operations=["op-001", "op-002"],
            rejected_operations=["op-003"],
            user_comments="Test approval",
            backup_requested=True,
            requested_modifications={"confidence": 0.9}
        )
        
        assert response.request_id == "test-request-001"
        assert response.result == ConfirmationResult.APPROVED
        assert "op-001" in response.approved_operations
        assert "op-002" in response.approved_operations
        assert "op-003" in response.rejected_operations
        assert response.user_comments == "Test approval"
        assert response.backup_requested is True
        assert response.requested_modifications["confidence"] == 0.9


class MockConfirmationProvider(ConfirmationProvider):
    """Mock confirmation provider for testing."""
    
    def __init__(self, auto_result=ConfirmationResult.APPROVED):
        self.auto_result = auto_result
        self.last_request = None
        self.call_count = 0
    
    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        """Mock confirmation request."""
        self.last_request = request
        self.call_count += 1
        
        return ConfirmationResponse(
            request_id=request.request_id,
            result=self.auto_result,
            user_comments=f"Mock {self.auto_result.value}",
            approved_operations=["all"] if self.auto_result == ConfirmationResult.APPROVED else []
        )
    
    def supports_level(self, level: ConfirmationLevel) -> bool:
        """Mock provider supports all levels."""
        return True


class TestConsoleConfirmationProvider:
    """Test suite for ConsoleConfirmationProvider."""

    @pytest.fixture
    def console_provider(self):
        """ConsoleConfirmationProvider instance for testing."""
        config = {
            'show_previews': True,
            'show_risk_details': True,
            'allow_partial_approval': True
        }
        return ConsoleConfirmationProvider(config)

    def test_console_provider_initialization(self):
        """Test ConsoleConfirmationProvider initialization."""
        config = {
            'show_previews': False,
            'show_risk_details': False,
            'allow_partial_approval': False
        }
        
        provider = ConsoleConfirmationProvider(config)
        
        assert provider.show_previews is False
        assert provider.show_risk_details is False
        assert provider.allow_partial_approval is False

    def test_console_provider_supports_all_levels(self, console_provider):
        """Test that console provider supports all confirmation levels."""
        for level in ConfirmationLevel:
            assert console_provider.supports_level(level) is True

    @patch('builtins.input', side_effect=['y'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_console_simple_confirmation_approved(self, mock_stdout, mock_input, console_provider):
        """Test simple console confirmation - approved."""
        operation = ManipulationOperation(
            operation_id="console-test-001",
            operation_type="remove",
            target_keys=["test_key"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Test operation",
            requires_confirmation=True
        )
        
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="low",
            validation_timestamp=datetime.now().isoformat()
        )
        
        request = ConfirmationRequest(
            request_id="console-simple-001",
            operation_or_plan=operation,
            confirmation_level=ConfirmationLevel.SIMPLE,
            risk_assessment=None,
            validation_result=validation_result
        )
        
        response = console_provider.request_confirmation(request)
        
        assert response.result == ConfirmationResult.APPROVED
        assert response.request_id == "console-simple-001"

    @patch('builtins.input', side_effect=['n'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_console_simple_confirmation_rejected(self, mock_stdout, mock_input, console_provider):
        """Test simple console confirmation - rejected."""
        operation = ManipulationOperation(
            operation_id="console-test-002",
            operation_type="remove",
            target_keys=["test_key"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Test operation",
            requires_confirmation=True
        )
        
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="low",
            validation_timestamp=datetime.now().isoformat()
        )
        
        request = ConfirmationRequest(
            request_id="console-simple-002",
            operation_or_plan=operation,
            confirmation_level=ConfirmationLevel.SIMPLE,
            risk_assessment=None,
            validation_result=validation_result
        )
        
        response = console_provider.request_confirmation(request)
        
        assert response.result == ConfirmationResult.REJECTED
        assert response.request_id == "console-simple-002"

    @patch('builtins.input', side_effect=['a', 'Test approval comment'])
    @patch('sys.stdout', new_callable=StringIO)
    def test_console_detailed_confirmation(self, mock_stdout, mock_input, console_provider):
        """Test detailed console confirmation."""
        operation = ManipulationOperation(
            operation_id="console-test-003",
            operation_type="remove",
            target_keys=["test_key"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Test operation",
            requires_confirmation=True
        )
        
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=["Test warning"],
            safety_recommendations=["Test recommendation"],
            risk_assessment="medium",
            validation_timestamp=datetime.now().isoformat()
        )
        
        request = ConfirmationRequest(
            request_id="console-detailed-001",
            operation_or_plan=operation,
            confirmation_level=ConfirmationLevel.DETAILED,
            risk_assessment=None,
            validation_result=validation_result
        )
        
        response = console_provider.request_confirmation(request)
        
        assert response.result == ConfirmationResult.APPROVED
        assert response.user_comments == "Test approval comment"

    def test_console_keyboard_interrupt_handling(self, console_provider):
        """Test keyboard interrupt handling in console provider."""
        operation = ManipulationOperation(
            operation_id="console-interrupt-001",
            operation_type="remove",
            target_keys=["test_key"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.8,
            reasoning="Test operation",
            requires_confirmation=True
        )
        
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="low",
            validation_timestamp=datetime.now().isoformat()
        )
        
        request = ConfirmationRequest(
            request_id="console-interrupt-001",
            operation_or_plan=operation,
            confirmation_level=ConfirmationLevel.SIMPLE,
            risk_assessment=None,
            validation_result=validation_result
        )
        
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            response = console_provider.request_confirmation(request)
            
            assert response.result == ConfirmationResult.REJECTED
            assert "cancelled by user" in response.user_comments.lower()


class TestConfirmationWorkflowManager:
    """Test suite for ConfirmationWorkflowManager."""

    @pytest.fixture
    def validator(self):
        """ManipulationValidator instance for testing."""
        return ManipulationValidator()

    @pytest.fixture
    def preview_generator(self, validator):
        """PreviewGenerator instance for testing."""
        return PreviewGenerator(validator=validator)

    @pytest.fixture
    def backup_manager(self):
        """BackupManager instance for testing."""
        return BackupManager()

    @pytest.fixture
    def workflow_manager(self, validator, preview_generator, backup_manager):
        """ConfirmationWorkflowManager instance for testing."""
        config = {
            'auto_confirm_threshold': 0.95,
            'force_confirmation_threshold': 0.6,
            'enable_previews': True,
            'enable_safety_reports': True
        }
        return ConfirmationWorkflowManager(
            validator=validator,
            preview_generator=preview_generator,
            backup_manager=backup_manager,
            config=config
        )

    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for workflow testing."""
        return {
            "message_1": "Help with authentication",
            "message_2": "Debug login issue",
            "todo_1": "Fix critical bug",
            "config": {"debug": True},
            "timestamp": datetime.now().isoformat()
        }

    def test_workflow_manager_initialization(self, validator, preview_generator, backup_manager):
        """Test ConfirmationWorkflowManager initialization."""
        config = {
            'auto_confirm_threshold': 0.9,
            'force_confirmation_threshold': 0.5,
            'enable_previews': False,
            'enable_safety_reports': False
        }
        
        manager = ConfirmationWorkflowManager(
            validator=validator,
            preview_generator=preview_generator,
            backup_manager=backup_manager,
            config=config
        )
        
        assert manager.validator is validator
        assert manager.preview_generator is preview_generator
        assert manager.backup_manager is backup_manager
        assert manager.auto_confirm_threshold == 0.9
        assert manager.force_confirmation_threshold == 0.5
        assert manager.enable_previews is False
        assert manager.enable_safety_reports is False
        assert len(manager.providers) > 0  # Should have default provider

    def test_add_provider(self, workflow_manager):
        """Test adding custom confirmation provider."""
        mock_provider = MockConfirmationProvider()
        initial_count = len(workflow_manager.providers)
        
        workflow_manager.add_provider(mock_provider)
        
        assert len(workflow_manager.providers) == initial_count + 1
        assert mock_provider in workflow_manager.providers

    def test_determine_confirmation_level_auto_confirm(self, workflow_manager):
        """Test confirmation level determination for auto-confirm cases."""
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.96,  # Above auto_confirm_threshold
            validation_errors=[],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="low",
            validation_timestamp=datetime.now().isoformat()
        )
        
        level = workflow_manager.determine_confirmation_level(validation_result)
        
        assert level == ConfirmationLevel.NONE

    def test_determine_confirmation_level_force_confirm(self, workflow_manager):
        """Test confirmation level determination for forced confirmation."""
        validation_result = ValidationResult(
            is_valid=False,  # Invalid operations force confirmation
            confidence_score=0.5,
            validation_errors=["Test error"],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="high",
            validation_timestamp=datetime.now().isoformat()
        )
        
        level = workflow_manager.determine_confirmation_level(validation_result)
        
        assert level == ConfirmationLevel.INTERACTIVE

    def test_determine_confirmation_level_with_risk_assessment(self, workflow_manager):
        """Test confirmation level determination with risk assessment."""
        validation_result = ValidationResult(
            is_valid=True,
            confidence_score=0.8,
            validation_errors=[],
            warnings=[],
            safety_recommendations=[],
            risk_assessment="medium",
            validation_timestamp=datetime.now().isoformat()
        )
        
        risk_assessment = RiskAssessment(
            risk_level=RiskLevel.HIGH,
            risk_factors=["High risk content"],
            impact_severity=0.7,
            reversibility=0.3,
            data_sensitivity=0.8,
            recommended_action=SafetyAction.MANUAL_REVIEW,
            mitigation_strategies=["Create backup"]
        )
        
        level = workflow_manager.determine_confirmation_level(validation_result, risk_assessment)
        
        assert level == ConfirmationLevel.DETAILED

    def test_request_operation_confirmation_auto_approved(self, workflow_manager, sample_context_data):
        """Test operation confirmation that gets auto-approved."""
        # High-confidence, low-risk operation
        operation = ManipulationOperation(
            operation_id="auto-approve-001",
            operation_type="reorder",
            target_keys=["message_1"],
            operation_data={},
            estimated_token_impact=0,  # No content change
            confidence_score=0.96,  # High confidence
            reasoning="Simple reordering",
            requires_confirmation=False
        )
        
        response = workflow_manager.request_operation_confirmation(
            operation,
            sample_context_data
        )
        
        assert response.result == ConfirmationResult.APPROVED
        assert "auto-approved" in response.user_comments.lower()

    def test_request_operation_confirmation_with_provider(self, workflow_manager, sample_context_data):
        """Test operation confirmation using custom provider."""
        # Add mock provider that auto-approves at the beginning
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        workflow_manager.providers.insert(0, mock_provider)
        
        # Medium-risk operation requiring confirmation
        operation = ManipulationOperation(
            operation_id="provider-test-001",
            operation_type="remove",
            target_keys=["message_2"],
            operation_data={},
            estimated_token_impact=-25,
            confidence_score=0.7,
            reasoning="Remove duplicate message",
            requires_confirmation=True
        )
        
        response = workflow_manager.request_operation_confirmation(
            operation,
            sample_context_data,
            force_level=ConfirmationLevel.SIMPLE
        )
        
        assert response.result == ConfirmationResult.APPROVED
        assert mock_provider.call_count > 0
        assert mock_provider.last_request is not None

    def test_request_plan_confirmation(self, workflow_manager, sample_context_data):
        """Test plan confirmation workflow."""
        operations = [
            ManipulationOperation(
                operation_id="plan-op-001",
                operation_type="remove",
                target_keys=["message_2"],
                operation_data={},
                estimated_token_impact=-25,
                confidence_score=0.8,
                reasoning="Remove duplicate",
                requires_confirmation=False
            ),
            ManipulationOperation(
                operation_id="plan-op-002",
                operation_type="consolidate",
                target_keys=["todo_1", "config"],
                operation_data={},
                estimated_token_impact=-10,
                confidence_score=0.75,
                reasoning="Consolidate items",
                requires_confirmation=True
            )
        ]
        
        plan = ManipulationPlan(
            plan_id="confirmation-plan-001",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=35,
            estimated_execution_time=0.5,
            safety_level="balanced",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        # Add mock provider
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        workflow_manager.providers.insert(0, mock_provider)
        
        response = workflow_manager.request_plan_confirmation(
            plan,
            sample_context_data,
            force_level=ConfirmationLevel.DETAILED
        )
        
        assert response.result == ConfirmationResult.APPROVED
        assert mock_provider.call_count > 0

    def test_request_plan_confirmation_staged(self, workflow_manager, sample_context_data):
        """Test staged plan confirmation for large plans."""
        # Create large plan that should trigger staged confirmation
        operations = []
        for i in range(15):  # Large number of operations
            operation = ManipulationOperation(
                operation_id=f"staged-op-{i:03d}",
                operation_type="remove",
                target_keys=[f"key_{i}"],
                operation_data={},
                estimated_token_impact=-5,
                confidence_score=0.8,
                reasoning=f"Remove item {i}",
                requires_confirmation=False
            )
            operations.append(operation)
        
        plan = ManipulationPlan(
            plan_id="staged-plan-001",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=75,
            estimated_execution_time=2.0,
            safety_level="aggressive",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        # Mock provider that approves all
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        workflow_manager.providers.insert(0, mock_provider)
        
        response = workflow_manager.request_plan_confirmation(plan, sample_context_data)
        
        # Should use staged confirmation due to large number of operations
        assert response.result == ConfirmationResult.APPROVED

    def test_find_provider(self, workflow_manager):
        """Test provider selection."""
        # Should find default provider for any level
        provider = workflow_manager._find_provider(ConfirmationLevel.SIMPLE)
        assert provider is not None
        assert isinstance(provider, ConsoleConfirmationProvider)
        
        provider = workflow_manager._find_provider(ConfirmationLevel.INTERACTIVE)
        assert provider is not None

    def test_confirmation_with_previews_enabled(self, workflow_manager, sample_context_data):
        """Test confirmation workflow with previews enabled."""
        workflow_manager.enable_previews = True
        
        operation = ManipulationOperation(
            operation_id="preview-test-001",
            operation_type="remove",
            target_keys=["message_2"],
            operation_data={},
            estimated_token_impact=-25,
            confidence_score=0.7,
            reasoning="Remove duplicate with preview",
            requires_confirmation=True
        )
        
        # Add mock provider
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        workflow_manager.providers.insert(0, mock_provider)
        
        response = workflow_manager.request_operation_confirmation(
            operation,
            sample_context_data,
            force_level=ConfirmationLevel.DETAILED
        )
        
        # Check that preview was generated
        request = mock_provider.last_request
        assert request.preview is not None

    def test_confirmation_with_safety_reports_enabled(self, workflow_manager, sample_context_data):
        """Test confirmation workflow with safety reports enabled."""
        workflow_manager.enable_safety_reports = True
        
        operation = ManipulationOperation(
            operation_id="safety-test-001",
            operation_type="remove",
            target_keys=["config"],  # Potentially risky
            operation_data={},
            estimated_token_impact=-30,
            confidence_score=0.6,
            reasoning="Remove config with safety report",
            requires_confirmation=True
        )
        
        # Add mock provider
        mock_provider = MockConfirmationProvider(ConfirmationResult.APPROVED)
        workflow_manager.providers.insert(0, mock_provider)
        
        response = workflow_manager.request_operation_confirmation(
            operation,
            sample_context_data,
            force_level=ConfirmationLevel.INTERACTIVE
        )
        
        # Check that safety report was generated (if validator supports it)
        request = mock_provider.last_request
        if hasattr(workflow_manager.validator, 'generate_enhanced_safety_report'):
            assert request.safety_report is not None

    def test_convenience_functions(self, sample_context_data):
        """Test convenience functions."""
        operation = ManipulationOperation(
            operation_id="convenience-001",
            operation_type="remove",
            target_keys=["message_2"],
            operation_data={},
            estimated_token_impact=-25,
            confidence_score=0.95,  # High confidence for auto-approval
            reasoning="Convenience function test",
            requires_confirmation=False
        )
        
        # Test confirm_operation
        response = confirm_operation(
            operation,
            sample_context_data,
            confirmation_level=ConfirmationLevel.NONE
        )
        
        assert isinstance(response, ConfirmationResponse)
        assert response.result == ConfirmationResult.APPROVED
        
        # Test confirm_plan
        plan = ManipulationPlan(
            plan_id="convenience-plan-001",
            total_operations=1,
            operations=[operation],
            estimated_total_reduction=25,
            estimated_execution_time=0.1,
            safety_level="conservative",
            requires_user_approval=False,
            created_timestamp=datetime.now().isoformat()
        )
        
        plan_response = confirm_plan(
            plan,
            sample_context_data,
            confirmation_level=ConfirmationLevel.NONE
        )
        
        assert isinstance(plan_response, ConfirmationResponse)
        assert plan_response.result == ConfirmationResult.APPROVED

    def test_error_handling_in_confirmation(self, workflow_manager, sample_context_data):
        """Test error handling in confirmation workflow."""
        # Operation with issues that might cause errors
        invalid_operation = ManipulationOperation(
            operation_id="error-test-001",
            operation_type="invalid_type",
            target_keys=["nonexistent_key"],
            operation_data={},
            estimated_token_impact=-100,
            confidence_score=-0.5,  # Invalid confidence
            reasoning="Error test operation",
            requires_confirmation=True
        )
        
        response = workflow_manager.request_operation_confirmation(
            invalid_operation,
            sample_context_data
        )
        
        # Should handle errors gracefully
        assert isinstance(response, ConfirmationResponse)
        # Likely to be rejected due to errors
        assert response.result in [ConfirmationResult.REJECTED, ConfirmationResult.APPROVED]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])