"""
Privacy-First User Feedback Collection System

Comprehensive feedback collection for Context Cleaner that respects user privacy
while providing insights for performance optimization and feature development.

Features:
- Anonymous feedback collection (no personal data)
- Local-only data storage (never transmitted)
- Performance impact measurement
- User satisfaction tracking
- GDPR/CCPA compliant data handling
"""

from .feedback_collector import FeedbackCollector
from .user_feedback_collector import (
    UserFeedbackCollector,
    FeedbackEvent,
    UserPreferences,
    FeedbackStorage
)
from .performance_feedback_integration import PerformanceFeedbackIntegration
from .feedback_analytics import FeedbackAnalytics

__all__ = [
    'FeedbackCollector',
    'UserFeedbackCollector',
    'FeedbackEvent', 
    'UserPreferences',
    'FeedbackStorage',
    'PerformanceFeedbackIntegration',
    'FeedbackAnalytics'
]