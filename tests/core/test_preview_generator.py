#!/usr/bin/env python3
"""
Tests for PreviewGenerator

Tests the preview and diff generation system including:
- Operation preview generation
- Plan preview generation
- Diff generation in multiple formats
- Change detection and analysis
- Risk highlighting and warnings
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from context_cleaner.core.preview_generator import (
    PreviewGenerator,
    PreviewFormat,
    ChangeType,
    ChangeDetail,
    OperationPreview,
    PlanPreview,
    preview_single_operation,
    preview_manipulation_plan
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


class TestPreviewGenerator:
    """Test suite for PreviewGenerator."""

    @pytest.fixture
    def validator(self):
        """ManipulationValidator instance for preview testing."""
        return ManipulationValidator()

    @pytest.fixture
    def preview_generator(self, validator):
        """PreviewGenerator instance for testing."""
        config = {
            'max_preview_size': 5000,
            'show_unchanged_context': False,
            'highlight_risks': True,
            'include_validation': True,
            'truncate_long_values': True,
            'max_value_length': 200
        }
        return PreviewGenerator(validator=validator, config=config)

    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for preview testing."""
        return {
            "message_1": "Help me debug this authentication issue",
            "message_2": "Help me debug this authentication issue",  # Duplicate
            "todo_active": "Fix critical login bug in auth system",
            "todo_completed": "Write unit tests for auth module - COMPLETED",
            "config_secret": "api_key = secret_abc123",  # High-risk content
            "normal_content": "This is regular user content",
            "large_content": "x" * 500,  # Large content for truncation testing
            "timestamp": datetime.now().isoformat()
        }

    @pytest.fixture
    def remove_operation(self):
        """Remove operation for testing."""
        return ManipulationOperation(
            operation_id="preview-remove-001",
            operation_type="remove",
            target_keys=["message_2", "todo_completed"],
            operation_data={"removal_type": "safe_delete"},
            estimated_token_impact=-75,
            confidence_score=0.9,
            reasoning="Removing duplicate message and completed todo",
            requires_confirmation=False
        )

    @pytest.fixture
    def consolidate_operation(self):
        """Consolidate operation for testing."""
        return ManipulationOperation(
            operation_id="preview-consolidate-001",
            operation_type="consolidate",
            target_keys=["message_1", "normal_content"],
            operation_data={"strategy": "merge_related"},
            estimated_token_impact=-20,
            confidence_score=0.8,
            reasoning="Consolidating related messages",
            requires_confirmation=True
        )

    @pytest.fixture
    def risky_operation(self):
        """High-risk operation for testing."""
        return ManipulationOperation(
            operation_id="preview-risky-001",
            operation_type="remove",
            target_keys=["config_secret"],
            operation_data={"removal_type": "safe_delete"},
            estimated_token_impact=-50,
            confidence_score=0.6,  # Lower confidence
            reasoning="Removing sensitive configuration",
            requires_confirmation=True
        )

    def test_preview_generator_initialization(self, validator):
        """Test PreviewGenerator initialization."""
        config = {
            'max_preview_size': 10000,
            'show_unchanged_context': True,
            'highlight_risks': False,
            'include_validation': False
        }
        
        generator = PreviewGenerator(validator=validator, config=config)
        
        assert generator.validator is validator
        assert generator.max_preview_size == 10000
        assert generator.show_unchanged_context is True
        assert generator.highlight_risks is False
        assert generator.include_validation is False

    def test_simulate_operation_execution_remove(self, preview_generator, sample_context_data, remove_operation):
        """Test operation execution simulation for remove operations."""
        simulated_context = preview_generator._simulate_operation_execution(
            remove_operation, 
            sample_context_data
        )
        
        # Keys should be removed
        assert "message_2" not in simulated_context
        assert "todo_completed" not in simulated_context
        
        # Other keys should remain
        assert "message_1" in simulated_context
        assert "todo_active" in simulated_context
        assert simulated_context["message_1"] == sample_context_data["message_1"]

    def test_simulate_operation_execution_consolidate(self, preview_generator, sample_context_data, consolidate_operation):
        """Test operation execution simulation for consolidate operations."""
        simulated_context = preview_generator._simulate_operation_execution(
            consolidate_operation,
            sample_context_data
        )
        
        # Original keys should be removed
        assert "message_1" not in simulated_context
        assert "normal_content" not in simulated_context
        
        # Consolidated key should be created
        consolidated_key = "consolidated_message_1"
        assert consolidated_key in simulated_context
        assert "message_1:" in simulated_context[consolidated_key]
        assert "normal_content:" in simulated_context[consolidated_key]

    def test_simulate_operation_execution_summarize(self, preview_generator, sample_context_data):
        """Test operation execution simulation for summarize operations."""
        summarize_operation = ManipulationOperation(
            operation_id="preview-summarize-001",
            operation_type="summarize",
            target_keys=["large_content"],
            operation_data={"strategy": "extract_key_points"},
            estimated_token_impact=-200,
            confidence_score=0.75,
            reasoning="Summarizing large content",
            requires_confirmation=False
        )
        
        simulated_context = preview_generator._simulate_operation_execution(
            summarize_operation,
            sample_context_data
        )
        
        # Large content should be summarized (shortened)
        original_content = sample_context_data["large_content"]
        summarized_content = simulated_context["large_content"]
        
        assert len(summarized_content) < len(original_content)
        assert "[summarized]" in summarized_content

    def test_generate_change_details_remove(self, preview_generator, sample_context_data, remove_operation):
        """Test change detail generation for remove operations."""
        modified_context = preview_generator._simulate_operation_execution(
            remove_operation,
            sample_context_data
        )
        
        changes = preview_generator._generate_change_details(
            sample_context_data,
            modified_context,
            remove_operation
        )
        
        # Should detect removed keys
        removed_changes = [c for c in changes if c.change_type == ChangeType.REMOVED]
        assert len(removed_changes) == 2
        
        removed_keys = [c.key for c in removed_changes]
        assert "message_2" in removed_keys
        assert "todo_completed" in removed_keys
        
        # Should calculate negative size changes for removals
        for change in removed_changes:
            assert change.size_change < 0

    def test_generate_change_details_consolidate(self, preview_generator, sample_context_data, consolidate_operation):
        """Test change detail generation for consolidate operations."""
        modified_context = preview_generator._simulate_operation_execution(
            consolidate_operation,
            sample_context_data
        )
        
        changes = preview_generator._generate_change_details(
            sample_context_data,
            modified_context,
            consolidate_operation
        )
        
        # Should detect removed original keys
        removed_changes = [c for c in changes if c.change_type == ChangeType.REMOVED]
        removed_keys = [c.key for c in removed_changes]
        assert "message_1" in removed_keys
        assert "normal_content" in removed_keys
        
        # Should detect added consolidated key
        added_changes = [c for c in changes if c.change_type == ChangeType.ADDED]
        assert len(added_changes) == 1
        assert added_changes[0].key.startswith("consolidated_")

    def test_calculate_change_confidence(self, preview_generator, sample_context_data, remove_operation):
        """Test change confidence calculation."""
        # Test confidence for removing duplicate content
        confidence = preview_generator._calculate_change_confidence(
            remove_operation,
            "message_2", 
            sample_context_data
        )
        
        # Should have high confidence for removing duplicates
        assert confidence >= remove_operation.confidence_score

    def test_preview_operation_basic(self, preview_generator, sample_context_data, remove_operation):
        """Test basic operation preview generation."""
        preview = preview_generator.preview_operation(
            remove_operation,
            sample_context_data,
            include_validation=False
        )
        
        assert isinstance(preview, OperationPreview)
        assert preview.operation == remove_operation
        assert len(preview.changes) > 0
        assert preview.validation_result is None  # Validation disabled
        assert "estimated_impact" in preview.__dict__
        
        # Should detect changes
        removed_changes = [c for c in preview.changes if c.change_type == ChangeType.REMOVED]
        assert len(removed_changes) == 2

    def test_preview_operation_with_validation(self, preview_generator, sample_context_data, remove_operation):
        """Test operation preview with validation."""
        preview = preview_generator.preview_operation(
            remove_operation,
            sample_context_data,
            include_validation=True
        )
        
        assert preview.validation_result is not None
        assert isinstance(preview.validation_result, ValidationResult)
        
        # Risk assessment should be included if validator supports it
        if hasattr(preview_generator.validator, 'validate_operation_enhanced'):
            assert preview.risk_assessment is not None

    def test_preview_operation_warnings(self, preview_generator, sample_context_data, risky_operation):
        """Test operation preview warning generation."""
        preview = preview_generator.preview_operation(
            risky_operation,
            sample_context_data,
            include_validation=True
        )
        
        # Should generate warnings for risky operation
        assert len(preview.warnings) > 0
        
        # Should indicate high risk
        high_risk_changes = [c for c in preview.changes if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        assert len(high_risk_changes) > 0

    def test_preview_plan_basic(self, preview_generator, sample_context_data, remove_operation, consolidate_operation):
        """Test basic plan preview generation."""
        operations = [remove_operation, consolidate_operation]
        
        plan = ManipulationPlan(
            plan_id="preview-plan-001",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=95,
            estimated_execution_time=0.5,
            safety_level="balanced",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        preview = preview_generator.preview_plan(
            plan,
            sample_context_data,
            include_validation=False
        )
        
        assert isinstance(preview, PlanPreview)
        assert preview.plan == plan
        assert len(preview.operation_previews) == 2
        assert preview.total_changes > 0
        assert preview.total_size_reduction > 0
        assert preview.requires_confirmation is True  # Plan requires approval

    def test_preview_plan_risk_assessment(self, preview_generator, sample_context_data, remove_operation, risky_operation):
        """Test plan preview risk assessment."""
        operations = [remove_operation, risky_operation]
        
        plan = ManipulationPlan(
            plan_id="preview-risk-plan-001",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=125,
            estimated_execution_time=0.8,
            safety_level="aggressive",
            requires_user_approval=False,
            created_timestamp=datetime.now().isoformat()
        )
        
        preview = preview_generator.preview_plan(plan, sample_context_data)
        
        # Should detect high risk due to risky operation
        assert preview.overall_risk != RiskLevel.LOW
        assert preview.requires_confirmation is True  # Should require confirmation due to risk

    def test_generate_diff_text(self, preview_generator, sample_context_data, remove_operation):
        """Test diff generation in text format."""
        modified_context = preview_generator._simulate_operation_execution(
            remove_operation,
            sample_context_data
        )
        
        diff = preview_generator.generate_diff(
            sample_context_data,
            modified_context,
            PreviewFormat.TEXT
        )
        
        assert isinstance(diff, str)
        assert len(diff) > 0
        assert "message_2" in diff  # Should show removed key
        assert "todo_completed" in diff  # Should show removed key

    def test_generate_diff_json(self, preview_generator, sample_context_data, remove_operation):
        """Test diff generation in JSON format."""
        modified_context = preview_generator._simulate_operation_execution(
            remove_operation,
            sample_context_data
        )
        
        diff = preview_generator.generate_diff(
            sample_context_data,
            modified_context,
            PreviewFormat.JSON
        )
        
        assert isinstance(diff, str)
        import json
        diff_data = json.loads(diff)
        
        assert "original" in diff_data
        assert "modified" in diff_data
        assert "diff_generated_at" in diff_data
        assert diff_data["original"] == sample_context_data
        assert diff_data["modified"] == modified_context

    def test_generate_diff_html(self, preview_generator, sample_context_data, remove_operation):
        """Test diff generation in HTML format."""
        modified_context = preview_generator._simulate_operation_execution(
            remove_operation,
            sample_context_data
        )
        
        diff = preview_generator.generate_diff(
            sample_context_data,
            modified_context,
            PreviewFormat.HTML
        )
        
        assert isinstance(diff, str)
        assert "<html>" in diff.lower()
        assert "<table>" in diff.lower()
        assert len(diff) > 0

    def test_generate_diff_markdown(self, preview_generator, sample_context_data, remove_operation):
        """Test diff generation in Markdown format."""
        modified_context = preview_generator._simulate_operation_execution(
            remove_operation,
            sample_context_data
        )
        
        diff = preview_generator.generate_diff(
            sample_context_data,
            modified_context,
            PreviewFormat.MARKDOWN
        )
        
        assert isinstance(diff, str)
        assert "```diff" in diff
        assert "```" in diff
        assert len(diff) > 0

    def test_format_preview_text_operation(self, preview_generator, sample_context_data, remove_operation):
        """Test formatting operation preview as text."""
        preview = preview_generator.preview_operation(remove_operation, sample_context_data)
        
        formatted = preview_generator.format_preview(
            preview,
            PreviewFormat.TEXT,
            include_details=True
        )
        
        assert isinstance(formatted, str)
        assert "OPERATION PREVIEW" in formatted
        assert remove_operation.operation_id in formatted
        assert remove_operation.operation_type in formatted
        assert len(formatted) > 0

    def test_format_preview_json_operation(self, preview_generator, sample_context_data, remove_operation):
        """Test formatting operation preview as JSON."""
        preview = preview_generator.preview_operation(remove_operation, sample_context_data)
        
        formatted = preview_generator.format_preview(
            preview,
            PreviewFormat.JSON,
            include_details=True
        )
        
        import json
        preview_data = json.loads(formatted)
        
        assert "operation_id" in preview_data
        assert "operation_type" in preview_data
        assert "changes" in preview_data
        assert preview_data["operation_id"] == remove_operation.operation_id

    def test_format_preview_markdown_plan(self, preview_generator, sample_context_data, remove_operation, consolidate_operation):
        """Test formatting plan preview as Markdown."""
        operations = [remove_operation, consolidate_operation]
        
        plan = ManipulationPlan(
            plan_id="preview-md-plan-001",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=95,
            estimated_execution_time=0.5,
            safety_level="balanced",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat()
        )
        
        preview = preview_generator.preview_plan(plan, sample_context_data)
        
        formatted = preview_generator.format_preview(
            preview,
            PreviewFormat.MARKDOWN,
            include_details=True
        )
        
        assert isinstance(formatted, str)
        assert "# Manipulation Plan Preview" in formatted
        assert plan.plan_id in formatted
        assert "## Summary" in formatted
        assert "## Operations" in formatted

    def test_truncate_long_values(self, preview_generator, sample_context_data):
        """Test truncation of long values in previews."""
        long_content = "x" * 1000
        truncated = preview_generator._truncate_value(long_content)
        
        assert len(truncated) < len(long_content)
        assert "truncated" in truncated.lower()

    def test_change_type_enum(self):
        """Test ChangeType enum values."""
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.MOVED.value == "moved"
        assert ChangeType.UNCHANGED.value == "unchanged"

    def test_preview_format_enum(self):
        """Test PreviewFormat enum values."""
        assert PreviewFormat.TEXT.value == "text"
        assert PreviewFormat.HTML.value == "html"
        assert PreviewFormat.JSON.value == "json"
        assert PreviewFormat.MARKDOWN.value == "markdown"

    def test_change_detail_structure(self):
        """Test ChangeDetail data structure."""
        change = ChangeDetail(
            change_type=ChangeType.REMOVED,
            key="test_key",
            original_value="original",
            new_value=None,
            size_change=-8,
            confidence=0.9,
            risk_level=RiskLevel.LOW,
            description="Test removal"
        )
        
        assert change.change_type == ChangeType.REMOVED
        assert change.key == "test_key"
        assert change.original_value == "original"
        assert change.new_value is None
        assert change.size_change == -8
        assert change.confidence == 0.9
        assert change.risk_level == RiskLevel.LOW
        assert change.description == "Test removal"

    def test_preview_error_handling(self, preview_generator, sample_context_data):
        """Test preview generation error handling."""
        # Create operation with invalid data
        invalid_operation = ManipulationOperation(
            operation_id="invalid-preview-001",
            operation_type="invalid_type",  # Invalid type
            target_keys=["nonexistent_key"],
            operation_data={},
            estimated_token_impact=0,
            confidence_score=0.5,
            reasoning="Invalid operation for testing",
            requires_confirmation=False
        )
        
        # Should handle gracefully and return preview with warnings
        preview = preview_generator.preview_operation(invalid_operation, sample_context_data)
        
        assert isinstance(preview, OperationPreview)
        assert len(preview.warnings) > 0

    def test_convenience_functions(self, sample_context_data, remove_operation):
        """Test convenience functions."""
        # Test preview_single_operation
        text_preview = preview_single_operation(
            remove_operation,
            sample_context_data,
            PreviewFormat.TEXT
        )
        
        assert isinstance(text_preview, str)
        assert remove_operation.operation_id in text_preview
        
        # Test preview_manipulation_plan
        operations = [remove_operation]
        plan = ManipulationPlan(
            plan_id="convenience-test-001",
            total_operations=1,
            operations=operations,
            estimated_total_reduction=50,
            estimated_execution_time=0.2,
            safety_level="conservative",
            requires_user_approval=False,
            created_timestamp=datetime.now().isoformat()
        )
        
        plan_preview = preview_manipulation_plan(
            plan,
            sample_context_data,
            PreviewFormat.JSON
        )
        
        assert isinstance(plan_preview, str)
        import json
        plan_data = json.loads(plan_preview)
        assert "plan_id" in plan_data

    def test_preview_with_unchanged_context(self):
        """Test preview generation with unchanged context display."""
        config = {'show_unchanged_context': True}
        validator = ManipulationValidator()
        generator = PreviewGenerator(validator=validator, config=config)
        
        context_data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        
        # Operation that only affects one key
        operation = ManipulationOperation(
            operation_id="unchanged-test-001",
            operation_type="remove",
            target_keys=["key2"],
            operation_data={},
            estimated_token_impact=-10,
            confidence_score=0.9,
            reasoning="Remove single key",
            requires_confirmation=False
        )
        
        preview = generator.preview_operation(operation, context_data)
        
        # Should include unchanged keys in changes list
        unchanged_changes = [c for c in preview.changes if c.change_type == ChangeType.UNCHANGED]
        assert len(unchanged_changes) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])