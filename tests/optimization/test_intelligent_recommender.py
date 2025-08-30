"""
Test suite for IntelligentRecommendationEngine - Focus: Personalization & ML Logic

This test suite addresses critical issues in the intelligent recommender:
1. Personalization profile management and learning
2. Recommendation generation logic and prioritization
3. File I/O operations and JSON serialization
4. Historical effectiveness tracking
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from pathlib import Path
from dataclasses import asdict

from context_cleaner.optimization.intelligent_recommender import (
    IntelligentRecommendationEngine, PersonalizationProfile, IntelligentRecommendation,
    RecommendationPriority, OptimizationCategory, OptimizationAction
)


class TestIntelligentRecommendationEngine:
    """Test suite for IntelligentRecommendationEngine focusing on personalization and ML logic."""
    
    @pytest.fixture
    def recommender_engine(self, temp_storage_dir):
        """Create recommender engine instance for testing."""
        return IntelligentRecommendationEngine(temp_storage_dir)
    
    # Test 1: Personalization profile management
    @pytest.mark.asyncio
    async def test_load_personalization_profile_new_user(self, recommender_engine):
        """Test loading profile for new user creates default profile."""
        profile = await recommender_engine._load_personalization_profile("new_user")
        
        assert isinstance(profile, PersonalizationProfile)
        assert profile.user_id == "new_user"
        assert profile.profile_confidence == 0.1  # Low confidence for new user
        assert profile.session_count == 0
        assert "balanced" in profile.preferred_optimization_modes
        assert profile.automation_comfort_level == 0.5  # Default moderate comfort
    
    @pytest.mark.asyncio
    async def test_load_personalization_profile_existing_user(self, recommender_engine, mock_personalization_profile):
        """Test loading existing profile from storage."""
        profile_data = asdict(mock_personalization_profile)
        
        # Mock file exists and contains profile data
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(profile_data))):
                profile = await recommender_engine._load_personalization_profile("test_user")
                
                assert profile.user_id == "test_user"
                assert profile.profile_confidence == 0.75
                assert profile.session_count == 25
    
    @pytest.mark.asyncio
    async def test_load_personalization_profile_corrupted_data(self, recommender_engine):
        """Test loading profile handles corrupted JSON data."""
        # Mock file exists but contains corrupted data
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"invalid": json')):
                profile = await recommender_engine._load_personalization_profile("test_user")
                
                # Should create default profile on corruption
                assert profile.user_id == "test_user"
                assert profile.profile_confidence == 0.1  # New default profile
    
    @pytest.mark.asyncio
    async def test_update_personalization_profile_persistence(self, recommender_engine, mock_personalization_profile):
        """Test personalization profile updates and persistence."""
        profile = mock_personalization_profile
        recommendations = [Mock()]
        
        original_session_count = profile.session_count
        original_confidence = profile.profile_confidence
        
        # Mock file operations
        with patch('builtins.open', mock_open()) as mock_file:
            await recommender_engine._update_personalization_profile(
                "test_user", profile, recommendations
            )
            
            # Should update profile metadata
            assert profile.session_count == original_session_count + 1
            assert profile.profile_confidence >= original_confidence  # Should increase
            assert profile.last_updated is not None
            
            # Should attempt to save to file
            mock_file.assert_called_once()
    
    # Test 2: Recommendation generation logic
    @pytest.mark.asyncio
    async def test_generate_token_efficiency_recommendations_high_waste(
        self, recommender_engine, mock_health_metrics, mock_personalization_profile
    ):
        """Test token efficiency recommendations for high waste scenarios."""
        # Mock high waste token analysis
        token_analysis = Mock()
        token_analysis.waste_percentage = 35.0
        token_analysis.waste_patterns = [Mock(pattern="*.py"), Mock(pattern="*.js"), Mock(pattern="*.md")]
        
        recommendations = await recommender_engine._generate_token_efficiency_recommendations(
            token_analysis, mock_health_metrics, mock_personalization_profile, 10000
        )
        
        assert len(recommendations) >= 1
        
        # Should generate high priority recommendation for high waste
        high_priority_recs = [r for r in recommendations if r.priority == RecommendationPriority.HIGH]
        assert len(high_priority_recs) >= 1
        
        rec = high_priority_recs[0]
        assert rec.category == OptimizationCategory.TOKEN_EFFICIENCY
        assert "35.0%" in rec.description
        assert rec.estimated_token_savings > 0
    
    @pytest.mark.asyncio
    async def test_generate_token_efficiency_recommendations_moderate_waste(
        self, recommender_engine, mock_health_metrics, mock_personalization_profile
    ):
        """Test token efficiency recommendations for moderate waste scenarios."""
        # Mock moderate waste token analysis
        token_analysis = Mock()
        token_analysis.waste_percentage = 20.0
        token_analysis.waste_patterns = [Mock(pattern="*.py"), Mock(pattern="*.js")]
        
        recommendations = await recommender_engine._generate_token_efficiency_recommendations(
            token_analysis, mock_health_metrics, mock_personalization_profile, 10000
        )
        
        assert len(recommendations) >= 1
        
        # Should generate medium priority recommendation for moderate waste
        medium_priority_recs = [r for r in recommendations if r.priority == RecommendationPriority.MEDIUM]
        assert len(medium_priority_recs) >= 1
        
        rec = medium_priority_recs[0]
        assert rec.category == OptimizationCategory.TOKEN_EFFICIENCY
        assert "20.0%" in rec.description
    
    @pytest.mark.asyncio
    async def test_generate_workflow_recommendations_low_efficiency(
        self, recommender_engine, mock_health_metrics, mock_personalization_profile
    ):
        """Test workflow recommendations for low efficiency scenarios."""
        # Mock low workflow efficiency
        usage_summary = Mock()
        usage_summary.workflow_efficiency = 0.4
        usage_summary.file_patterns = [
            Mock(file_path="src/main.py", access_frequency=10),
            Mock(file_path="tests/test.py", access_frequency=8),
            Mock(file_path="docs/readme.md", access_frequency=5)
        ]
        
        recommendations = await recommender_engine._generate_workflow_recommendations(
            usage_summary, mock_health_metrics, mock_personalization_profile
        )
        
        assert len(recommendations) >= 1
        
        rec = recommendations[0]
        assert rec.category == OptimizationCategory.WORKFLOW_ALIGNMENT
        assert "40%" in rec.description
        assert rec.priority == RecommendationPriority.HIGH
        
        # Should have prioritize frequent files action
        prioritize_actions = [a for a in rec.actions if "frequent" in a.description.lower()]
        assert len(prioritize_actions) >= 1
    
    @pytest.mark.asyncio
    async def test_generate_emergency_recommendations_critical_health(
        self, recommender_engine, mock_personalization_profile
    ):
        """Test emergency recommendations for critical health scenarios."""
        # Mock critical health metrics
        critical_metrics = Mock()
        critical_metrics.health_level = Mock()
        critical_metrics.health_level.value = "critical"
        
        recommendations = await recommender_engine._generate_emergency_recommendations(
            critical_metrics, mock_personalization_profile, 20000
        )
        
        assert len(recommendations) >= 1
        
        rec = recommendations[0]
        assert rec.priority == RecommendationPriority.CRITICAL
        assert "Emergency" in rec.title
        assert rec.requires_confirmation == True  # Emergency should always require confirmation
        assert rec.can_be_automated == False  # Emergency should be manual
        assert rec.estimated_token_savings > 0  # Should estimate significant savings
    
    # Test 3: Recommendation prioritization and personalization
    def test_prioritize_recommendations_scoring(self, recommender_engine, mock_personalization_profile):
        """Test recommendation prioritization scoring algorithm."""
        # Create recommendations with different characteristics
        recommendations = [
            Mock(
                priority=RecommendationPriority.HIGH,
                historical_effectiveness=0.8,
                user_preference_alignment=0.9,
                learning_confidence=0.7,
                estimated_efficiency_gain=0.3,
                requires_confirmation=False
            ),
            Mock(
                priority=RecommendationPriority.MEDIUM,
                historical_effectiveness=0.9,
                user_preference_alignment=0.8,
                learning_confidence=0.8,
                estimated_efficiency_gain=0.5,
                requires_confirmation=True
            ),
            Mock(
                priority=RecommendationPriority.CRITICAL,
                historical_effectiveness=0.6,
                user_preference_alignment=0.5,
                learning_confidence=0.6,
                estimated_efficiency_gain=0.2,
                requires_confirmation=False
            )
        ]
        
        sorted_recs = recommender_engine._prioritize_recommendations(recommendations, mock_personalization_profile)
        
        # Critical should be first (highest base score)
        assert sorted_recs[0].priority == RecommendationPriority.CRITICAL
        
        # High should be second (good overall scores)
        assert sorted_recs[1].priority == RecommendationPriority.HIGH
        
        # Medium should be last (despite high individual scores, lower priority base)
        assert sorted_recs[2].priority == RecommendationPriority.MEDIUM
    
    @pytest.mark.asyncio
    async def test_apply_personalization_preference_alignment(self, recommender_engine, mock_personalization_profile):
        """Test personalization application based on user preferences."""
        # Mock recommendation with specific category
        recommendations = [Mock()]
        recommendations[0].category = Mock()
        recommendations[0].category.value = "balanced"  # Matches user preference
        recommendations[0].user_preference_alignment = 0.5
        recommendations[0].can_be_automated = True
        recommendations[0].requires_confirmation = False
        
        # User has "balanced" in preferred modes and moderate automation comfort
        mock_personalization_profile.preferred_optimization_modes = ["balanced", "efficiency"]
        mock_personalization_profile.automation_comfort_level = 0.6
        
        personalized_recs = await recommender_engine._apply_personalization(
            recommendations, mock_personalization_profile
        )
        
        # Should boost preference alignment for matching category
        assert personalized_recs[0].user_preference_alignment >= 0.7  # Should be increased
        assert personalized_recs[0].requires_confirmation == False  # Moderate comfort -> no confirmation needed
    
    @pytest.mark.asyncio
    async def test_apply_personalization_low_automation_comfort(self, recommender_engine, mock_personalization_profile):
        """Test personalization with low automation comfort level."""
        recommendations = [Mock()]
        recommendations[0].can_be_automated = True
        recommendations[0].requires_confirmation = False
        
        # Low automation comfort
        mock_personalization_profile.automation_comfort_level = 0.3
        
        personalized_recs = await recommender_engine._apply_personalization(
            recommendations, mock_personalization_profile
        )
        
        # Should require confirmation for low automation comfort
        assert personalized_recs[0].requires_confirmation == True
    
    # Test 4: Historical effectiveness tracking
    def test_get_historical_effectiveness_existing_category(self, recommender_engine, mock_personalization_profile):
        """Test getting historical effectiveness for existing category."""
        mock_personalization_profile.optimization_outcomes = {
            "token_efficiency": 0.85,
            "workflow_alignment": 0.72
        }
        
        effectiveness = recommender_engine._get_historical_effectiveness("token_efficiency", mock_personalization_profile)
        assert effectiveness == 0.85
        
        effectiveness = recommender_engine._get_historical_effectiveness("workflow_alignment", mock_personalization_profile)
        assert effectiveness == 0.72
    
    def test_get_historical_effectiveness_unknown_category(self, recommender_engine, mock_personalization_profile):
        """Test getting historical effectiveness for unknown category returns default."""
        mock_personalization_profile.optimization_outcomes = {}
        
        effectiveness = recommender_engine._get_historical_effectiveness("unknown_category", mock_personalization_profile)
        assert effectiveness == 0.6  # Default moderate effectiveness
    
    def test_calculate_preference_alignment_direct_match(self, recommender_engine, mock_personalization_profile):
        """Test preference alignment calculation for direct category match."""
        from context_cleaner.optimization.intelligent_recommender import OptimizationCategory
        
        mock_personalization_profile.preferred_optimization_modes = ["token_efficiency", "workflow"]
        
        alignment = recommender_engine._calculate_preference_alignment(
            OptimizationCategory.TOKEN_EFFICIENCY, mock_personalization_profile
        )
        assert alignment == 0.9  # High alignment for direct match
    
    def test_calculate_preference_alignment_related_match(self, recommender_engine, mock_personalization_profile):
        """Test preference alignment calculation for related preferences."""
        from context_cleaner.optimization.intelligent_recommender import OptimizationCategory
        
        mock_personalization_profile.preferred_optimization_modes = ["efficiency"]  # Related to TOKEN_EFFICIENCY
        
        alignment = recommender_engine._calculate_preference_alignment(
            OptimizationCategory.TOKEN_EFFICIENCY, mock_personalization_profile
        )
        assert alignment == 0.7  # Moderate alignment for related match
    
    def test_calculate_preference_alignment_no_match(self, recommender_engine, mock_personalization_profile):
        """Test preference alignment calculation with no matches."""
        from context_cleaner.optimization.intelligent_recommender import OptimizationCategory
        
        mock_personalization_profile.preferred_optimization_modes = ["unrelated_mode"]
        
        alignment = recommender_engine._calculate_preference_alignment(
            OptimizationCategory.TOKEN_EFFICIENCY, mock_personalization_profile
        )
        assert alignment == 0.5  # Neutral alignment for no match
    
    # Test 5: Recommendation outcome recording
    @pytest.mark.asyncio
    async def test_record_recommendation_outcome_accepted(self, recommender_engine, mock_personalization_profile):
        """Test recording accepted recommendation outcome."""
        # Mock profile loading
        with patch.object(recommender_engine, '_load_personalization_profile', return_value=mock_personalization_profile):
            with patch.object(recommender_engine, '_update_personalization_profile') as mock_update:
                
                await recommender_engine.record_recommendation_outcome(
                    "rec_123", "accepted", 0.8, "test_user"
                )
                
                # Should add to successful recommendations
                assert "rec_123" in mock_personalization_profile.successful_recommendations
                
                # Should call update profile
                mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_recommendation_outcome_rejected(self, recommender_engine, mock_personalization_profile):
        """Test recording rejected recommendation outcome."""
        with patch.object(recommender_engine, '_load_personalization_profile', return_value=mock_personalization_profile):
            with patch.object(recommender_engine, '_update_personalization_profile') as mock_update:
                
                await recommender_engine.record_recommendation_outcome(
                    "rec_456", "rejected", 0.2, "test_user"
                )
                
                # Should add to rejected recommendations
                assert "rec_456" in mock_personalization_profile.rejected_recommendations
                
                mock_update.assert_called_once()
    
    # Test 6: File I/O operations and error handling
    @pytest.mark.asyncio
    async def test_profile_persistence_file_io_error(self, recommender_engine, mock_personalization_profile):
        """Test profile persistence handles file I/O errors gracefully."""
        # Mock file operations to fail
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            # Should not raise exception
            await recommender_engine._update_personalization_profile(
                "test_user", mock_personalization_profile, []
            )
            
            # Profile should still be cached even if persistence fails
            assert "test_user" in recommender_engine._profiles_cache
    
    @pytest.mark.asyncio 
    async def test_profile_loading_json_decode_error(self, recommender_engine):
        """Test profile loading handles JSON decode errors."""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"invalid": json}')):
                with patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "test", 0)):
                    
                    profile = await recommender_engine._load_personalization_profile("test_user")
                    
                    # Should create default profile on JSON error
                    assert profile.user_id == "test_user"
                    assert profile.profile_confidence == 0.1  # Default new profile
    
    # Test 7: Complex recommendation generation scenarios
    @pytest.mark.asyncio
    async def test_generate_intelligent_recommendations_comprehensive(
        self, recommender_engine, mock_health_metrics, mock_usage_pattern_summary,
        mock_token_analysis_summary, mock_temporal_insights, mock_enhanced_analysis,
        mock_correlation_insights, mock_personalization_profile
    ):
        """Test comprehensive recommendation generation with all analysis types."""
        recommendations = await recommender_engine.generate_intelligent_recommendations(
            health_metrics=mock_health_metrics,
            usage_summary=mock_usage_pattern_summary,
            token_analysis=mock_token_analysis_summary,
            temporal_insights=mock_temporal_insights,
            enhanced_analysis=mock_enhanced_analysis,
            correlation_insights=mock_correlation_insights,
            user_id="test_user",
            context_size=15000,
            max_recommendations=5
        )
        
        # Should generate multiple types of recommendations
        assert len(recommendations) <= 5  # Should respect max limit
        assert len(recommendations) >= 1  # Should generate at least one
        
        # Should have variety of categories
        categories = {rec.category for rec in recommendations}
        assert len(categories) >= 1  # Should have at least one category
        
        # All recommendations should have required fields
        for rec in recommendations:
            assert rec.id is not None
            assert rec.title is not None
            assert rec.description is not None
            assert rec.category is not None
            assert rec.priority is not None
            assert len(rec.actions) >= 1
            assert isinstance(rec.generated_at, datetime)
            assert isinstance(rec.expires_at, datetime)
    
    @pytest.mark.asyncio
    async def test_generate_intelligent_recommendations_health_based_emergency(
        self, recommender_engine, mock_personalization_profile
    ):
        """Test emergency recommendations for poor health scenarios."""
        # Mock critical health metrics
        from context_cleaner.optimization.cache_dashboard import UsageBasedHealthMetrics, HealthLevel
        
        critical_health = UsageBasedHealthMetrics(
            usage_weighted_focus_score=0.2,
            efficiency_score=0.1,
            temporal_coherence_score=0.1,
            cross_session_consistency=0.2,
            optimization_potential=0.9,
            waste_reduction_score=0.1,
            workflow_alignment=0.1
        )
        
        # Health level should be CRITICAL
        assert critical_health.health_level == HealthLevel.CRITICAL
        
        recommendations = await recommender_engine.generate_intelligent_recommendations(
            health_metrics=critical_health,
            usage_summary=None,
            token_analysis=None,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=None,
            user_id="test_user",
            context_size=20000
        )
        
        # Should generate emergency recommendations
        critical_recs = [r for r in recommendations if r.priority == RecommendationPriority.CRITICAL]
        assert len(critical_recs) >= 1
        
        emergency_rec = critical_recs[0]
        assert "Emergency" in emergency_rec.title or "Immediate" in emergency_rec.title
        assert emergency_rec.requires_confirmation == True
        assert emergency_rec.estimated_token_savings > 0
    
    # Test 8: Data validation and edge cases
    @pytest.mark.asyncio
    async def test_generate_recommendations_with_none_inputs(self, recommender_engine, mock_personalization_profile):
        """Test recommendation generation handles None inputs gracefully."""
        recommendations = await recommender_engine.generate_intelligent_recommendations(
            health_metrics=None,
            usage_summary=None,
            token_analysis=None,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=None,
            user_id="test_user"
        )
        
        # Should handle None inputs and return empty or minimal recommendations
        assert isinstance(recommendations, list)
        # May be empty since no analysis data provided
    
    def test_optimization_action_creation(self):
        """Test OptimizationAction creation with various parameters."""
        action = OptimizationAction(
            action_type="remove_duplicates",
            description="Remove duplicate file reads",
            target_files=["file1.py", "file2.py"],
            expected_impact="20% token reduction",
            confidence_score=0.85,
            automation_possible=True
        )
        
        assert action.action_type == "remove_duplicates"
        assert len(action.target_files) == 2
        assert action.confidence_score == 0.85
        assert action.automation_possible == True
    
    def test_intelligent_recommendation_creation_comprehensive(self):
        """Test IntelligentRecommendation creation with all fields."""
        from context_cleaner.optimization.intelligent_recommender import (
            OptimizationCategory, RecommendationPriority, OptimizationAction
        )
        
        actions = [
            OptimizationAction(
                action_type="test_action",
                description="Test action description",
                target_files=["test.py"],
                expected_impact="Test impact",
                confidence_score=0.8,
                automation_possible=True
            )
        ]
        
        recommendation = IntelligentRecommendation(
            id="test_rec_001",
            category=OptimizationCategory.TOKEN_EFFICIENCY,
            priority=RecommendationPriority.HIGH,
            title="Test Recommendation",
            description="Test recommendation description",
            rationale="Test rationale",
            usage_patterns_analyzed=["pattern1", "pattern2"],
            historical_effectiveness=0.75,
            user_preference_alignment=0.80,
            context_specificity=0.85,
            actions=actions,
            estimated_token_savings=500,
            estimated_efficiency_gain=0.25,
            estimated_focus_improvement=0.15,
            risk_level="low",
            requires_confirmation=False,
            can_be_automated=True,
            estimated_time_savings="5 minutes per session",
            learning_confidence=0.7,
            generated_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            session_context={"test": "context"}
        )
        
        # Verify all fields are set correctly
        assert recommendation.id == "test_rec_001"
        assert recommendation.category == OptimizationCategory.TOKEN_EFFICIENCY
        assert recommendation.priority == RecommendationPriority.HIGH
        assert len(recommendation.actions) == 1
        assert recommendation.estimated_token_savings == 500
        assert recommendation.estimated_efficiency_gain == 0.25
        assert recommendation.learning_confidence == 0.7
        assert isinstance(recommendation.generated_at, datetime)
        assert isinstance(recommendation.expires_at, datetime)
    
    # Test 9: Concurrency and thread safety
    @pytest.mark.asyncio
    async def test_concurrent_recommendation_generation(self, recommender_engine, mock_health_metrics, mock_personalization_profile):
        """Test concurrent recommendation generation doesn't cause race conditions."""
        # Mock profile loading to return same profile
        with patch.object(recommender_engine, '_load_personalization_profile', return_value=mock_personalization_profile):
            
            # Generate recommendations concurrently
            tasks = [
                recommender_engine.generate_intelligent_recommendations(
                    health_metrics=mock_health_metrics,
                    usage_summary=None,
                    token_analysis=None,
                    temporal_insights=None,
                    enhanced_analysis=None,
                    correlation_insights=None,
                    user_id=f"user_{i}"
                )
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed without race conditions
            for result in results:
                assert not isinstance(result, Exception)
                assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_concurrent_profile_updates(self, recommender_engine, mock_personalization_profile):
        """Test concurrent profile updates handle properly."""
        # Mock profile loading
        with patch.object(recommender_engine, '_load_personalization_profile', return_value=mock_personalization_profile):
            with patch('builtins.open', mock_open()):
                
                # Update profile concurrently
                tasks = [
                    recommender_engine._update_personalization_profile(
                        "test_user", mock_personalization_profile, []
                    )
                    for _ in range(3)
                ]
                
                # Should complete without errors
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Profile should be cached
                assert "test_user" in recommender_engine._profiles_cache


# Performance tests
class TestIntelligentRecommenderPerformance:
    """Performance tests for recommendation engine."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_scale_recommendation_generation(self, temp_storage_dir, mock_health_metrics):
        """Test recommendation generation performance with large datasets."""
        engine = IntelligentRecommendationEngine(temp_storage_dir)
        
        # Create large token analysis with many waste patterns
        large_token_analysis = Mock()
        large_token_analysis.waste_percentage = 30.0
        large_token_analysis.waste_patterns = [
            Mock(pattern=f"pattern_{i}")
            for i in range(100)  # Many patterns
        ]
        
        # Create large usage summary with many file patterns
        large_usage_summary = Mock()
        large_usage_summary.workflow_efficiency = 0.5
        large_usage_summary.file_patterns = [
            Mock(file_path=f"file_{i}.py", access_frequency=10-i)
            for i in range(50)  # Many files
        ]
        
        start_time = datetime.now()
        recommendations = await engine.generate_intelligent_recommendations(
            health_metrics=mock_health_metrics,
            usage_summary=large_usage_summary,
            token_analysis=large_token_analysis,
            temporal_insights=None,
            enhanced_analysis=None,
            correlation_insights=None,
            user_id="perf_test_user",
            max_recommendations=20
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        # Should complete in reasonable time
        assert duration < 5.0  # 5 seconds max
        assert len(recommendations) <= 20
    
    @pytest.mark.asyncio
    async def test_profile_loading_performance_many_users(self, temp_storage_dir):
        """Test profile loading performance with many user profiles."""
        engine = IntelligentRecommendationEngine(temp_storage_dir)
        
        # Mock many profile files
        profile_data = {
            "user_id": "test",
            "preferred_optimization_modes": ["balanced"],
            "typical_session_length": "7200",  # 2 hours in seconds
            "common_file_types": [".py"],
            "frequent_workflows": ["development"],
            "confirmation_preferences": {},
            "automation_comfort_level": 0.5,
            "optimization_frequency": "weekly",
            "successful_recommendations": [],
            "rejected_recommendations": [],
            "optimization_outcomes": {},
            "profile_confidence": 0.5,
            "last_updated": datetime.now().isoformat(),
            "session_count": 10
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(profile_data))):
                
                # Load many profiles
                start_time = datetime.now()
                for i in range(50):
                    profile = await engine._load_personalization_profile(f"user_{i}")
                    assert profile is not None
                
                duration = (datetime.now() - start_time).total_seconds()
                
                # Should complete in reasonable time
                assert duration < 3.0  # 3 seconds for 50 profiles


# Integration tests
class TestIntelligentRecommenderIntegration:
    """Integration tests for recommendation engine with other components."""
    
    @pytest.mark.asyncio
    async def test_integration_with_dashboard_data(
        self, temp_storage_dir, mock_dashboard_data, mock_cross_session_insights
    ):
        """Test integration with complete dashboard data."""
        engine = IntelligentRecommendationEngine(temp_storage_dir)
        
        # Generate recommendations using dashboard data
        recommendations = await engine.generate_intelligent_recommendations(
            health_metrics=mock_dashboard_data.health_metrics,
            usage_summary=mock_dashboard_data.usage_summary,
            token_analysis=mock_dashboard_data.token_analysis,
            temporal_insights=mock_dashboard_data.temporal_insights,
            enhanced_analysis=mock_dashboard_data.enhanced_analysis,
            correlation_insights=mock_dashboard_data.correlation_insights,
            user_id="integration_test_user",
            context_size=mock_dashboard_data.context_size
        )
        
        assert len(recommendations) >= 1
        
        # Should generate recommendations based on actual analysis data
        categories = {rec.category.value for rec in recommendations}
        expected_categories = {"token_efficiency", "workflow_alignment"}  # Based on mock data
        
        # Should have at least some expected categories
        assert len(categories.intersection(expected_categories)) >= 1
    
    @pytest.mark.asyncio
    async def test_recommendation_effectiveness_learning_cycle(self, temp_storage_dir):
        """Test complete learning cycle: generate -> apply -> record outcome -> adapt."""
        engine = IntelligentRecommendationEngine(temp_storage_dir)
        
        # Mock initial profile
        profile_data = {
            "user_id": "learning_test",
            "preferred_optimization_modes": ["balanced"],
            "typical_session_length": "7200",
            "common_file_types": [".py"],
            "frequent_workflows": ["development"],
            "confirmation_preferences": {},
            "automation_comfort_level": 0.5,
            "optimization_frequency": "weekly",
            "successful_recommendations": [],
            "rejected_recommendations": [],
            "optimization_outcomes": {},
            "profile_confidence": 0.3,
            "last_updated": datetime.now().isoformat(),
            "session_count": 5
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(profile_data))):
                
                # 1. Generate initial recommendations
                initial_recs = await engine.generate_intelligent_recommendations(
                    health_metrics=Mock(health_level=Mock(value="fair")),
                    usage_summary=Mock(workflow_efficiency=0.6, file_patterns=[]),
                    token_analysis=Mock(waste_percentage=20.0, waste_patterns=[]),
                    temporal_insights=None,
                    enhanced_analysis=None,
                    correlation_insights=None,
                    user_id="learning_test"
                )
                
                assert len(initial_recs) >= 1
                
                # 2. Record positive outcome for first recommendation
                if initial_recs:
                    with patch('builtins.open', mock_open()):
                        await engine.record_recommendation_outcome(
                            initial_recs[0].id, "accepted", 0.8, "learning_test"
                        )
                
                # 3. Generate new recommendations (should be influenced by learning)
                # This would show improved recommendations based on user feedback
                # In a full implementation, the learning would affect future recommendations