"""
Performance Feedback Integration

Integrates the user feedback collection system with memory and CPU optimizers
to automatically track performance improvements and user satisfaction.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from .user_feedback_collector import UserFeedbackCollector
from .feedback_collector import FeedbackCollector, FeedbackType, SeverityLevel
from ..optimization.memory_optimizer import MemoryOptimizer
from ..optimization.cpu_optimizer import CPUOptimizer, TaskPriority
from ..config.settings import ContextCleanerConfig

logger = logging.getLogger(__name__)


class PerformanceFeedbackIntegration:
    """
    Integrates feedback collection with performance monitoring to automatically
    track optimization effectiveness and user experience improvements.
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """Initialize performance feedback integration."""
        self.config = config or ContextCleanerConfig.from_env()
        
        # Feedback collectors
        self.user_feedback = UserFeedbackCollector(config)
        self.structured_feedback = FeedbackCollector(config)
        
        # Performance optimizers (optional - may be provided externally)
        self._memory_optimizer: Optional[MemoryOptimizer] = None
        self._cpu_optimizer: Optional[CPUOptimizer] = None
        
        # Performance tracking
        self._performance_baselines: Dict[str, Any] = {}
        self._optimization_history: List[Dict[str, Any]] = []
        
        # Monitoring state
        self._is_monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        logger.info("Performance feedback integration initialized")
    
    def connect_optimizers(self, memory_optimizer: MemoryOptimizer, 
                          cpu_optimizer: CPUOptimizer):
        """Connect performance optimizers for automatic feedback collection."""
        self._memory_optimizer = memory_optimizer
        self._cpu_optimizer = cpu_optimizer
        
        # Set baselines
        self._set_performance_baselines()
        
        logger.info("Connected performance optimizers to feedback system")
    
    def start_integrated_monitoring(self):
        """Start integrated performance and feedback monitoring."""
        # Start individual feedback systems
        self.user_feedback.start_monitoring()
        
        # Start integrated monitoring
        if not self._is_monitoring:
            self._is_monitoring = True
            self._stop_monitoring.clear()
            
            self._monitor_thread = threading.Thread(
                target=self._integrated_monitoring_loop,
                daemon=True,
                name="PerformanceFeedbackIntegration"
            )
            self._monitor_thread.start()
        
        logger.info("Integrated performance feedback monitoring started")
    
    def stop_integrated_monitoring(self):
        """Stop integrated monitoring."""
        # Stop individual systems
        self.user_feedback.stop_monitoring()
        
        # Stop integrated monitoring
        if self._is_monitoring:
            self._is_monitoring = False
            self._stop_monitoring.set()
            
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5.0)
        
        logger.info("Integrated performance feedback monitoring stopped")
    
    def _integrated_monitoring_loop(self):
        """Main integrated monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                # Collect performance metrics if optimizers are connected
                if self._memory_optimizer and self._cpu_optimizer:
                    self._collect_performance_feedback()
                
                # Analyze optimization effectiveness
                self._analyze_optimization_effectiveness()
                
                # Sleep for 10 minutes between collections
                self._stop_monitoring.wait(timeout=600)
                
            except Exception as e:
                logger.warning(f"Integrated monitoring error: {e}")
                self._stop_monitoring.wait(timeout=900)  # 15 min on error
    
    def _set_performance_baselines(self):
        """Set performance baselines for comparison."""
        if not (self._memory_optimizer and self._cpu_optimizer):
            return
        
        try:
            # Memory baseline
            memory_report = self._memory_optimizer.get_memory_report()
            memory_baseline = {
                'memory_mb': memory_report['current']['process_mb'],
                'health_score': memory_report['current']['health_score'],
                'cache_memory_mb': memory_report['caches']['total_memory_mb'],
                'timestamp': datetime.now()
            }
            
            # CPU baseline
            cpu_report = self._cpu_optimizer.get_performance_report()
            cpu_baseline = {
                'cpu_percent': cpu_report['summary']['current_cpu_percent'],
                'health_score': cpu_report['summary']['health_score'],
                'pending_tasks': cpu_report['scheduler']['scheduling']['total_pending_tasks'],
                'timestamp': datetime.now()
            }
            
            self._performance_baselines = {
                'memory': memory_baseline,
                'cpu': cpu_baseline,
                'established_at': datetime.now()
            }
            
            # Record baseline establishment
            self.user_feedback.record_feature_usage(
                'performance_baseline_established',
                success=True,
                memory_mb=memory_baseline['memory_mb'],
                cpu_percent=cpu_baseline['cpu_percent']
            )
            
            logger.info("Performance baselines established")
            
        except Exception as e:
            logger.warning(f"Failed to set performance baselines: {e}")
    
    def _collect_performance_feedback(self):
        """Collect current performance feedback compared to baselines."""
        if not self._performance_baselines:
            self._set_performance_baselines()
            return
        
        try:
            # Get current performance
            memory_report = self._memory_optimizer.get_memory_report()
            cpu_report = self._cpu_optimizer.get_performance_report()
            
            current_memory_mb = memory_report['current']['process_mb']
            current_cpu_percent = cpu_report['summary']['current_cpu_percent']
            
            # Compare with baselines
            baseline_memory = self._performance_baselines['memory']['memory_mb']
            baseline_cpu = self._performance_baselines['cpu']['cpu_percent']
            
            memory_improvement = baseline_memory - current_memory_mb
            cpu_improvement = baseline_cpu - current_cpu_percent
            
            # Record significant improvements or degradations
            if abs(memory_improvement) > 5:  # >5MB change
                improvement_type = "memory_optimization" if memory_improvement > 0 else "memory_regression"
                
                self.user_feedback.record_feature_usage(
                    improvement_type,
                    success=memory_improvement > 0,
                    memory_change_mb=memory_improvement,
                    current_memory_mb=current_memory_mb,
                    baseline_memory_mb=baseline_memory
                )
                
                # Also record in structured feedback
                severity = SeverityLevel.LOW if memory_improvement > 0 else SeverityLevel.MEDIUM
                self.structured_feedback.collect_feedback(
                    FeedbackType.PERFORMANCE_ISSUE if memory_improvement < 0 else FeedbackType.PRODUCTIVITY_IMPROVEMENT,
                    "memory",
                    f"Memory usage {'improved' if memory_improvement > 0 else 'increased'} by {abs(memory_improvement):.1f}MB",
                    severity,
                    {
                        'memory_change_mb': memory_improvement,
                        'current_mb': current_memory_mb,
                        'baseline_mb': baseline_memory
                    }
                )
            
            # Similar logic for CPU
            if abs(cpu_improvement) > 1:  # >1% change
                improvement_type = "cpu_optimization" if cpu_improvement > 0 else "cpu_regression"
                
                self.user_feedback.record_feature_usage(
                    improvement_type,
                    success=cpu_improvement > 0,
                    cpu_change_percent=cpu_improvement,
                    current_cpu_percent=current_cpu_percent,
                    baseline_cpu_percent=baseline_cpu
                )
                
                # Structured feedback
                severity = SeverityLevel.LOW if cpu_improvement > 0 else SeverityLevel.MEDIUM
                self.structured_feedback.collect_feedback(
                    FeedbackType.PERFORMANCE_ISSUE if cpu_improvement < 0 else FeedbackType.PRODUCTIVITY_IMPROVEMENT,
                    "cpu",
                    f"CPU usage {'improved' if cpu_improvement > 0 else 'increased'} by {abs(cpu_improvement):.1f}%",
                    severity,
                    {
                        'cpu_change_percent': cpu_improvement,
                        'current_percent': current_cpu_percent,
                        'baseline_percent': baseline_cpu
                    }
                )
        
        except Exception as e:
            logger.debug(f"Performance feedback collection failed: {e}")
    
    def _analyze_optimization_effectiveness(self):
        """Analyze the effectiveness of optimizations over time."""
        try:
            # Get recent feedback summary
            user_summary = self.user_feedback.get_feedback_summary()
            structured_summary = self.structured_feedback.get_feedback_summary(days=7)
            
            # Calculate overall optimization effectiveness
            total_improvements = (
                structured_summary['summary']['by_type'].get('productivity_improvement', 0) +
                user_summary.get('performance_impact', {}).get('measurements_count', 0)
            )
            
            total_issues = (
                structured_summary['summary']['by_type'].get('performance_issue', 0) +
                structured_summary['critical_issues']
            )
            
            if total_improvements + total_issues > 10:  # Enough data for analysis
                effectiveness_ratio = total_improvements / (total_improvements + total_issues)
                
                if effectiveness_ratio > 0.8:
                    # High effectiveness
                    self.structured_feedback.collect_feedback(
                        FeedbackType.PRODUCTIVITY_IMPROVEMENT,
                        "optimization_effectiveness",
                        f"Optimization system highly effective: {effectiveness_ratio:.1%} positive outcomes",
                        SeverityLevel.LOW,
                        {
                            'effectiveness_ratio': effectiveness_ratio,
                            'total_improvements': total_improvements,
                            'total_issues': total_issues
                        }
                    )
                
                elif effectiveness_ratio < 0.5:
                    # Low effectiveness - needs attention
                    self.structured_feedback.collect_feedback(
                        FeedbackType.PERFORMANCE_ISSUE,
                        "optimization_effectiveness",
                        f"Optimization system needs tuning: {effectiveness_ratio:.1%} positive outcomes",
                        SeverityLevel.MEDIUM,
                        {
                            'effectiveness_ratio': effectiveness_ratio,
                            'total_improvements': total_improvements,
                            'total_issues': total_issues
                        }
                    )
        
        except Exception as e:
            logger.debug(f"Optimization effectiveness analysis failed: {e}")
    
    @contextmanager
    def track_operation(self, operation_name: str, expected_improvement: str = None):
        """
        Context manager to track performance of specific operations.
        
        Args:
            operation_name: Name of the operation being tracked
            expected_improvement: Expected type of improvement (memory, cpu, both)
        """
        start_time = time.perf_counter()
        start_metrics = {}
        
        # Capture starting metrics if optimizers available
        if self._memory_optimizer and self._cpu_optimizer:
            try:
                memory_report = self._memory_optimizer.get_memory_report()
                cpu_report = self._cpu_optimizer.get_performance_report()
                
                start_metrics = {
                    'memory_mb': memory_report['current']['process_mb'],
                    'cpu_percent': cpu_report['summary']['current_cpu_percent'],
                    'timestamp': datetime.now()
                }
            except Exception as e:
                logger.debug(f"Failed to capture start metrics: {e}")
        
        try:
            yield
            
            # Success path
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            
            # Capture end metrics
            end_metrics = {}
            if self._memory_optimizer and self._cpu_optimizer and start_metrics:
                try:
                    memory_report = self._memory_optimizer.get_memory_report()
                    cpu_report = self._cpu_optimizer.get_performance_report()
                    
                    end_metrics = {
                        'memory_mb': memory_report['current']['process_mb'],
                        'cpu_percent': cpu_report['summary']['current_cpu_percent'],
                        'timestamp': datetime.now()
                    }
                    
                    # Record optimization impact
                    self.user_feedback.record_optimization_impact(
                        operation_name,
                        start_metrics,
                        end_metrics
                    )
                    
                except Exception as e:
                    logger.debug(f"Failed to capture end metrics: {e}")
            
            # Record successful operation
            self.user_feedback.record_feature_usage(
                operation_name,
                success=True,
                duration_ms=duration_ms,
                expected_improvement=expected_improvement
            )
            
            # Performance feedback based on duration
            if duration_ms > 5000:  # >5 seconds
                self.structured_feedback.report_performance_issue(
                    operation_name,
                    duration_ms
                )
            
        except Exception as e:
            # Error path
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            
            self.user_feedback.record_feature_usage(
                operation_name,
                success=False,
                duration_ms=duration_ms,
                error_type=type(e).__name__
            )
            
            self.user_feedback.record_error(
                f"{operation_name}_failed",
                str(e)[:100]  # Truncated error context
            )
            
            raise  # Re-raise the exception
    
    def get_comprehensive_feedback_report(self) -> Dict[str, Any]:
        """Get comprehensive feedback report combining all feedback sources."""
        try:
            user_summary = self.user_feedback.get_feedback_summary()
            structured_summary = self.structured_feedback.get_feedback_summary(days=7)
            
            # Performance trends
            performance_trend = "stable"
            if self._performance_baselines:
                baseline_age = (datetime.now() - self._performance_baselines['established_at']).days
                
                if baseline_age > 7:  # At least a week of data
                    improvements = structured_summary['summary']['by_type'].get('productivity_improvement', 0)
                    issues = structured_summary['summary']['by_type'].get('performance_issue', 0)
                    
                    if improvements > issues * 2:
                        performance_trend = "improving"
                    elif issues > improvements * 2:
                        performance_trend = "declining"
            
            # User experience metrics
            satisfaction_metrics = {}
            if 'performance_impact' in user_summary:
                perf_impact = user_summary['performance_impact']
                satisfaction_metrics = {
                    'avg_memory_saved_mb': perf_impact.get('avg_memory_saved_mb', 0),
                    'avg_cpu_improvement_percent': perf_impact.get('avg_cpu_improvement_percent', 0),
                    'total_optimizations': perf_impact.get('measurements_count', 0)
                }
            
            return {
                'reporting_period_days': 7,
                'timestamp': datetime.now().isoformat(),
                'performance_trend': performance_trend,
                'user_feedback_summary': user_summary,
                'structured_feedback_summary': structured_summary,
                'satisfaction_metrics': satisfaction_metrics,
                'optimization_effectiveness': {
                    'total_improvements': structured_summary['summary']['by_type'].get('productivity_improvement', 0),
                    'total_issues': structured_summary['summary']['by_type'].get('performance_issue', 0),
                    'critical_issues': structured_summary['critical_issues']
                },
                'recommendations': self._generate_performance_recommendations(
                    user_summary, 
                    structured_summary
                )
            }
            
        except Exception as e:
            logger.warning(f"Failed to generate comprehensive feedback report: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _generate_performance_recommendations(self, user_summary: Dict[str, Any], 
                                           structured_summary: Dict[str, Any]) -> List[str]:
        """Generate performance recommendations based on feedback."""
        recommendations = []
        
        try:
            # Check for performance issues
            perf_issues = structured_summary['summary']['by_type'].get('performance_issue', 0)
            if perf_issues > 5:
                recommendations.append(
                    f"Multiple performance issues detected ({perf_issues}). "
                    "Consider reviewing optimization thresholds."
                )
            
            # Check satisfaction
            avg_satisfaction = structured_summary.get('metrics', {}).get('avg_satisfaction_rating')
            if avg_satisfaction and avg_satisfaction < 3.5:
                recommendations.append(
                    f"User satisfaction below target ({avg_satisfaction:.1f}/5). "
                    "Review feature usability and performance."
                )
            
            # Check effectiveness
            improvements = structured_summary['summary']['by_type'].get('productivity_improvement', 0)
            if improvements == 0 and structured_summary['total_items'] > 10:
                recommendations.append(
                    "No productivity improvements recorded. "
                    "Optimization system may need tuning."
                )
            
            # Positive feedback
            if perf_issues < 2 and improvements > 5:
                recommendations.append(
                    "Optimization system performing well. "
                    "Continue current monitoring approach."
                )
            
            # Default
            if not recommendations:
                recommendations.append(
                    "Feedback data insufficient for specific recommendations. "
                    "Continue monitoring for trends."
                )
        
        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")
        
        return recommendations
    
    def export_performance_data(self, anonymize: bool = True) -> Dict[str, Any]:
        """Export all performance feedback data for analysis."""
        return {
            'user_feedback_data': self.user_feedback.get_feedback_summary(),
            'structured_feedback_data': self.structured_feedback.export_feedback_for_analysis(anonymize),
            'performance_baselines': self._performance_baselines if not anonymize else {},
            'export_timestamp': datetime.now().isoformat(),
            'privacy_level': 'anonymous' if anonymize else 'detailed'
        }