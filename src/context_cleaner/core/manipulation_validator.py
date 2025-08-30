#!/usr/bin/env python3
"""
Manipulation Validation Engine

Provides validation and safety checks for context manipulation operations:
- Pre-execution validation (safety checks, impact analysis)
- Post-execution validation (integrity verification, rollback detection)
- Operation impact assessment (token changes, content preservation)
- Safety constraint enforcement (limits, confidence thresholds)

Integrated with ManipulationEngine to ensure safe operation execution.
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from copy import deepcopy

from .manipulation_engine import ManipulationOperation, ManipulationPlan

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation checks."""
    
    is_valid: bool  # Whether operation/plan passes validation
    confidence_score: float  # Overall confidence in safety (0-1)
    validation_errors: List[str]  # Specific validation errors
    warnings: List[str]  # Non-blocking warnings
    safety_recommendations: List[str]  # Recommended safety measures
    risk_assessment: str  # low, medium, high
    validation_timestamp: str  # When validation was performed


@dataclass
class IntegrityCheck:
    """Result of content integrity verification."""
    
    integrity_maintained: bool  # Whether content integrity is preserved
    critical_content_preserved: bool  # Whether critical content remains
    token_count_accurate: bool  # Whether token estimates are accurate
    structure_preserved: bool  # Whether data structure is preserved
    errors_detected: List[str]  # Integrity errors found
    

