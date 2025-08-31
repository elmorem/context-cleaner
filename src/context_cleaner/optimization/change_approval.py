"""
Change Approval System

This module provides selective approval and change selection functionality
for interactive optimization workflows. Allows users to cherry-pick which
changes to apply from an optimization plan.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ..core.manipulation_engine import ManipulationOperation, ManipulationPlan
from ..core.preview_generator import OperationPreview, PlanPreview, ChangeDetail


class ApprovalDecision(Enum):
    """User decisions for change approval."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    DEFER = "defer"


class ChangeCategory(Enum):
    """Categories of changes for grouping."""

    REMOVAL = "removal"
    CONSOLIDATION = "consolidation"
    REORDERING = "reordering"
    SUMMARIZATION = "summarization"
    SAFETY = "safety"


@dataclass
class ChangeSelection:
    """Represents a user's selection for a specific change."""

    operation_id: str
    operation_type: str
    decision: ApprovalDecision
    reason: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    selected_at: str = None

    def __post_init__(self):
        if self.selected_at is None:
            self.selected_at = datetime.now().isoformat()


@dataclass
class SelectiveApprovalResult:
    """Result of selective approval process."""

    approval_id: str
    total_operations: int
    approved_operations: List[str]
    rejected_operations: List[str]
    modified_operations: List[str]
    deferred_operations: List[str]
    approval_rate: float
    user_feedback: Optional[str]
    selections: List[ChangeSelection]
    created_at: str


