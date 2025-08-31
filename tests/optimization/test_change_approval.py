"""
Unit tests for PR19 Change Approval System

Tests the ChangeApprovalSystem class and related functionality including:
- Selective approval workflows and change selection
- Category-based batch approval operations
- User preference learning and auto-approval
- Change categorization and user feedback collection
"""

import pytest
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from context_cleaner.optimization.change_approval import (
    ChangeApprovalSystem,
    ChangeSelection,
    SelectiveApprovalResult,
    ApprovalDecision,
    ChangeCategory,
    create_quick_approval,
    approve_all_operations,
    approve_safe_operations_only
)
from context_cleaner.core.manipulation_engine import ManipulationOperation, ManipulationPlan


class TestApprovalDecision:
    """Test ApprovalDecision enumeration."""
    
    def test_approval_decision_values(self):
        """Test approval decision enum values."""
        assert ApprovalDecision.APPROVE.value == "approve"
        assert ApprovalDecision.REJECT.value == "reject"
        assert ApprovalDecision.MODIFY.value == "modify"
        assert ApprovalDecision.DEFER.value == "defer"


class TestChangeCategory:
    """Test ChangeCategory enumeration."""
    
    def test_change_category_values(self):
        """Test change category enum values."""
        assert ChangeCategory.REMOVAL.value == "removal"
        assert ChangeCategory.CONSOLIDATION.value == "consolidation"
        assert ChangeCategory.REORDERING.value == "reordering"
        assert ChangeCategory.SUMMARIZATION.value == "summarization"
        assert ChangeCategory.SAFETY.value == "safety"


class TestChangeSelection:
    """Test ChangeSelection data class."""
    
    def test_change_selection_creation(self):
        """Test creating a change selection."""
        selection = ChangeSelection(
            operation_id="op-001",
            operation_type="remove",
            decision=ApprovalDecision.APPROVE,
            reason="Safe removal operation",
            modifications={"preserve_references": True}
        )
        
        assert selection.operation_id == "op-001"
        assert selection.operation_type == "remove"
        assert selection.decision == ApprovalDecision.APPROVE
        assert selection.reason == "Safe removal operation"
        assert selection.modifications["preserve_references"] is True
        assert selection.selected_at is not None
    
    def test_change_selection_auto_timestamp(self):
        """Test automatic timestamp generation."""
        selection = ChangeSelection(
            operation_id="op-001",
            operation_type="remove",
            decision=ApprovalDecision.APPROVE
        )
        
        # Should have timestamp within last few seconds
        timestamp = datetime.fromisoformat(selection.selected_at)
        assert (datetime.now() - timestamp).total_seconds() < 5


class TestSelectiveApprovalResult:
    """Test SelectiveApprovalResult data class."""
    
    def test_approval_result_structure(self):
        """Test approval result data structure."""
        selections = [
            ChangeSelection("op-001", "remove", ApprovalDecision.APPROVE),
            ChangeSelection("op-002", "consolidate", ApprovalDecision.REJECT)
        ]
        
        result = SelectiveApprovalResult(
            approval_id="approval-001",
            total_operations=5,
            approved_operations=["op-001", "op-003"],
            rejected_operations=["op-002"],
            modified_operations=["op-004"],
            deferred_operations=["op-005"],
            approval_rate=0.4,  # 2/5 approved
            user_feedback="Good optimization suggestions",
            selections=selections,
            created_at=datetime.now().isoformat()
        )
        
        assert result.approval_id == "approval-001"
        assert result.total_operations == 5
        assert len(result.approved_operations) == 2
        assert len(result.rejected_operations) == 1
        assert result.approval_rate == 0.4
        assert result.user_feedback == "Good optimization suggestions"
        assert len(result.selections) == 2


