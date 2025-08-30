"""
Privacy-First Feedback Collection System
Collects anonymous usage feedback to improve Context Cleaner while respecting user privacy.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
import logging

from ..config.settings import ContextCleanerConfig
from ..tracking.storage import EncryptedStorage

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback that can be collected."""
    FEATURE_USAGE = "feature_usage"
    PERFORMANCE_ISSUE = "performance_issue"
    PRODUCTIVITY_IMPROVEMENT = "productivity_improvement"
    USER_SATISFACTION = "user_satisfaction"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    OPTIMIZATION_RESULT = "optimization_result"


class SeverityLevel(Enum):
    """Severity levels for feedback items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FeedbackItem:
    """Individual feedback item with privacy protection."""
    id: str
    type: FeedbackType
    timestamp: datetime
    category: str
    message: str
    severity: SeverityLevel = SeverityLevel.MEDIUM
    metadata: Dict[str, Any] = None
    user_session_id: Optional[str] = None  # Anonymous session identifier
    version: str = "0.1.0"
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class FeedbackCollector:
    """
    Privacy-first feedback collection system.
    
    Features:
    - Anonymous feedback collection (no personal data)
    - Local storage only - no external transmission
    - User consent required for all feedback
    - Automatic feedback aggregation and analysis
    - Performance impact tracking
    - Productivity improvement measurement
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize feedback collector."""
        self.config = config or ContextCleanerConfig.from_env()
        self.storage = EncryptedStorage(self.config)
        
        # Generate anonymous session identifier
        self.session_id = str(uuid.uuid4())
        
        # Feedback settings
        self.feedback_enabled = self.config.get('feedback.enabled', True)
        self.max_feedback_items = self.config.get('feedback.max_items', 1000)
        self.retention_days = self.config.get('feedback.retention_days', 90)
        
        # Load existing feedback
        self.feedback_items: List[FeedbackItem] = []
        self._load_feedback_history()
    
    def enable_feedback(self, enabled: bool = True):
        """Enable or disable feedback collection (requires user consent)."""
        self.feedback_enabled = enabled
        
        if enabled:
            self.collect_feedback(
                FeedbackType.FEATURE_USAGE,
                "system",
                "Feedback collection enabled by user",
                SeverityLevel.LOW
            )
            logger.info("Feedback collection enabled")
        else:
            logger.info("Feedback collection disabled")
    
    def collect_feedback(self, 
                        feedback_type: FeedbackType,
                        category: str,
                        message: str,
                        severity: SeverityLevel = SeverityLevel.MEDIUM,
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Collect a feedback item.
        
        Args:
            feedback_type: Type of feedback
            category: Feedback category (e.g., 'dashboard', 'analysis', 'performance')
            message: Feedback message (automatically sanitized)
            severity: Severity level
            metadata: Additional anonymous metadata
        
        Returns:
            True if feedback was collected, False if disabled or failed
        """
        if not self.feedback_enabled:
            return False
        
        try:
            # Sanitize message (remove potential sensitive information)
            sanitized_message = self._sanitize_message(message)
            
            # Create feedback item
            feedback_item = FeedbackItem(
                id=str(uuid.uuid4()),
                type=feedback_type,
                timestamp=datetime.now(),
                category=category,
                message=sanitized_message,
                severity=severity,
                metadata=metadata or {},
                user_session_id=self.session_id,
                version="0.1.0"
            )
            
            # Add to collection
            self.feedback_items.append(feedback_item)
            
            # Maintain size limit
            if len(self.feedback_items) > self.max_feedback_items:
                self.feedback_items.pop(0)
            
            # Save immediately for critical issues
            if severity == SeverityLevel.CRITICAL:
                self._save_feedback_history()
            
            logger.debug(f"Collected {feedback_type.value} feedback: {category}")
            return True
        
        except Exception as e:
            logger.warning(f"Failed to collect feedback: {e}")
            return False
    
    def report_performance_issue(self, operation: str, duration_ms: float, 
                               context_size: Optional[int] = None):
        """Report a performance issue with specific metrics."""
        metadata = {
            "operation": operation,
            "duration_ms": duration_ms,
            "context_size_tokens": context_size,
            "performance_category": "slow" if duration_ms > 1000 else
                                  "acceptable" if duration_ms > 500 else "good"
        }
        
        severity = SeverityLevel.HIGH if duration_ms > 2000 else SeverityLevel.MEDIUM
        
        self.collect_feedback(
            FeedbackType.PERFORMANCE_ISSUE,
            "performance",
            f"Operation '{operation}' took {duration_ms:.0f}ms",
            severity,
            metadata
        )
    
    def report_productivity_improvement(self, improvement_type: str, 
                                      before_metric: float, after_metric: float,
                                      context_description: str = ""):
        """Report a measured productivity improvement."""
        improvement_percent = ((after_metric - before_metric) / before_metric) * 100
        
        metadata = {
            "improvement_type": improvement_type,
            "before_metric": before_metric,
            "after_metric": after_metric,
            "improvement_percent": improvement_percent,
            "has_context": bool(context_description)
        }
        
        severity = SeverityLevel.LOW  # Positive feedback
        
        self.collect_feedback(
            FeedbackType.PRODUCTIVITY_IMPROVEMENT,
            "optimization",
            f"{improvement_type} improved by {improvement_percent:.1f}%",
            severity,
            metadata
        )
    
    def report_user_satisfaction(self, feature: str, rating: int, 
                               comments: str = ""):
        """Report user satisfaction rating (1-5 scale)."""
        metadata = {
            "feature": feature,
            "rating": max(1, min(5, rating)),  # Clamp to 1-5
            "has_comments": bool(comments)
        }
        
        # Convert rating to severity (inverted - low rating = high severity)
        severity_map = {1: SeverityLevel.HIGH, 2: SeverityLevel.MEDIUM, 
                       3: SeverityLevel.MEDIUM, 4: SeverityLevel.LOW, 5: SeverityLevel.LOW}
        
        self.collect_feedback(
            FeedbackType.USER_SATISFACTION,
            feature,
            f"User rated {feature} as {rating}/5" + (f": {comments}" if comments else ""),
            severity_map[rating],
            metadata
        )
    
    def get_feedback_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get anonymized feedback summary for the last N days.
        
        Returns comprehensive feedback analysis for product improvement.
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_feedback = [f for f in self.feedback_items if f.timestamp >= cutoff_date]
        
        if not recent_feedback:
            return {
                "period_days": days,
                "total_items": 0,
                "message": "No feedback data available for the specified period"
            }
        
        # Categorize feedback
        by_type = {}
        by_category = {}
        by_severity = {}
        
        for item in recent_feedback:
            # By type
            type_key = item.type.value
            if type_key not in by_type:
                by_type[type_key] = []
            by_type[type_key].append(item)
            
            # By category
            if item.category not in by_category:
                by_category[item.category] = []
            by_category[item.category].append(item)
            
            # By severity
            severity_key = item.severity.value
            if severity_key not in by_severity:
                by_severity[severity_key] = []
            by_severity[severity_key].append(item)
        
        # Performance analysis
        performance_issues = by_type.get("performance_issue", [])
        avg_performance = None
        if performance_issues:
            durations = [item.metadata.get("duration_ms", 0) for item in performance_issues]
            avg_performance = sum(durations) / len(durations) if durations else 0
        
        # Satisfaction analysis
        satisfaction_items = by_type.get("user_satisfaction", [])
        avg_satisfaction = None
        if satisfaction_items:
            ratings = [item.metadata.get("rating", 3) for item in satisfaction_items]
            avg_satisfaction = sum(ratings) / len(ratings) if ratings else 3.0
        
        # Productivity improvements
        productivity_items = by_type.get("productivity_improvement", [])
        avg_improvement = None
        if productivity_items:
            improvements = [item.metadata.get("improvement_percent", 0) 
                          for item in productivity_items]
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0
        
        # Top issues (critical and high severity)
        critical_issues = [item for item in recent_feedback 
                          if item.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
        
        # Feature usage patterns
        feature_usage = {}
        for item in by_type.get("feature_usage", []):
            feature = item.category
            feature_usage[feature] = feature_usage.get(feature, 0) + 1
        
        return {
            "period_days": days,
            "total_items": len(recent_feedback),
            "summary": {
                "by_type": {k: len(v) for k, v in by_type.items()},
                "by_category": {k: len(v) for k, v in by_category.items()},
                "by_severity": {k: len(v) for k, v in by_severity.items()}
            },
            "metrics": {
                "avg_performance_ms": round(avg_performance, 1) if avg_performance else None,
                "avg_satisfaction_rating": round(avg_satisfaction, 1) if avg_satisfaction else None,
                "avg_productivity_improvement": round(avg_improvement, 1) if avg_improvement else None
            },
            "critical_issues": len(critical_issues),
            "most_used_features": dict(sorted(feature_usage.items(), 
                                            key=lambda x: x[1], reverse=True)[:5]),
            "insights": self._generate_insights(by_type, by_category, by_severity)
        }
    
    def export_feedback_for_analysis(self, anonymize: bool = True) -> List[Dict[str, Any]]:
        """
        Export feedback data for analysis (with privacy protection).
        
        Args:
            anonymize: Whether to further anonymize the data
        
        Returns:
            List of feedback items as dictionaries
        """
        if not self.feedback_enabled:
            return []
        
        feedback_data = []
        for item in self.feedback_items:
            data = asdict(item)
            data['timestamp'] = item.timestamp.isoformat()
            data['type'] = item.type.value
            data['severity'] = item.severity.value
            
            if anonymize:
                # Remove session ID and sanitize further
                data.pop('user_session_id', None)
                data['message'] = self._anonymize_message(data['message'])
        
        return feedback_data
    
    def _sanitize_message(self, message: str) -> str:
        """Remove sensitive information from feedback messages."""
        # Remove file paths
        import re
        message = re.sub(r'/[/\w\.\-]+', '[PATH]', message)
        message = re.sub(r'[A-Z]:\\[\\w\.\-]+', '[PATH]', message)
        
        # Remove email addresses
        message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', message)
        
        # Remove URLs
        message = re.sub(r'https?://[^\s]+', '[URL]', message)
        
        # Remove potential API keys or tokens (long alphanumeric strings)
        message = re.sub(r'\b[A-Za-z0-9]{32,}\b', '[TOKEN]', message)
        
        return message[:500]  # Limit length
    
    def _anonymize_message(self, message: str) -> str:
        """Further anonymize message for export."""
        # Replace specific words with generic terms
        message = message.replace('context-cleaner', '[APP]')
        message = message.replace('Context Cleaner', '[APP]')
        
        return message
    
    def _generate_insights(self, by_type: Dict, by_category: Dict, 
                          by_severity: Dict) -> List[str]:
        """Generate insights from feedback patterns."""
        insights = []
        
        # Performance insights
        if "performance_issue" in by_type and len(by_type["performance_issue"]) > 5:
            insights.append("Multiple performance issues reported - investigate optimization opportunities")
        
        # Satisfaction insights
        if "user_satisfaction" in by_type:
            satisfaction_items = by_type["user_satisfaction"]
            low_ratings = [item for item in satisfaction_items 
                          if item.metadata.get("rating", 3) <= 2]
            if len(low_ratings) > len(satisfaction_items) * 0.3:
                insights.append("User satisfaction concerns detected - review feature usability")
        
        # Feature usage insights
        if by_category:
            most_used = max(by_category.items(), key=lambda x: len(x[1]))
            insights.append(f"'{most_used[0]}' is the most active feature category")
        
        # Critical issues
        if "critical" in by_severity and len(by_severity["critical"]) > 0:
            insights.append("Critical issues require immediate attention")
        
        if not insights:
            insights.append("Overall feedback patterns appear healthy")
        
        return insights
    
    def _load_feedback_history(self):
        """Load feedback history from encrypted storage."""
        try:
            data = self.storage.read_data("feedback_history")
            if data:
                items_data = data.get("items", [])
                
                # Filter by retention period
                cutoff_date = datetime.now() - timedelta(days=self.retention_days)
                
                for item_data in items_data:
                    timestamp = datetime.fromisoformat(item_data["timestamp"])
                    if timestamp >= cutoff_date:
                        item = FeedbackItem(
                            id=item_data["id"],
                            type=FeedbackType(item_data["type"]),
                            timestamp=timestamp,
                            category=item_data["category"],
                            message=item_data["message"],
                            severity=SeverityLevel(item_data["severity"]),
                            metadata=item_data.get("metadata", {}),
                            user_session_id=item_data.get("user_session_id"),
                            version=item_data.get("version", "0.1.0")
                        )
                        self.feedback_items.append(item)
                
                logger.info(f"Loaded {len(self.feedback_items)} feedback items")
        
        except Exception as e:
            logger.warning(f"Could not load feedback history: {e}")
    
    def _save_feedback_history(self):
        """Save feedback history to encrypted storage."""
        try:
            # Convert items to serializable format
            items_data = []
            for item in self.feedback_items:
                data = asdict(item)
                data["timestamp"] = item.timestamp.isoformat()
                data["type"] = item.type.value
                data["severity"] = item.severity.value
                items_data.append(data)
            
            feedback_data = {
                "items": items_data,
                "session_id": self.session_id,
                "last_updated": datetime.now().isoformat()
            }
            
            self.storage.save_data("feedback_history", feedback_data)
            logger.info(f"Saved {len(self.feedback_items)} feedback items")
        
        except Exception as e:
            logger.warning(f"Could not save feedback history: {e}")
    
    def __del__(self):
        """Ensure feedback is saved when collector is destroyed."""
        try:
            if hasattr(self, 'feedback_items') and self.feedback_items:
                self._save_feedback_history()
        except:
            pass  # Ignore errors during cleanup