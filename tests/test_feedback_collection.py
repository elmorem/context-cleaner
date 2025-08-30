"""
Tests for User Feedback Collection System (Phase 3 component).
"""

import pytest
from datetime import datetime

from context_cleaner.feedback.feedback_collector import (
    FeedbackCollector,
    FeedbackItem,
    FeedbackType,
    SeverityLevel,
)


@pytest.fixture
def feedback_collector(test_config):
    """Create FeedbackCollector instance for testing."""
    return FeedbackCollector(test_config)


class TestFeedbackCollector:
    """Test suite for FeedbackCollector class."""

    def test_initialization(self, feedback_collector):
        """Test proper initialization of feedback collector."""
        assert feedback_collector.feedback_enabled is True
        assert feedback_collector.max_feedback_items == 1000
        assert feedback_collector.retention_days == 90
        assert len(feedback_collector.feedback_items) == 0
        assert feedback_collector.session_id is not None

    def test_enable_disable_feedback(self, feedback_collector):
        """Test enabling and disabling feedback collection."""
        # Test disable
        feedback_collector.enable_feedback(False)
        assert feedback_collector.feedback_enabled is False

        # Try to collect feedback when disabled
        result = feedback_collector.collect_feedback(
            FeedbackType.FEATURE_USAGE, "test", "Test message"
        )
        assert result is False
        assert len(feedback_collector.feedback_items) == 0

        # Test re-enable
        feedback_collector.enable_feedback(True)
        assert feedback_collector.feedback_enabled is True

    def test_collect_feedback_basic(self, feedback_collector):
        """Test basic feedback collection."""
        result = feedback_collector.collect_feedback(
            FeedbackType.FEATURE_USAGE,
            "dashboard",
            "User accessed productivity dashboard",
            SeverityLevel.LOW,
            {"duration_seconds": 120},
        )

        assert result is True
        assert len(feedback_collector.feedback_items) == 1

        item = feedback_collector.feedback_items[0]
        assert item.type == FeedbackType.FEATURE_USAGE
        assert item.category == "dashboard"
        assert "productivity dashboard" in item.message
        assert item.severity == SeverityLevel.LOW
        assert item.metadata["duration_seconds"] == 120
        assert item.user_session_id == feedback_collector.session_id

    def test_collect_feedback_sanitization(self, feedback_collector):
        """Test message sanitization during feedback collection."""
        # Test with potentially sensitive information
        message_with_paths = "Error in /home/user/secret/file.py at line 42"

        feedback_collector.collect_feedback(
            FeedbackType.BUG_REPORT, "system", message_with_paths
        )

        item = feedback_collector.feedback_items[0]
        # Should sanitize file paths
        assert "/home/user/secret/file.py" not in item.message
        assert "[PATH]" in item.message

    def test_performance_issue_reporting(self, feedback_collector):
        """Test performance issue reporting."""
        feedback_collector.report_performance_issue(
            operation="context_analysis", duration_ms=2500.0, context_size=15000
        )

        assert len(feedback_collector.feedback_items) == 1
        item = feedback_collector.feedback_items[0]

        assert item.type == FeedbackType.PERFORMANCE_ISSUE
        assert item.category == "performance"
        assert item.severity == SeverityLevel.HIGH  # >2000ms is high severity
        assert item.metadata["operation"] == "context_analysis"
        assert item.metadata["duration_ms"] == 2500.0
        assert item.metadata["context_size_tokens"] == 15000
        assert item.metadata["performance_category"] == "slow"

    def test_productivity_improvement_reporting(self, feedback_collector):
        """Test productivity improvement reporting."""
        feedback_collector.report_productivity_improvement(
            improvement_type="context_optimization",
            before_metric=120.0,
            after_metric=90.0,
            context_description="Reduced context size",
        )

        item = feedback_collector.feedback_items[0]

        assert item.type == FeedbackType.PRODUCTIVITY_IMPROVEMENT
        assert item.category == "optimization"
        assert item.severity == SeverityLevel.LOW  # Positive feedback
        assert item.metadata["improvement_percent"] == -25.0  # 25% improvement
        assert item.metadata["improvement_type"] == "context_optimization"

    def test_user_satisfaction_reporting(self, feedback_collector):
        """Test user satisfaction reporting."""
        # Test high satisfaction
        feedback_collector.report_user_satisfaction(
            feature="dashboard", rating=5, comments="Excellent visualization!"
        )

        item = feedback_collector.feedback_items[0]
        assert item.type == FeedbackType.USER_SATISFACTION
        assert item.category == "dashboard"
        assert item.severity == SeverityLevel.LOW  # High rating = low severity
        assert item.metadata["rating"] == 5
        assert "5/5" in item.message

        # Test low satisfaction
        feedback_collector.report_user_satisfaction(
            feature="analysis", rating=2, comments="Too slow"
        )

        item = feedback_collector.feedback_items[1]
        assert item.severity == SeverityLevel.MEDIUM  # Low rating = higher severity

    def test_feedback_summary_empty(self, feedback_collector):
        """Test feedback summary with no data."""
        summary = feedback_collector.get_feedback_summary(days=7)

        assert summary["period_days"] == 7
        assert summary["total_items"] == 0
        assert "No feedback data available" in summary["message"]

    def test_feedback_summary_with_data(self, feedback_collector):
        """Test feedback summary with various feedback types."""
        # Add diverse feedback
        feedback_items = [
            (
                FeedbackType.FEATURE_USAGE,
                "dashboard",
                SeverityLevel.LOW,
                {"duration": 60},
            ),
            (
                FeedbackType.PERFORMANCE_ISSUE,
                "analysis",
                SeverityLevel.HIGH,
                {"duration_ms": 3000},
            ),
            (
                FeedbackType.USER_SATISFACTION,
                "dashboard",
                SeverityLevel.LOW,
                {"rating": 5},
            ),
            (
                FeedbackType.BUG_REPORT,
                "export",
                SeverityLevel.MEDIUM,
                {"error_code": "E001"},
            ),
            (
                FeedbackType.FEATURE_REQUEST,
                "visualization",
                SeverityLevel.MEDIUM,
                {"priority": "medium"},
            ),
        ]

        for fb_type, category, severity, metadata in feedback_items:
            feedback_collector.collect_feedback(
                fb_type, category, f"Test {fb_type.value}", severity, metadata
            )

        summary = feedback_collector.get_feedback_summary(days=1)

        # Verify summary structure
        assert summary["total_items"] == 5
        assert len(summary["summary"]["by_type"]) == 5
        assert len(summary["summary"]["by_category"]) >= 3
        assert len(summary["summary"]["by_severity"]) >= 2

        # Verify metrics
        assert "avg_satisfaction_rating" in summary["metrics"]
        assert summary["metrics"]["avg_satisfaction_rating"] == 5.0

        # Verify insights
        assert len(summary["insights"]) > 0
        assert summary["critical_issues"] == 0  # No critical severity items

    def test_export_feedback_anonymization(self, feedback_collector):
        """Test feedback export with anonymization."""
        # Add feedback with session ID
        feedback_collector.collect_feedback(
            FeedbackType.FEATURE_USAGE,
            "context-cleaner",
            "User used Context Cleaner optimize feature",
        )

        # Export without anonymization
        export_data = feedback_collector.export_feedback_for_analysis(anonymize=False)
        assert len(export_data) == 1
        assert export_data[0]["user_session_id"] == feedback_collector.session_id
        assert "Context Cleaner" in export_data[0]["message"]

        # Export with anonymization
        export_data_anon = feedback_collector.export_feedback_for_analysis(
            anonymize=True
        )
        assert len(export_data_anon) == 1
        assert "user_session_id" not in export_data_anon[0]
        assert "[APP]" in export_data_anon[0]["message"]
        assert "Context Cleaner" not in export_data_anon[0]["message"]

    def test_feedback_item_limit(self, feedback_collector):
        """Test feedback item count limit enforcement."""
        # Set a low limit for testing
        feedback_collector.max_feedback_items = 5

        # Add more items than the limit
        for i in range(10):
            feedback_collector.collect_feedback(
                FeedbackType.FEATURE_USAGE, "test", f"Test message {i}"
            )

        # Should only keep the most recent items
        assert len(feedback_collector.feedback_items) == 5

        # Verify it kept the most recent items
        messages = [item.message for item in feedback_collector.feedback_items]
        assert "Test message 9" in messages[-1]
        assert "Test message 5" in messages[0]

    def test_message_sanitization_methods(self, feedback_collector):
        """Test message sanitization helper methods."""
        # Test path sanitization
        message_with_paths = (
            "Error in /usr/local/bin/app.py and C:\\Windows\\System32\\file.exe"
        )
        sanitized = feedback_collector._sanitize_message(message_with_paths)
        assert "/usr/local/bin/app.py" not in sanitized
        assert "C:\\Windows\\System32\\file.exe" not in sanitized
        assert "[PATH]" in sanitized

        # Test email sanitization
        message_with_email = "Contact user@example.com for support"
        sanitized = feedback_collector._sanitize_message(message_with_email)
        assert "user@example.com" not in sanitized
        assert "[EMAIL]" in sanitized

        # Test URL sanitization
        message_with_url = "Visit https://example.com/secret-page for more info"
        sanitized = feedback_collector._sanitize_message(message_with_url)
        assert "https://example.com/secret-page" not in sanitized
        assert "[URL]" in sanitized

        # Test token sanitization
        message_with_token = "API key: abc123def456ghi789jkl012mno345pqr678"
        sanitized = feedback_collector._sanitize_message(message_with_token)
        assert "abc123def456ghi789jkl012mno345pqr678" not in sanitized
        assert "[TOKEN]" in sanitized

    def test_insights_generation(self, feedback_collector):
        """Test automatic insights generation from feedback patterns."""
        # Add performance issues
        for i in range(6):
            feedback_collector.collect_feedback(
                FeedbackType.PERFORMANCE_ISSUE,
                "analysis",
                f"Slow analysis {i}",
                SeverityLevel.HIGH,
            )

        # Add low satisfaction ratings
        for i in range(3):
            feedback_collector.report_user_satisfaction("dashboard", rating=2)

        # Add high satisfaction rating for comparison
        feedback_collector.report_user_satisfaction("export", rating=5)

        summary = feedback_collector.get_feedback_summary(days=1)
        insights = summary["insights"]

        # Should detect performance issues
        assert any("performance issues" in insight.lower() for insight in insights)

        # Should detect satisfaction concerns
        assert any("satisfaction concerns" in insight.lower() for insight in insights)