class ChangeApprovalSystem:
    """
    Manages selective approval and change selection for optimization plans.

    Provides functionality for:
    - Categorizing changes by type and impact
    - Selective approval workflows
    - Change modification and customization
    - Batch approval by category
    - User feedback collection
    """

    def __init__(self):
        """Initialize change approval system."""
        self.approval_history: List[SelectiveApprovalResult] = []
        self.user_preferences: Dict[str, Any] = {}
        self.category_settings: Dict[ChangeCategory, Dict[str, Any]] = {}

        # Initialize default category settings
        self._initialize_category_settings()

    def categorize_operations(
        self, operations: List[ManipulationOperation]
    ) -> Dict[ChangeCategory, List[ManipulationOperation]]:
        """
        Categorize operations by change type for easier user review.

        Args:
            operations: List of manipulation operations

        Returns:
            Dict mapping categories to operations
        """
        categorized = {category: [] for category in ChangeCategory}

        for operation in operations:
            category = self._get_operation_category(operation)
            categorized[category].append(operation)

        return categorized

    def create_approval_session(
        self, plan: ManipulationPlan, preview: Optional[PlanPreview] = None
    ) -> str:
        """
        Create a new approval session for a manipulation plan.

        Args:
            plan: Manipulation plan to approve
            preview: Optional preview of changes

        Returns:
            Approval session ID
        """
        approval_id = f"approval-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.approval_history):03d}"

        # Create initial approval result (will be updated as user makes selections)
        result = SelectiveApprovalResult(
            approval_id=approval_id,
            total_operations=len(plan.operations),
            approved_operations=[],
            rejected_operations=[],
            modified_operations=[],
            deferred_operations=[],
            approval_rate=0.0,
            user_feedback=None,
            selections=[],
            created_at=datetime.now().isoformat(),
        )

        self.approval_history.append(result)
        return approval_id

    def select_operation(
        self,
        approval_id: str,
        operation_id: str,
        decision: ApprovalDecision,
        reason: Optional[str] = None,
        modifications: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Make a selection decision for a specific operation.

        Args:
            approval_id: Approval session ID
            operation_id: Operation to make decision on
            decision: User's decision
            reason: Optional reason for decision
            modifications: Optional modifications to operation

        Returns:
            True if selection was recorded successfully
        """
        result = self._get_approval_result(approval_id)

        # Remove any existing selection for this operation
        result.selections = [
            s for s in result.selections if s.operation_id != operation_id
        ]

        # Add new selection
        selection = ChangeSelection(
            operation_id=operation_id,
            operation_type="",  # Will be filled when we have access to the operation
            decision=decision,
            reason=reason,
            modifications=modifications,
        )

        result.selections.append(selection)

        # Update approval lists
        self._update_approval_lists(result)

        return True

    def select_by_category(
        self,
        approval_id: str,
        category: ChangeCategory,
        decision: ApprovalDecision,
        operation_ids: List[str],
        reason: Optional[str] = None,
    ) -> int:
        """
        Make batch selection decision for all operations in a category.

        Args:
            approval_id: Approval session ID
            category: Category to apply decision to
            decision: Decision to apply to all operations in category
            operation_ids: List of operation IDs in this category
            reason: Optional reason for batch decision

        Returns:
            Number of operations updated
        """
        count = 0
        batch_reason = (
            reason or f"Batch {decision.value} for {category.value} operations"
        )

        for operation_id in operation_ids:
            if self.select_operation(approval_id, operation_id, decision, batch_reason):
                count += 1

        return count

    def apply_user_preferences(
        self, approval_id: str, operations: List[ManipulationOperation]
    ) -> int:
        """
        Auto-apply decisions based on learned user preferences.

        Args:
            approval_id: Approval session ID
            operations: Operations to apply preferences to

        Returns:
            Number of operations auto-decided
        """
        result = self._get_approval_result(approval_id)
        count = 0

        for operation in operations:
            # Check if user has preferences for this type of operation
            operation_category = self._get_operation_category(operation)

            if operation_category in self.category_settings:
                settings = self.category_settings[operation_category]

                # Auto-approve if confidence is high and user typically approves this category
                if (
                    operation.confidence_score >= settings.get("min_confidence", 0.8)
                    and settings.get("default_action") == ApprovalDecision.APPROVE
                ):

                    if self.select_operation(
                        approval_id,
                        operation.operation_id,
                        ApprovalDecision.APPROVE,
                        f"Auto-approved based on user preferences for {operation_category.value}",
                    ):
                        count += 1

        return count

    def get_approval_summary(self, approval_id: str) -> Dict[str, Any]:
        """
        Get summary of current approval state.

        Args:
            approval_id: Approval session ID

        Returns:
            Summary dictionary with approval statistics
        """
        result = self._get_approval_result(approval_id)

        # Calculate statistics
        decisions_made = len(result.selections)
        approval_rate = (
            len(result.approved_operations) / result.total_operations
            if result.total_operations > 0
            else 0
        )

        # Group by decision type
        decision_counts = {}
        for decision in ApprovalDecision:
            count = sum(1 for s in result.selections if s.decision == decision)
            decision_counts[decision.value] = count

        return {
            "approval_id": approval_id,
            "total_operations": result.total_operations,
            "decisions_made": decisions_made,
            "pending_decisions": result.total_operations - decisions_made,
            "approval_rate": approval_rate,
            "decision_counts": decision_counts,
            "selections": [asdict(s) for s in result.selections],
            "created_at": result.created_at,
        }

    def finalize_approval(
        self, approval_id: str, user_feedback: Optional[str] = None
    ) -> SelectiveApprovalResult:
        """
        Finalize approval session and return final result.

        Args:
            approval_id: Approval session ID
            user_feedback: Optional user feedback about the process

        Returns:
            Final approval result
        """
        result = self._get_approval_result(approval_id)

        # Update user feedback
        if user_feedback:
            result.user_feedback = user_feedback

        # Ensure approval lists are up to date
        self._update_approval_lists(result)

        # Learn from user decisions to improve future recommendations
        self._learn_from_selections(result)

        return result

    def get_selected_operations(self, approval_id: str) -> List[str]:
        """
        Get list of operation IDs that were approved.

        Args:
            approval_id: Approval session ID

        Returns:
            List of approved operation IDs
        """
        result = self._get_approval_result(approval_id)
        return result.approved_operations.copy()

    def export_approval_data(self, approval_id: str) -> Dict[str, Any]:
        """
        Export approval data for external processing or storage.

        Args:
            approval_id: Approval session ID

        Returns:
            Complete approval data as dictionary
        """
        result = self._get_approval_result(approval_id)
        return asdict(result)

    def import_approval_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        Import user preferences from previous sessions.

        Args:
            preferences: Preference data to import

        Returns:
            True if preferences were imported successfully
        """
        try:
            self.user_preferences.update(preferences.get("user_preferences", {}))

            # Import category settings
            for category_name, settings in preferences.get(
                "category_settings", {}
            ).items():
                try:
                    category = ChangeCategory(category_name)
                    self.category_settings[category].update(settings)
                except ValueError:
                    # Skip unknown categories
                    pass

            return True
        except Exception:
            return False

    # Private methods

    def _get_operation_category(
        self, operation: ManipulationOperation
    ) -> ChangeCategory:
        """Determine the category for an operation."""
        operation_type = operation.operation_type.lower()

        if operation_type == "remove":
            return ChangeCategory.REMOVAL
        elif operation_type == "consolidate":
            return ChangeCategory.CONSOLIDATION
        elif operation_type == "reorder":
            return ChangeCategory.REORDERING
        elif operation_type == "summarize":
            return ChangeCategory.SUMMARIZATION
        else:
            return ChangeCategory.SAFETY

    def _get_approval_result(self, approval_id: str) -> SelectiveApprovalResult:
        """Get approval result by ID or raise error."""
        for result in self.approval_history:
            if result.approval_id == approval_id:
                return result
        raise ValueError(f"Approval session {approval_id} not found.")

    def _update_approval_lists(self, result: SelectiveApprovalResult):
        """Update the approval lists based on current selections."""
        result.approved_operations = []
        result.rejected_operations = []
        result.modified_operations = []
        result.deferred_operations = []

        for selection in result.selections:
            if selection.decision == ApprovalDecision.APPROVE:
                result.approved_operations.append(selection.operation_id)
            elif selection.decision == ApprovalDecision.REJECT:
                result.rejected_operations.append(selection.operation_id)
            elif selection.decision == ApprovalDecision.MODIFY:
                result.modified_operations.append(selection.operation_id)
            elif selection.decision == ApprovalDecision.DEFER:
                result.deferred_operations.append(selection.operation_id)

        # Update approval rate
        result.approval_rate = (
            len(result.approved_operations) / result.total_operations
            if result.total_operations > 0
            else 0
        )

    def _learn_from_selections(self, result: SelectiveApprovalResult):
        """Learn user preferences from their selections."""
        if len(result.selections) < 3:  # Need minimum data to learn
            return

        # Count decisions by category (would need operation details to implement fully)
        category_decisions = {}

        # Update user preferences based on patterns
        if result.approval_rate > 0.8:
            self.user_preferences["tends_to_approve"] = True
        elif result.approval_rate < 0.3:
            self.user_preferences["tends_to_reject"] = True
        else:
            self.user_preferences["selective_approver"] = True

    def _initialize_category_settings(self):
        """Initialize default category settings."""
        for category in ChangeCategory:
            self.category_settings[category] = {
                "default_action": None,
                "min_confidence": 0.7,
                "auto_approve_threshold": 0.9,
                "requires_confirmation": True,
            }

        # Set category-specific defaults
        self.category_settings[ChangeCategory.REMOVAL]["requires_confirmation"] = True
        self.category_settings[ChangeCategory.REORDERING][
            "requires_confirmation"
        ] = False
        self.category_settings[ChangeCategory.SAFETY][
            "default_action"
        ] = ApprovalDecision.APPROVE


# Convenience functions


def create_quick_approval(
    operations: List[ManipulationOperation], auto_approve_safe: bool = True
) -> Tuple[ChangeApprovalSystem, str]:
    """
    Create a quick approval session with optional auto-approval for safe operations.

    Args:
        operations: Operations to create approval for
        auto_approve_safe: Whether to auto-approve safe operations

    Returns:
        Tuple of (approval_system, approval_id)
    """
    from ..core.manipulation_engine import ManipulationPlan

    # Create a temporary plan
    plan = ManipulationPlan(
        plan_id=f"quick-approval-{datetime.now().strftime('%H%M%S')}",
        total_operations=len(operations),
        operations=operations,
        estimated_total_reduction=sum(op.estimated_token_impact for op in operations),
        estimated_execution_time=0.1 * len(operations),
        safety_level="balanced",
        requires_user_approval=True,
        created_timestamp=datetime.now().isoformat(),
    )

    system = ChangeApprovalSystem()
    approval_id = system.create_approval_session(plan)

    if auto_approve_safe:
        # Auto-approve operations with high confidence
        for operation in operations:
            if (
                operation.confidence_score >= 0.9
                and not operation.requires_confirmation
            ):
                system.select_operation(
                    approval_id,
                    operation.operation_id,
                    ApprovalDecision.APPROVE,
                    "Auto-approved: high confidence and safe operation",
                )

    return system, approval_id


def approve_all_operations(operations: List[ManipulationOperation]) -> List[str]:
    """
    Convenience function to approve all operations.

    Args:
        operations: Operations to approve

    Returns:
        List of approved operation IDs
    """
    return [op.operation_id for op in operations]


def approve_safe_operations_only(
    operations: List[ManipulationOperation], min_confidence: float = 0.8
) -> List[str]:
    """
    Approve only operations that meet safety criteria.

    Args:
        operations: Operations to filter
        min_confidence: Minimum confidence score required

    Returns:
        List of approved operation IDs
    """
    approved = []

    for operation in operations:
        if (
            operation.confidence_score >= min_confidence
            and not operation.requires_confirmation
            and operation.operation_type in ["reorder", "consolidate"]
        ):
            approved.append(operation.operation_id)

    return approved
