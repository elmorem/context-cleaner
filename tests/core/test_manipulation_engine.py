#!/usr/bin/env python3
"""
Tests for ManipulationEngine

Tests the core context manipulation operations including:
- Content removal operations
- Content consolidation operations  
- Content reordering operations
- Content summarization operations
- Plan creation and execution
- Integration with analysis components
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from context_cleaner.core.manipulation_engine import (
    ManipulationEngine,
    ManipulationOperation,
    ManipulationPlan,
    ManipulationResult,
    create_manipulation_plan,
    execute_manipulation_plan
)
from context_cleaner.core.context_analyzer import ContextAnalysisResult, ContextAnalyzer
from context_cleaner.core.redundancy_detector import RedundancyReport
from context_cleaner.core.priority_analyzer import PriorityReport, PriorityItem
from context_cleaner.core.focus_scorer import FocusMetrics
from context_cleaner.core.recency_analyzer import RecencyReport


class TestManipulationEngine:
    """Test suite for ManipulationEngine."""

    @pytest.fixture
    def sample_context_data(self):
        """Sample context data for testing."""
        return {
            "message_1": "Help me debug this authentication function", 
            "message_2": "Help me debug this authentication function",  # Exact duplicate
            "message_3": "Can you help debug the auth function?",  # Similar content
            
            "todo_1": "Fix the login bug in authentication system",
            "todo_2": "Write unit tests for auth module", 
            "todo_3": "Fix the login bug - COMPLETED ✅",  # Obsolete
            "todo_4": "Deploy auth fix to staging - DONE",  # Obsolete
            
            "file_ref_1": "/project/src/auth/login.py",
            "file_ref_2": "/project/src/auth/login.py",  # Duplicate file reference
            "file_ref_3": "/project/src/auth/utils.py",
            
            "conversation": "User: How do I fix this authentication bug? Assistant: You can fix it by updating the login function and adding proper null checks. " * 100,  # Very verbose/repetitive
            
            "error_1": "TypeError: 'NoneType' object is not subscriptable in auth.py",
            "error_2": "Fixed: TypeError in auth.py - resolved by null check",  # Resolved error
            
            "timestamp": datetime.now().isoformat()
        }

    @pytest.fixture
    def mock_analysis_result(self):
        """Mock analysis result for testing."""
        redundancy_report = Mock(spec=RedundancyReport)
        redundancy_report.duplicate_items = []
        redundancy_report.obsolete_items = []
        redundancy_report.safe_to_remove = []
        redundancy_report.consolidation_candidates = []
        redundancy_report.redundant_file_groups = []
        
        priority_report = Mock(spec=PriorityReport)
        priority_report.high_priority_items = []
        priority_report.priority_alignment_score = 75
        
        focus_metrics = Mock(spec=FocusMetrics)
        focus_metrics.focus_score = 65
        
        recency_report = Mock(spec=RecencyReport)
        recency_report.stale_context_percentage = 20
        
        analysis_result = Mock(spec=ContextAnalysisResult)
        analysis_result.redundancy_report = redundancy_report
        analysis_result.priority_report = priority_report
        analysis_result.focus_metrics = focus_metrics
        analysis_result.recency_report = recency_report
        analysis_result.optimization_potential = 0.3
        
        return analysis_result

    @pytest.fixture
    def manipulation_engine(self):
        """ManipulationEngine instance for testing."""
        return ManipulationEngine()

    def test_engine_initialization(self):
        """Test ManipulationEngine initialization."""
        engine = ManipulationEngine()
        
        assert engine.max_operations == ManipulationEngine.MAX_OPERATIONS_PER_PLAN
        assert engine.confidence_threshold == ManipulationEngine.MIN_CONFIDENCE_THRESHOLD
        assert engine.require_confirmation_by_default is True

    def test_engine_initialization_with_config(self):
        """Test ManipulationEngine initialization with custom config."""
        config = {
            'max_operations': 50,
            'confidence_threshold': 0.8,
            'require_confirmation': False
        }
        
        engine = ManipulationEngine(config)
        
        assert engine.max_operations == 50
        assert engine.confidence_threshold == 0.8
        assert engine.require_confirmation_by_default is False

    def test_generate_removal_operations_duplicates(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test removal operation generation for duplicates."""
        operations = manipulation_engine.generate_removal_operations(
            sample_context_data, 
            mock_analysis_result.redundancy_report
        )
        
        # Should find exact duplicates
        duplicate_ops = [op for op in operations if "duplicate" in op.reasoning.lower()]
        assert len(duplicate_ops) >= 1
        
        # Check operation properties
        for op in duplicate_ops:
            assert op.operation_type == "remove"
            assert len(op.target_keys) >= 1
            assert op.confidence_score >= 0.9  # High confidence for exact duplicates
            assert op.estimated_token_impact < 0  # Should reduce tokens

    def test_generate_removal_operations_obsolete(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test removal operation generation for obsolete content."""
        operations = manipulation_engine.generate_removal_operations(
            sample_context_data, 
            mock_analysis_result.redundancy_report
        )
        
        # Should find obsolete todos
        obsolete_ops = [op for op in operations if "obsolete" in op.reasoning.lower()]
        assert len(obsolete_ops) >= 1
        
        for op in obsolete_ops:
            assert op.operation_type == "remove"
            assert op.confidence_score >= 0.8  # High confidence for obvious obsolete items

    def test_generate_removal_operations_resolved_errors(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test removal operation generation for resolved errors."""
        operations = manipulation_engine.generate_removal_operations(
            sample_context_data, 
            mock_analysis_result.redundancy_report
        )
        
        # Should find resolved errors
        error_ops = [op for op in operations if "resolved error" in op.reasoning.lower()]
        assert len(error_ops) >= 1
        
        for op in error_ops:
            assert op.operation_type == "remove"
            assert "error_2" in op.target_keys  # Should target the resolved error

    def test_generate_consolidation_operations_files(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test consolidation operation generation for duplicate file references."""
        operations = manipulation_engine.generate_consolidation_operations(
            sample_context_data, 
            mock_analysis_result.redundancy_report
        )
        
        # Should find duplicate file references to consolidate
        file_ops = [op for op in operations if "file" in op.reasoning.lower()]
        assert len(file_ops) >= 1
        
        for op in file_ops:
            assert op.operation_type == "consolidate"
            assert len(op.target_keys) >= 2  # Need multiple items to consolidate
            assert op.estimated_token_impact <= 0  # Should reduce or maintain tokens

    def test_generate_reorder_operations(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test reorder operation generation."""
        operations = manipulation_engine.generate_reorder_operations(
            sample_context_data, 
            mock_analysis_result.priority_report
        )
        
        # May or may not generate reorder operations depending on content
        for op in operations:
            assert op.operation_type == "reorder"
            assert len(op.target_keys) >= 2  # Need multiple items to reorder
            assert op.estimated_token_impact == 0  # Reordering doesn't change token count
            assert op.confidence_score >= 0.8  # Reordering is generally safe

    def test_generate_summarization_operations(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test summarization operation generation."""
        operations = manipulation_engine.generate_summarization_operations(
            sample_context_data, 
            mock_analysis_result.redundancy_report
        )
        
        # Should find verbose content to summarize
        summary_ops = [op for op in operations if op.operation_type == "summarize"]
        assert len(summary_ops) >= 1  # Should find the long conversation
        
        for op in summary_ops:
            assert op.operation_type == "summarize"
            assert op.estimated_token_impact < 0  # Should reduce tokens
            assert op.requires_confirmation is True  # Summarization always needs confirmation

    def test_create_manipulation_plan_conservative(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test manipulation plan creation with conservative safety level."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "conservative"
        )
        
        assert isinstance(plan, ManipulationPlan)
        assert plan.safety_level == "conservative"
        assert plan.total_operations == len(plan.operations)
        
        # Conservative mode should only have high-confidence operations
        for op in plan.operations:
            assert op.confidence_score >= 0.9

    def test_create_manipulation_plan_balanced(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test manipulation plan creation with balanced safety level."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "balanced"
        )
        
        assert plan.safety_level == "balanced"
        
        # Balanced mode should have medium-high confidence operations
        for op in plan.operations:
            assert op.confidence_score >= 0.7

    def test_create_manipulation_plan_aggressive(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test manipulation plan creation with aggressive safety level."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "aggressive"
        )
        
        assert plan.safety_level == "aggressive"
        
        # Aggressive mode may include summarization operations
        op_types = [op.operation_type for op in plan.operations]
        # Should have various operation types

    def test_create_manipulation_plan_no_conflicts(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test that manipulation plans don't have conflicting operations."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "balanced"
        )
        
        # Check that no keys are used by multiple operations
        used_keys = set()
        for op in plan.operations:
            for key in op.target_keys:
                assert key not in used_keys, f"Key {key} used by multiple operations"
                used_keys.add(key)

    def test_execute_operation_remove(self, manipulation_engine, sample_context_data):
        """Test executing a remove operation."""
        operation = ManipulationOperation(
            operation_id="test-remove-001",
            operation_type="remove",
            target_keys=["message_2"],  # Remove duplicate
            operation_data={"removal_type": "safe_delete"},
            estimated_token_impact=-50,
            confidence_score=0.95,
            reasoning="Test removal",
            requires_confirmation=False
        )
        
        modified_context, result = manipulation_engine.execute_operation(
            operation, sample_context_data
        )
        
        assert result["success"] is True
        assert "message_2" not in modified_context
        assert "message_1" in modified_context  # Should preserve original
        assert len(modified_context) == len(sample_context_data) - 1

    def test_execute_operation_consolidate(self, manipulation_engine, sample_context_data):
        """Test executing a consolidate operation."""
        operation = ManipulationOperation(
            operation_id="test-consolidate-001",
            operation_type="consolidate",
            target_keys=["file_ref_1", "file_ref_2"],  # Consolidate duplicate files
            operation_data={"strategy": "merge_file_references"},
            estimated_token_impact=-30,
            confidence_score=0.8,
            reasoning="Test consolidation",
            requires_confirmation=False
        )
        
        modified_context, result = manipulation_engine.execute_operation(
            operation, sample_context_data
        )
        
        assert result["success"] is True
        assert "file_ref_1" not in modified_context
        assert "file_ref_2" not in modified_context
        # Should have a consolidated key
        consolidated_keys = [k for k in modified_context.keys() if k.startswith("consolidated_")]
        assert len(consolidated_keys) >= 1

    def test_execute_operation_reorder(self, manipulation_engine, sample_context_data):
        """Test executing a reorder operation."""
        original_keys = ["todo_1", "todo_2"]
        new_order = ["todo_2", "todo_1"]  # Reverse order
        
        operation = ManipulationOperation(
            operation_id="test-reorder-001",
            operation_type="reorder",
            target_keys=original_keys,
            operation_data={"new_order": new_order},
            estimated_token_impact=0,
            confidence_score=0.9,
            reasoning="Test reordering",
            requires_confirmation=False
        )
        
        modified_context, result = manipulation_engine.execute_operation(
            operation, sample_context_data
        )
        
        assert result["success"] is True
        # Both keys should still exist
        assert "todo_1" in modified_context
        assert "todo_2" in modified_context
        # Check that order was changed in the context keys
        context_keys = list(modified_context.keys())
        todo1_index = context_keys.index("todo_1")
        todo2_index = context_keys.index("todo_2")
        # todo_2 should come before todo_1 now
        assert todo2_index < todo1_index

    def test_execute_plan_success(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test successful plan execution."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "balanced"
        )
        
        result = manipulation_engine.execute_plan(
            plan, sample_context_data, execute_all=True
        )
        
        assert isinstance(result, ManipulationResult)
        assert result.plan_id == plan.plan_id
        assert result.execution_success is True
        assert result.operations_executed > 0
        assert result.operations_failed == 0
        assert len(result.modified_context) <= len(sample_context_data)  # Should reduce or maintain size

    def test_execute_plan_selective(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test selective plan execution (skip operations requiring confirmation)."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "aggressive"  # May include operations requiring confirmation
        )
        
        result = manipulation_engine.execute_plan(
            plan, sample_context_data, execute_all=False
        )
        
        assert result.execution_success is True
        # May have executed fewer operations than planned due to confirmation requirements

    def test_convenience_functions(self, sample_context_data, mock_analysis_result):
        """Test convenience functions."""
        # Test create_manipulation_plan function
        plan = create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "balanced"
        )
        
        assert isinstance(plan, ManipulationPlan)
        
        # Test execute_manipulation_plan function
        result = execute_manipulation_plan(
            plan, sample_context_data, execute_all=True
        )
        
        assert isinstance(result, ManipulationResult)
        assert result.execution_success is True

    def test_operation_token_calculation(self, manipulation_engine):
        """Test token calculation for operations."""
        content = "This is a test string with some content"
        tokens = manipulation_engine._calculate_content_tokens(content)
        
        assert tokens > 0
        assert tokens == len(content) // 4  # Rough estimation

    def test_operation_id_generation(self, manipulation_engine):
        """Test operation ID generation."""
        id1 = manipulation_engine._generate_operation_id()
        id2 = manipulation_engine._generate_operation_id()
        
        assert len(id1) == 8  # Should be 8 character hash
        assert len(id2) == 8
        assert id1 != id2  # Should be unique

    def test_plan_metrics_calculation(self, manipulation_engine, sample_context_data, mock_analysis_result):
        """Test plan metrics are calculated correctly."""
        plan = manipulation_engine.create_manipulation_plan(
            sample_context_data,
            mock_analysis_result,
            "balanced"
        )
        
        assert plan.estimated_total_reduction >= 0
        assert plan.estimated_execution_time > 0
        assert isinstance(plan.requires_user_approval, bool)
        assert plan.created_timestamp is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])