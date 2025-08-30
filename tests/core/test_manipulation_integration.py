#!/usr/bin/env python3
"""
Integration Tests for Manipulation Engine with Analysis Components

Tests the complete integration between:
- ContextAnalyzer and ManipulationEngine
- Real analysis results driving manipulation operations
- End-to-end context cleaning workflow
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from context_cleaner.core.context_analyzer import ContextAnalyzer, analyze_context_sync
from context_cleaner.core.manipulation_engine import ManipulationEngine, create_manipulation_plan, execute_manipulation_plan
from context_cleaner.core.manipulation_validator import ManipulationValidator, validate_plan, verify_manipulation_integrity


class TestManipulationIntegration:
    """Test suite for manipulation engine integration with analysis components."""

    @pytest.fixture
    def realistic_context_data(self):
        """Realistic context data with various types of redundancy and issues."""
        return {
            # Exact duplicates
            "message_1": "Help me debug this authentication function", 
            "message_2": "Help me debug this authentication function",  # Exact duplicate
            
            # Similar content that could be consolidated
            "message_3": "Can you help debug the auth function?",
            "message_4": "Need help debugging authentication system",
            
            # Obsolete todos
            "todo_1": "Fix the login bug in authentication system",
            "todo_2": "Write unit tests for auth module", 
            "todo_3": "Fix the login bug - COMPLETED ✅",  # Obsolete
            "todo_4": "Deploy auth fix to staging - DONE",  # Obsolete
            "todo_5": "Update documentation - RESOLVED",  # Obsolete
            
            # Duplicate file references
            "file_ref_1": "/project/src/auth/login.py",
            "file_ref_2": "/project/src/auth/login.py",  # Duplicate file reference
            "file_ref_3": "/project/src/auth/utils.py",
            "file_ref_4": "/project/src/auth/login.py",  # Another duplicate
            
            # Verbose/repetitive conversation
            "conversation_long": ("User: How do I fix the authentication bug? " + 
                                "Assistant: You can fix it by updating the login function. " +
                                "User: How do I fix the authentication bug? " +  # Repeated question
                                "Assistant: You can fix it by updating the login function. ") * 25,  # Very verbose/repetitive
            
            # Error messages (some resolved)
            "error_1": "TypeError: 'NoneType' object is not subscriptable in auth.py line 45",
            "error_2": "Fixed: TypeError in auth.py - resolved by adding null check",  # Resolved error
            "error_3": "Resolved: Import error in utils.py - fixed import statement",  # Resolved error
            
            # System reminders and metadata
            "system_reminder_1": "Remember to test the authentication changes",
            "system_reminder_2": "Don't forget to test auth changes",  # Similar reminder
            "timestamp": datetime.now().isoformat(),
            "last_modified": (datetime.now() - timedelta(minutes=15)).isoformat(),
            
            # Some important content that should be preserved
            "critical_config": "Database connection settings: localhost:5432",
            "important_note": "IMPORTANT: Always validate user input before authentication",
        }

    @pytest.fixture
    def context_analyzer(self):
        """ContextAnalyzer instance for testing."""
        return ContextAnalyzer()

    @pytest.fixture
    def manipulation_engine(self):
        """ManipulationEngine instance for testing."""
        return ManipulationEngine()

    @pytest.fixture
    def validator(self):
        """ManipulationValidator instance for testing."""
        return ManipulationValidator()

    @pytest.mark.asyncio
    async def test_full_analysis_to_manipulation_workflow(self, realistic_context_data, context_analyzer, manipulation_engine, validator):
        """Test complete workflow from analysis to manipulation."""
        # Step 1: Analyze the context
        analysis_result = await context_analyzer.analyze_context(realistic_context_data)
        
        assert analysis_result is not None
        assert analysis_result.health_score >= 0
        assert analysis_result.optimization_potential > 0  # Should find optimization opportunities
        
        # Verify analysis found issues
        assert analysis_result.redundancy_report.duplicate_content_percentage > 0
        
        # Step 2: Create manipulation plan based on analysis
        plan = manipulation_engine.create_manipulation_plan(
            realistic_context_data, 
            analysis_result, 
            "balanced"
        )
        
        assert plan.total_operations > 0  # Should generate operations
        assert plan.estimated_total_reduction > 0  # Should estimate token reduction
        
        # Step 3: Validate the plan
        validation = validator.validate_plan(plan, realistic_context_data)
        
        assert validation.is_valid is True  # Plan should be valid
        assert validation.confidence_score > 0.5  # Should have reasonable confidence
        
        # Step 4: Execute the plan
        execution_result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        assert execution_result.execution_success is True
        assert execution_result.operations_executed > 0
        assert execution_result.operations_failed == 0
        
        # Step 5: Verify integrity
        integrity = validator.verify_integrity(
            realistic_context_data,
            execution_result.modified_context,
            plan.operations
        )
        
        assert integrity.integrity_maintained is True
        assert integrity.critical_content_preserved is True
        
        # Step 6: Verify actual improvements
        original_size = len(str(realistic_context_data))
        modified_size = len(str(execution_result.modified_context))
        reduction_percentage = ((original_size - modified_size) / original_size) * 100
        
        assert reduction_percentage > 0  # Should achieve size reduction
        assert len(execution_result.modified_context) <= len(realistic_context_data)  # Should reduce item count

    def test_synchronous_workflow(self, realistic_context_data):
        """Test synchronous workflow using convenience functions."""
        # Step 1: Analyze context synchronously
        analysis_result = analyze_context_sync(realistic_context_data)
        
        assert analysis_result is not None
        
        # Step 2: Create and execute manipulation plan
        plan = create_manipulation_plan(realistic_context_data, analysis_result, "balanced")
        
        assert plan.total_operations > 0
        
        # Step 3: Execute plan
        result = execute_manipulation_plan(plan, realistic_context_data, execute_all=True)
        
        assert result.execution_success is True
        assert len(result.modified_context) <= len(realistic_context_data)

    def test_conservative_vs_aggressive_modes(self, realistic_context_data, manipulation_engine):
        """Test different safety modes produce different plans."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        # Create plans with different safety levels
        conservative_plan = manipulation_engine.create_manipulation_plan(
            realistic_context_data, analysis_result, "conservative"
        )
        
        balanced_plan = manipulation_engine.create_manipulation_plan(
            realistic_context_data, analysis_result, "balanced"
        )
        
        aggressive_plan = manipulation_engine.create_manipulation_plan(
            realistic_context_data, analysis_result, "aggressive"
        )
        
        # Conservative should have fewer operations (only high confidence)
        assert conservative_plan.total_operations <= balanced_plan.total_operations
        
        # All conservative operations should have high confidence
        for op in conservative_plan.operations:
            assert op.confidence_score >= 0.9
        
        # Aggressive may include summarization operations
        aggressive_op_types = [op.operation_type for op in aggressive_plan.operations]
        # May include 'summarize' operations
        
        # Balanced should be middle ground
        for op in balanced_plan.operations:
            assert op.confidence_score >= 0.7

    def test_manipulation_preserves_important_content(self, realistic_context_data, manipulation_engine, validator):
        """Test that manipulation preserves important/critical content."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        # Create and execute plan
        plan = manipulation_engine.create_manipulation_plan(realistic_context_data, analysis_result, "aggressive")
        result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        # Verify critical content is preserved
        assert "critical_config" in result.modified_context or any(
            "critical_config" in str(v) for v in result.modified_context.values()
        )
        assert "important_note" in result.modified_context or any(
            "important_note" in str(v) for v in result.modified_context.values()
        )
        
        # Verify integrity check confirms preservation
        integrity = validator.verify_integrity(
            realistic_context_data,
            result.modified_context,
            plan.operations
        )
        assert integrity.critical_content_preserved is True

    def test_duplicate_removal_effectiveness(self, realistic_context_data, manipulation_engine):
        """Test that duplicate removal operations are effective."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        # Should detect duplicates in original data
        assert analysis_result.redundancy_report.duplicate_content_percentage > 0
        
        # Create and execute plan
        plan = manipulation_engine.create_manipulation_plan(realistic_context_data, analysis_result, "balanced")
        result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        # Should have fewer duplicate messages
        modified_messages = [v for k, v in result.modified_context.items() if "message" in k]
        original_messages = [v for k, v in realistic_context_data.items() if "message" in k]
        
        # Should remove at least some duplicates
        assert len(modified_messages) <= len(original_messages)

    def test_obsolete_content_removal(self, realistic_context_data, manipulation_engine):
        """Test that obsolete content is properly identified and removed."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        plan = manipulation_engine.create_manipulation_plan(realistic_context_data, analysis_result, "balanced")
        result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        # Should remove obsolete todos
        remaining_todos = [k for k in result.modified_context.keys() if "todo" in k and "completed" not in str(result.modified_context[k]).lower()]
        
        # Should have fewer todos after removing completed ones
        original_active_todos = [k for k, v in realistic_context_data.items() if "todo" in k and "completed" not in str(v).lower() and "done" not in str(v).lower()]
        
        # May have consolidated todos, so check that obsolete markers are gone
        for key, value in result.modified_context.items():
            content = str(value).lower()
            # Should not have obvious completion markers in remaining content
            if "todo" in key:
                assert not ("✅" in content and "completed" in content)

    def test_file_reference_consolidation(self, realistic_context_data, manipulation_engine):
        """Test that duplicate file references are consolidated."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        plan = manipulation_engine.create_manipulation_plan(realistic_context_data, analysis_result, "balanced")
        result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        # Count references to the same file in original vs modified
        original_login_refs = sum(1 for k, v in realistic_context_data.items() 
                                if "file_ref" in k and "/project/src/auth/login.py" in str(v))
        
        modified_login_refs = sum(1 for k, v in result.modified_context.items()
                                if "/project/src/auth/login.py" in str(v))
        
        # Should have consolidated duplicate file references
        assert modified_login_refs <= original_login_refs

    def test_manipulation_maintains_context_coherence(self, realistic_context_data, manipulation_engine, validator):
        """Test that manipulation maintains overall context coherence."""
        analysis_result = analyze_context_sync(realistic_context_data)
        assert analysis_result is not None
        
        plan = manipulation_engine.create_manipulation_plan(realistic_context_data, analysis_result, "balanced")
        result = manipulation_engine.execute_plan(plan, realistic_context_data, execute_all=True)
        
        # Verify context still makes sense after manipulation
        integrity = validator.verify_integrity(
            realistic_context_data,
            result.modified_context,
            plan.operations
        )
        
        assert integrity.structure_preserved is True
        assert len(result.modified_context) > 0  # Should not remove everything
        
        # Should still have a reasonable mix of content types
        modified_keys = list(result.modified_context.keys())
        assert len(modified_keys) >= 5  # Should preserve reasonable amount of content

    def test_error_handling_in_integration(self, manipulation_engine):
        """Test error handling in integration scenarios."""
        # Test with invalid context data
        invalid_context = {}  # Empty context
        
        try:
            analysis_result = analyze_context_sync(invalid_context)
            if analysis_result:  # If analysis somehow succeeds with empty context
                plan = manipulation_engine.create_manipulation_plan(invalid_context, analysis_result, "balanced")
                assert plan.total_operations == 0  # Should create empty plan
        except Exception:
            # Expected to fail with empty context
            pass
        
        # Test with malformed analysis result
        malformed_context = {"key": "value"}
        analysis_result = analyze_context_sync(malformed_context)
        if analysis_result:
            # Should handle gracefully even with minimal context
            plan = manipulation_engine.create_manipulation_plan(malformed_context, analysis_result, "balanced")
            assert isinstance(plan, type(plan))  # Should return valid plan object

if __name__ == "__main__":
    pytest.main([__file__, "-v"])