class TestChangeApprovalSystem:
    """Test ChangeApprovalSystem functionality."""
    
    @pytest.fixture
    def approval_system(self):
        """Create change approval system instance."""
        return ChangeApprovalSystem()
    
    @pytest.fixture
    def mock_operations(self):
        """Create mock manipulation operations."""
        ops = []
        
        # Removal operation
        op1 = Mock(spec=ManipulationOperation)
        op1.operation_id = "op-001"
        op1.operation_type = "remove"
        op1.confidence_score = 0.9
        op1.requires_confirmation = False
        ops.append(op1)
        
        # Consolidation operation
        op2 = Mock(spec=ManipulationOperation)
        op2.operation_id = "op-002"
        op2.operation_type = "consolidate"
        op2.confidence_score = 0.8
        op2.requires_confirmation = True
        ops.append(op2)
        
        # Reordering operation
        op3 = Mock(spec=ManipulationOperation)
        op3.operation_id = "op-003"
        op3.operation_type = "reorder"
        op3.confidence_score = 0.95
        op3.requires_confirmation = False
        ops.append(op3)
        
        return ops
    
    @pytest.fixture
    def mock_plan(self, mock_operations):
        """Create mock manipulation plan."""
        plan = Mock(spec=ManipulationPlan)
        plan.plan_id = "test-plan-001"
        plan.operations = mock_operations
        plan.total_operations = len(mock_operations)
        plan.estimated_total_reduction = 500
        return plan
    
    def test_initialization(self, approval_system):
        """Test system initialization."""
        assert approval_system.approval_history == []
        assert approval_system.user_preferences == {}
        assert isinstance(approval_system.category_settings, dict)
        assert len(approval_system.category_settings) == len(ChangeCategory)
    
    def test_categorize_operations(self, approval_system, mock_operations):
        """Test operation categorization."""
        categorized = approval_system.categorize_operations(mock_operations)
        
        assert len(categorized) == len(ChangeCategory)
        assert len(categorized[ChangeCategory.REMOVAL]) == 1
        assert len(categorized[ChangeCategory.CONSOLIDATION]) == 1
        assert len(categorized[ChangeCategory.REORDERING]) == 1
        assert len(categorized[ChangeCategory.SUMMARIZATION]) == 0
        assert len(categorized[ChangeCategory.SAFETY]) == 0
    
    def test_create_approval_session(self, approval_system, mock_plan):
        """Test creating approval session."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        assert approval_id.startswith("approval-")
        assert len(approval_system.approval_history) == 1
        
        result = approval_system.approval_history[0]
        assert result.approval_id == approval_id
        assert result.total_operations == len(mock_plan.operations)
        assert result.approved_operations == []
        assert result.rejected_operations == []
    
    def test_select_operation(self, approval_system, mock_plan):
        """Test selecting individual operations."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # Approve first operation
        success = approval_system.select_operation(
            approval_id,
            "op-001",
            ApprovalDecision.APPROVE,
            "Safe removal operation"
        )
        
        assert success is True
        
        result = approval_system._get_approval_result(approval_id)
        assert len(result.selections) == 1
        assert result.selections[0].operation_id == "op-001"
        assert result.selections[0].decision == ApprovalDecision.APPROVE
        assert "op-001" in result.approved_operations
    
    def test_select_operation_update_existing(self, approval_system, mock_plan):
        """Test updating existing operation selection."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # First selection
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        
        # Update selection
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.REJECT, "Changed mind")
        
        result = approval_system._get_approval_result(approval_id)
        assert len(result.selections) == 1  # Should still be 1, not 2
        assert result.selections[0].decision == ApprovalDecision.REJECT
        assert result.selections[0].reason == "Changed mind"
        assert "op-001" in result.rejected_operations
        assert "op-001" not in result.approved_operations
    
    def test_select_by_category(self, approval_system, mock_plan):
        """Test batch selection by category."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # Approve all removal operations
        count = approval_system.select_by_category(
            approval_id,
            ChangeCategory.REMOVAL,
            ApprovalDecision.APPROVE,
            ["op-001"],  # Only one removal operation
            "Batch approve all removal operations"
        )
        
        assert count == 1
        
        result = approval_system._get_approval_result(approval_id)
        assert len(result.selections) == 1
        assert result.selections[0].operation_id == "op-001"
        assert result.selections[0].decision == ApprovalDecision.APPROVE
    
    def test_apply_user_preferences(self, approval_system, mock_operations, mock_plan):
        """Test applying user preferences for auto-approval."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # Set up category preferences for reordering
        approval_system.category_settings[ChangeCategory.REORDERING] = {
            'default_action': ApprovalDecision.APPROVE,
            'min_confidence': 0.8,
            'auto_approve_threshold': 0.9,
            'requires_confirmation': False
        }
        
        count = approval_system.apply_user_preferences(approval_id, mock_operations)
        
        # Should auto-approve the reordering operation (op-003) with confidence 0.95
        assert count == 1
        
        result = approval_system._get_approval_result(approval_id)
        approved_ops = [s.operation_id for s in result.selections if s.decision == ApprovalDecision.APPROVE]
        assert "op-003" in approved_ops
    
    def test_get_approval_summary(self, approval_system, mock_plan):
        """Test getting approval summary."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # Make some selections
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        approval_system.select_operation(approval_id, "op-002", ApprovalDecision.REJECT)
        
        summary = approval_system.get_approval_summary(approval_id)
        
        assert summary["approval_id"] == approval_id
        assert summary["total_operations"] == 3
        assert summary["decisions_made"] == 2
        assert summary["pending_decisions"] == 1
        assert summary["approval_rate"] == 1/3  # 1 approved out of 3 total
        assert summary["decision_counts"]["approve"] == 1
        assert summary["decision_counts"]["reject"] == 1
        assert len(summary["selections"]) == 2
    
    def test_finalize_approval(self, approval_system, mock_plan):
        """Test finalizing approval session."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # Make selections
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        approval_system.select_operation(approval_id, "op-002", ApprovalDecision.REJECT)
        
        result = approval_system.finalize_approval(
            approval_id,
            "Good optimization suggestions overall"
        )
        
        assert result.user_feedback == "Good optimization suggestions overall"
        assert result.approval_rate == 1/3  # 1 approved out of 3 total
        
        # Should learn from selections
        assert "tends_to_approve" not in approval_system.user_preferences  # Low approval rate
    
    def test_get_selected_operations(self, approval_system, mock_plan):
        """Test getting list of approved operations."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        approval_system.select_operation(approval_id, "op-002", ApprovalDecision.REJECT)
        approval_system.select_operation(approval_id, "op-003", ApprovalDecision.APPROVE)
        
        selected_ops = approval_system.get_selected_operations(approval_id)
        
        assert len(selected_ops) == 2
        assert "op-001" in selected_ops
        assert "op-003" in selected_ops
        assert "op-002" not in selected_ops
    
    def test_export_approval_data(self, approval_system, mock_plan):
        """Test exporting approval data."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        
        exported_data = approval_system.export_approval_data(approval_id)
        
        assert isinstance(exported_data, dict)
        assert exported_data["approval_id"] == approval_id
        assert exported_data["total_operations"] == 3
        assert len(exported_data["selections"]) == 1
    
    def test_import_approval_preferences(self, approval_system):
        """Test importing user preferences."""
        preferences_data = {
            "user_preferences": {
                "tends_to_approve": True,
                "preferred_strategy": "balanced"
            },
            "category_settings": {
                "removal": {
                    "default_action": "approve",
                    "min_confidence": 0.8
                }
            }
        }
        
        success = approval_system.import_approval_preferences(preferences_data)
        
        assert success is True
        assert approval_system.user_preferences["tends_to_approve"] is True
        assert approval_system.user_preferences["preferred_strategy"] == "balanced"
        assert approval_system.category_settings[ChangeCategory.REMOVAL]["min_confidence"] == 0.8
    
    def test_import_invalid_preferences(self, approval_system):
        """Test importing invalid preferences data."""
        # Test with invalid category
        invalid_data = {
            "category_settings": {
                "invalid_category": {"setting": "value"}
            }
        }
        
        success = approval_system.import_approval_preferences(invalid_data)
        
        # Should still succeed but skip invalid categories
        assert success is True
    
    def test_approval_session_not_found(self, approval_system):
        """Test error handling for non-existent approval session."""
        with pytest.raises(ValueError, match="Approval session .* not found"):
            approval_system.get_selected_operations("non-existent-id")
    
    def test_learning_from_selections(self, approval_system, mock_plan):
        """Test user preference learning from selections."""
        approval_id = approval_system.create_approval_session(mock_plan)
        
        # High approval rate scenario
        approval_system.select_operation(approval_id, "op-001", ApprovalDecision.APPROVE)
        approval_system.select_operation(approval_id, "op-002", ApprovalDecision.APPROVE)
        approval_system.select_operation(approval_id, "op-003", ApprovalDecision.APPROVE)
        
        approval_system.finalize_approval(approval_id)
        
        # Should learn high approval tendency
        assert approval_system.user_preferences.get("tends_to_approve") is True
    
    def test_category_settings_initialization(self, approval_system):
        """Test that category settings are properly initialized."""
        # Check all categories have settings
        for category in ChangeCategory:
            assert category in approval_system.category_settings
            settings = approval_system.category_settings[category]
            assert "min_confidence" in settings
            assert "requires_confirmation" in settings
        
        # Check specific defaults
        assert approval_system.category_settings[ChangeCategory.REMOVAL]["requires_confirmation"] is True
        assert approval_system.category_settings[ChangeCategory.REORDERING]["requires_confirmation"] is False
        assert approval_system.category_settings[ChangeCategory.SAFETY]["default_action"] == ApprovalDecision.APPROVE


class TestConvenienceFunctions:
    """Test convenience functions for change approval."""
    
    @pytest.fixture
    def mock_operations(self):
        """Create mock manipulation operations."""
        ops = []
        
        # High confidence, safe operation
        op1 = Mock(spec=ManipulationOperation)
        op1.operation_id = "op-001"
        op1.operation_type = "reorder"
        op1.confidence_score = 0.95
        op1.requires_confirmation = False
        op1.estimated_token_impact = -50
        ops.append(op1)
        
        # Lower confidence operation
        op2 = Mock(spec=ManipulationOperation)
        op2.operation_id = "op-002"
        op2.operation_type = "remove"
        op2.confidence_score = 0.7
        op2.requires_confirmation = True
        op2.estimated_token_impact = -100
        ops.append(op2)
        
        return ops
    
    def test_create_quick_approval(self, mock_operations):
        """Test create_quick_approval convenience function."""
        system, approval_id = create_quick_approval(mock_operations, auto_approve_safe=True)
        
        assert isinstance(system, ChangeApprovalSystem)
        assert approval_id.startswith("approval-")
        
        # Should have auto-approved the safe, high-confidence operation
        selected_ops = system.get_selected_operations(approval_id)
        assert "op-001" in selected_ops  # High confidence reorder operation
        assert "op-002" not in selected_ops  # Requires confirmation
    
    def test_create_quick_approval_no_auto(self, mock_operations):
        """Test create_quick_approval without auto-approval."""
        system, approval_id = create_quick_approval(mock_operations, auto_approve_safe=False)
        
        # Should not auto-approve any operations
        selected_ops = system.get_selected_operations(approval_id)
        assert len(selected_ops) == 0
    
    def test_approve_all_operations(self, mock_operations):
        """Test approve_all_operations convenience function."""
        approved_ops = approve_all_operations(mock_operations)
        
        assert len(approved_ops) == 2
        assert "op-001" in approved_ops
        assert "op-002" in approved_ops
    
    def test_approve_safe_operations_only(self, mock_operations):
        """Test approve_safe_operations_only convenience function."""
        approved_ops = approve_safe_operations_only(mock_operations, min_confidence=0.8)
        
        # Only the high-confidence reorder operation should be approved
        assert len(approved_ops) == 1
        assert "op-001" in approved_ops
        assert "op-002" not in approved_ops  # Below confidence threshold and requires confirmation
    
    def test_approve_safe_operations_lower_threshold(self, mock_operations):
        """Test approve_safe_operations_only with lower threshold."""
        # Add a consolidate operation that should be safe
        op3 = Mock(spec=ManipulationOperation)
        op3.operation_id = "op-003"
        op3.operation_type = "consolidate"
        op3.confidence_score = 0.85
        op3.requires_confirmation = False
        mock_operations.append(op3)
        
        approved_ops = approve_safe_operations_only(mock_operations, min_confidence=0.7)
        
        assert len(approved_ops) == 2  # op-001 (reorder) and op-003 (consolidate)
        assert "op-001" in approved_ops
        assert "op-003" in approved_ops
        assert "op-002" not in approved_ops  # Requires confirmation


class TestPerformanceAndScalability:
    """Test performance aspects of change approval system."""
    
    @pytest.fixture
    def approval_system(self):
        """Create change approval system instance."""
        return ChangeApprovalSystem()
    
    def test_large_number_of_operations(self, approval_system):
        """Test handling large number of operations efficiently."""
        # Create large number of mock operations
        operations = []
        for i in range(1000):
            op = Mock(spec=ManipulationOperation)
            op.operation_id = f"op-{i:04d}"
            op.operation_type = ["remove", "consolidate", "reorder"][i % 3]
            op.confidence_score = 0.5 + (i % 500) / 1000.0
            op.requires_confirmation = i % 10 == 0  # 10% require confirmation
            op.estimated_token_impact = -(i % 200 + 50)
            operations.append(op)
        
        # Create mock plan
        plan = Mock(spec=ManipulationPlan)
        plan.operations = operations
        plan.total_operations = len(operations)
        
        approval_id = approval_system.create_approval_session(plan)
        
        # Should handle large dataset efficiently
        assert approval_system._get_approval_result(approval_id).total_operations == 1000
        
        # Test categorization performance
        categorized = approval_system.categorize_operations(operations)
        total_categorized = sum(len(ops) for ops in categorized.values())
        assert total_categorized == 1000
        
        # Test batch approval performance
        removal_ops = [op.operation_id for op in operations if op.operation_type == "remove"]
        count = approval_system.select_by_category(
            approval_id, 
            ChangeCategory.REMOVAL, 
            ApprovalDecision.APPROVE,
            removal_ops
        )
        assert count == len(removal_ops)
    
    def test_concurrent_approval_sessions(self, approval_system):
        """Test handling multiple concurrent approval sessions."""
        plans = []
        approval_ids = []
        
        # Create multiple mock plans
        for i in range(10):
            operations = [
                Mock(operation_id=f"session-{i}-op-{j}", operation_type="remove") 
                for j in range(5)
            ]
            plan = Mock(operations=operations, total_operations=5)
            plans.append(plan)
            
            approval_id = approval_system.create_approval_session(plan)
            approval_ids.append(approval_id)
        
        # All sessions should be tracked independently
        assert len(approval_system.approval_history) == 10
        
        # Each session should be independent
        for i, approval_id in enumerate(approval_ids):
            approval_system.select_operation(
                approval_id, 
                f"session-{i}-op-0", 
                ApprovalDecision.APPROVE
            )
            
            selected_ops = approval_system.get_selected_operations(approval_id)
            assert len(selected_ops) == 1
            assert f"session-{i}-op-0" in selected_ops
    
    def test_memory_efficiency(self, approval_system):
        """Test memory efficiency with approval history."""
        # Create many approval sessions to test memory usage
        for i in range(100):
            operations = [Mock(operation_id=f"op-{j}") for j in range(10)]
            plan = Mock(operations=operations, total_operations=10)
            approval_id = approval_system.create_approval_session(plan)
            
            # Make some selections
            approval_system.select_operation(approval_id, f"op-0", ApprovalDecision.APPROVE)
            approval_system.finalize_approval(approval_id)
        
        assert len(approval_system.approval_history) == 100
        
        # Each result should have minimal memory footprint
        for result in approval_system.approval_history:
            assert len(result.selections) <= 1  # Only one selection per session
            assert result.total_operations == 10