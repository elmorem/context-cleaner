#!/usr/bin/env python3
"""
User Confirmation Workflows

Provides interactive confirmation workflows for high-risk context manipulation operations:
- Interactive operation approval with detailed risk assessment
- Staged confirmation for complex operations
- User-friendly risk communication and explanation
- Customizable confirmation thresholds and workflows
- Integration with safety validation and preview systems
- Batch operation confirmation with selective approval

Integrates with ManipulationValidator, PreviewGenerator, and BackupManager for comprehensive safety.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from .manipulation_engine import ManipulationOperation, ManipulationPlan
from .manipulation_validator import (
    ManipulationValidator, ValidationResult, RiskAssessment, RiskLevel, SafetyAction
)
from .preview_generator import PreviewGenerator, OperationPreview, PlanPreview, PreviewFormat
from .backup_manager import BackupManager

logger = logging.getLogger(__name__)


class ConfirmationLevel(Enum):
    """Levels of confirmation required for operations."""
    NONE = "none"  # No confirmation needed
    SIMPLE = "simple"  # Simple yes/no confirmation
    DETAILED = "detailed"  # Show detailed information before confirmation
    INTERACTIVE = "interactive"  # Full interactive review
    STAGED = "staged"  # Staged confirmation for multiple operations


class ConfirmationResult(Enum):
    """Result of user confirmation."""
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"  # User requested modifications
    DEFERRED = "deferred"  # Postponed for later review


@dataclass
class ConfirmationRequest:
    """Request for user confirmation of an operation."""
    
    request_id: str
    operation_or_plan: Union[ManipulationOperation, ManipulationPlan]
    confirmation_level: ConfirmationLevel
    risk_assessment: Optional[RiskAssessment]
    validation_result: ValidationResult
    preview: Optional[Union[OperationPreview, PlanPreview]] = None
    safety_report: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    requires_backup: bool = False
    timeout_minutes: Optional[int] = None


@dataclass
class ConfirmationResponse:
    """Response from user confirmation workflow."""
    
    request_id: str
    result: ConfirmationResult
    approved_operations: List[str] = field(default_factory=list)  # For partial approvals
    rejected_operations: List[str] = field(default_factory=list)
    user_comments: str = ""
    response_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    requested_modifications: Optional[Dict[str, Any]] = None
    backup_requested: bool = False


class ConfirmationProvider(ABC):
    """Abstract base class for confirmation providers."""
    
    @abstractmethod
    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        """Request confirmation from user."""
        pass
    
    @abstractmethod
    def supports_level(self, level: ConfirmationLevel) -> bool:
        """Check if this provider supports the given confirmation level."""
        pass


class ConsoleConfirmationProvider(ConfirmationProvider):
    """Console-based confirmation provider for interactive terminals."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize console confirmation provider."""
        self.config = config or {}
        self.show_previews = self.config.get('show_previews', True)
        self.show_risk_details = self.config.get('show_risk_details', True)
        self.allow_partial_approval = self.config.get('allow_partial_approval', True)

    def supports_level(self, level: ConfirmationLevel) -> bool:
        """Console provider supports all levels."""
        return True

    def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        """Request confirmation via console interaction."""
        try:
            print("\n" + "="*60)
            print("🚨 OPERATION CONFIRMATION REQUIRED")
            print("="*60)
            
            # Show basic operation information
            if isinstance(request.operation_or_plan, ManipulationPlan):
                print(f"📋 Plan ID: {request.operation_or_plan.plan_id}")
                print(f"📊 Operations: {len(request.operation_or_plan.operations)}")
                print(f"⏱️  Estimated Time: {request.operation_or_plan.estimated_execution_time:.2f}s")
            else:
                op = request.operation_or_plan
                print(f"🔧 Operation: {op.operation_type.upper()}")
                print(f"🎯 Target Keys: {', '.join(op.target_keys)}")
                print(f"📈 Confidence: {op.confidence_score:.2f}")
            
            print(f"⚠️  Risk Level: {request.validation_result.risk_assessment.upper()}")
            print(f"✅ Validation: {'PASSED' if request.validation_result.is_valid else 'FAILED'}")
            
            if request.requires_backup:
                print("💾 Backup will be created before execution")
            
            # Show detailed risk information
            if self.show_risk_details and request.risk_assessment:
                self._show_risk_details(request.risk_assessment)
            
            # Show validation errors/warnings
            if request.validation_result.validation_errors:
                print("\n❌ VALIDATION ERRORS:")
                for error in request.validation_result.validation_errors:
                    print(f"   • {error}")
            
            if request.validation_result.warnings:
                print("\n⚠️  WARNINGS:")
                for warning in request.validation_result.warnings:
                    print(f"   • {warning}")
            
            # Show recommendations
            if request.validation_result.safety_recommendations:
                print("\n💡 SAFETY RECOMMENDATIONS:")
                for rec in request.validation_result.safety_recommendations:
                    print(f"   • {rec}")
            
            # Show preview if available
            if self.show_previews and request.preview:
                self._show_preview(request.preview)
            
            # Get user decision based on confirmation level
            if request.confirmation_level == ConfirmationLevel.SIMPLE:
                response = self._simple_confirmation()
            elif request.confirmation_level == ConfirmationLevel.DETAILED:
                response = self._detailed_confirmation()
            elif request.confirmation_level == ConfirmationLevel.INTERACTIVE:
                response = self._interactive_confirmation(request)
            elif request.confirmation_level == ConfirmationLevel.STAGED:
                response = self._staged_confirmation(request)
            else:
                response = self._simple_confirmation()
            
            response.request_id = request.request_id
            return response
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Operation cancelled by user")
            return ConfirmationResponse(
                request_id=request.request_id,
                result=ConfirmationResult.REJECTED,
                user_comments="Cancelled by user (Ctrl+C)"
            )
        except Exception as e:
            logger.error(f"Error in confirmation workflow: {e}")
            print(f"\n❌ Error in confirmation workflow: {e}")
            return ConfirmationResponse(
                request_id=request.request_id,
                result=ConfirmationResult.REJECTED,
                user_comments=f"Error during confirmation: {e}"
            )

    def _show_risk_details(self, risk_assessment: RiskAssessment) -> None:
        """Show detailed risk assessment information."""
        print(f"\n🎯 RISK ASSESSMENT DETAILS")
        print(f"   Risk Level: {risk_assessment.risk_level.value.upper()}")
        print(f"   Impact Severity: {risk_assessment.impact_severity:.2f}")
        print(f"   Reversibility: {risk_assessment.reversibility:.2f}")
        print(f"   Data Sensitivity: {risk_assessment.data_sensitivity:.2f}")
        print(f"   Recommended Action: {risk_assessment.recommended_action.value.upper()}")
        
        if risk_assessment.risk_factors:
            print("\n🚩 Risk Factors:")
            for factor in risk_assessment.risk_factors:
                print(f"   • {factor}")
        
        if risk_assessment.mitigation_strategies:
            print("\n🛡️  Mitigation Strategies:")
            for strategy in risk_assessment.mitigation_strategies:
                print(f"   • {strategy}")

    def _show_preview(self, preview: Union[OperationPreview, PlanPreview]) -> None:
        """Show operation/plan preview."""
        print("\n📋 OPERATION PREVIEW")
        print("-" * 40)
        
        from .preview_generator import PreviewGenerator
        generator = PreviewGenerator()
        preview_text = generator.format_preview(preview, PreviewFormat.TEXT, include_details=False)
        
        # Show first 500 characters of preview
        if len(preview_text) > 500:
            print(preview_text[:500] + "...\n   [Preview truncated - full details available]")
        else:
            print(preview_text)

    def _simple_confirmation(self) -> ConfirmationResponse:
        """Simple yes/no confirmation."""
        print("\n" + "-" * 60)
        while True:
            response = input("Do you want to proceed with this operation? [y/N]: ").strip().lower()
            if response in ['y', 'yes']:
                return ConfirmationResponse(
                    request_id="",  # Will be set by caller
                    result=ConfirmationResult.APPROVED,
                    user_comments="Simple approval"
                )
            elif response in ['n', 'no', '']:
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.REJECTED,
                    user_comments="Simple rejection"
                )
            else:
                print("Please enter 'y' for yes or 'n' for no.")

    def _detailed_confirmation(self) -> ConfirmationResponse:
        """Detailed confirmation with options."""
        print("\n" + "-" * 60)
        print("CONFIRMATION OPTIONS:")
        print("  [a] Approve - Proceed with operation")
        print("  [r] Reject - Cancel operation")
        print("  [b] Approve with Backup - Create backup first")
        print("  [d] Defer - Postpone decision")
        print("  [c] Cancel")
        
        while True:
            response = input("Select option [a/r/b/d/c]: ").strip().lower()
            
            if response in ['a', 'approve']:
                comment = input("Optional comment: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.APPROVED,
                    user_comments=comment or "Detailed approval"
                )
            elif response in ['r', 'reject']:
                comment = input("Reason for rejection: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.REJECTED,
                    user_comments=comment or "Detailed rejection"
                )
            elif response in ['b', 'backup']:
                comment = input("Optional comment: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.APPROVED,
                    user_comments=comment or "Approved with backup",
                    backup_requested=True
                )
            elif response in ['d', 'defer']:
                comment = input("Reason for deferral: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.DEFERRED,
                    user_comments=comment or "Deferred for later review"
                )
            elif response in ['c', 'cancel']:
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.REJECTED,
                    user_comments="Cancelled by user"
                )
            else:
                print("Invalid option. Please select a, r, b, d, or c.")

    def _interactive_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        """Interactive confirmation with full details."""
        print("\n" + "-" * 60)
        print("INTERACTIVE CONFIRMATION MODE")
        print("Available commands:")
        print("  [p] Show full preview")
        print("  [s] Show safety report")
        print("  [r] Show risk assessment")
        print("  [a] Approve operation")
        print("  [reject] Reject operation")
        print("  [modify] Request modifications")
        print("  [help] Show this help")
        print("  [quit] Cancel operation")
        
        while True:
            command = input("\nEnter command: ").strip().lower()
            
            if command in ['p', 'preview']:
                self._show_full_preview(request.preview)
            elif command in ['s', 'safety']:
                self._show_safety_report(request.safety_report)
            elif command in ['r', 'risk']:
                if request.risk_assessment:
                    self._show_risk_details(request.risk_assessment)
                else:
                    print("No detailed risk assessment available")
            elif command in ['a', 'approve']:
                backup = input("Create backup first? [Y/n]: ").strip().lower() not in ['n', 'no']
                comment = input("Optional comment: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.APPROVED,
                    user_comments=comment or "Interactive approval",
                    backup_requested=backup
                )
            elif command in ['reject']:
                reason = input("Reason for rejection: ").strip()
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.REJECTED,
                    user_comments=reason or "Interactive rejection"
                )
            elif command in ['modify']:
                return self._request_modifications()
            elif command in ['help']:
                print("\nAvailable commands: p(review), s(afety), r(isk), a(pprove), reject, modify, help, quit")
            elif command in ['quit', 'cancel']:
                return ConfirmationResponse(
                    request_id="",
                    result=ConfirmationResult.REJECTED,
                    user_comments="Cancelled in interactive mode"
                )
            else:
                print(f"Unknown command: {command}. Type 'help' for available commands.")

    def _staged_confirmation(self, request: ConfirmationRequest) -> ConfirmationResponse:
        """Staged confirmation for plans with multiple operations."""
        if not isinstance(request.operation_or_plan, ManipulationPlan):
            return self._detailed_confirmation()
        
        plan = request.operation_or_plan
        print(f"\n📋 STAGED CONFIRMATION - {len(plan.operations)} operations")
        print("Review each operation individually:")
        
        approved_ops = []
        rejected_ops = []
        
        for i, operation in enumerate(plan.operations, 1):
            print(f"\n--- Operation {i}/{len(plan.operations)} ---")
            print(f"Type: {operation.operation_type}")
            print(f"Target Keys: {', '.join(operation.target_keys)}")
            print(f"Confidence: {operation.confidence_score:.2f}")
            print(f"Reasoning: {operation.reasoning}")
            
            while True:
                choice = input(f"Operation {i} - [a]pprove, [r]eject, [s]kip, [q]uit: ").strip().lower()
                
                if choice in ['a', 'approve']:
                    approved_ops.append(operation.operation_id)
                    print("✅ Approved")
                    break
                elif choice in ['r', 'reject']:
                    rejected_ops.append(operation.operation_id)
                    print("❌ Rejected")
                    break
                elif choice in ['s', 'skip']:
                    print("⏭️  Skipped")
                    break
                elif choice in ['q', 'quit']:
                    return ConfirmationResponse(
                        request_id="",
                        result=ConfirmationResult.REJECTED,
                        user_comments="Cancelled during staged review"
                    )
                else:
                    print("Please enter a, r, s, or q")
        
        # Final summary
        print(f"\n📊 STAGED REVIEW SUMMARY")
        print(f"Approved: {len(approved_ops)} operations")
        print(f"Rejected: {len(rejected_ops)} operations")
        print(f"Skipped: {len(plan.operations) - len(approved_ops) - len(rejected_ops)} operations")
        
        if approved_ops:
            backup = input("Create backup before executing approved operations? [Y/n]: ").strip().lower() not in ['n', 'no']
            comment = input("Final comment: ").strip()
            
            return ConfirmationResponse(
                request_id="",
                result=ConfirmationResult.APPROVED if approved_ops else ConfirmationResult.REJECTED,
                approved_operations=approved_ops,
                rejected_operations=rejected_ops,
                user_comments=comment or "Staged approval",
                backup_requested=backup
            )
        else:
            return ConfirmationResponse(
                request_id="",
                result=ConfirmationResult.REJECTED,
                approved_operations=approved_ops,
                rejected_operations=rejected_ops,
                user_comments="No operations approved in staged review"
            )

    def _show_full_preview(self, preview: Optional[Union[OperationPreview, PlanPreview]]) -> None:
        """Show full preview details."""
        if not preview:
            print("No preview available")
            return
        
        from .preview_generator import PreviewGenerator
        generator = PreviewGenerator()
        preview_text = generator.format_preview(preview, PreviewFormat.TEXT, include_details=True)
        print("\n" + "="*60)
        print("FULL PREVIEW")
        print("="*60)
        print(preview_text)

    def _show_safety_report(self, safety_report: Optional[Dict[str, Any]]) -> None:
        """Show safety report details."""
        if not safety_report:
            print("No safety report available")
            return
        
        print("\n" + "="*60)
        print("SAFETY REPORT")
        print("="*60)
        print(json.dumps(safety_report, indent=2))

    def _request_modifications(self) -> ConfirmationResponse:
        """Handle modification requests."""
        print("\n🔧 MODIFICATION REQUEST")
        print("What modifications would you like to request?")
        
        modifications = {}
        
        while True:
            mod_type = input("Modification type [confidence/keys/type/other/done]: ").strip().lower()
            
            if mod_type == 'done':
                break
            elif mod_type == 'confidence':
                min_conf = input("Minimum confidence required: ").strip()
                try:
                    modifications['min_confidence'] = float(min_conf)
                except ValueError:
                    print("Invalid confidence value")
            elif mod_type == 'keys':
                keys = input("Keys to exclude (comma-separated): ").strip()
                if keys:
                    modifications['exclude_keys'] = [k.strip() for k in keys.split(',')]
            elif mod_type == 'type':
                new_type = input("Preferred operation type: ").strip()
                if new_type:
                    modifications['operation_type'] = new_type
            elif mod_type == 'other':
                other = input("Other modification: ").strip()
                if other:
                    modifications['other'] = other
            else:
                print("Unknown modification type")
        
        comment = input("Additional comments: ").strip()
        
        return ConfirmationResponse(
            request_id="",
            result=ConfirmationResult.MODIFIED,
            requested_modifications=modifications,
            user_comments=comment or "Modification requested"
        )


