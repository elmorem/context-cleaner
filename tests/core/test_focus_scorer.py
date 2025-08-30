#!/usr/bin/env python3
"""
Tests for the Focus Scoring Engine

Comprehensive tests for focus scoring including:
- Focus score calculation
- Priority alignment assessment
- Current work ratio analysis
- Attention clarity scoring
- Content positioning analysis
- Keyword detection and categorization
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from src.context_cleaner.core.focus_scorer import (
    FocusScorer, FocusMetrics
)


class TestFocusScorer:
    """Test suite for FocusScorer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = FocusScorer()
        
        self.high_focus_context = {
            'current_objectives': [
                'Currently implementing OAuth2 authentication system',  # High focus
                'Fix urgent login bug that\'s blocking users',          # High focus + priority
                'Need to write unit tests for auth module'             # Actionable current work
            ],
            'action_items': [
                'TODO: Implement password validation',                 # Clear action
                '[ ] Test OAuth flow with Google provider',           # Clear action
                'Must deploy hotfix by end of day'                    # Urgent action
            ]
        }
        
        self.low_focus_context = {
            'completed_tasks': [
                'Completed database migration last week',              # Distraction (completed)
                'Old legacy system documentation',                     # Distraction (old)
                'Archived project from 2023'                          # Distraction (archived)
            ],
            'mixed_content': [
                'Random note about coffee preferences',                # Noise
                'Historical context from previous sprint',             # Potential distraction
                'Maybe consider refactoring later'                     # Low priority
            ]
        }
        
        self.mixed_context = {
            'current_work': [
                'Debug session for current auth implementation',       # Current work
                'Review pull request - high priority'                 # Priority work  
            ],
            'random_notes': [
                'Should probably update documentation',                # Vague action
                'Random thought about architecture'                   # Noise
            ]
        }
    
    @pytest.mark.asyncio
    async def test_calculate_focus_metrics_high_focus(self):
        """Test focus metrics calculation with high-focus content."""
        metrics = await self.scorer.calculate_focus_metrics(self.high_focus_context)
        
        assert isinstance(metrics, FocusMetrics)
        assert metrics.focus_score >= 70  # Should be high for focused content
        assert metrics.priority_alignment_score >= 50
        assert metrics.current_work_ratio > 0.5  # Mostly current work
        assert metrics.attention_clarity_score >= 60
        assert metrics.total_content_items > 0
    
    @pytest.mark.asyncio
    async def test_calculate_focus_metrics_low_focus(self):
        """Test focus metrics calculation with low-focus content."""
        metrics = await self.scorer.calculate_focus_metrics(self.low_focus_context)
        
        assert isinstance(metrics, FocusMetrics)
        assert metrics.focus_score <= 60  # Should be low for unfocused content
        assert metrics.current_work_ratio < 0.3  # Little current work
        assert metrics.noise_items > 0  # Should detect noise
    
    def test_extract_content_with_positions(self):
        """Test content extraction with position information."""
        items = self.scorer._extract_content_with_positions(self.high_focus_context)
        
        assert len(items) > 0
        
        # Check structure of returned items
        for position, path, content in items:
            assert isinstance(position, int)
            assert isinstance(path, str)
            assert position >= 0
            assert len(path) > 0
    
    def test_analyze_content_focus_current_work(self):
        """Test content focus analysis for current work."""
        content = "Currently implementing OAuth2 authentication system"
        analysis = self.scorer._analyze_content_focus(content)
        
        assert analysis['is_current_work'] is True
        assert analysis['focus_score'] > 50
        assert len(analysis['focus_keywords']) > 0
        assert 'currently' in analysis['focus_keywords']
    
    def test_analyze_content_focus_high_priority(self):
        """Test content focus analysis for high priority items."""
        content = "URGENT: Fix critical authentication bug immediately"
        analysis = self.scorer._analyze_content_focus(content)
        
        assert analysis['is_high_priority'] is True
        assert analysis['focus_score'] > 70
        assert len(analysis['priority_keywords']) > 0
    
    def test_analyze_content_focus_actionable(self):
        """Test content focus analysis for actionable items."""
        content = "TODO: Implement password validation function"
        analysis = self.scorer._analyze_content_focus(content)
        
        assert analysis['is_actionable'] is True
        assert analysis['focus_score'] > 50
        assert len(analysis['action_patterns']) > 0
    
    def test_analyze_content_focus_distraction(self):
        """Test content focus analysis for distracting content."""
        content = "Completed old legacy system migration last month"
        analysis = self.scorer._analyze_content_focus(content)
        
        assert analysis['is_distraction'] is True
        assert analysis['focus_score'] < 50
        assert len(analysis['distraction_keywords']) > 0
    
    def test_analyze_content_focus_multiple_signals(self):
        """Test content with multiple focus signals."""
        content = "URGENT: Currently implementing critical OAuth fix - must deploy today"
        analysis = self.scorer._analyze_content_focus(content)
        
        # Should detect multiple positive signals
        assert analysis['is_current_work'] is True
        assert analysis['is_high_priority'] is True
        assert analysis['focus_score'] > 80  # Should get bonus for multiple signals
    
    def test_calculate_priority_alignment_good_alignment(self):
        """Test priority alignment calculation with well-aligned content."""
        # Mock items where high priority items appear early
        items_with_analysis = [
            (0, 'path1', 'content1', {'is_high_priority': True, 'is_current_work': True, 'is_actionable': False, 'is_distraction': False}),
            (1, 'path2', 'content2', {'is_high_priority': True, 'is_current_work': False, 'is_actionable': True, 'is_distraction': False}),
            (2, 'path3', 'content3', {'is_high_priority': False, 'is_current_work': False, 'is_actionable': False, 'is_distraction': False}),
            (3, 'path4', 'content4', {'is_high_priority': False, 'is_current_work': False, 'is_actionable': False, 'is_distraction': True})
        ]
        
        score = self.scorer._calculate_priority_alignment(items_with_analysis)
        assert score >= 80  # Good alignment, priority items at top
    
    def test_calculate_priority_alignment_poor_alignment(self):
        """Test priority alignment calculation with poorly aligned content."""
        # Mock items where high priority items appear late
        items_with_analysis = [
            (0, 'path1', 'content1', {'is_high_priority': False, 'is_current_work': False, 'is_actionable': False, 'is_distraction': True}),
            (1, 'path2', 'content2', {'is_high_priority': False, 'is_current_work': False, 'is_actionable': False, 'is_distraction': False}),
            (2, 'path3', 'content3', {'is_high_priority': True, 'is_current_work': True, 'is_actionable': False, 'is_distraction': False}),
            (3, 'path4', 'content4', {'is_high_priority': True, 'is_current_work': False, 'is_actionable': True, 'is_distraction': False})
        ]
        
        score = self.scorer._calculate_priority_alignment(items_with_analysis)
        assert score <= 40  # Poor alignment, priority items at bottom
    
    def test_calculate_attention_clarity_high_clarity(self):
        """Test attention clarity calculation with high clarity."""
        # Mock items with many actionable and current work items
        items_with_analysis = [
            (0, 'path1', 'content1', {'is_actionable': True, 'is_current_work': True, 'is_distraction': False}),
            (1, 'path2', 'content2', {'is_actionable': True, 'is_current_work': False, 'is_distraction': False}),
            (2, 'path3', 'content3', {'is_actionable': False, 'is_current_work': True, 'is_distraction': False}),
            (3, 'path4', 'content4', {'is_actionable': False, 'is_current_work': False, 'is_distraction': False})
        ]
        
        score = self.scorer._calculate_attention_clarity(items_with_analysis)
        assert score >= 60  # High clarity with actionable items
    
    def test_calculate_attention_clarity_low_clarity(self):
        """Test attention clarity calculation with low clarity."""
        # Mock items with many distractions and few actionable items
        items_with_analysis = [
            (0, 'path1', 'content1', {'is_actionable': False, 'is_current_work': False, 'is_distraction': True}),
            (1, 'path2', 'content2', {'is_actionable': False, 'is_current_work': False, 'is_distraction': True}),
            (2, 'path3', 'content3', {'is_actionable': False, 'is_current_work': False, 'is_distraction': False}),
            (3, 'path4', 'content4', {'is_actionable': True, 'is_current_work': False, 'is_distraction': False})
        ]
        
        score = self.scorer._calculate_attention_clarity(items_with_analysis)
        assert score <= 40  # Low clarity with many distractions
    
    def test_calculate_context_coherence_good_coherence(self):
        """Test context coherence calculation with good coherence."""
        # Mock items with some repeated but not excessive keywords
        items_with_analysis = [
            (0, 'path1', 'content1', {'focus_keywords': ['auth', 'implement'], 'priority_keywords': ['urgent']}),
            (1, 'path2', 'content2', {'focus_keywords': ['auth', 'test'], 'priority_keywords': []}),
            (2, 'path3', 'content3', {'focus_keywords': ['auth', 'deploy'], 'priority_keywords': ['priority']}),
            (3, 'path4', 'content4', {'focus_keywords': ['docs', 'update'], 'priority_keywords': []})
        ]
        
        score = self.scorer._calculate_context_coherence(items_with_analysis)
        assert 50 <= score <= 100
    
    def test_calculate_overall_focus_score(self):
        """Test overall focus score calculation."""
        metrics = {
            'work_related_ratio': 0.8,  # 80% work related
            'priority_alignment_score': 75,
            'attention_clarity_score': 80,
            'context_coherence_score': 70
        }
        
        score = self.scorer._calculate_overall_focus_score(metrics)
        assert 0 <= score <= 100
        assert isinstance(score, int)
        # Should be relatively high given good component scores
        assert score >= 70
    
    @pytest.mark.asyncio
    async def test_calculate_focus_metrics_empty_context(self):
        """Test focus metrics calculation with empty context."""
        empty_context = {}
        
        metrics = await self.scorer.calculate_focus_metrics(empty_context)
        
        # Should return default metrics for empty context
        assert isinstance(metrics, FocusMetrics)
        assert metrics.focus_score == 50  # Neutral score
        assert metrics.total_content_items == 0
        assert metrics.current_work_ratio == 0.0
    
    @pytest.mark.asyncio
    async def test_calculate_focus_metrics_position_analysis(self):
        """Test position analysis in focus metrics."""
        # Create context where we can control position
        ordered_context = {
            'item1': 'URGENT: Fix critical bug now',  # High priority, should be at top
            'item2': 'Currently working on feature X',  # Current work
            'item3': 'Random note about something',     # Noise
            'item4': 'Completed task from last week'   # Distraction
        }
        
        metrics = await self.scorer.calculate_focus_metrics(ordered_context)
        
        # Should analyze position correctly
        assert metrics.important_items_in_top_quarter >= 0
        assert metrics.current_work_in_top_half >= 0
        assert metrics.noise_in_bottom_half >= 0
    
    def test_keyword_regex_patterns(self):
        """Test that keyword regex patterns work correctly."""
        # Test current work keywords
        current_work_text = "Currently implementing new authentication system"
        assert self.scorer.current_work_regex.search(current_work_text) is not None
        
        # Test distraction keywords
        distraction_text = "Completed old legacy system migration"
        assert self.scorer.distraction_regex.search(distraction_text) is not None
        
        # Test high priority keywords
        priority_text = "URGENT: Critical bug needs immediate attention"
        assert self.scorer.high_priority_regex.search(priority_text) is not None
    
    def test_task_action_patterns(self):
        """Test task action pattern recognition."""
        actionable_texts = [
            "TODO: Implement user authentication",
            "Need to fix the login bug",
            "Must deploy the hotfix today",
            "[ ] Write unit tests",
            "Going to refactor the auth module"
        ]
        
        for text in actionable_texts:
            found_pattern = False
            for pattern in self.scorer.task_action_patterns:
                if pattern.search(text):
                    found_pattern = True
                    break
            assert found_pattern, f"No action pattern found in: {text}"
    
    @pytest.mark.asyncio
    async def test_focus_metrics_completeness(self):
        """Test that focus metrics contain all expected fields."""
        metrics = await self.scorer.calculate_focus_metrics(self.mixed_context)
        
        # Check all required fields are present
        assert hasattr(metrics, 'focus_score')
        assert hasattr(metrics, 'priority_alignment_score')
        assert hasattr(metrics, 'current_work_ratio')
        assert hasattr(metrics, 'attention_clarity_score')
        assert hasattr(metrics, 'total_content_items')
        assert hasattr(metrics, 'work_related_items')
        assert hasattr(metrics, 'high_priority_items')
        assert hasattr(metrics, 'active_task_items')
        assert hasattr(metrics, 'noise_items')
        assert hasattr(metrics, 'context_coherence_score')
        assert hasattr(metrics, 'task_clarity_score')
        assert hasattr(metrics, 'goal_alignment_score')
        assert hasattr(metrics, 'focus_keywords_found')
        assert hasattr(metrics, 'distraction_keywords_found')
        assert hasattr(metrics, 'analysis_method_breakdown')
        assert hasattr(metrics, 'focus_analysis_duration')
    
    @pytest.mark.asyncio
    async def test_focus_metrics_score_ranges(self):
        """Test that all scores are within expected ranges."""
        metrics = await self.scorer.calculate_focus_metrics(self.mixed_context)
        
        # All percentage scores should be 0-100
        assert 0 <= metrics.focus_score <= 100
        assert 0 <= metrics.priority_alignment_score <= 100
        assert 0 <= metrics.attention_clarity_score <= 100
        assert 0 <= metrics.context_coherence_score <= 100
        assert 0 <= metrics.task_clarity_score <= 100
        assert 0 <= metrics.goal_alignment_score <= 100
        
        # Ratio should be 0-1
        assert 0.0 <= metrics.current_work_ratio <= 1.0
        
        # Counts should be non-negative
        assert metrics.total_content_items >= 0
        assert metrics.work_related_items >= 0
        assert metrics.high_priority_items >= 0
        assert metrics.active_task_items >= 0
        assert metrics.noise_items >= 0
    
    @pytest.mark.asyncio
    async def test_focus_scorer_performance(self):
        """Test focus scorer performance with large dataset."""
        # Create large context
        large_context = {}
        for i in range(200):
            large_context[f'item_{i}'] = f"This is test content item {i} with various keywords like current work and priority"
        
        start_time = datetime.now()
        metrics = await self.scorer.calculate_focus_metrics(large_context)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        assert duration < 2.0  # Should complete quickly
        assert metrics.total_content_items == 200
    
    @pytest.mark.asyncio
    async def test_get_empty_focus_metrics(self):
        """Test empty focus metrics fallback."""
        start_time = datetime.now()
        metrics = self.scorer._get_empty_focus_metrics(start_time)
        
        assert isinstance(metrics, FocusMetrics)
        assert metrics.focus_score == 50
        assert metrics.total_content_items == 0
        assert metrics.focus_analysis_duration > 0


