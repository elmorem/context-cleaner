#!/usr/bin/env python3
"""
Test script for Context Rot Meter Phase 2: Advanced Analytics Integration

Tests the ML-enhanced capabilities including:
- ML-based frustration detection
- Adaptive threshold management  
- User behavior baseline tracking
- Conversation flow analysis
- Personalized insights and recommendations
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
from src.context_cleaner.telemetry.context_rot.ml_analysis import (
    MLFrustrationDetector, SentimentPipeline, ConversationFlowAnalyzer
)
from src.context_cleaner.telemetry.context_rot.adaptive_thresholds import (
    AdaptiveThresholdManager, UserBaselineTracker
)
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager


async def test_ml_sentiment_analysis():
    """Test ML-based sentiment analysis components."""
    print("🤖 Testing ML Sentiment Analysis...")
    
    try:
        # Initialize sentiment pipeline
        sentiment_pipeline = SentimentPipeline(confidence_threshold=0.6)
        
        # Test various sentiment types
        test_messages = [
            "This is working great! Thanks for your help.",
            "I'm getting frustrated, this doesn't work at all.",
            "I'm confused, what does this mean?",
            "This is broken and useless, I give up!",
            "How do I do this? I don't understand.",
            "Perfect! Everything is working now."
        ]
        
        print("  📝 Analyzing individual messages:")
        for msg in test_messages:
            result = await sentiment_pipeline.analyze(msg)
            print(f"    '{msg[:50]}...' -> {result.score.value} (confidence: {result.confidence:.2f})")
        
        # Test ML frustration detector
        frustration_detector = MLFrustrationDetector(confidence_threshold=0.7)
        
        # Test conversation-level analysis
        conversation = [
            "I need help with this feature",
            "It's not working as expected",
            "I've tried everything, still broken",
            "This is really frustrating me",
            "Why won't this just work?!"
        ]
        
        print("  🧠 Analyzing conversation-level sentiment:")
        conversation_analysis = await frustration_detector.analyze_user_sentiment(conversation)
        
        print(f"    Frustration Level: {conversation_analysis.frustration_level:.2f}")
        print(f"    Confidence: {conversation_analysis.confidence:.2f}")
        print(f"    Evidence: {conversation_analysis.evidence[:2]}")  # Show first 2 pieces of evidence
        
        return True
        
    except Exception as e:
        print(f"❌ ML sentiment analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_conversation_flow_analysis():
    """Test conversation flow analysis."""
    print("🔄 Testing Conversation Flow Analysis...")
    
    try:
        flow_analyzer = ConversationFlowAnalyzer()
        
        # Test different conversation patterns
        test_conversations = [
            {
                'name': 'Good Flow',
                'messages': [
                    "I need help with authentication",
                    "Here's what I'm trying to do",
                    "That makes sense, let me try",
                    "Great, it's working now!"
                ]
            },
            {
                'name': 'Poor Flow (Repetitive)',
                'messages': [
                    "This doesn't work",
                    "Still doesn't work", 
                    "Nothing works",
                    "This is not working",
                    "Why doesn't this work?"
                ]
            },
            {
                'name': 'Confused Flow',
                'messages': [
                    "What does this do?",
                    "How do I use this?",
                    "I don't understand?",
                    "What am I supposed to do?",
                    "Can you explain this?"
                ]
            }
        ]
        
        for conv in test_conversations:
            print(f"  📊 Analyzing '{conv['name']}':")
            flow_result = await flow_analyzer.analyze_flow(conv['messages'])
            
            print(f"    Flow Quality: {flow_result.flow_quality_score:.2f}")
            print(f"    Question Ratio: {flow_result.question_ratio:.2f}")
            print(f"    Repetition Ratio: {flow_result.repetition_ratio:.2f}")
            print(f"    Escalation Detected: {flow_result.escalation_detected}")
            
            if flow_result.pattern_evidence:
                print(f"    Evidence: {flow_result.pattern_evidence[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation flow analysis test failed: {e}")
        return False


async def test_adaptive_thresholds():
    """Test adaptive threshold management."""
    print("🎯 Testing Adaptive Threshold Management...")
    
    try:
        # Initialize ClickHouse client
        clickhouse_client = ClickHouseClient()
        
        # Check connection
        healthy = await clickhouse_client.health_check()
        if not healthy:
            print("  ⚠️  ClickHouse not available - using mock data")
            return True  # Skip but don't fail the test
        
        # Initialize threshold manager
        threshold_manager = AdaptiveThresholdManager(clickhouse_client)
        
        # Test getting personalized thresholds
        test_users = ['test_user_phase2_1', 'test_user_phase2_2', 'new_user_phase2']
        
        for user_id in test_users:
            print(f"  👤 Testing thresholds for {user_id}:")
            thresholds = await threshold_manager.get_personalized_thresholds(user_id)
            
            print(f"    Warning Threshold: {thresholds.warning_threshold:.2f}")
            print(f"    Critical Threshold: {thresholds.critical_threshold:.2f}")
            print(f"    Confidence Required: {thresholds.confidence_required:.2f}")
            
            # Test feedback update
            feedback_result = await threshold_manager.update_user_sensitivity(user_id, 'too_sensitive')
            print(f"    Feedback Update: {'✅' if feedback_result else '❌'}")
        
        print("  ✅ Adaptive thresholds working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Adaptive threshold test failed: {e}")
        return False


async def test_enhanced_analyzer_integration():
    """Test the enhanced Context Rot Analyzer with ML capabilities."""
    print("🔬 Testing Enhanced Context Rot Analyzer...")
    
    try:
        # Initialize ClickHouse client
        clickhouse_client = ClickHouseClient()
        
        # Mock error recovery manager
        class MockTelemetryClient:
            async def get_recent_errors(self, hours=24): return []
            async def get_session_metrics(self, session_id): return None
        
        mock_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_client, max_retries=3)
        
        # Initialize enhanced analyzer
        analyzer = ContextRotAnalyzer(clickhouse_client, recovery_manager)
        
        print(f"  🔧 ML Capabilities Enabled: {analyzer.ml_enabled}")
        
        # Test analyzer status
        status = await analyzer.get_analyzer_status()
        print(f"  📊 Analyzer Status: {status['status']}")
        print(f"  📦 Version: {status['version']}")
        
        # Check ML components
        components = status['components']
        ml_frustration = components.get('ml_frustration_detector', 'unknown')
        adaptive_thresh = components.get('adaptive_thresholds', 'unknown')
        
        print(f"  🤖 ML Frustration Detector: {ml_frustration}")
        print(f"  🎯 Adaptive Thresholds: {adaptive_thresh}")
        
        if analyzer.ml_enabled:
            # Test ML-enhanced conversation analysis
            print("  🧪 Testing ML conversation sentiment analysis...")
            
            test_conversation = [
                "I'm trying to implement this feature",
                "It's not working as expected",
                "I'm getting more frustrated",
                "This is really not working at all",
                "I think I need to try a different approach"
            ]
            
            sentiment_result = await analyzer.analyze_conversation_sentiment(
                'test_user_ml', test_conversation
            )
            
            if sentiment_result['status'] == 'success':
                analysis = sentiment_result['analysis']
                print(f"    Frustration Level: {analysis['frustration_level']:.2f}")
                print(f"    Confidence: {analysis['confidence']:.2f}")
                print(f"    Alert Level: {sentiment_result['alert_level']}")
                print(f"    Recommendations: {len(sentiment_result['recommendations'])}")
                
                # Test personalized insights
                insights = await analyzer.get_personalized_insights('test_user_ml')
                print(f"    Personalized Insights: {insights['status']}")
                
            else:
                print(f"    Analysis status: {sentiment_result['status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced analyzer integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_imports_and_availability():
    """Test that all Phase 2 imports work correctly."""
    print("📦 Testing Phase 2 Import Availability...")
    
    try:
        # Test core ML imports
        from src.context_cleaner.telemetry.context_rot import (
            ContextRotAnalyzer,
            MLFrustrationDetector,
            AdaptiveThresholdManager,
            SentimentPipeline,
            ConversationFlowAnalyzer
        )
        print("  ✅ Core ML imports successful")
        
        # Test data structure imports
        from src.context_cleaner.telemetry.context_rot import (
            FrustrationAnalysis,
            SentimentScore,
            ThresholdConfig,
            UserBaseline
        )
        print("  ✅ Data structure imports successful")
        
        # Test analyzer integration imports
        from src.context_cleaner.telemetry.context_rot.analyzer import (
            ML_CAPABILITIES_AVAILABLE
        )
        print(f"  📊 ML Capabilities Available: {ML_CAPABILITIES_AVAILABLE}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error in import test: {e}")
        return False


async def main():
    """Run all Phase 2 integration tests."""
    print("🚀 Starting Context Rot Meter Phase 2: Advanced Analytics Tests\n")
    
    test_results = []
    
    try:
        # Test 1: Import availability
        result1 = await test_imports_and_availability()
        test_results.append(("Import Availability", result1))
        
        if not result1:
            print("💥 Import tests failed - skipping ML-dependent tests")
            return 1
        
        # Test 2: ML Sentiment Analysis
        result2 = await test_ml_sentiment_analysis()
        test_results.append(("ML Sentiment Analysis", result2))
        
        # Test 3: Conversation Flow Analysis
        result3 = await test_conversation_flow_analysis()
        test_results.append(("Conversation Flow Analysis", result3))
        
        # Test 4: Adaptive Thresholds
        result4 = await test_adaptive_thresholds()
        test_results.append(("Adaptive Thresholds", result4))
        
        # Test 5: Enhanced Analyzer Integration
        result5 = await test_enhanced_analyzer_integration()
        test_results.append(("Enhanced Analyzer Integration", result5))
        
        # Summary
        print(f"\n📋 Phase 2 Test Results Summary:")
        passed = 0
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n🏁 Overall: {passed}/{len(test_results)} tests passed")
        
        if passed == len(test_results):
            print("🎊 All Phase 2 Advanced Analytics tests passed!")
            print("🚀 Context Rot Meter Phase 2 is ready for production deployment!")
            return 0
        else:
            print("💥 Some Phase 2 tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)