class ManipulationValidator:
    """
    Validation Engine for Context Manipulation Operations
    
    Provides comprehensive safety and integrity checks for manipulation operations.
    """
    
    # Validation thresholds
    MIN_SAFE_CONFIDENCE = 0.7  # Minimum confidence for safe execution
    MAX_SINGLE_OPERATION_IMPACT = 0.3  # Max 30% of content in single operation
    MAX_TOTAL_REDUCTION = 0.8  # Max 80% total content reduction
    CRITICAL_CONTENT_THRESHOLD = 0.1  # Must preserve at least 10% as critical
    
    # Content type risk levels
    HIGH_RISK_PATTERNS = [
        r"\bpassword\b|\bsecret\b|\bapi[_-]?key\b|\btoken\b|\bcredential\b",  # Security sensitive (word boundaries)
        r"\bcritical\b|\bimportant\b|\burgent\b|\bpriority\b",  # Business critical
        r"\bbackup\b|\brestore\b|\brecovery\b",  # Data recovery
        r"\bconfig\b|\bsetting\b|\bparameter\b"  # Configuration
    ]
    
    MEDIUM_RISK_PATTERNS = [
        r"todo|task|action",  # Work items
        r"conversation|message|chat",  # Communications
        r"file|document|code"  # Content files
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize validation engine with safety configuration."""
        self.config = config or {}
        
        # Safety thresholds (configurable)
        self.min_confidence = self.config.get('min_confidence', self.MIN_SAFE_CONFIDENCE)
        self.max_operation_impact = self.config.get('max_operation_impact', self.MAX_SINGLE_OPERATION_IMPACT)
        self.max_total_reduction = self.config.get('max_total_reduction', self.MAX_TOTAL_REDUCTION)
        
        logger.info("ManipulationValidator initialized with safety constraints")

    def _assess_content_risk(self, content: str) -> str:
        """Assess risk level of content being modified."""
        import re
        
        content_lower = content.lower()
        
        # Check for high-risk patterns
        for pattern in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, content_lower):
                return "high"
        
        # Check for medium-risk patterns  
        for pattern in self.MEDIUM_RISK_PATTERNS:
            if re.search(pattern, content_lower):
                return "medium"
        
        return "low"

    def _calculate_content_importance(self, key: str, content: Any) -> float:
        """Calculate importance score of content (0-1, higher = more important)."""
        try:
            content_str = str(content).lower()
            importance_score = 0.5  # Base importance
            
            # Boost importance for certain key patterns
            if any(pattern in key.lower() for pattern in ['config', 'setting', 'critical', 'important']):
                importance_score += 0.3
            
            # Boost for certain content patterns
            if 'critical' in content_str or 'important' in content_str:
                importance_score += 0.2
            
            # Reduce importance for obviously redundant content
            if 'duplicate' in content_str or 'completed' in content_str:
                importance_score -= 0.3
            
            # Length-based importance (longer content often more important)
            content_length = len(content_str)
            if content_length > 1000:
                importance_score += 0.1
            elif content_length < 50:
                importance_score -= 0.1
            
            return max(0.0, min(1.0, importance_score))
            
        except Exception as e:
            logger.warning(f"Error calculating content importance: {e}")
            return 0.5  # Default medium importance

    def validate_operation(
        self, 
        operation: ManipulationOperation,
        context_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a single manipulation operation."""
        validation_start = datetime.now()
        
        try:
            errors = []
            warnings = []
            recommendations = []
            risk_levels = []
            
            # Basic operation validation
            if not operation.target_keys:
                errors.append("Operation has no target keys specified")
            
            if operation.confidence_score < 0 or operation.confidence_score > 1:
                errors.append(f"Invalid confidence score: {operation.confidence_score}")
            
            # Validate target keys exist
            missing_keys = [key for key in operation.target_keys if key not in context_data]
            if missing_keys:
                errors.append(f"Target keys not found in context: {missing_keys}")
            
            # Calculate operation impact
            total_context_tokens = sum(
                len(str(value)) // 4 for value in context_data.values()
            )
            
            if total_context_tokens > 0:
                operation_impact_ratio = abs(operation.estimated_token_impact) / total_context_tokens
                if operation_impact_ratio > self.max_operation_impact:
                    errors.append(
                        f"Operation impact {operation_impact_ratio:.1%} exceeds maximum allowed {self.max_operation_impact:.1%}"
                    )
            
            # Confidence threshold check
            if operation.confidence_score < self.min_confidence:
                warnings.append(
                    f"Operation confidence {operation.confidence_score:.2f} below recommended threshold {self.min_confidence:.2f}"
                )
                recommendations.append("Consider requiring user confirmation for this operation")
            
            # Assess risk for each target key
            for key in operation.target_keys:
                if key in context_data:
                    content_risk = self._assess_content_risk(str(context_data[key]))
                    risk_levels.append(content_risk)
                    
                    if content_risk == "high":
                        recommendations.append(f"High-risk content detected in key '{key}' - recommend backup before modification")
                    
                    # Check content importance
                    importance = self._calculate_content_importance(key, context_data[key])
                    if importance > 0.8 and operation.operation_type == "remove":
                        warnings.append(f"Removing high-importance content from key '{key}'")
            
            # Operation-specific validation
            if operation.operation_type == "remove":
                if len(operation.target_keys) > 10:
                    warnings.append(f"Removing large number of items ({len(operation.target_keys)}) in single operation")
            
            elif operation.operation_type == "consolidate":
                if len(operation.target_keys) > 5:
                    warnings.append(f"Consolidating large number of items ({len(operation.target_keys)})")
                    
            elif operation.operation_type == "summarize":
                # Summarization is always risky as it can lose information
                warnings.append("Summarization may result in information loss")
                recommendations.append("Review summarized content carefully")
            
            # Overall risk assessment
            if "high" in risk_levels or len(errors) > 0:
                overall_risk = "high"
            elif "medium" in risk_levels or len(warnings) > 2:
                overall_risk = "medium"  
            else:
                overall_risk = "low"
            
            # Calculate overall confidence
            confidence_factors = [
                operation.confidence_score,
                1.0 - (len(errors) * 0.3),  # Reduce confidence for errors
                1.0 - (len(warnings) * 0.1),  # Slightly reduce for warnings
                0.9 if overall_risk == "low" else 0.7 if overall_risk == "medium" else 0.5
            ]
            overall_confidence = max(0.0, min(1.0, sum(confidence_factors) / len(confidence_factors)))
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                confidence_score=overall_confidence,
                validation_errors=errors,
                warnings=warnings,
                safety_recommendations=recommendations,
                risk_assessment=overall_risk,
                validation_timestamp=validation_start.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Operation validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                validation_errors=[f"Validation error: {e}"],
                warnings=[],
                safety_recommendations=["Manual review required due to validation failure"],
                risk_assessment="high",
                validation_timestamp=validation_start.isoformat()
            )

    def validate_plan(
        self,
        plan: ManipulationPlan,
        context_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate entire manipulation plan."""
        validation_start = datetime.now()
        
        try:
            all_errors = []
            all_warnings = []
            all_recommendations = []
            risk_levels = []
            confidence_scores = []
            
            # Basic plan validation
            if not plan.operations:
                all_errors.append("Plan contains no operations")
            
            if plan.total_operations != len(plan.operations):
                all_warnings.append(f"Plan operation count mismatch: claimed {plan.total_operations}, actual {len(plan.operations)}")
            
            # Validate total impact
            total_context_tokens = sum(len(str(v)) // 4 for v in context_data.values())
            if total_context_tokens > 0:
                total_reduction_ratio = plan.estimated_total_reduction / total_context_tokens
                if total_reduction_ratio > self.max_total_reduction:
                    all_errors.append(
                        f"Total reduction {total_reduction_ratio:.1%} exceeds maximum allowed {self.max_total_reduction:.1%}"
                    )
            
            # Validate individual operations
            all_target_keys = set()
            operation_conflicts = []
            
            for i, operation in enumerate(plan.operations):
                # Validate individual operation
                op_validation = self.validate_operation(operation, context_data)
                
                all_errors.extend([f"Op {i+1}: {error}" for error in op_validation.validation_errors])
                all_warnings.extend([f"Op {i+1}: {warning}" for warning in op_validation.warnings])
                all_recommendations.extend(op_validation.safety_recommendations)
                
                risk_levels.append(op_validation.risk_assessment)
                confidence_scores.append(op_validation.confidence_score)
                
                # Check for conflicts between operations
                operation_keys = set(operation.target_keys)
                conflicting_keys = operation_keys & all_target_keys
                if conflicting_keys:
                    operation_conflicts.append(f"Operations {i+1} conflicts with previous operations on keys: {conflicting_keys}")
                
                all_target_keys.update(operation_keys)
            
            if operation_conflicts:
                all_errors.extend(operation_conflicts)
            
            # Check for critical content preservation
            critical_content_ratio = len(context_data) - len(all_target_keys)
            if critical_content_ratio < len(context_data) * self.CRITICAL_CONTENT_THRESHOLD:
                all_errors.append("Plan may remove too much critical content")
                all_recommendations.append("Ensure critical content is preserved")
            
            # Plan-level risk assessment
            if "high" in risk_levels or len(all_errors) > 0:
                overall_risk = "high"
            elif "medium" in risk_levels or len(all_warnings) > 5:
                overall_risk = "medium"
            else:
                overall_risk = "low"
            
            # Overall confidence calculation
            if confidence_scores:
                avg_confidence = sum(confidence_scores) / len(confidence_scores)
            else:
                avg_confidence = 0.0
            
            # Adjust for plan-level factors
            confidence_adjustments = [
                -0.1 * len(all_errors),  # Reduce for errors
                -0.05 * len(all_warnings),  # Slightly reduce for warnings
                -0.1 if overall_risk == "high" else -0.05 if overall_risk == "medium" else 0,
                -0.1 if len(plan.operations) > 20 else 0  # Reduce confidence for very complex plans
            ]
            
            overall_confidence = max(0.0, avg_confidence + sum(confidence_adjustments))
            
            # Add plan-level recommendations
            if len(plan.operations) > 10:
                all_recommendations.append("Consider executing plan in smaller batches")
            
            if plan.requires_user_approval:
                all_recommendations.append("Plan requires user approval - review all operations carefully")
            
            return ValidationResult(
                is_valid=len(all_errors) == 0,
                confidence_score=overall_confidence,
                validation_errors=all_errors,
                warnings=all_warnings,
                safety_recommendations=list(set(all_recommendations)),  # Remove duplicates
                risk_assessment=overall_risk,
                validation_timestamp=validation_start.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Plan validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                validation_errors=[f"Plan validation error: {e}"],
                warnings=[],
                safety_recommendations=["Manual review required due to validation failure"],
                risk_assessment="high",
                validation_timestamp=validation_start.isoformat()
            )

    def verify_integrity(
        self,
        original_context: Dict[str, Any],
        modified_context: Dict[str, Any],
        executed_operations: List[ManipulationOperation]
    ) -> IntegrityCheck:
        """Verify integrity after manipulation operations."""
        try:
            errors = []
            
            # Basic structure validation
            if not isinstance(modified_context, dict):
                errors.append("Modified context is not a dictionary")
                return IntegrityCheck(
                    integrity_maintained=False,
                    critical_content_preserved=False,
                    token_count_accurate=False,
                    structure_preserved=False,
                    errors_detected=errors
                )
            
            # Calculate token counts
            original_tokens = sum(len(str(v)) // 4 for v in original_context.values())
            modified_tokens = sum(len(str(v)) // 4 for v in modified_context.values())
            
            # Expected token reduction from operations
            expected_reduction = sum(
                abs(op.estimated_token_impact) for op in executed_operations
                if op.estimated_token_impact < 0
            )
            
            actual_reduction = original_tokens - modified_tokens
            
            # Check if token reduction is within reasonable bounds (±20% tolerance)
            token_accuracy_threshold = 0.2
            if expected_reduction > 0:
                accuracy_ratio = abs(actual_reduction - expected_reduction) / expected_reduction
                token_count_accurate = accuracy_ratio <= token_accuracy_threshold
                if not token_count_accurate:
                    errors.append(f"Token count discrepancy: expected {expected_reduction}, actual {actual_reduction}")
            else:
                token_count_accurate = True  # No reduction expected
            
            # Critical content preservation check
            critical_keys_preserved = 0
            total_critical_keys = 0
            
            for key, value in original_context.items():
                importance = self._calculate_content_importance(key, value)
                if importance > 0.8:  # Critical content
                    total_critical_keys += 1
                    if key in modified_context:
                        critical_keys_preserved += 1
                    else:
                        # Check if content was consolidated rather than lost
                        consolidated_key = f"consolidated_{key}"
                        if consolidated_key not in modified_context:
                            errors.append(f"Critical content lost: key '{key}'")
            
            critical_preservation_ratio = (
                critical_keys_preserved / total_critical_keys if total_critical_keys > 0 else 1.0
            )
            critical_content_preserved = critical_preservation_ratio >= 0.9  # 90% of critical content must be preserved
            
            # Structure preservation (basic checks)
            structure_preserved = True
            if len(modified_context) == 0 and len(original_context) > 0:
                errors.append("All content was removed - this is likely an error")
                structure_preserved = False
            
            # Check for any operations that should have preserved certain keys
            for operation in executed_operations:
                if operation.operation_type == "reorder":
                    # Reorder should preserve all keys
                    for key in operation.target_keys:
                        if key not in modified_context and f"consolidated_{key}" not in modified_context:
                            errors.append(f"Reorder operation lost key: {key}")
                            structure_preserved = False
            
            integrity_maintained = (
                len(errors) == 0 
                and critical_content_preserved 
                and token_count_accurate 
                and structure_preserved
            )
            
            return IntegrityCheck(
                integrity_maintained=integrity_maintained,
                critical_content_preserved=critical_content_preserved,
                token_count_accurate=token_count_accurate,
                structure_preserved=structure_preserved,
                errors_detected=errors
            )
            
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            return IntegrityCheck(
                integrity_maintained=False,
                critical_content_preserved=False,
                token_count_accurate=False,
                structure_preserved=False,
                errors_detected=[f"Integrity check error: {e}"]
            )

    def generate_safety_report(
        self,
        validation_result: ValidationResult,
        integrity_check: Optional[IntegrityCheck] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive safety report."""
        report = {
            "validation_summary": {
                "is_safe": validation_result.is_valid and validation_result.confidence_score >= self.min_confidence,
                "confidence_score": validation_result.confidence_score,
                "risk_level": validation_result.risk_assessment,
                "validation_timestamp": validation_result.validation_timestamp
            },
            "validation_details": {
                "errors": validation_result.validation_errors,
                "warnings": validation_result.warnings,
                "recommendations": validation_result.safety_recommendations
            }
        }
        
        if integrity_check:
            report["integrity_check"] = {
                "integrity_maintained": integrity_check.integrity_maintained,
                "critical_content_preserved": integrity_check.critical_content_preserved,
                "structure_preserved": integrity_check.structure_preserved,
                "errors": integrity_check.errors_detected
            }
        
        # Overall safety assessment
        if integrity_check:
            overall_safe = (
                validation_result.is_valid 
                and integrity_check.integrity_maintained
                and validation_result.confidence_score >= self.min_confidence
            )
        else:
            overall_safe = (
                validation_result.is_valid
                and validation_result.confidence_score >= self.min_confidence
            )
        
        report["overall_assessment"] = {
            "safe_to_proceed": overall_safe,
            "requires_manual_review": not overall_safe or validation_result.risk_assessment == "high",
            "recommended_action": (
                "Proceed with operation" if overall_safe 
                else "Manual review required before proceeding"
            )
        }
        
        return report


# Convenience functions
def validate_operation(
    operation: ManipulationOperation,
    context_data: Dict[str, Any]
) -> ValidationResult:
    """Convenience function for operation validation."""
    validator = ManipulationValidator()
    return validator.validate_operation(operation, context_data)


def validate_plan(
    plan: ManipulationPlan,
    context_data: Dict[str, Any]
) -> ValidationResult:
    """Convenience function for plan validation."""
    validator = ManipulationValidator()
    return validator.validate_plan(plan, context_data)


def verify_manipulation_integrity(
    original_context: Dict[str, Any],
    modified_context: Dict[str, Any], 
    executed_operations: List[ManipulationOperation]
) -> IntegrityCheck:
    """Convenience function for integrity verification."""
    validator = ManipulationValidator()
    return validator.verify_integrity(original_context, modified_context, executed_operations)


if __name__ == "__main__":
    # Test validation system
    print("Testing Manipulation Validation Engine...")
    
    from .manipulation_engine import ManipulationOperation
    
    # Create test operation
    test_operation = ManipulationOperation(
        operation_id="test-001",
        operation_type="remove",
        target_keys=["duplicate_key"],
        operation_data={"removal_type": "safe_delete"},
        estimated_token_impact=-100,
        confidence_score=0.9,
        reasoning="Removing duplicate content",
        requires_confirmation=False
    )
    
    test_context = {
        "duplicate_key": "This is duplicate content",
        "important_key": "This is critical information",
        "normal_key": "Regular content"
    }
    
    # Validate operation
    result = validate_operation(test_operation, test_context)
    print(f"\n✅ Validation result: {'SAFE' if result.is_valid else 'UNSAFE'}")
    print(f"Confidence: {result.confidence_score:.2f}")
    print(f"Risk Level: {result.risk_assessment}")
    
    if result.validation_errors:
        print(f"Errors: {result.validation_errors}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")