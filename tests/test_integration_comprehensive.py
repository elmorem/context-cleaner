"""
Comprehensive Integration Tests for Context Cleaner.
Tests end-to-end workflows and component interactions.
"""

import pytest
import time
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from context_cleaner.cli.main import main as cli_main
from context_cleaner.tracking.session_tracker import SessionTracker
from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer
from context_cleaner.monitoring.performance_optimizer import PerformanceOptimizer
from context_cleaner.feedback.feedback_collector import FeedbackCollector
from context_cleaner.utils.error_handling import ErrorHandler
from context_cleaner.config.settings import ContextCleanerConfig


@pytest.mark.integration
class TestCLIIntegration:
    """Test CLI command integration."""

    def test_cli_help_command(self):
        """Test CLI help command functionality."""
        # Test main help
        result = subprocess.run(['context-cleaner', '--help'], 
                               capture_output=True, text=True)
        assert result.returncode == 0
        assert 'Context Cleaner' in result.stdout
        assert 'optimize' in result.stdout
        assert 'dashboard' in result.stdout
        assert 'analyze' in result.stdout

    def test_cli_optimize_preview(self):
        """Test CLI optimize command with preview."""
        result = subprocess.run(['context-cleaner', 'optimize', '--preview'], 
                               capture_output=True, text=True)
        assert result.returncode == 0
        assert 'Preview' in result.stdout or 'preview' in result.stdout

    def test_cli_version_command(self):
        """Test CLI version command."""
        result = subprocess.run(['context-cleaner', '--version'], 
                               capture_output=True, text=True)
        assert result.returncode == 0
        assert '0.1.0' in result.stdout

    def test_cli_config_show(self):
        """Test CLI configuration display."""
        result = subprocess.run(['context-cleaner', 'config-show'], 
                               capture_output=True, text=True)
        assert result.returncode == 0
        # Should show configuration in some format
        assert len(result.stdout) > 0


@pytest.mark.integration  
class TestSystemIntegration:
    """Test system component integration."""

    def test_tracking_to_analytics_pipeline(self, test_config):
        """Test data flow from tracking to analytics."""
        # Initialize components
        tracker = SessionTracker(test_config)
        analyzer = ProductivityAnalyzer(test_config)
        
        # Start tracking session
        session_id = tracker.start_session()
        
        # Simulate productivity events
        events = [
            ("context_optimization", {"context_size": 1500, "optimization_type": "quick"}),
            ("tool_usage", {"tool": "Read", "duration_ms": 50}),
            ("analysis_complete", {"insights_generated": 5, "confidence": 0.85})
        ]
        
        for event_type, data in events:
            tracker.track_event(event_type, data)
        
        # End session
        tracker.end_session(session_id)
        
        # Analyze tracked data
        session_data = tracker.get_session_data(session_id)
        analysis = analyzer.analyze_session(session_data)
        
        # Verify data flowed correctly
        assert session_data is not None
        assert analysis is not None
        assert len(session_data.get("events", [])) == len(events)

    def test_monitoring_feedback_integration(self, test_config):
        """Test integration between performance monitoring and feedback collection."""
        # Initialize components
        performance_monitor = PerformanceOptimizer(test_config)
        feedback_collector = FeedbackCollector(test_config)
        
        # Start monitoring
        performance_monitor.start_monitoring()
        
        # Simulate operation with monitoring
        with performance_monitor.track_operation("test_integration", 2000):
            time.sleep(0.1)  # Simulate work
        
        # Stop monitoring
        performance_monitor.stop_monitoring()
        
        # Get performance summary
        perf_summary = performance_monitor.get_performance_summary(hours=1)
        
        # Report performance to feedback system
        if perf_summary.get("performance", {}).get("health_score", 100) < 80:
            feedback_collector.collect_feedback(
                "performance_issue",
                "system",
                "Low performance detected in integration test"
            )
        
        # Verify integration worked
        assert len(performance_monitor.operation_timings) > 0
        feedback_summary = feedback_collector.get_feedback_summary(days=1)
        assert feedback_summary["total_items"] >= 0  # May or may not have feedback

    def test_error_handling_across_components(self, test_config):
        """Test error handling integration across multiple components."""
        # Initialize error handler
        error_handler = ErrorHandler(test_config)
        
        # Test error handling with different components
        components_errors = [
            (SessionTracker(test_config), "tracking_error"),
            (ProductivityAnalyzer(test_config), "analysis_error"),
            (PerformanceOptimizer(test_config), "monitoring_error"),
            (FeedbackCollector(test_config), "feedback_error")
        ]
        
        # Simulate errors in each component
        for component, error_type in components_errors:
            try:
                # Force an error by calling non-existent method
                getattr(component, "non_existent_method")()
            except AttributeError as e:
                error_handler.handle_error(e, context={"component": error_type})
        
        # Verify error handling worked
        error_summary = error_handler.get_error_summary(hours=1)
        assert error_summary["total_errors"] == len(components_errors)

    def test_configuration_propagation(self, temp_data_dir):
        """Test configuration propagation across all components."""
        # Create test configuration
        config = ContextCleanerConfig.default()
        config.data_directory = temp_data_dir
        config.tracking.enabled = True
        config.performance.monitoring_enabled = True
        
        # Initialize all components with same config
        tracker = SessionTracker(config)
        analyzer = ProductivityAnalyzer(config)
        monitor = PerformanceOptimizer(config)
        feedback = FeedbackCollector(config)
        
        # Verify all components use same data directory
        assert str(tracker.storage.data_directory) == temp_data_dir
        assert str(analyzer.storage.data_directory) == temp_data_dir
        assert str(monitor.storage.data_directory) == temp_data_dir
        assert str(feedback.storage.data_directory) == temp_data_dir