class ConfirmationWorkflowManager:
    """
    Manager for user confirmation workflows.
    
    Coordinates confirmation requests with appropriate providers and
    integrates with safety validation systems.
    """
    
    def __init__(self,
                 validator: Optional[ManipulationValidator] = None,
                 preview_generator: Optional[PreviewGenerator] = None,
                 backup_manager: Optional[BackupManager] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize confirmation workflow manager."""
        self.validator = validator or ManipulationValidator()
        self.preview_generator = preview_generator or PreviewGenerator()
        self.backup_manager = backup_manager or BackupManager()
        self.config = config or {}
        
        # Confirmation providers
        self.providers: List[ConfirmationProvider] = []
        self.default_provider = ConsoleConfirmationProvider(self.config.get('console_provider', {}))
        self.providers.append(self.default_provider)
        
        # Configuration
        self.auto_confirm_threshold = self.config.get('auto_confirm_threshold', 0.9)
        self.force_confirmation_threshold = self.config.get('force_confirmation_threshold', 0.5)
        self.enable_previews = self.config.get('enable_previews', True)
        self.enable_safety_reports = self.config.get('enable_safety_reports', True)
        
        logger.info("ConfirmationWorkflowManager initialized")

    def add_provider(self, provider: ConfirmationProvider) -> None:
        """Add a confirmation provider."""
        self.providers.append(provider)
        logger.info(f"Added confirmation provider: {type(provider).__name__}")

    def determine_confirmation_level(self,
                                   validation_result: ValidationResult,
                                   risk_assessment: Optional[RiskAssessment] = None) -> ConfirmationLevel:
        """Determine required confirmation level based on risk assessment."""
        try:
            # Auto-confirm if very safe
            if (validation_result.is_valid and 
                validation_result.confidence_score >= self.auto_confirm_threshold and
                validation_result.risk_assessment == "low"):
                return ConfirmationLevel.NONE
            
            # Force confirmation for critical operations
            if (not validation_result.is_valid or
                validation_result.confidence_score < self.force_confirmation_threshold or
                validation_result.risk_assessment in ["high", "critical"]):
                return ConfirmationLevel.INTERACTIVE
            
            # Risk-based confirmation level
            if risk_assessment:
                if risk_assessment.risk_level in [RiskLevel.CRITICAL]:
                    return ConfirmationLevel.INTERACTIVE
                elif risk_assessment.risk_level == RiskLevel.HIGH:
                    return ConfirmationLevel.DETAILED
                elif risk_assessment.risk_level == RiskLevel.MEDIUM:
                    return ConfirmationLevel.SIMPLE
                else:
                    return ConfirmationLevel.NONE
            
            # Default based on validation result
            if validation_result.risk_assessment == "high":
                return ConfirmationLevel.DETAILED
            elif validation_result.risk_assessment == "medium":
                return ConfirmationLevel.SIMPLE
            else:
                return ConfirmationLevel.NONE
                
        except Exception as e:
            logger.error(f"Error determining confirmation level: {e}")
            # Default to interactive for safety
            return ConfirmationLevel.INTERACTIVE

    def request_operation_confirmation(self,
                                     operation: ManipulationOperation,
                                     context_data: Dict[str, Any],
                                     force_level: Optional[ConfirmationLevel] = None) -> ConfirmationResponse:
        """Request confirmation for a single operation."""
        try:
            # Validate operation
            if hasattr(self.validator, 'validate_operation_enhanced'):
                validation_result, risk_assessment = self.validator.validate_operation_enhanced(
                    operation, context_data, enable_risk_assessment=True
                )
            else:
                validation_result = self.validator.validate_operation(operation, context_data)
                risk_assessment = None
            
            # Determine confirmation level
            confirmation_level = force_level or self.determine_confirmation_level(validation_result, risk_assessment)
            
            if confirmation_level == ConfirmationLevel.NONE:
                return ConfirmationResponse(
                    request_id=f"auto-{operation.operation_id}",
                    result=ConfirmationResult.APPROVED,
                    user_comments="Auto-approved based on safety assessment"
                )
            
            # Generate preview if needed
            preview = None
            if self.enable_previews:
                preview = self.preview_generator.preview_operation(operation, context_data)
            
            # Generate safety report if needed
            safety_report = None
            if self.enable_safety_reports and hasattr(self.validator, 'generate_enhanced_safety_report'):
                safety_report = self.validator.generate_enhanced_safety_report(
                    validation_result, risk_assessment=risk_assessment
                )
            
            # Create confirmation request
            request = ConfirmationRequest(
                request_id=f"op-{operation.operation_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                operation_or_plan=operation,
                confirmation_level=confirmation_level,
                risk_assessment=risk_assessment,
                validation_result=validation_result,
                preview=preview,
                safety_report=safety_report,
                requires_backup=(
                    risk_assessment and 
                    risk_assessment.impact_severity > self.validator.safety_constraints.require_backup_threshold
                    if risk_assessment else False
                )
            )
            
            # Find suitable provider
            provider = self._find_provider(confirmation_level)
            if not provider:
                logger.error(f"No provider found for confirmation level {confirmation_level}")
                return ConfirmationResponse(
                    request_id=request.request_id,
                    result=ConfirmationResult.REJECTED,
                    user_comments="No suitable confirmation provider available"
                )
            
            # Request confirmation
            response = provider.request_confirmation(request)
            logger.info(f"Confirmation completed: {response.result.value}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in operation confirmation workflow: {e}")
            return ConfirmationResponse(
                request_id=f"error-{operation.operation_id}",
                result=ConfirmationResult.REJECTED,
                user_comments=f"Confirmation error: {e}"
            )

    def request_plan_confirmation(self,
                                plan: ManipulationPlan,
                                context_data: Dict[str, Any],
                                force_level: Optional[ConfirmationLevel] = None) -> ConfirmationResponse:
        """Request confirmation for a manipulation plan."""
        try:
            # Validate plan
            plan_validation = self.validator.validate_plan(plan, context_data)
            
            # Validate individual operations for detailed assessment
            operation_validations = []
            for operation in plan.operations:
                if hasattr(self.validator, 'validate_operation_enhanced'):
                    val_result, risk_assessment = self.validator.validate_operation_enhanced(
                        operation, context_data, enable_risk_assessment=True
                    )
                else:
                    val_result = self.validator.validate_operation(operation, context_data)
                    risk_assessment = None
                operation_validations.append((operation, val_result, risk_assessment))
            
            # Find highest risk level among operations first
            max_risk_assessment = None
            for _, val_result, risk_assessment in operation_validations:
                if risk_assessment and (not max_risk_assessment or 
                                      risk_assessment.risk_level.value > max_risk_assessment.risk_level.value):
                    max_risk_assessment = risk_assessment
            
            # Determine confirmation level based on plan complexity
            if force_level:
                confirmation_level = force_level
            elif len(plan.operations) > 10:
                confirmation_level = ConfirmationLevel.STAGED
            else:
                confirmation_level = self.determine_confirmation_level(plan_validation, max_risk_assessment)
            
            if confirmation_level == ConfirmationLevel.NONE:
                return ConfirmationResponse(
                    request_id=f"auto-{plan.plan_id}",
                    result=ConfirmationResult.APPROVED,
                    user_comments="Auto-approved based on safety assessment",
                    approved_operations=[op.operation_id for op in plan.operations]
                )
            
            # Generate preview if needed
            preview = None
            if self.enable_previews:
                preview = self.preview_generator.preview_plan(plan, context_data)
            
            # Generate safety report if needed
            safety_report = None
            if self.enable_safety_reports and hasattr(self.validator, 'generate_plan_safety_report'):
                safety_report = self.validator.generate_plan_safety_report(
                    plan_validation, operation_validations
                )
            
            # Create confirmation request
            request = ConfirmationRequest(
                request_id=f"plan-{plan.plan_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                operation_or_plan=plan,
                confirmation_level=confirmation_level,
                risk_assessment=max_risk_assessment,
                validation_result=plan_validation,
                preview=preview,
                safety_report=safety_report,
                requires_backup=any(
                    risk and risk.impact_severity > self.validator.safety_constraints.require_backup_threshold
                    for _, _, risk in operation_validations if risk
                )
            )
            
            # Find suitable provider
            provider = self._find_provider(confirmation_level)
            if not provider:
                logger.error(f"No provider found for confirmation level {confirmation_level}")
                return ConfirmationResponse(
                    request_id=request.request_id,
                    result=ConfirmationResult.REJECTED,
                    user_comments="No suitable confirmation provider available"
                )
            
            # Request confirmation
            response = provider.request_confirmation(request)
            logger.info(f"Plan confirmation completed: {response.result.value}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in plan confirmation workflow: {e}")
            return ConfirmationResponse(
                request_id=f"error-{plan.plan_id}",
                result=ConfirmationResult.REJECTED,
                user_comments=f"Plan confirmation error: {e}"
            )

    def _find_provider(self, confirmation_level: ConfirmationLevel) -> Optional[ConfirmationProvider]:
        """Find a suitable provider for the given confirmation level."""
        for provider in self.providers:
            if provider.supports_level(confirmation_level):
                return provider
        return None


# Convenience functions
def confirm_operation(
    operation: ManipulationOperation,
    context_data: Dict[str, Any],
    confirmation_level: Optional[ConfirmationLevel] = None,
    validator: Optional[ManipulationValidator] = None,
    preview_generator: Optional[PreviewGenerator] = None
) -> ConfirmationResponse:
    """Convenience function to confirm a single operation."""
    manager = ConfirmationWorkflowManager(
        validator=validator,
        preview_generator=preview_generator
    )
    return manager.request_operation_confirmation(operation, context_data, confirmation_level)


def confirm_plan(
    plan: ManipulationPlan,
    context_data: Dict[str, Any],
    confirmation_level: Optional[ConfirmationLevel] = None,
    validator: Optional[ManipulationValidator] = None,
    preview_generator: Optional[PreviewGenerator] = None
) -> ConfirmationResponse:
    """Convenience function to confirm a manipulation plan."""
    manager = ConfirmationWorkflowManager(
        validator=validator,
        preview_generator=preview_generator
    )
    return manager.request_plan_confirmation(plan, context_data, confirmation_level)


if __name__ == "__main__":
    # Test confirmation system
    print("Testing Confirmation Workflows...")
    
    from .manipulation_engine import ManipulationOperation
    
    # Test operation
    test_operation = ManipulationOperation(
        operation_id="confirm-test-001",
        operation_type="remove",
        target_keys=["test_key"],
        operation_data={"removal_type": "safe_delete"},
        estimated_token_impact=-25,
        confidence_score=0.6,  # Medium confidence to trigger confirmation
        reasoning="Test operation for confirmation system",
        requires_confirmation=True
    )
    
    test_context = {
        "test_key": "This is test content for removal",
        "important_key": "This is important content to preserve"
    }
    
    print("🔧 Testing operation confirmation...")
    try:
        response = confirm_operation(test_operation, test_context)
        print(f"✅ Confirmation result: {response.result.value}")
        print(f"Comments: {response.user_comments}")
    except KeyboardInterrupt:
        print("\n⚠️  Test cancelled by user")
    except Exception as e:
        print(f"❌ Test error: {e}")