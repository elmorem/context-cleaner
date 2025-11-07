"""
Context Health Scoring Algorithms

Advanced algorithms for evaluating context health with multiple scoring models
and intelligent weighting based on usage patterns.
"""

import json
import statistics
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from context_cleaner.telemetry.context_rot.config import get_config, ApplicationConfig
from context_cleaner.api.models import create_error_response

logger = logging.getLogger(__name__)


class HealthScoringModel(Enum):
    """Different scoring models for context health."""

    BASIC = "basic"  # Simple size-based scoring
    ADVANCED = "advanced"  # Multi-factor analysis
    ADAPTIVE = "adaptive"  # Learning-based scoring
    PRODUCTIVITY_FOCUSED = "productivity"  # Optimized for productivity metrics


@dataclass
class HealthScore:
    """Comprehensive health score result."""

    overall_score: int  # 0-100 overall health score
    component_scores: Dict[str, int]  # Individual component scores
    confidence: float  # Confidence in the score (0-1)
    model_used: str  # Scoring model used
    factors: Dict[str, Any]  # Detailed scoring factors
    recommendations: List[str]  # Specific improvement suggestions
    timestamp: str  # When score was calculated

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "component_scores": self.component_scores,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "factors": self.factors,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


class ContextHealthScorer:
    """
    Advanced context health scoring with multiple algorithms and adaptive learning.

    Features:
    - Multiple scoring models (basic, advanced, adaptive, productivity-focused)
    - Component-based scoring (size, structure, freshness, complexity)
    - Adaptive weighting based on usage patterns
    - Historical trend analysis for scoring calibration
    - Confidence metrics for score reliability
    """

    def __init__(self, config: Optional[ApplicationConfig] = None):
        """
        Initialize context health scorer.

        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ApplicationConfig.from_env()

        # Scoring model weights - can be adapted based on usage
        self.model_weights = {
            HealthScoringModel.BASIC: {
                "size": 0.6,
                "structure": 0.2,
                "freshness": 0.1,
                "complexity": 0.1,
            },
            HealthScoringModel.ADVANCED: {
                "size": 0.3,
                "structure": 0.3,
                "freshness": 0.2,
                "complexity": 0.2,
            },
            HealthScoringModel.ADAPTIVE: {
                "size": 0.25,
                "structure": 0.25,
                "freshness": 0.25,
                "complexity": 0.25,
            },
            HealthScoringModel.PRODUCTIVITY_FOCUSED: {
                "size": 0.4,
                "structure": 0.4,
                "freshness": 0.15,
                "complexity": 0.05,
            },
        }

        # Historical data for adaptive learning
        self.scoring_history = []
        self.performance_feedback = {}

        # Confidence thresholds
        self.confidence_thresholds = {
            "high": 0.8,  # Very confident in score accuracy
            "medium": 0.6,  # Moderately confident
            "low": 0.4,  # Low confidence - score may be unreliable
        }

    def calculate_health_score(
        self,
        context_data: Dict[str, Any],
        model: HealthScoringModel = HealthScoringModel.ADVANCED,
        include_history: bool = True,
    ) -> HealthScore:
        """
        Calculate comprehensive context health score.

        Args:
            context_data: Context data to score
            model: Scoring model to use
            include_history: Whether to consider historical data

        Returns:
            HealthScore with detailed analysis
        """
        try:
            start_time = time.time()

            # Calculate individual component scores
            component_scores = self._calculate_component_scores(context_data)

            # Apply model-specific weighting
            weights = self.model_weights[model]

            # Adaptive weighting if enabled
            if model == HealthScoringModel.ADAPTIVE and include_history:
                weights = self._adapt_weights(weights, context_data)

            # Calculate weighted overall score
            overall_score = int(
                sum(
                    component_scores[component] * weight
                    for component, weight in weights.items()
                    if component in component_scores
                )
            )

            # Ensure score is within bounds
            overall_score = max(0, min(100, overall_score))

            # Calculate confidence
            confidence = self._calculate_confidence(
                component_scores, context_data, model
            )

            # Generate recommendations
            recommendations = self._generate_health_recommendations(
                overall_score, component_scores, context_data
            )

            # Extract detailed factors
            factors = self._extract_scoring_factors(
                context_data, component_scores, weights
            )

            calculation_time = time.time() - start_time

            result = HealthScore(
                overall_score=overall_score,
                component_scores=component_scores,
                confidence=confidence,
                model_used=model.value,
                factors=factors,
                recommendations=recommendations,
                timestamp=datetime.now().isoformat(),
            )

            # Store for adaptive learning
            self._record_scoring_event(result, calculation_time, context_data)

            logger.debug(
                f"Health score calculated: {overall_score}/100 (confidence: {confidence:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"Health scoring failed: {e}")

            # Return fallback score
            return HealthScore(
                overall_score=50,
                component_scores={"error": 50},
                confidence=0.1,
                model_used=model.value,
                factors={"error": str(e)},
                recommendations=[
                    "Health scoring encountered an error - manual review recommended"
                ],
                timestamp=datetime.now().isoformat(),
            )

    def _calculate_component_scores(
        self, context_data: Dict[str, Any]
    ) -> Dict[str, int]:
        """Calculate scores for individual health components."""
        try:
            scores = {}

            # Size scoring (0-100)
            scores["size"] = self._score_context_size(context_data)

            # Structure scoring (0-100)
            scores["structure"] = self._score_context_structure(context_data)

            # Freshness scoring (0-100)
            scores["freshness"] = self._score_content_freshness(context_data)

            # Complexity scoring (0-100)
            scores["complexity"] = self._score_context_complexity(context_data)

            return scores

        except Exception as e:
            logger.error(f"Component scoring failed: {e}")
            return {"size": 50, "structure": 50, "freshness": 50, "complexity": 50}

    def _score_context_size(self, context_data: Dict[str, Any]) -> int:
        """Score context based on size metrics using enhanced token analysis."""
        try:
            # Try to get actual token count from enhanced analysis first
            estimated_tokens = self._get_enhanced_token_count(context_data)

            if estimated_tokens == 0:
                # Fallback: check if context_data has token metrics directly
                if "token_metrics" in context_data:
                    token_metrics = context_data["token_metrics"]
                    if (
                        isinstance(token_metrics, dict)
                        and "total_tokens" in token_metrics
                    ):
                        estimated_tokens = token_metrics["total_tokens"]
                elif "total_tokens" in context_data:
                    estimated_tokens = context_data.get("total_tokens", 0)
                elif "estimated_tokens" in context_data:
                    estimated_tokens = context_data.get("estimated_tokens", 0)

            # If no actual token data available, return neutral score
            # Following ccusage approach: no crude estimation fallbacks
            if estimated_tokens == 0:
                logger.info(
                    "No token metrics available for context scoring, returning neutral score"
                )
                return 70  # Neutral score when token data unavailable

            # Size-based scoring with diminishing returns (using actual tokens)
            if estimated_tokens < 1000:  # < 1K tokens
                return 100
            elif estimated_tokens < 5000:  # 1-5K tokens
                return 95
            elif estimated_tokens < 10000:  # 5-10K tokens
                return 85
            elif estimated_tokens < 20000:  # 10-20K tokens
                return 75
            elif estimated_tokens < 50000:  # 20-50K tokens
                return 60
            elif estimated_tokens < 100000:  # 50-100K tokens
                return 45
            else:  # > 100K tokens
                # Steep penalty for very large contexts
                excess_tokens = estimated_tokens - 100000
                penalty = min(40, excess_tokens // 10000 * 5)
                return max(5, 40 - penalty)

        except Exception as e:
            logger.error(f"Context size scoring failed: {e}")
            return 50  # Default score on error

    def _get_enhanced_token_count(self, context_data: Dict[str, Any]) -> int:
        """Attempt to get accurate token count using enhanced token analysis."""
        try:
            # Check if this is a session file path
            if isinstance(context_data, dict) and "session_file" in context_data:
                session_file = context_data["session_file"]
                if session_file and isinstance(session_file, str):
                    try:
                        from context_cleaner.analysis.context_window_analyzer import (
                            ContextWindowAnalyzer,
                        )

                        analyzer = ContextWindowAnalyzer(self.config)
                        analysis = analyzer._analyze_session_context(session_file)
                        if analysis and "estimated_tokens" in analysis:
                            return analysis["estimated_tokens"]
                    except Exception as e:
                        logger.debug(
                            f"Enhanced token analysis failed for {session_file}: {e}"
                        )

            # Try to get token count from enhanced token analysis service
            try:
                from context_cleaner.analysis.dashboard_integration import (
                    get_enhanced_token_analysis_sync,
                )

                enhanced_result = get_enhanced_token_analysis_sync()
                if enhanced_result and enhanced_result.get("total_tokens", 0) > 0:
                    # This gives us global token count, but we need specific context data
                    # This is a fallback only if context_data doesn't have specific metrics
                    pass
            except Exception as e:
                logger.debug(f"Global enhanced token analysis failed: {e}")

            return 0  # No enhanced token count available

        except Exception as e:
            logger.error(f"Enhanced token count extraction failed: {e}")
            return 0

    def _get_accurate_token_count(self, content_str: str) -> int:
        """Get accurate token count using ccusage approach."""
        try:
            from context_cleaner.analysis.enhanced_token_counter import (
                get_accurate_token_count,
            )

            return get_accurate_token_count(content_str)
        except ImportError:
            return 0

    def _score_context_structure(self, context_data: Dict[str, Any]) -> int:
        """Score context based on structural quality."""
        try:
            score = 100  # Start with perfect score

            # Analyze structure quality
            if isinstance(context_data, dict):
                # Check for reasonable key distribution
                num_keys = len(context_data)

                if num_keys > 100:
                    score -= 15  # Too many top-level keys
                elif num_keys < 3:
                    score -= 10  # Too few keys (might be under-structured)

                # Check for empty values
                empty_values = sum(1 for v in context_data.values() if not v)
                if empty_values > num_keys * 0.3:
                    score -= 20  # Too many empty values

                # Check for very long string values (unstructured content)
                long_strings = sum(
                    1
                    for v in context_data.values()
                    if isinstance(v, str) and len(v) > 5000
                )
                if long_strings > 0:
                    score -= 15  # Unstructured content penalty

                # Check for balanced nesting
                max_depth = self._calculate_nesting_depth(context_data)
                if max_depth > 8:
                    score -= 10  # Excessive nesting penalty
                elif max_depth < 2:
                    score -= 5  # Might be too flat

            else:
                score = 40  # Non-dict context is poorly structured

            # Check for common structural patterns that indicate good organization
            if isinstance(context_data, dict):
                good_patterns = sum(
                    1
                    for key in context_data.keys()
                    if isinstance(key, str)
                    and any(
                        pattern in key.lower()
                        for pattern in [
                            "timestamp",
                            "id",
                            "type",
                            "status",
                            "config",
                            "data",
                            "metadata",
                        ]
                    )
                )
                if good_patterns > 0:
                    score += min(10, good_patterns * 2)  # Bonus for good patterns

            return max(0, min(100, score))

        except Exception:
            return 60  # Default decent score

    def _score_content_freshness(self, context_data: Dict[str, Any]) -> int:
        """Score context based on content freshness."""
        try:
            # Look for timestamp indicators
            timestamp_keys = [
                "timestamp",
                "created_at",
                "updated_at",
                "last_modified",
                "time",
                "datetime",
                "date",
                "last_update",
            ]

            most_recent_timestamp = None

            def find_timestamps(obj, depth=0):
                nonlocal most_recent_timestamp
                if depth > 5:  # Limit recursion depth
                    return

                if isinstance(obj, dict):
                    for key, value in obj.items():
                        key_lower = key.lower() if isinstance(key, str) else str(key)

                        # Check if this is a timestamp key
                        if any(ts_key in key_lower for ts_key in timestamp_keys):
                            try:
                                if isinstance(value, str):
                                    # Try to parse various timestamp formats
                                    parsed_time = self._parse_timestamp(value)
                                    if parsed_time and (
                                        not most_recent_timestamp
                                        or parsed_time > most_recent_timestamp
                                    ):
                                        most_recent_timestamp = parsed_time
                            except Exception:
                                pass

                        # Recurse into nested structures
                        if isinstance(value, (dict, list)):
                            find_timestamps(value, depth + 1)

                elif isinstance(obj, list):
                    for item in obj[:10]:  # Limit to first 10 items for performance
                        find_timestamps(item, depth + 1)

            find_timestamps(context_data)

            if most_recent_timestamp:
                # Calculate age-based score
                age_hours = (
                    datetime.now() - most_recent_timestamp
                ).total_seconds() / 3600

                if age_hours < 1:
                    return 100  # Very fresh (< 1 hour)
                elif age_hours < 4:
                    return 95  # Fresh (< 4 hours)
                elif age_hours < 12:
                    return 85  # Recent (< 12 hours)
                elif age_hours < 24:
                    return 75  # Daily (< 1 day)
                elif age_hours < 72:
                    return 65  # Recent (< 3 days)
                elif age_hours < 168:
                    return 55  # Weekly (< 1 week)
                elif age_hours < 720:
                    return 45  # Monthly (< 1 month)
                else:
                    return 30  # Old (> 1 month)

            # No clear timestamps found - check for other freshness indicators
            if "session_id" in context_data or "current" in str(context_data).lower():
                return 70  # Appears to be current session data

            return 60  # Default - assume moderately fresh

        except Exception:
            return 60  # Default on error

    def _score_context_complexity(self, context_data: Dict[str, Any]) -> int:
        """Score context based on complexity - lower complexity is better."""
        try:
            # Calculate various complexity metrics
            depth = self._calculate_nesting_depth(context_data)
            breadth = self._calculate_average_breadth(context_data)
            variety = self._calculate_data_type_variety(context_data)

            # Start with base score
            score = 100

            # Depth penalty (excessive nesting is complex)
            if depth > 6:
                score -= (depth - 6) * 8  # 8 points per excessive level

            # Breadth penalty (too many siblings at each level)
            if breadth > 15:
                score -= (breadth - 15) * 2  # 2 points per excessive sibling

            # Variety bonus/penalty (some variety is good, too much is complex)
            if variety < 3:
                score -= 10  # Too homogeneous
            elif variety > 8:
                score -= (variety - 8) * 5  # Too heterogeneous
            else:
                score += 5  # Good variety

            # Check for repetitive patterns (good for complexity)
            repetition_score = self._assess_pattern_repetition(context_data)
            score += repetition_score

            return max(0, min(100, score))

        except Exception:
            return 70  # Default reasonable complexity score

    def _calculate_nesting_depth(self, obj: Any) -> int:
        """Calculate the maximum nesting depth of a data structure."""

        def _depth(o, current_depth=0):
            if current_depth > 20:  # Prevent infinite recursion
                return current_depth

            if isinstance(o, dict):
                return max(
                    [_depth(v, current_depth + 1) for v in o.values()],
                    default=current_depth,
                )
            elif isinstance(o, list):
                return max(
                    [_depth(item, current_depth + 1) for item in o],
                    default=current_depth,
                )
            else:
                return current_depth

        return _depth(obj)

    def _calculate_average_breadth(self, obj: Any) -> float:
        """Calculate the average breadth (number of children) at each level."""
        breadths = []

        def _collect_breadths(o):
            if isinstance(o, dict) and o:
                breadths.append(len(o))
                for v in o.values():
                    _collect_breadths(v)
            elif isinstance(o, list) and o:
                breadths.append(len(o))
                for item in o:
                    _collect_breadths(item)

        _collect_breadths(obj)
        return statistics.mean(breadths) if breadths else 0

    def _calculate_data_type_variety(self, obj: Any) -> int:
        """Calculate the variety of data types present."""
        types_seen = set()

        def _collect_types(o):
            types_seen.add(type(o).__name__)
            if isinstance(o, dict):
                for v in o.values():
                    _collect_types(v)
            elif isinstance(o, list):
                for item in o:
                    _collect_types(item)

        _collect_types(obj)
        return len(types_seen)

    def _assess_pattern_repetition(self, context_data: Dict[str, Any]) -> int:
        """Assess how repetitive/patterned the data is (bonus for good patterns)."""
        try:
            if not isinstance(context_data, dict):
                return 0

            # Look for repeated key patterns
            key_patterns = {}
            for key in context_data.keys():
                if isinstance(key, str):
                    # Extract pattern (e.g., "item_1", "item_2" -> "item_")
                    import re

                    pattern = re.sub(r"\d+", "#", key)
                    key_patterns[pattern] = key_patterns.get(pattern, 0) + 1

            # Bonus for having repeated patterns (indicates structure)
            repeated_patterns = sum(1 for count in key_patterns.values() if count > 1)
            pattern_bonus = min(10, repeated_patterns * 2)

            return pattern_bonus

        except Exception:
            return 0

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse various timestamp formats."""
        try:
            # Common timestamp formats to try
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds and Z
                "%Y-%m-%dT%H:%M:%SZ",  # ISO with Z
                "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
                "%Y-%m-%dT%H:%M:%S",  # ISO basic
                "%Y-%m-%d %H:%M:%S.%f",  # Space separated with microseconds
                "%Y-%m-%d %H:%M:%S",  # Space separated
                "%Y-%m-%d",  # Date only
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue

            # Try fromisoformat for more flexible parsing
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        except Exception:
            return None

    def _adapt_weights(
        self, base_weights: Dict[str, float], context_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Adapt scoring weights based on historical performance and context characteristics."""
        try:
            adapted_weights = base_weights.copy()

            # If we have enough historical data, adjust weights
            if len(self.scoring_history) > 10:
                # Analyze which components correlate best with actual productivity
                correlation_adjustments = self._calculate_component_correlations()

                # Apply adjustments (conservative approach)
                for component, adjustment in correlation_adjustments.items():
                    if component in adapted_weights:
                        adapted_weights[component] *= (
                            1 + adjustment * 0.1
                        )  # Max 10% adjustment

            # Context-specific adjustments
            context_str = json.dumps(context_data, default=str)

            # For very large contexts, emphasize size more
            if len(context_str) > 50000:
                adapted_weights["size"] *= 1.2
                adapted_weights["complexity"] *= 0.8

            # For development contexts, emphasize structure
            if any(
                keyword in context_str.lower()
                for keyword in ["code", "function", "class", "import"]
            ):
                adapted_weights["structure"] *= 1.15
                adapted_weights["freshness"] *= 0.9

            # Normalize weights to sum to 1
            total_weight = sum(adapted_weights.values())
            if total_weight > 0:
                adapted_weights = {
                    k: v / total_weight for k, v in adapted_weights.items()
                }

            return adapted_weights

        except Exception:
            return base_weights  # Return original weights on error

    def _calculate_confidence(
        self,
        component_scores: Dict[str, int],
        context_data: Dict[str, Any],
        model: HealthScoringModel,
    ) -> float:
        """Calculate confidence in the health score."""
        try:
            confidence_factors = []

            # Factor 1: Component score variance (low variance = higher confidence)
            if len(component_scores) > 1:
                variance = statistics.variance(component_scores.values())
                variance_confidence = max(0, 1 - (variance / 1000))  # Normalize
                confidence_factors.append(variance_confidence)

            # Factor 2: Data completeness
            context_str = json.dumps(context_data, default=str)
            if len(context_str) > 100:  # Sufficient data
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.4)  # Low confidence for small data

            # Factor 3: Model appropriateness
            model_confidence = {
                HealthScoringModel.BASIC: 0.6,
                HealthScoringModel.ADVANCED: 0.8,
                HealthScoringModel.ADAPTIVE: (
                    0.9 if len(self.scoring_history) > 5 else 0.6
                ),
                HealthScoringModel.PRODUCTIVITY_FOCUSED: 0.7,
            }.get(model, 0.5)
            confidence_factors.append(model_confidence)

            # Factor 4: Historical validation (if available)
            if len(self.scoring_history) > 3:
                # Check consistency with recent scores
                recent_scores = [h["overall_score"] for h in self.scoring_history[-3:]]
                current_score = int(statistics.mean(component_scores.values()))

                consistency = (
                    1 - abs(statistics.mean(recent_scores) - current_score) / 100
                )
                confidence_factors.append(max(0.3, consistency))

            # Calculate overall confidence
            overall_confidence = statistics.mean(confidence_factors)

            return max(0.1, min(1.0, overall_confidence))

        except Exception:
            return 0.5  # Default medium confidence

    def _generate_health_recommendations(
        self,
        overall_score: int,
        component_scores: Dict[str, int],
        context_data: Dict[str, Any],
    ) -> List[str]:
        """Generate specific recommendations based on health scores."""
        try:
            recommendations = []

            # Overall score recommendations
            if overall_score < 50:
                recommendations.append(
                    "Context health is poor - consider significant cleanup or restart"
                )
            elif overall_score < 70:
                recommendations.append(
                    "Context health is fair - optimization recommended"
                )
            elif overall_score > 90:
                recommendations.append(
                    "Excellent context health - maintain current practices"
                )

            # Component-specific recommendations
            if component_scores.get("size", 100) < 60:
                recommendations.append(
                    "Context size is large - consider removing unnecessary data or splitting into smaller contexts"
                )

            if component_scores.get("structure", 100) < 60:
                recommendations.append(
                    "Context structure could be improved - organize data more clearly"
                )

            if component_scores.get("freshness", 100) < 60:
                recommendations.append(
                    "Context contains outdated information - refresh with recent data"
                )

            if component_scores.get("complexity", 100) < 60:
                recommendations.append(
                    "Context is overly complex - simplify data structures where possible"
                )

            # Data-specific recommendations
            context_str = json.dumps(context_data, default=str)

            if len(context_str) > 100000:
                recommendations.append(
                    "Very large context detected - consider chunking or summarization"
                )

            if '"error"' in context_str.lower() or '"exception"' in context_str.lower():
                recommendations.append(
                    "Error information detected - resolve issues for better context health"
                )

            # Ensure we always have at least one recommendation
            if not recommendations:
                if overall_score > 80:
                    recommendations.append(
                        "Context health is good - continue current practices"
                    )
                else:
                    recommendations.append(
                        "Consider general context cleanup and optimization"
                    )

            return recommendations[:5]  # Limit to top 5 recommendations

        except Exception:
            return [
                "Unable to generate specific recommendations - manual review suggested"
            ]

    def _extract_scoring_factors(
        self,
        context_data: Dict[str, Any],
        component_scores: Dict[str, int],
        weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """Extract detailed factors that influenced the scoring."""
        try:
            context_str = json.dumps(context_data, default=str)

            return {
                "data_size_bytes": len(context_str.encode("utf-8")),
                "estimated_tokens": self._get_accurate_token_count(context_str),
                "nesting_depth": self._calculate_nesting_depth(context_data),
                "top_level_keys": (
                    len(context_data) if isinstance(context_data, dict) else 0
                ),
                "weights_used": weights,
                "component_contributions": {
                    component: score * weight
                    for component, score in component_scores.items()
                    for component_w, weight in weights.items()
                    if component == component_w
                },
                "scoring_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            raise create_error_response(
                "Unable to extract scoring factors",
                "SCORING_FACTORS_EXTRACTION_ERROR",
                500,
            )

    def _record_scoring_event(
        self, result: HealthScore, calculation_time: float, context_data: Dict[str, Any]
    ):
        """Record scoring event for learning and analytics."""
        try:
            event = {
                "overall_score": result.overall_score,
                "component_scores": result.component_scores,
                "model_used": result.model_used,
                "confidence": result.confidence,
                "calculation_time": calculation_time,
                "context_size": len(json.dumps(context_data, default=str)),
                "timestamp": result.timestamp,
            }

            self.scoring_history.append(event)

            # Limit history size
            if len(self.scoring_history) > 100:
                self.scoring_history = self.scoring_history[-50:]  # Keep most recent 50

        except Exception as e:
            logger.debug(f"Failed to record scoring event: {e}")

    def _calculate_component_correlations(self) -> Dict[str, float]:
        """Calculate which components correlate with good outcomes."""
        try:
            if len(self.scoring_history) < 10:
                return {}

            # For now, return neutral adjustments
            # In a full implementation, this would analyze actual productivity outcomes
            return {"size": 0.0, "structure": 0.0, "freshness": 0.0, "complexity": 0.0}

        except Exception:
            return {}

    def get_scoring_analytics(self) -> Dict[str, Any]:
        """Get analytics about scoring performance and trends."""
        try:
            if not self.scoring_history:
                return {"status": "no_data", "message": "No scoring history available"}

            scores = [h["overall_score"] for h in self.scoring_history]
            confidences = [h["confidence"] for h in self.scoring_history]

            return {
                "history_count": len(self.scoring_history),
                "score_statistics": {
                    "mean": statistics.mean(scores),
                    "median": statistics.median(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0,
                },
                "confidence_statistics": {
                    "mean": statistics.mean(confidences),
                    "high_confidence_percentage": sum(1 for c in confidences if c > 0.8)
                    / len(confidences)
                    * 100,
                },
                "model_usage": {
                    model: sum(
                        1 for h in self.scoring_history if h["model_used"] == model
                    )
                    for model in ["basic", "advanced", "adaptive", "productivity"]
                },
                "trends": {
                    "recent_average": (
                        statistics.mean(scores[-10:])
                        if len(scores) >= 10
                        else statistics.mean(scores)
                    ),
                    "trend_direction": (
                        "improving"
                        if len(scores) > 5
                        and statistics.mean(scores[-5:]) > statistics.mean(scores[:5])
                        else "stable"
                    ),
                },
            }

        except Exception as e:
            return {"status": "error", "message": f"Analytics calculation failed: {e}"}
