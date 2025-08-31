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
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum

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


class RiskLevel(Enum):
    """Risk assessment levels for operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SafetyAction(Enum):
    """Recommended safety actions."""
    PROCEED = "proceed"
    CONFIRM = "confirm"  
    BACKUP_FIRST = "backup_first"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


@dataclass
class RiskAssessment:
    """Detailed risk assessment for operations."""
    
    risk_level: RiskLevel
    risk_factors: List[str]  # Specific risk factors identified
    impact_severity: float  # 0-1 scale of potential impact
    reversibility: float  # 0-1 scale of how easily reversible the operation is
    data_sensitivity: float  # 0-1 scale of data sensitivity
    recommended_action: SafetyAction
    mitigation_strategies: List[str]  # Ways to reduce risk


@dataclass  
class SafetyConstraints:
    """Configuration for safety validation constraints."""
    
    max_single_operation_impact: float = 0.3  # Max 30% content change per operation
    max_total_reduction: float = 0.8  # Max 80% total reduction
    min_confidence_threshold: float = 0.7  # Minimum confidence for auto-execution
    critical_content_threshold: float = 0.1  # Must preserve 10% as critical
    require_backup_threshold: float = 0.5  # Require backup above this impact level
    max_operations_per_batch: int = 20  # Max operations in single batch
    enable_dry_run_mode: bool = True  # Enable preview/dry-run functionality
    
    
@dataclass
class OperationHistory:
    """Historical record of an operation for rollback purposes."""
    
    operation_id: str
    timestamp: str
    operation_type: str
    affected_keys: List[str]
    original_values: Dict[str, Any]  # Original values before modification
    backup_id: Optional[str] = None  # Associated backup identifier
    

class ManipulationValidator:
    """
    Enhanced Validation Engine for Context Manipulation Operations
    
    Provides comprehensive safety and integrity checks for manipulation operations
    with multi-layered risk assessment, operation history tracking, and enhanced
    safety validation with configurable constraints.
    """
    
    # Legacy thresholds (kept for backward compatibility)
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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, safety_constraints: Optional[SafetyConstraints] = None):
        """Initialize enhanced validation engine with safety configuration."""
        self.config = config or {}
        
        # Enhanced safety constraints
        if safety_constraints:
            self.safety_constraints = safety_constraints
        else:
            self.safety_constraints = SafetyConstraints(
                max_single_operation_impact=self.config.get('max_operation_impact', self.MAX_SINGLE_OPERATION_IMPACT),
                max_total_reduction=self.config.get('max_total_reduction', self.MAX_TOTAL_REDUCTION),
                min_confidence_threshold=self.config.get('min_confidence', self.MIN_SAFE_CONFIDENCE),
                critical_content_threshold=self.config.get('critical_content_threshold', self.CRITICAL_CONTENT_THRESHOLD),
                require_backup_threshold=self.config.get('require_backup_threshold', 0.5),
                max_operations_per_batch=self.config.get('max_operations_per_batch', 20),
                enable_dry_run_mode=self.config.get('enable_dry_run_mode', True)
            )
        
        # Legacy compatibility
        self.min_confidence = self.safety_constraints.min_confidence_threshold
        self.max_operation_impact = self.safety_constraints.max_single_operation_impact
        self.max_total_reduction = self.safety_constraints.max_total_reduction
        
        # Operation history tracking
        self.operation_history: List[OperationHistory] = []
        
        logger.info("Enhanced ManipulationValidator initialized with safety constraints")

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
    
    def _assess_operation_risk(
        self, 
        operation: ManipulationOperation, 
        context_data: Dict[str, Any]
    ) -> RiskAssessment:
        """Perform comprehensive risk assessment for an operation."""
        risk_factors = []
        impact_severity = 0.0
        reversibility = 1.0  # Start with fully reversible
        data_sensitivity = 0.0
        
        # Assess impact severity based on operation scope
        total_context_size = sum(len(str(v)) for v in context_data.values())
        if total_context_size > 0:
            operation_size = sum(len(str(context_data.get(key, ""))) for key in operation.target_keys)
            impact_severity = operation_size / total_context_size
            
        # Assess data sensitivity
        sensitive_content_found = False
        for key in operation.target_keys:
            if key in context_data:
                content_risk = self._assess_content_risk(str(context_data[key]))
                if content_risk == "high":
                    data_sensitivity = max(data_sensitivity, 0.9)
                    sensitive_content_found = True
                    risk_factors.append(f"High-risk content in key '{key}'")
                elif content_risk == "medium":
                    data_sensitivity = max(data_sensitivity, 0.6)
        
        # Assess reversibility based on operation type
        if operation.operation_type == "remove":
            reversibility = 0.3  # Hard to reverse deletions
            risk_factors.append("Removal operations are difficult to reverse")
        elif operation.operation_type == "summarize":
            reversibility = 0.1  # Very hard to reverse summarization
            risk_factors.append("Summarization operations lose original detail")
        elif operation.operation_type == "consolidate":
            reversibility = 0.5  # Moderately reversible
            risk_factors.append("Consolidation may lose some original structure")
        elif operation.operation_type == "reorder":
            reversibility = 0.9  # Easily reversible
            
        # Low confidence increases risk
        if operation.confidence_score < self.safety_constraints.min_confidence_threshold:
            risk_factors.append(f"Low confidence score: {operation.confidence_score:.2f}")
            
        # High impact operations increase risk
        if impact_severity > self.safety_constraints.max_single_operation_impact:
            risk_factors.append(f"High impact operation: {impact_severity:.1%} of total content")
            
        # Calculate overall risk level
        risk_score = (
            impact_severity * 0.4 +
            (1 - reversibility) * 0.3 +
            data_sensitivity * 0.2 +
            (1 - operation.confidence_score) * 0.1
        )
        
        if risk_score >= 0.8 or sensitive_content_found:
            risk_level = RiskLevel.CRITICAL
            recommended_action = SafetyAction.REJECT if risk_score >= 0.9 else SafetyAction.MANUAL_REVIEW
        elif risk_score >= 0.6:
            risk_level = RiskLevel.HIGH
            recommended_action = SafetyAction.BACKUP_FIRST
        elif risk_score >= 0.4:
            risk_level = RiskLevel.MEDIUM
            recommended_action = SafetyAction.CONFIRM
        else:
            risk_level = RiskLevel.LOW
            recommended_action = SafetyAction.PROCEED
            
        # Generate mitigation strategies
        mitigation_strategies = []
        if impact_severity > 0.3:
            mitigation_strategies.append("Create backup before proceeding")
        if operation.confidence_score < 0.8:
            mitigation_strategies.append("Verify operation parameters manually")
        if reversibility < 0.5:
            mitigation_strategies.append("Enable dry-run mode to preview changes")
        if sensitive_content_found:
            mitigation_strategies.append("Review sensitive content handling policies")
            
        return RiskAssessment(
            risk_level=risk_level,
            risk_factors=risk_factors,
            impact_severity=impact_severity,
            reversibility=reversibility,
            data_sensitivity=data_sensitivity,
            recommended_action=recommended_action,
            mitigation_strategies=mitigation_strategies
        )

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
    
    def record_operation_history(
        self,
        operation: ManipulationOperation,
        context_data: Dict[str, Any],
        backup_id: Optional[str] = None
    ) -> None:
        """Record operation in history for rollback capabilities."""
        try:
            # Capture original values for affected keys
            original_values = {}
            for key in operation.target_keys:
                if key in context_data:
                    original_values[key] = deepcopy(context_data[key])
            
            history_entry = OperationHistory(
                operation_id=operation.operation_id,
                timestamp=datetime.now().isoformat(),
                operation_type=operation.operation_type,
                affected_keys=operation.target_keys,
                original_values=original_values,
                backup_id=backup_id
            )
            
            self.operation_history.append(history_entry)
            logger.info(f"Recorded operation history for {operation.operation_id}")
            
        except Exception as e:
            logger.error(f"Failed to record operation history: {e}")
    
    def get_rollback_data(self, operation_id: str) -> Optional[OperationHistory]:
        """Get rollback data for a specific operation."""
        for entry in reversed(self.operation_history):  # Search from most recent
            if entry.operation_id == operation_id:
                return entry
        return None
    
    def validate_operation_enhanced(
        self,
        operation: ManipulationOperation,
        context_data: Dict[str, Any],
        enable_risk_assessment: bool = True
    ) -> Tuple[ValidationResult, Optional[RiskAssessment]]:
        """Enhanced operation validation with detailed risk assessment."""
        # Perform standard validation first
        standard_validation = self.validate_operation(operation, context_data)
        
        risk_assessment = None
        if enable_risk_assessment:
            risk_assessment = self._assess_operation_risk(operation, context_data)
            
            # Enhance validation result with risk assessment
            enhanced_errors = list(standard_validation.validation_errors)
            enhanced_warnings = list(standard_validation.warnings)
            enhanced_recommendations = list(standard_validation.safety_recommendations)
            
            # Add risk-based recommendations
            if risk_assessment.recommended_action == SafetyAction.REJECT:
                enhanced_errors.append("Operation rejected due to critical risk level")
            elif risk_assessment.recommended_action == SafetyAction.MANUAL_REVIEW:
                enhanced_warnings.append("Operation requires manual review due to high risk")
            elif risk_assessment.recommended_action == SafetyAction.BACKUP_FIRST:
                enhanced_recommendations.append("Create backup before proceeding with this operation")
            elif risk_assessment.recommended_action == SafetyAction.CONFIRM:
                enhanced_recommendations.append("Confirm operation parameters before proceeding")
                
            enhanced_recommendations.extend(risk_assessment.mitigation_strategies)
            
            # Update validation result with enhanced information
            enhanced_validation = ValidationResult(
                is_valid=standard_validation.is_valid and risk_assessment.recommended_action != SafetyAction.REJECT,
                confidence_score=min(standard_validation.confidence_score, 1.0 - risk_assessment.impact_severity * 0.3),
                validation_errors=enhanced_errors,
                warnings=enhanced_warnings,
                safety_recommendations=list(set(enhanced_recommendations)),  # Remove duplicates
                risk_assessment=risk_assessment.risk_level.value,
                validation_timestamp=standard_validation.validation_timestamp
            )
            
            return enhanced_validation, risk_assessment
        
        return standard_validation, None

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
        """Generate comprehensive safety report (legacy version)."""
        return self.generate_enhanced_safety_report(validation_result, integrity_check)
        
    def generate_enhanced_safety_report(
        self,
        validation_result: ValidationResult,
        integrity_check: Optional[IntegrityCheck] = None,
        risk_assessment: Optional[RiskAssessment] = None,
        operation_history: Optional[List[OperationHistory]] = None,
        include_mitigation_plan: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive enhanced safety report with detailed analysis."""
        report_timestamp = datetime.now().isoformat()
        
        # Basic validation summary
        is_safe = validation_result.is_valid and validation_result.confidence_score >= self.safety_constraints.min_confidence_threshold
        
        report = {
            "report_metadata": {
                "report_version": "2.0",
                "generated_at": report_timestamp,
                "validator_version": "PR18-Enhanced",
                "safety_constraints": {
                    "min_confidence_threshold": self.safety_constraints.min_confidence_threshold,
                    "max_operation_impact": self.safety_constraints.max_single_operation_impact,
                    "max_total_reduction": self.safety_constraints.max_total_reduction,
                    "require_backup_threshold": self.safety_constraints.require_backup_threshold
                }
            },
            
            "validation_summary": {
                "is_safe": is_safe,
                "confidence_score": validation_result.confidence_score,
                "risk_level": validation_result.risk_assessment,
                "validation_timestamp": validation_result.validation_timestamp,
                "total_errors": len(validation_result.validation_errors),
                "total_warnings": len(validation_result.warnings),
                "total_recommendations": len(validation_result.safety_recommendations)
            },
            
            "detailed_analysis": {
                "validation_errors": [
                    {
                        "error": error,
                        "severity": "high",
                        "blocking": True
                    } for error in validation_result.validation_errors
                ],
                "warnings": [
                    {
                        "warning": warning,
                        "severity": "medium",
                        "blocking": False
                    } for warning in validation_result.warnings
                ],
                "recommendations": [
                    {
                        "recommendation": rec,
                        "priority": "high" if any(word in rec.lower() for word in ['backup', 'critical', 'review']) else "medium",
                        "actionable": True
                    } for rec in validation_result.safety_recommendations
                ]
            }
        }
        
        # Enhanced risk assessment
        if risk_assessment:
            report["risk_assessment"] = {
                "overall_risk_level": risk_assessment.risk_level.value,
                "risk_score": (
                    risk_assessment.impact_severity * 0.4 +
                    (1 - risk_assessment.reversibility) * 0.3 +
                    risk_assessment.data_sensitivity * 0.3
                ),
                "impact_analysis": {
                    "impact_severity": risk_assessment.impact_severity,
                    "reversibility_score": risk_assessment.reversibility,
                    "data_sensitivity": risk_assessment.data_sensitivity,
                    "estimated_recovery_time": "immediate" if risk_assessment.reversibility > 0.8 else "hours" if risk_assessment.reversibility > 0.5 else "difficult"
                },
                "risk_factors": [
                    {
                        "factor": factor,
                        "category": "operational" if "operation" in factor.lower() else "content" if "content" in factor.lower() else "confidence",
                        "mitigation_available": True
                    } for factor in risk_assessment.risk_factors
                ],
                "recommended_action": risk_assessment.recommended_action.value,
                "mitigation_strategies": risk_assessment.mitigation_strategies
            }
        
        # Integrity check analysis
        if integrity_check:
            report["integrity_analysis"] = {
                "integrity_status": "maintained" if integrity_check.integrity_maintained else "compromised",
                "critical_content_status": "preserved" if integrity_check.critical_content_preserved else "at_risk",
                "token_accuracy": "accurate" if integrity_check.token_count_accurate else "inaccurate",
                "structure_status": "preserved" if integrity_check.structure_preserved else "modified",
                "integrity_score": (
                    (1 if integrity_check.integrity_maintained else 0) * 0.4 +
                    (1 if integrity_check.critical_content_preserved else 0) * 0.3 +
                    (1 if integrity_check.token_count_accurate else 0) * 0.15 +
                    (1 if integrity_check.structure_preserved else 0) * 0.15
                ),
                "errors": [
                    {
                        "error": error,
                        "impact": "high" if "critical" in error.lower() else "medium",
                        "recoverable": "critical" not in error.lower()
                    } for error in integrity_check.errors_detected
                ]
            }
        
        # Operation history analysis
        if operation_history:
            report["operation_history"] = {
                "total_operations": len(operation_history),
                "operations_by_type": {},
                "rollback_availability": True,
                "oldest_operation": min(op.timestamp for op in operation_history) if operation_history else None,
                "most_recent_operation": max(op.timestamp for op in operation_history) if operation_history else None,
                "operations": [
                    {
                        "operation_id": op.operation_id,
                        "timestamp": op.timestamp,
                        "type": op.operation_type,
                        "affected_keys": len(op.affected_keys),
                        "has_backup": op.backup_id is not None,
                        "rollback_available": True
                    } for op in operation_history[-10:]  # Last 10 operations
                ]
            }
            
            # Count operations by type
            for op in operation_history:
                op_type = op.operation_type
                report["operation_history"]["operations_by_type"][op_type] = \
                    report["operation_history"]["operations_by_type"].get(op_type, 0) + 1
        
        # Overall safety assessment with enhanced logic
        safety_factors = []
        safety_score = 1.0
        
        # Factor in validation results
        if not validation_result.is_valid:
            safety_factors.append("validation_failed")
            safety_score -= 0.4
            
        if validation_result.confidence_score < self.safety_constraints.min_confidence_threshold:
            safety_factors.append("low_confidence")
            safety_score -= 0.2
            
        # Factor in risk assessment
        if risk_assessment:
            if risk_assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                safety_factors.append("high_risk_operation")
                safety_score -= 0.3
            if risk_assessment.data_sensitivity > 0.7:
                safety_factors.append("sensitive_data")
                safety_score -= 0.15
            if risk_assessment.reversibility < 0.3:
                safety_factors.append("low_reversibility")
                safety_score -= 0.15
        
        # Factor in integrity issues
        if integrity_check and not integrity_check.integrity_maintained:
            safety_factors.append("integrity_issues")
            safety_score -= 0.25
        
        safety_score = max(0.0, safety_score)
        
        # Determine recommended actions
        recommended_actions = []
        if safety_score < 0.3:
            recommended_actions.append("REJECT_OPERATION")
        elif safety_score < 0.5:
            recommended_actions.append("REQUIRE_MANUAL_REVIEW")
            recommended_actions.append("CREATE_BACKUP")
        elif safety_score < 0.7:
            recommended_actions.append("CREATE_BACKUP")
            recommended_actions.append("REQUIRE_CONFIRMATION")
        else:
            recommended_actions.append("PROCEED_WITH_CAUTION")
        
        # Mitigation plan
        mitigation_plan = []
        if include_mitigation_plan:
            if "validation_failed" in safety_factors:
                mitigation_plan.append("Review and fix validation errors before proceeding")
            if "low_confidence" in safety_factors:
                mitigation_plan.append("Increase confidence by reviewing operation parameters")
            if "high_risk_operation" in safety_factors:
                mitigation_plan.append("Consider breaking operation into smaller, safer steps")
            if "sensitive_data" in safety_factors:
                mitigation_plan.append("Implement additional data protection measures")
            if "low_reversibility" in safety_factors:
                mitigation_plan.append("Create comprehensive backup before proceeding")
            if "integrity_issues" in safety_factors:
                mitigation_plan.append("Investigate and resolve integrity concerns")
        
        report["overall_assessment"] = {
            "safety_score": safety_score,
            "safety_level": (
                "safe" if safety_score >= 0.7 else
                "caution" if safety_score >= 0.5 else
                "dangerous" if safety_score >= 0.3 else
                "critical"
            ),
            "safe_to_proceed": safety_score >= 0.5,
            "requires_backup": safety_score < 0.7 or (risk_assessment and risk_assessment.impact_severity > self.safety_constraints.require_backup_threshold),
            "requires_confirmation": safety_score < 0.7,
            "requires_manual_review": safety_score < 0.5,
            "safety_factors": safety_factors,
            "recommended_actions": recommended_actions,
            "mitigation_plan": mitigation_plan,
            "estimated_risk_level": (
                "critical" if safety_score < 0.3 else
                "high" if safety_score < 0.5 else
                "medium" if safety_score < 0.7 else
                "low"
            )
        }
        
        return report
    
    def generate_plan_safety_report(
        self,
        plan_validation: ValidationResult,
        operation_validations: List[Tuple[ManipulationOperation, ValidationResult, Optional[RiskAssessment]]],
        integrity_check: Optional[IntegrityCheck] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive safety report for an entire manipulation plan."""
        report_timestamp = datetime.now().isoformat()
        
        # Aggregate statistics
        total_operations = len(operation_validations)
        failed_validations = sum(1 for _, val, _ in operation_validations if not val.is_valid)
        high_risk_operations = sum(1 for _, _, risk in operation_validations if risk and risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL])
        avg_confidence = sum(val.confidence_score for _, val, _ in operation_validations) / total_operations if total_operations > 0 else 0
        
        # Overall risk assessment
        max_risk_level = RiskLevel.LOW
        all_risk_factors = []
        total_impact_severity = 0
        min_reversibility = 1.0
        max_data_sensitivity = 0.0
        
        for _, validation, risk_assessment in operation_validations:
            if risk_assessment:
                if risk_assessment.risk_level.value > max_risk_level.value:
                    max_risk_level = risk_assessment.risk_level
                all_risk_factors.extend(risk_assessment.risk_factors)
                total_impact_severity += risk_assessment.impact_severity
                min_reversibility = min(min_reversibility, risk_assessment.reversibility)
                max_data_sensitivity = max(max_data_sensitivity, risk_assessment.data_sensitivity)
        
        avg_impact_severity = total_impact_severity / total_operations if total_operations > 0 else 0
        
        report = {
            "report_metadata": {
                "report_type": "plan_safety_report",
                "report_version": "2.0",
                "generated_at": report_timestamp,
                "validator_version": "PR18-Enhanced"
            },
            
            "plan_summary": {
                "total_operations": total_operations,
                "failed_validations": failed_validations,
                "high_risk_operations": high_risk_operations,
                "average_confidence": avg_confidence,
                "plan_validation_status": "valid" if plan_validation.is_valid else "invalid",
                "plan_confidence_score": plan_validation.confidence_score,
                "plan_risk_level": plan_validation.risk_assessment
            },
            
            "aggregated_risk_assessment": {
                "overall_risk_level": max_risk_level.value,
                "average_impact_severity": avg_impact_severity,
                "minimum_reversibility": min_reversibility,
                "maximum_data_sensitivity": max_data_sensitivity,
                "unique_risk_factors": list(set(all_risk_factors)),
                "risk_distribution": {
                    "low": sum(1 for _, _, risk in operation_validations if risk and risk.risk_level == RiskLevel.LOW),
                    "medium": sum(1 for _, _, risk in operation_validations if risk and risk.risk_level == RiskLevel.MEDIUM),
                    "high": sum(1 for _, _, risk in operation_validations if risk and risk.risk_level == RiskLevel.HIGH),
                    "critical": sum(1 for _, _, risk in operation_validations if risk and risk.risk_level == RiskLevel.CRITICAL)
                }
            },
            
            "operation_details": [
                {
                    "operation_id": operation.operation_id,
                    "operation_type": operation.operation_type,
                    "target_keys": operation.target_keys,
                    "validation_status": "valid" if validation.is_valid else "invalid",
                    "confidence_score": validation.confidence_score,
                    "risk_level": risk.risk_level.value if risk else "unknown",
                    "errors": validation.validation_errors,
                    "warnings": validation.warnings,
                    "requires_backup": risk and risk.impact_severity > self.safety_constraints.require_backup_threshold if risk else False
                }
                for operation, validation, risk in operation_validations
            ]
        }
        
        # Plan-level safety assessment
        plan_safety_score = 1.0
        plan_safety_factors = []
        
        if failed_validations > 0:
            plan_safety_factors.append(f"{failed_validations}_failed_validations")
            plan_safety_score -= (failed_validations / total_operations) * 0.5
            
        if high_risk_operations > 0:
            plan_safety_factors.append(f"{high_risk_operations}_high_risk_operations")
            plan_safety_score -= (high_risk_operations / total_operations) * 0.4
            
        if avg_confidence < self.safety_constraints.min_confidence_threshold:
            plan_safety_factors.append("low_average_confidence")
            plan_safety_score -= 0.2
            
        if max_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            plan_safety_factors.append("contains_high_risk_operations")
            plan_safety_score -= 0.3
        
        plan_safety_score = max(0.0, plan_safety_score)
        
        report["plan_safety_assessment"] = {
            "plan_safety_score": plan_safety_score,
            "safety_level": (
                "safe" if plan_safety_score >= 0.7 else
                "caution" if plan_safety_score >= 0.5 else
                "dangerous" if plan_safety_score >= 0.3 else
                "critical"
            ),
            "safe_to_execute": plan_safety_score >= 0.5 and failed_validations == 0,
            "requires_staged_execution": high_risk_operations > 0 or total_operations > self.safety_constraints.max_operations_per_batch,
            "requires_full_backup": plan_safety_score < 0.7 or avg_impact_severity > 0.3,
            "plan_safety_factors": plan_safety_factors,
            "recommended_approach": (
                "execute_normally" if plan_safety_score >= 0.8 else
                "execute_with_backup" if plan_safety_score >= 0.6 else
                "execute_staged" if plan_safety_score >= 0.4 else
                "manual_review_required"
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