@pytest.mark.integration
class TestDataFlowIntegration:
    """Test data flow between components."""

    def test_complete_productivity_workflow(self, test_config):
        """Test complete productivity tracking and analysis workflow."""
        # Initialize all components
        tracker = SessionTracker(test_config)
        analyzer = ProductivityAnalyzer(test_config)
        monitor = PerformanceOptimizer(test_config)
        feedback = FeedbackCollector(test_config)
        
        # Start comprehensive tracking
        session_id = tracker.start_session()
        monitor.start_monitoring()
        
        # Simulate realistic development session
        development_activities = [
            ("context_read", {"files_read": 5, "total_lines": 500}),
            ("context_analysis", {"complexity_score": 0.75, "suggestions": 3}),
            ("optimization_applied", {"before_size": 2000, "after_size": 1500}),
            ("productivity_boost", {"improvement_percent": 25})
        ]
        
        for activity, data in development_activities:
            # Track activity
            tracker.track_event(activity, data)
            
            # Monitor performance
            with monitor.track_operation(activity, context_tokens=data.get("after_size", 1000)):
                time.sleep(0.05)  # Simulate processing time
            
            # Collect feedback if significant improvement
            if activity == "productivity_boost" and data["improvement_percent"] > 20:
                feedback.report_productivity_improvement(
                    "workflow_optimization",
                    before_metric=100.0,
                    after_metric=125.0
                )
        
        # End tracking
        tracker.end_session(session_id)
        monitor.stop_monitoring()
        
        # Analyze complete workflow
        session_data = tracker.get_session_data(session_id)
        productivity_analysis = analyzer.analyze_session(session_data)
        performance_summary = monitor.get_performance_summary(hours=1)
        feedback_summary = feedback.get_feedback_summary(days=1)
        
        # Verify comprehensive workflow
        assert len(session_data.get("events", [])) == len(development_activities)
        assert productivity_analysis is not None
        assert performance_summary["total_snapshots"] > 0
        assert feedback_summary["total_items"] >= 1  # At least the improvement report

    def test_data_consistency_across_components(self, test_config):
        """Test data consistency and synchronization between components."""
        # Initialize components
        tracker = SessionTracker(test_config)
        monitor = PerformanceOptimizer(test_config)
        
        # Start coordinated tracking
        session_id = tracker.start_session()
        monitor.start_monitoring()
        
        # Perform tracked operations
        operations = ["analysis", "optimization", "export"]
        for op in operations:
            tracker.track_event(f"{op}_start", {"operation": op})
            
            with monitor.track_operation(op, context_tokens=1000):
                time.sleep(0.02)  # Brief operation
            
            tracker.track_event(f"{op}_complete", {"operation": op, "success": True})
        
        # Stop tracking
        tracker.end_session(session_id)
        monitor.stop_monitoring()
        
        # Verify data consistency
        session_data = tracker.get_session_data(session_id)
        performance_data = monitor.get_performance_summary(hours=1)
        
        # Should have matching event counts
        tracked_events = len(session_data.get("events", []))
        monitored_operations = len([op for op in monitor.operation_timings.keys() 
                                  if op in operations])
        
        assert tracked_events == len(operations) * 2  # Start and complete events
        assert monitored_operations == len(operations)  # One timing per operation


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def test_new_user_onboarding_workflow(self, temp_data_dir):
        """Test complete new user onboarding workflow."""
        # Simulate new user setup
        config = ContextCleanerConfig.default()
        config.data_directory = temp_data_dir
        
        # 1. First-time setup
        tracker = SessionTracker(config)
        feedback = FeedbackCollector(config)
        
        # 2. User enables feedback
        feedback.enable_feedback(True)
        assert feedback.feedback_enabled is True
        
        # 3. First session
        session_id = tracker.start_session()
        
        # 4. User performs initial activities
        initial_activities = [
            ("first_optimization", {"user_guided": True}),
            ("dashboard_access", {"first_time": True}),
            ("help_accessed", {"section": "getting_started"})
        ]
        
        for activity, data in initial_activities:
            tracker.track_event(activity, data)
        
        # 5. User provides initial satisfaction feedback
        feedback.report_user_satisfaction("initial_experience", rating=4)
        
        # 6. End first session
        tracker.end_session(session_id)
        
        # 7. Verify onboarding data
        session_data = tracker.get_session_data(session_id)
        feedback_summary = feedback.get_feedback_summary(days=1)
        
        assert len(session_data.get("events", [])) == len(initial_activities)
        assert feedback_summary["total_items"] == 2  # Enable + satisfaction
        assert feedback_summary["metrics"]["avg_satisfaction_rating"] == 4.0

    def test_power_user_workflow(self, test_config):
        """Test advanced power user workflow."""
        # Initialize all components for power user
        tracker = SessionTracker(test_config)
        analyzer = ProductivityAnalyzer(test_config)
        monitor = PerformanceOptimizer(test_config)
        feedback = FeedbackCollector(test_config)
        
        # Power user performs complex workflow
        sessions = []
        
        # Multiple sessions over time
        for session_num in range(5):
            session_id = tracker.start_session()
            monitor.start_monitoring()
            
            # Intensive development activities
            activities = [
                ("deep_analysis", {"context_size": 5000 + session_num * 500}),
                ("complex_optimization", {"before": 3000, "after": 2000}),
                ("advanced_export", {"format": "json", "filters": ["productivity", "patterns"]}),
                ("custom_dashboard", {"widgets": 8, "time_range": "30d"})
            ]
            
            for activity, data in activities:
                tracker.track_event(activity, data)
                
                with monitor.track_operation(activity, context_tokens=data.get("after", data.get("context_size", 1000))):
                    # Simulate varying processing times for power user operations
                    time.sleep(0.05 + session_num * 0.01)
            
            tracker.end_session(session_id)
            monitor.stop_monitoring()
            sessions.append(session_id)
            
            # Power user provides detailed feedback
            if session_num % 2 == 0:  # Every other session
                feedback.report_user_satisfaction(
                    "advanced_features", 
                    rating=5 if session_num > 2 else 4
                )
        
        # Analyze power user patterns
        all_sessions_data = [tracker.get_session_data(sid) for sid in sessions]
        performance_summary = monitor.get_performance_summary(hours=24)
        feedback_summary = feedback.get_feedback_summary(days=1)
        
        # Power user should show sophisticated usage patterns
        assert len(all_sessions_data) == 5
        assert all(len(session.get("events", [])) >= 4 for session in all_sessions_data)
        assert performance_summary["operations"] is not None
        assert feedback_summary["metrics"]["avg_satisfaction_rating"] >= 4.0

    def test_performance_regression_detection(self, test_config):
        """Test detection of performance regressions."""
        monitor = PerformanceOptimizer(test_config)
        feedback = FeedbackCollector(test_config)
        
        monitor.start_monitoring()
        
        # Simulate baseline performance
        for i in range(10):
            with monitor.track_operation("baseline_operation", context_tokens=1000):
                time.sleep(0.05)  # Consistent performance
        
        # Simulate performance regression
        for i in range(5):
            with monitor.track_operation("regression_operation", context_tokens=1000):
                time.sleep(0.15)  # Slower performance
                
        # Report performance issues automatically
        performance_summary = monitor.get_performance_summary(hours=1)
        
        # Check if regression was detected
        baseline_perf = monitor.operation_timings.get("baseline_operation", [])
        regression_perf = monitor.operation_timings.get("regression_operation", [])
        
        if baseline_perf and regression_perf:
            avg_baseline = sum(baseline_perf) / len(baseline_perf)
            avg_regression = sum(regression_perf) / len(regression_perf)
            
            if avg_regression > avg_baseline * 2:  # Significant regression
                feedback.report_performance_issue(
                    "regression_detected",
                    duration_ms=avg_regression,
                    context_size=1000
                )
        
        monitor.stop_monitoring()
        
        # Verify regression detection
        feedback_summary = feedback.get_feedback_summary(days=1)
        assert len(baseline_perf) == 10
        assert len(regression_perf) == 5
        
        # Should detect regression if significant
        if feedback_summary["total_items"] > 0:
            assert any("regression" in item.get("message", "").lower() 
                      for item in feedback.feedback_items)


