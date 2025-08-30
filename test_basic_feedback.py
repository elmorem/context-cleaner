#!/usr/bin/env python3
"""
Basic User Feedback System Test

Quick test to verify the user feedback collection system works.
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from context_cleaner.feedback.user_feedback_collector import UserFeedbackCollector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Basic feedback test."""
    logger.info("🚀 Starting Basic User Feedback Test")
    
    try:
        # Test 1: Initialize collector
        logger.info("1. Initializing feedback collector...")
        collector = UserFeedbackCollector()
        
        # Test 2: Record some feedback
        logger.info("2. Recording test feedback...")
        collector.record_feature_usage(
            'test_feature',
            success=True,
            test_metric=42
        )
        
        collector.record_error('test_error', 'Test error context')
        
        before_metrics = {'memory_mb': 100, 'cpu_percent': 5}
        after_metrics = {'memory_mb': 80, 'cpu_percent': 3}
        collector.record_optimization_impact(
            'test_optimization',
            before_metrics,
            after_metrics
        )
        
        # Test 3: Get feedback summary
        logger.info("3. Getting feedback summary...")
        summary = collector.get_feedback_summary()
        
        logger.info("Feedback Summary:")
        logger.info(f"  Session duration: {summary.get('session_duration_hours', 0):.2f} hours")
        logger.info(f"  Events (24h): {summary.get('events_last_24h', 0)}")
        logger.info(f"  Top features: {summary.get('top_features', {})}")
        logger.info(f"  Performance impact: {summary.get('performance_impact', {})}")
        
        # Test 4: Privacy controls
        logger.info("4. Testing privacy controls...")
        original_enabled = collector.preferences.feedback_enabled
        
        collector.disable_feedback()
        assert not collector.preferences.feedback_enabled, "Feedback not disabled"
        
        collector.update_preferences(feedback_enabled=True)
        assert collector.preferences.feedback_enabled, "Feedback not re-enabled"
        
        logger.info("   ✅ Privacy controls work!")
        
        logger.info("\n🎉 Basic user feedback test passed!")
        logger.info("Privacy-first feedback collection system is functional.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic feedback test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)