class TestFocusMetrics:
    """Test suite for FocusMetrics dataclass."""
    
    def test_focus_metrics_creation(self):
        """Test creating FocusMetrics with all fields."""
        metrics = FocusMetrics(
            focus_score=85,
            priority_alignment_score=75,
            current_work_ratio=0.6,
            attention_clarity_score=80,
            total_content_items=20,
            work_related_items=12,
            high_priority_items=5,
            active_task_items=8,
            noise_items=2,
            context_coherence_score=70,
            task_clarity_score=78,
            goal_alignment_score=82,
            important_items_in_top_quarter=3,
            current_work_in_top_half=6,
            noise_in_bottom_half=2,
            focus_keywords_found=['current', 'urgent', 'priority'],
            distraction_keywords_found=['old', 'completed'],
            analysis_method_breakdown={'keyword_based': 10, 'priority_based': 5},
            focus_analysis_duration=1.5
        )
        
        assert metrics.focus_score == 85
        assert metrics.current_work_ratio == 0.6
        assert len(metrics.focus_keywords_found) == 3
        assert metrics.focus_analysis_duration == 1.5
    
    def test_get_focus_summary(self):
        """Test focus summary generation."""
        metrics = FocusMetrics(
            focus_score=88,
            priority_alignment_score=76,
            current_work_ratio=0.65,
            attention_clarity_score=82,
            total_content_items=20, work_related_items=13, high_priority_items=5,
            active_task_items=8, noise_items=1, context_coherence_score=70,
            task_clarity_score=78, goal_alignment_score=82,
            important_items_in_top_quarter=3, current_work_in_top_half=6,
            noise_in_bottom_half=1, focus_keywords_found=[], distraction_keywords_found=[],
            analysis_method_breakdown={}, focus_analysis_duration=1.0
        )
        
        summary = metrics.get_focus_summary()
        
        assert "88%" in summary  # Focus score
        assert "76%" in summary  # Priority alignment
        assert "65%" in summary  # Current work ratio  
        assert "82%" in summary  # Clarity score


if __name__ == "__main__":
    # Run tests if script is executed directly  
    pytest.main([__file__, "-v"])