class TestFeedbackItem:
    """Test suite for FeedbackItem dataclass."""

    def test_feedback_item_creation(self):
        """Test creation of feedback item."""
        timestamp = datetime.now()
        metadata = {"test_key": "test_value"}

        item = FeedbackItem(
            id="test-123",
            type=FeedbackType.FEATURE_USAGE,
            timestamp=timestamp,
            category="test_category",
            message="Test message",
            severity=SeverityLevel.LOW,
            metadata=metadata,
            user_session_id="session-456",
            version="0.1.0",
        )

        assert item.id == "test-123"
        assert item.type == FeedbackType.FEATURE_USAGE
        assert item.timestamp == timestamp
        assert item.category == "test_category"
        assert item.message == "Test message"
        assert item.severity == SeverityLevel.LOW
        assert item.metadata == metadata
        assert item.user_session_id == "session-456"
        assert item.version == "0.1.0"

    def test_feedback_item_default_metadata(self):
        """Test feedback item with default metadata."""
        item = FeedbackItem(
            id="test-123",
            type=FeedbackType.BUG_REPORT,
            timestamp=datetime.now(),
            category="system",
            message="Test bug report",
        )

        assert item.metadata == {}
        assert item.severity == SeverityLevel.MEDIUM  # Default severity


@pytest.mark.integration
class TestFeedbackCollectionIntegration:
    """Integration tests for feedback collection system."""

    def test_feedback_storage_integration(self, feedback_collector):
        """Test integration with encrypted storage system."""
        # Add feedback data
        feedback_collector.collect_feedback(
            FeedbackType.PRODUCTIVITY_IMPROVEMENT,
            "optimization",
            "Context optimization improved response time by 30%",
            SeverityLevel.LOW,
            {"improvement_percent": 30.0},
        )

        # Test save functionality
        try:
            feedback_collector._save_feedback_history()
        except Exception as e:
            pytest.fail(f"Storage save failed: {e}")

        # Test load functionality
        try:
            feedback_collector._load_feedback_history()
        except Exception as e:
            pytest.fail(f"Storage load failed: {e}")

    def test_feedback_workflow_complete(self, feedback_collector):
        """Test complete feedback collection workflow."""
        # Simulate various user interactions

        # 1. User starts using feature
        feedback_collector.collect_feedback(
            FeedbackType.FEATURE_USAGE, "dashboard", "User accessed dashboard"
        )

        # 2. Performance issue encountered
        feedback_collector.report_performance_issue(
            "dashboard_render", duration_ms=1500.0, context_size=12000
        )

        # 3. User reports satisfaction
        feedback_collector.report_user_satisfaction(
            "dashboard", rating=4, comments="Good but could be faster"
        )

        # 4. Productivity improvement after optimization
        feedback_collector.report_productivity_improvement(
            "render_time",
            before_metric=1500.0,
            after_metric=800.0,
            context_description="After optimization",
        )

        # Generate comprehensive summary
        summary = feedback_collector.get_feedback_summary(hours=1)

        # Verify all feedback types are captured
        assert summary["total_items"] == 4
        assert len(summary["summary"]["by_type"]) == 3  # Different types used

        # Verify metrics calculation
        assert summary["metrics"]["avg_satisfaction_rating"] == 4.0
        assert summary["metrics"]["avg_productivity_improvement"] is not None

        # Verify insights generation
        assert len(summary["insights"]) > 0

    def test_privacy_compliance(self, feedback_collector):
        """Test privacy compliance of feedback collection."""
        # Add feedback with potentially sensitive data
        sensitive_message = "User john.doe@company.com had error in /home/john/secret.txt with token abc123xyz789"

        feedback_collector.collect_feedback(
            FeedbackType.BUG_REPORT, "security", sensitive_message
        )

        # Export data with anonymization
        export_data = feedback_collector.export_feedback_for_analysis(anonymize=True)
        exported_message = export_data[0]["message"]

        # Verify no sensitive data in export
        assert "john.doe@company.com" not in exported_message
        assert "/home/john/secret.txt" not in exported_message
        assert "abc123xyz789" not in exported_message

        # Verify sanitization markers are present
        assert "[EMAIL]" in exported_message
        assert "[PATH]" in exported_message
        assert "[TOKEN]" in exported_message


if __name__ == "__main__":
    pytest.main([__file__])
