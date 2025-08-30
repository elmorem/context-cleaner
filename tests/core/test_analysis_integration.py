#!/usr/bin/env python3
"""
Integration Tests for Context Analysis Engine Components

Comprehensive integration tests that verify all analysis components work together:
- Full analysis workflow with ContextAnalyzer
- Component interaction and data flow
- Performance of integrated system
- Error handling across components
- Real-world scenario testing
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytz

from src.context_cleaner.core.context_analyzer import ContextAnalyzer, ContextAnalysisResult
from src.context_cleaner.core.redundancy_detector import RedundancyDetector
from src.context_cleaner.core.recency_analyzer import RecencyAnalyzer
from src.context_cleaner.core.focus_scorer import FocusScorer
from src.context_cleaner.core.priority_analyzer import PriorityAnalyzer


class TestContextAnalysisIntegration:
    """Integration tests for the complete context analysis system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ContextAnalyzer()
        
        # Create comprehensive test context with known characteristics
        now = datetime.now(pytz.UTC)
        
        self.comprehensive_context = {
            # Current high-priority work (should score high on focus/priority)
            'urgent_current_work': [
                'CRITICAL: Currently fixing authentication bug blocking all users',
                'HIGH PRIORITY: Implementing OAuth2 integration - due today',
                'Working on user session management module right now'
            ],
            
            # Recent development tasks (should be recent, actionable)
            'recent_development': [
                {
                    'task': 'DEBUG: Login flow investigation',
                    'timestamp': (now - timedelta(hours=2)).isoformat(),
                    'priority': 'high'
                },
                {
                    'task': 'TODO: Write unit tests for auth module',
                    'timestamp': (now - timedelta(hours=1)).isoformat(),
                    'status': 'in_progress'
                },
                {
                    'task': 'REVIEW: Pull request for security updates',
                    'timestamp': (now - timedelta(minutes=45)).isoformat(),
                    'urgent': True
                }
            ],
            
            # Duplicate content (should be detected by redundancy analysis)
            'messages_with_duplicates': [
                'Help me debug the authentication system',
                'Need to fix the login functionality',
                'Help me debug the authentication system',  # Exact duplicate
                'Help me debug the authentication flow',    # Similar content
                'Authentication system working now - fixed!'  # Resolution
            ],
            
            # Files with redundancy
            'file_accesses': [
                {'path': '/src/auth/login.py', 'last_access': (now - timedelta(minutes=30)).isoformat()},
                {'path': '/src/auth/oauth.py', 'last_access': (now - timedelta(hours=1)).isoformat()},
                {'path': '/src/auth/login.py', 'last_access': (now - timedelta(minutes=15)).isoformat()},  # Duplicate
                {'path': '/src/tests/auth_test.py', 'last_access': (now - timedelta(hours=3)).isoformat()},
                {'path': '/src/auth/login.py', 'last_access': (now - timedelta(minutes=5)).isoformat()}   # Another duplicate
            ],
            
            # Completed/obsolete tasks (should be identified as noise/stale)
            'completed_obsolete': [
                {
                    'task': 'Database migration - COMPLETED ✅',
                    'timestamp': (now - timedelta(days=3)).isoformat(),
                    'status': 'done'
                },
                {
                    'task': 'Old user interface redesign - archived',
                    'timestamp': (now - timedelta(days=7)).isoformat(),
                    'status': 'obsolete'
                },
                {
                    'task': 'Legacy API cleanup - no longer needed',
                    'timestamp': (now - timedelta(days=5)).isoformat(),
                    'status': 'resolved'
                }
            ],
            
            # Mixed priority items for priority alignment testing
            'mixed_priority_items': [
                'Low priority: Maybe add dark mode someday',           # Should be low priority
                'URGENT: Server performance degradation detected',     # Should be critical
                'Nice to have: Improve error messages',               # Should be low priority
                'BLOCKING: Waiting for security team approval',       # Should be high priority
                'Currently implementing user preferences system',      # Should be current work
                'Enhancement: Consider migrating to React 18',        # Should be low priority
                'ASAP: Deploy critical security patch'                # Should be critical
            ],
            
            # Content with dependencies and deadlines
            'dependencies_deadlines': [
                'Blocked by: Database schema changes needed first',
                'Due by end of week: Complete API documentation',
                'Waiting for: Design team mockup approval',
                'Deadline Friday: Submit security audit report',
                'Depends on: Infrastructure team server setup'
            ],
            
            # Session metadata
            'session_info': {
                'session_id': 'integration-test-session',
                'start_time': (now - timedelta(hours=4)).isoformat(),
                'current_focus': 'authentication system debugging',
                'project': 'user-management-service'
            }
        }
    
    @pytest.mark.asyncio
    async def test_full_analysis_integration(self):
        """Test complete analysis workflow with all components."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        # Verify result structure
        assert result is not None
        assert isinstance(result, ContextAnalysisResult)
        
        # Check that all component reports are present
        assert result.focus_metrics is not None
        assert result.redundancy_report is not None
        assert result.recency_report is not None
        assert result.priority_report is not None
        
        # Verify overall health score is reasonable
        assert 0 <= result.health_score <= 100
        
        # Verify size calculations
        assert result.total_tokens > 0
        assert result.total_chars > 0
        assert result.total_chars == len(json.dumps(self.comprehensive_context, default=str))
    
    @pytest.mark.asyncio
    async def test_redundancy_detection_integration(self):
        """Test that redundancy is properly detected and reported."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        redundancy = result.redundancy_report
        
        # Should detect duplicates in messages
        assert redundancy.duplicate_content_percentage > 0
        assert len(redundancy.duplicate_items) > 0
        
        # Should detect redundant file accesses
        assert redundancy.redundant_files_count >= 1  # login.py accessed multiple times
        
        # Should detect obsolete todos
        assert redundancy.obsolete_todos_count >= 3  # We have 3 completed items
        
        # Should have optimization recommendations
        assert len(redundancy.safe_to_remove) > 0
    
    @pytest.mark.asyncio
    async def test_focus_analysis_integration(self):
        """Test that focus analysis correctly evaluates content quality."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        focus = result.focus_metrics
        
        # Should have reasonable focus score given mix of current work and noise
        assert 40 <= focus.focus_score <= 90
        
        # Should detect current work items
        assert focus.work_related_items > 0
        assert focus.current_work_ratio > 0
        
        # Should detect high priority items
        assert focus.high_priority_items > 0
        
        # Should detect actionable items
        assert focus.active_task_items > 0
        
        # Should detect some noise/distractions
        assert focus.noise_items > 0
    
    @pytest.mark.asyncio
    async def test_priority_analysis_integration(self):
        """Test that priority analysis correctly categorizes and scores content."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        priority = result.priority_report
        
        # Should have reasonable priority alignment
        assert 0 <= priority.priority_alignment_score <= 100
        
        # Should detect critical items (URGENT, CRITICAL, ASAP)
        assert len(priority.critical_items) >= 2
        
        # Should detect high priority items
        assert len(priority.high_priority_items) >= 1
        
        # Should detect low priority items (nice to have, maybe, someday)
        assert len(priority.low_priority_items) >= 2
        
        # Should detect noise items (completed, obsolete)
        assert len(priority.noise_items) >= 3
        
        # Should detect items with deadlines
        assert len(priority.items_with_deadlines) >= 2
        
        # Should detect blocking dependencies
        assert len(priority.blocking_dependencies) >= 1
    
    @pytest.mark.asyncio
    async def test_recency_analysis_integration(self):
        """Test that recency analysis properly categorizes content by age."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        recency = result.recency_report
        
        # Should have items in different recency categories
        assert recency.fresh_context_percentage > 0    # Recent timestamps
        assert recency.recent_context_percentage > 0   # Within session
        assert recency.stale_context_percentage > 0    # Old completed items
        
        # Should detect fresh items (recent timestamps)
        assert len(recency.fresh_items) > 0
        
        # Should detect stale items (old completed tasks)
        assert len(recency.stale_items) > 0
        
        # Should estimate session characteristics
        assert recency.session_duration_minutes > 0
        assert 0.0 <= recency.session_activity_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_optimization_potential_calculation(self):
        """Test that optimization potential is calculated correctly."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        # Should have optimization potential due to duplicates and stale content
        assert 0.1 <= result.optimization_potential <= 0.8
        
        # Critical context ratio should complement optimization potential
        assert abs(result.optimization_potential + result.critical_context_ratio - 1.0) < 0.01
        
        # Should estimate cleanup impact
        assert result.cleanup_impact_estimate > 0
        assert result.cleanup_impact_estimate < result.total_tokens
    
    @pytest.mark.asyncio
    async def test_health_score_calculation_integration(self):
        """Test that overall health score reflects component analyses."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        # Extract component scores
        focus_score = result.focus_metrics.focus_score
        redundancy_penalty = result.redundancy_report.duplicate_content_percentage
        recency_score = (result.recency_report.fresh_context_percentage + 
                        result.recency_report.recent_context_percentage) * 0.5
        priority_score = result.priority_report.priority_alignment_score
        
        # Health score should be reasonable given component scores
        assert 30 <= result.health_score <= 95
        
        # Health score should correlate with component quality
        if focus_score > 80 and redundancy_penalty < 20:
            assert result.health_score > 70
        
        if focus_score < 50 or redundancy_penalty > 40:
            assert result.health_score < 80
    
    @pytest.mark.asyncio
    async def test_performance_integration(self):
        """Test that integrated analysis completes within performance requirements."""
        start_time = datetime.now()
        
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Should complete within performance target (<2s for complex context)
        assert total_duration < 2.0
        
        # Individual component durations should be reasonable
        assert result.redundancy_report.redundancy_analysis_duration < 1.0
        assert result.recency_report.recency_analysis_duration < 1.0  
        assert result.focus_metrics.focus_analysis_duration < 1.0
        assert result.priority_report.priority_analysis_duration < 1.0
        
        # Overall analysis duration should match
        assert abs(result.analysis_duration - total_duration) < 0.5
    
    @pytest.mark.asyncio
    async def test_component_interaction_consistency(self):
        """Test that components provide consistent analysis of the same content."""
        result = await self.analyzer.analyze_context(self.comprehensive_context)
        
        # Components should agree on basic content characteristics
        total_items_focus = result.focus_metrics.total_content_items
        total_items_priority = result.priority_report.total_items_analyzed
        total_items_recency = result.recency_report.total_items_categorized
        
        # Item counts should be similar (allowing for different extraction strategies)
        max_items = max(total_items_focus, total_items_priority, total_items_recency)
        min_items = min(total_items_focus, total_items_priority, total_items_recency)
        
        assert max_items > 0
        assert (max_items - min_items) / max_items < 0.3  # Within 30%
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self):
        """Test error recovery when individual components fail."""
        # Mock one component to fail
        with patch.object(self.analyzer.redundancy_detector, 'analyze_redundancy') as mock:
            mock.side_effect = Exception("Redundancy analysis failed")
            
            result = await self.analyzer.analyze_context(self.comprehensive_context)
            
            # Should handle component failure gracefully
            assert result is None  # Main analyzer should return None on component failure
    
    @pytest.mark.asyncio
    async def test_caching_integration(self):
        """Test that caching works correctly across analysis runs."""
        # First analysis
        result1 = await self.analyzer.analyze_context(self.comprehensive_context, use_cache=True)
        assert result1 is not None
        
        # Second analysis should be cached and faster
        start_time = datetime.now()
        result2 = await self.analyzer.analyze_context(self.comprehensive_context, use_cache=True)
        cache_duration = (datetime.now() - start_time).total_seconds()
        
        assert result2 is not None
        assert cache_duration < 0.1  # Should be very fast (cached)
        assert result1.analysis_timestamp == result2.analysis_timestamp  # Same analysis
    
    @pytest.mark.asyncio
    async def test_realistic_development_scenario(self):
        """Test analysis with realistic development session context."""
        realistic_context = {
            # Active debugging session
            'current_debugging': [
                'Currently investigating OAuth token validation bug',
                'ERROR: Invalid token signature in production logs',
                'URGENT: Users cannot log in - blocking critical functionality',
                'Debugging session started 2 hours ago'
            ],
            
            # Code files being worked on
            'active_files': [
                '/src/auth/oauth_validator.py - modified 10 minutes ago',
                '/src/auth/token_manager.py - modified 30 minutes ago', 
                '/src/tests/test_oauth.py - created 45 minutes ago',
                '/docs/oauth_troubleshooting.md - updated 1 hour ago'
            ],
            
            # Task progress
            'task_status': [
                'TODO: Reproduce bug in development environment ✅',
                'TODO: Identify root cause in token validation',
                'TODO: Implement fix and write regression test',
                'TODO: Deploy hotfix to production - URGENT',
                'DONE: Set up debugging environment'
            ],
            
            # Communication/notes
            'session_notes': [
                'Team notified of production issue at 10:30 AM',
                'Security team consulted on token validation approach',
                'Identified potential issue in JWT signature verification',
                'Need to coordinate deployment with DevOps team'
            ]
        }
        
        result = await self.analyzer.analyze_context(realistic_context)
        
        # Should recognize this as a focused debugging session
        assert result.health_score >= 70  # Good focus on current problem
        assert result.focus_metrics.focus_score >= 75  # High focus
        assert result.focus_metrics.current_work_ratio >= 0.7  # Mostly current work
        
        # Should detect urgency and priority
        assert len(result.priority_report.critical_items) >= 1  # URGENT items
        assert result.priority_report.current_work_focus_percentage >= 60
        
        # Should recognize recency of activity
        assert result.recency_report.recent_context_percentage >= 50
        
        # Should have minimal redundancy in focused session
        assert result.redundancy_report.duplicate_content_percentage <= 20
    
    @pytest.mark.asyncio
    async def test_messy_context_scenario(self):
        """Test analysis with cluttered, unfocused context."""
        messy_context = {
            'random_notes': [
                'Maybe we should consider microservices architecture',
                'Coffee meeting notes from last Tuesday',
                'Random thought about database indexing',
                'Link to interesting blog post about React patterns',
                'Shopping list: milk, eggs, bread'
            ],
            
            'old_completed_work': [
                'Completed: Q3 planning session - DONE',
                'Finished: Legacy system migration last month', 
                'Archived: Old mobile app project',
                'Resolved: Customer complaint from 2 weeks ago',
                'Closed: Duplicate bug report from July'
            ],
            
            'mixed_todos': [
                'Someday: Learn new programming language',
                'Maybe: Refactor entire codebase', 
                'Nice to have: Add animations to UI',
                'Consider: Moving to cloud infrastructure',
                'Future: Implement machine learning features'
            ],
            
            'duplicate_content': [
                'Check the user authentication system',
                'Review the authentication system',
                'Check the user authentication system',  # Duplicate
                'Verify authentication system functionality',
                'Look at the authentication system code'
            ]
        }
        
        result = await self.analyzer.analyze_context(messy_context)
        
        # Should recognize poor focus and organization
        assert result.health_score <= 60  # Poor health due to lack of focus
        assert result.focus_metrics.focus_score <= 50  # Low focus
        assert result.focus_metrics.current_work_ratio <= 0.3  # Little current work
        
        # Should detect high redundancy
        assert result.redundancy_report.duplicate_content_percentage >= 20
        assert result.redundancy_report.stale_content_percentage >= 30
        
        # Should suggest high optimization potential
        assert result.optimization_potential >= 0.4  # Lots could be cleaned up


class TestIndividualComponentIntegration:
    """Test individual component integration without full ContextAnalyzer."""
    
    @pytest.mark.asyncio
    async def test_redundancy_focus_correlation(self):
        """Test correlation between redundancy and focus analysis."""
        # Context with known redundancy that should affect focus
        redundant_context = {
            'messages': [
                'Fix the login bug',
                'Fix the login bug',  # Duplicate should lower focus
                'Fix the login bug',  # Another duplicate
                'Work on something else entirely',
                'Random unrelated note'
            ]
        }
        
        redundancy_detector = RedundancyDetector()
        focus_scorer = FocusScorer()
        
        redundancy_report = await redundancy_detector.analyze_redundancy(redundant_context)
        focus_metrics = await focus_scorer.calculate_focus_metrics(redundant_context)
        
        # High redundancy should correlate with lower focus
        assert redundancy_report.duplicate_content_percentage > 30
        assert focus_metrics.focus_score < 70  # Redundancy should hurt focus
    
    @pytest.mark.asyncio
    async def test_priority_recency_correlation(self):
        """Test correlation between priority and recency analysis."""
        now = datetime.now(pytz.UTC)
        
        # Context with current high-priority work
        current_priority_context = {
            'urgent_current': {
                'task': 'CRITICAL: Fix production bug now',
                'timestamp': now.isoformat(),
                'priority': 'urgent'
            },
            'old_completed': {
                'task': 'Completed: Old feature from last month',
                'timestamp': (now - timedelta(days=30)).isoformat(),
                'status': 'done'
            }
        }
        
        priority_analyzer = PriorityAnalyzer()
        recency_analyzer = RecencyAnalyzer()
        
        priority_report = await priority_analyzer.analyze_priorities(current_priority_context)
        recency_report = await recency_analyzer.analyze_recency(current_priority_context)
        
        # Recent high-priority work should be detected by both
        assert len(priority_report.critical_items) >= 1
        assert recency_report.fresh_context_percentage > 0
        assert len(recency_report.stale_items) >= 1  # Old completed item
    
    @pytest.mark.asyncio
    async def test_component_performance_isolation(self):
        """Test that individual components maintain performance in isolation."""
        # Create moderately large context
        large_context = {}
        for i in range(50):
            large_context[f'section_{i}'] = [
                f'Item {j} in section {i}' for j in range(5)
            ]
        
        # Test each component individually
        start_time = datetime.now()
        redundancy_detector = RedundancyDetector()
        await redundancy_detector.analyze_redundancy(large_context)
        redundancy_time = (datetime.now() - start_time).total_seconds()
        
        start_time = datetime.now()
        focus_scorer = FocusScorer()
        await focus_scorer.calculate_focus_metrics(large_context)
        focus_time = (datetime.now() - start_time).total_seconds()
        
        start_time = datetime.now()
        priority_analyzer = PriorityAnalyzer()
        await priority_analyzer.analyze_priorities(large_context)
        priority_time = (datetime.now() - start_time).total_seconds()
        
        start_time = datetime.now()
        recency_analyzer = RecencyAnalyzer()
        await recency_analyzer.analyze_recency(large_context)
        recency_time = (datetime.now() - start_time).total_seconds()
        
        # Each component should complete within reasonable time
        assert redundancy_time < 1.0
        assert focus_time < 1.0
        assert priority_time < 1.0
        assert recency_time < 1.0


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])