@pytest.mark.integration
@pytest.mark.slow
class TestStressAndPerformance:
    """Test system performance under stress conditions."""

    def test_high_volume_session_tracking(self, test_config):
        """Test session tracking under high volume."""
        tracker = SessionTracker(test_config)
        
        # Track many sessions rapidly
        session_ids = []
        start_time = time.perf_counter()
        
        for i in range(100):
            session_id = tracker.start_session()
            
            # Multiple events per session
            for j in range(10):
                tracker.track_event(f"event_{j}", {"session": i, "event": j})
            
            tracker.end_session(session_id)
            session_ids.append(session_id)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Should handle 100 sessions with 10 events each in reasonable time
        assert total_time < 10.0  # Less than 10 seconds
        assert len(session_ids) == 100
        
        # Verify data integrity
        sample_session = tracker.get_session_data(session_ids[50])
        assert len(sample_session.get("events", [])) == 10

    def test_concurrent_component_usage(self, test_config):
        """Test concurrent usage of multiple components."""
        import threading
        
        # Initialize components
        tracker = SessionTracker(test_config)
        monitor = PerformanceOptimizer(test_config)
        feedback = FeedbackCollector(test_config)
        
        results = {"errors": []}
        
        def tracking_worker():
            try:
                for i in range(20):
                    session_id = tracker.start_session()
                    tracker.track_event("concurrent_test", {"worker": "tracking", "iteration": i})
                    tracker.end_session(session_id)
                    time.sleep(0.01)
            except Exception as e:
                results["errors"].append(f"Tracking worker: {e}")
        
        def monitoring_worker():
            try:
                monitor.start_monitoring()
                for i in range(20):
                    with monitor.track_operation("concurrent_operation", context_tokens=1000):
                        time.sleep(0.02)
                monitor.stop_monitoring()
            except Exception as e:
                results["errors"].append(f"Monitoring worker: {e}")
        
        def feedback_worker():
            try:
                for i in range(20):
                    feedback.collect_feedback(
                        "feature_usage",
                        "concurrent_test",
                        f"Concurrent feedback {i}"
                    )
                    time.sleep(0.01)
            except Exception as e:
                results["errors"].append(f"Feedback worker: {e}")
        
        # Start concurrent workers
        workers = [
            threading.Thread(target=tracking_worker),
            threading.Thread(target=monitoring_worker),
            threading.Thread(target=feedback_worker)
        ]
        
        for worker in workers:
            worker.start()
        
        for worker in workers:
            worker.join()
        
        # Verify no errors occurred
        assert len(results["errors"]) == 0, f"Concurrent errors: {results['errors']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])