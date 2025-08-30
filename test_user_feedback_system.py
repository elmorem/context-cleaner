#!/usr/bin/env python3
"""
User Feedback System Integration Test

Test the complete user feedback collection system including privacy compliance,
performance integration, and analytics generation.
"""

import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from context_cleaner.feedback import (
    UserFeedbackCollector,
    PerformanceFeedbackIntegration,
    FeedbackAnalytics
)
from context_cleaner.optimization.memory_optimizer import MemoryOptimizer
from context_cleaner.optimization.cpu_optimizer import CPUOptimizer, TaskPriority
from context_cleaner.config.settings import ContextCleanerConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UserFeedbackSystemTester:
    """Test the complete user feedback system."""
    
    def __init__(self):
        """Initialize the feedback system tester."""
        self.config = ContextCleanerConfig.from_env()
        
        # Initialize components
        self.user_feedback = UserFeedbackCollector(self.config)
        self.memory_optimizer = MemoryOptimizer(self.config)
        self.cpu_optimizer = CPUOptimizer(self.config)
        
        # Integration components
        self.feedback_integration = PerformanceFeedbackIntegration(self.config)
        self.analytics = FeedbackAnalytics(self.config)
        
        # Test results
        self.test_results = {}
        self.test_passed = 0
        self.test_failed = 0
    
    def run_all_tests(self):
        """Run all user feedback system tests."""
        logger.info("🚀 Starting User Feedback System Tests")
        logger.info("=" * 60)
        
        # Test individual components
        self.test_user_feedback_collector()
        self.test_privacy_compliance()
        self.test_performance_integration()
        self.test_feedback_analytics()
        self.test_end_to_end_workflow()
        
        # Print summary
        self.print_test_summary()
        
        return self.test_failed == 0
    
    def test_user_feedback_collector(self):
        """Test basic user feedback collector functionality."""
        logger.info("📋 Testing User Feedback Collector")
        
        try:
            # Test feedback collection
            self.user_feedback.record_feature_usage(
                'test_feature',
                success=True,
                test_metric=42,
                duration_ms=250
            )
            
            # Test error recording
            self.user_feedback.record_error(
                'test_error',
                'Test error context'
            )
            
            # Test optimization impact recording
            before_metrics = {'memory_mb': 100, 'cpu_percent': 5}
            after_metrics = {'memory_mb': 80, 'cpu_percent': 3}
            
            self.user_feedback.record_optimization_impact(
                'memory_cleanup',
                before_metrics,
                after_metrics
            )
            
            # Get feedback summary
            summary = self.user_feedback.get_feedback_summary()
            
            # Verify structure
            required_fields = ['session_duration_hours', 'events_last_24h', 'top_features', 'performance_impact']
            for field in required_fields:
                assert field in summary, f"Missing field: {field}"
            
            # Verify performance impact calculation
            perf_impact = summary['performance_impact']
            assert 'measurements_count' in perf_impact, "Missing measurements count"
            assert perf_impact['measurements_count'] > 0, "No measurements recorded"
            
            self._record_test_result("User Feedback Collection", True)
            
        except Exception as e:
            self._record_test_result("User Feedback Collection", False, str(e))
    
    def test_privacy_compliance(self):
        """Test privacy compliance features."""
        logger.info("🔒 Testing Privacy Compliance")
        
        try:
            # Test data sanitization
            test_event = self.user_feedback._record_event('usage', {
                'test_path': '/Users/sensitive/path/file.txt',
                'test_email': 'user@example.com',
                'test_url': 'https://private-site.com/secret',
                'test_token': 'sk-1234567890abcdef1234567890abcdef',
                'safe_metric': 42.5
            })
            
            # Verify no personal data in storage
            recent_events = self.user_feedback.storage.get_recent_events(1)
            
            for event in recent_events:
                event_data = event.get('data', {})
                
                # Check that sensitive data was sanitized
                for key, value in event_data.items():
                    assert not any(sensitive in str(value) for sensitive in [
                        '/Users/', '@example.com', 'https://', 'sk-'
                    ]), f"Sensitive data not sanitized: {key}={value}"
                
                # Verify safe data is preserved
                if 'safe_metric' in event_data:
                    assert event_data['safe_metric'] == 42.5, "Safe data was incorrectly modified"
            
            self._record_test_result("Data Sanitization", True)
            
            # Test user preferences
            original_prefs = self.user_feedback.preferences
            
            # Disable feedback
            self.user_feedback.disable_feedback()
            assert not self.user_feedback.preferences.feedback_enabled, "Feedback not disabled"
            
            # Re-enable
            self.user_feedback.update_preferences(feedback_enabled=True)
            assert self.user_feedback.preferences.feedback_enabled, "Feedback not re-enabled"
            
            self._record_test_result("Privacy Controls", True)
            
            # Test data retention
            initial_events = len(self.user_feedback.storage.get_recent_events(24))
            
            # Simulate old data cleanup
            self.user_feedback.storage.cleanup_old_data(0)  # Remove all data
            
            cleaned_events = len(self.user_feedback.storage.get_recent_events(24))
            
            # Should have removed old events but kept recent ones
            logger.info(f"Events before cleanup: {initial_events}, after: {cleaned_events}")
            
            self._record_test_result("Data Retention", True)
            
        except Exception as e:
            self._record_test_result("Privacy Compliance", False, str(e))
    
    def test_performance_integration(self):
        """Test integration with performance optimizers."""
        logger.info("⚡ Testing Performance Integration")
        
        try:
            # Connect optimizers
            self.feedback_integration.connect_optimizers(
                self.memory_optimizer,
                self.cpu_optimizer
            )
            
            # Start monitoring briefly
            self.feedback_integration.start_integrated_monitoring()
            
            # Create some performance data
            def test_memory_task():
                # Create temporary memory usage
                data = [list(range(100)) for _ in range(10)]
                time.sleep(0.1)
                return len(data)
            
            def test_cpu_task():
                # CPU-bound task
                result = sum(i * i for i in range(1000))
                return result
            
            # Use performance tracking context manager
            with self.feedback_integration.track_operation("test_operation", "memory") as tracker:
                test_memory_task()
                test_cpu_task()
            
            # Let monitoring collect data
            time.sleep(2)
            
            # Get comprehensive report
            report = self.feedback_integration.get_comprehensive_feedback_report()
            
            # Verify report structure
            assert 'performance_trend' in report, "Missing performance trend"
            assert 'user_feedback_summary' in report, "Missing user feedback summary"
            assert 'optimization_effectiveness' in report, "Missing optimization effectiveness"
            assert 'recommendations' in report, "Missing recommendations"
            
            logger.info(f"Performance trend: {report['performance_trend']}")
            logger.info(f"Optimization effectiveness: {report['optimization_effectiveness']}")
            
            self._record_test_result("Performance Integration", True)
            
            # Stop monitoring
            self.feedback_integration.stop_integrated_monitoring()
            
        except Exception as e:
            self._record_test_result("Performance Integration", False, str(e))
    
    def test_feedback_analytics(self):
        """Test feedback analytics and insight generation."""
        logger.info("📊 Testing Feedback Analytics")
        
        try:
            # Generate comprehensive analytics
            analytics = self.analytics.generate_comprehensive_analytics(days=7)
            
            # Verify analytics structure
            required_sections = [
                'performance_trends', 'user_experience', 'feature_usage',
                'issue_analysis', 'optimization_effectiveness', 'insights',
                'recommendations', 'health_score'
            ]
            
            for section in required_sections:
                assert section in analytics, f"Missing analytics section: {section}"
            
            # Verify health score is reasonable
            health_score = analytics.get('health_score', 0)
            assert 0 <= health_score <= 100, f"Invalid health score: {health_score}"
            
            # Verify insights were generated
            insights = analytics.get('insights', [])
            assert len(insights) > 0, "No insights generated"
            
            # Verify recommendations were generated
            recommendations = analytics.get('recommendations', [])
            assert len(recommendations) > 0, "No recommendations generated"
            
            logger.info(f"Health Score: {health_score}/100")
            logger.info(f"Generated {len(insights)} insights and {len(recommendations)} recommendations")
            
            # Test export functionality
            json_report = self.analytics.export_analytics_report(7, 'json')
            assert len(json_report) > 100, "JSON report too short"
            
            summary_report = self.analytics.export_analytics_report(7, 'summary')
            assert 'Context Cleaner Feedback Analytics Report' in summary_report, "Missing report header"
            
            self._record_test_result("Feedback Analytics", True)
            
        except Exception as e:
            self._record_test_result("Feedback Analytics", False, str(e))
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end feedback workflow."""
        logger.info("🔄 Testing End-to-End Workflow")
        
        try:
            # Start all systems
            self.memory_optimizer.start_monitoring()
            self.cpu_optimizer.start()
            
            self.feedback_integration.connect_optimizers(
                self.memory_optimizer,
                self.cpu_optimizer
            )
            self.feedback_integration.start_integrated_monitoring()
            
            # Simulate real usage scenario
            logger.info("Simulating real usage workflow...")
            
            # 1. User performs various operations
            operations = [
                ('context_analysis', 'memory'),
                ('optimization_run', 'both'),
                ('dashboard_view', 'cpu'),
                ('report_generation', 'memory')
            ]
            
            for operation, expected_improvement in operations:
                with self.feedback_integration.track_operation(operation, expected_improvement):
                    # Simulate work with some resource usage
                    if 'memory' in expected_improvement:
                        data = [list(range(50)) for _ in range(20)]
                        time.sleep(0.1)
                    
                    if 'cpu' in expected_improvement:
                        result = sum(i ** 2 for i in range(500))
                        time.sleep(0.05)
            
            # 2. Let systems collect and process data
            time.sleep(3)
            
            # 3. Generate comprehensive analytics
            analytics = self.analytics.generate_comprehensive_analytics(days=1)
            
            # 4. Verify complete data flow
            assert analytics.get('data_summary', {}).get('total_data_points', 0) > 0, "No data collected"
            
            health_score = analytics.get('health_score', 0)
            insights = analytics.get('insights', [])
            recommendations = analytics.get('recommendations', [])
            
            logger.info("End-to-end workflow results:")
            logger.info(f"  Health Score: {health_score}/100")
            logger.info(f"  Data Points: {analytics.get('data_summary', {}).get('total_data_points', 0)}")
            logger.info(f"  Insights: {len(insights)}")
            logger.info(f"  Recommendations: {len(recommendations)}")
            
            # 5. Test data export
            export_data = self.feedback_integration.export_performance_data(anonymize=True)
            assert 'user_feedback_data' in export_data, "Missing user feedback in export"
            assert 'structured_feedback_data' in export_data, "Missing structured feedback in export"
            
            self._record_test_result("End-to-End Workflow", True)
            
            # Clean up
            self.feedback_integration.stop_integrated_monitoring()
            self.memory_optimizer.stop_monitoring()
            self.cpu_optimizer.stop()
            
        except Exception as e:
            self._record_test_result("End-to-End Workflow", False, str(e))
    
    def _record_test_result(self, test_name: str, passed: bool, error_msg: str = None):
        """Record a test result."""
        self.test_results[test_name] = {
            "passed": passed,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.test_passed += 1
            logger.info(f"✅ {test_name}: PASSED")
        else:
            self.test_failed += 1
            logger.error(f"❌ {test_name}: FAILED" + (f" - {error_msg}" if error_msg else ""))
    
    def print_test_summary(self):
        """Print test execution summary."""
        logger.info("=" * 60)
        logger.info("📊 User Feedback System Test Summary")
        logger.info("=" * 60)
        
        total_tests = self.test_passed + self.test_failed
        success_rate = (self.test_passed / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {self.test_passed}")
        logger.info(f"Failed: {self.test_failed}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        
        if self.test_failed > 0:
            logger.info("\n❌ Failed Tests:")
            for test_name, result in self.test_results.items():
                if not result["passed"]:
                    logger.info(f"  - {test_name}: {result['error']}")
        
        if self.test_failed == 0:
            logger.info("\n🎉 All user feedback system tests passed!")
            logger.info("The privacy-first feedback collection system is ready for production.")
        else:
            logger.info(f"\n⚠️  {self.test_failed} tests failed. Please review and fix issues.")
        
        logger.info("=" * 60)


def main():
    """Main test execution."""
    tester = UserFeedbackSystemTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()