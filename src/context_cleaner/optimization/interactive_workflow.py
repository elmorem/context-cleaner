"""
Interactive Optimization Workflow Manager

This module provides interactive workflows for context optimization with user approval,
change previews, and selective application. Integrates with PR17 manipulation engine
and PR18 safety framework for comprehensive optimization with user control.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Core imports
from ..core.manipulation_engine import (
    ManipulationEngine,
    ManipulationPlan,
    ManipulationOperation,
)
from ..core.preview_generator import (
    PreviewGenerator,
    PlanPreview,
    PreviewFormat,
)
from ..core.confirmation_workflows import (
    ConfirmationWorkflowManager,
    ConfirmationLevel,
    ConfirmationResult,
)
from ..core.transaction_manager import TransactionManager

# Optimization imports
from .personalized_strategies import (
    StrategyType,
    PersonalizedOptimizationEngine,
)


class WorkflowStep(Enum):
    """Steps in the interactive optimization workflow."""

    ANALYSIS = "analysis"
    STRATEGY_SELECTION = "strategy_selection"
    PREVIEW_GENERATION = "preview_generation"
    USER_CONFIRMATION = "user_confirmation"
    CHANGE_SELECTION = "change_selection"
    EXECUTION = "execution"
    VERIFICATION = "verification"


class UserAction(Enum):
    """User actions during interactive workflow."""

    APPROVE_ALL = "approve_all"
    SELECTIVE_APPROVE = "selective_approve"
    REJECT_ALL = "reject_all"
    MODIFY_STRATEGY = "modify_strategy"
    REQUEST_PREVIEW = "request_preview"
    CANCEL = "cancel"


@dataclass
class WorkflowResult:
    """Result of an interactive optimization workflow."""

    workflow_id: str
    success: bool
    strategy_used: StrategyType
    operations_planned: int
    operations_executed: int
    operations_rejected: int
    execution_time: float
    user_satisfaction: Optional[float]  # 1-5 scale
    changes_applied: List[Dict[str, Any]]
    error_messages: List[str]
    created_at: str


@dataclass
class InteractiveSession:
    """Represents an interactive optimization session."""

    session_id: str
    context_data: Dict[str, Any]
    selected_strategy: Optional[StrategyType]
    manipulation_plan: Optional[ManipulationPlan]
    preview: Optional[PlanPreview]
    user_selections: Dict[str, bool]  # operation_id -> approved
    current_step: WorkflowStep
    started_at: str
    metadata: Dict[str, Any]


class InteractiveWorkflowManager:
    """
    Manages interactive optimization workflows with user approval and change selection.

    Provides comprehensive user control over context optimization including:
    - Strategy selection and customization
    - Operation preview and approval
    - Selective change application
    - Transaction safety and rollback
    """

    def __init__(
        self,
        manipulation_engine: Optional[ManipulationEngine] = None,
        preview_generator: Optional[PreviewGenerator] = None,
        confirmation_manager: Optional[ConfirmationWorkflowManager] = None,
        transaction_manager: Optional[TransactionManager] = None,
        personalization_engine: Optional[PersonalizedOptimizationEngine] = None,
    ):
        """Initialize interactive workflow manager."""
        self.manipulation_engine = manipulation_engine or ManipulationEngine()
        self.preview_generator = preview_generator or PreviewGenerator()
        self.confirmation_manager = (
            confirmation_manager or ConfirmationWorkflowManager()
        )
        self.transaction_manager = transaction_manager or TransactionManager()
        self.personalization_engine = (
            personalization_engine or PersonalizedOptimizationEngine()
        )

        # Session management
        self.active_sessions: Dict[str, InteractiveSession] = {}
        self.session_history: List[WorkflowResult] = []

    def _get_accurate_token_count(self, content_str: str) -> int:
        """Get accurate token count using ccusage approach."""
        try:
            from ..analysis.enhanced_token_counter import get_accurate_token_count
            return get_accurate_token_count(content_str)
        except ImportError:
            return 0

        # Configuration
        self.max_active_sessions = 10
        self.default_preview_format = PreviewFormat.TEXT
        self.auto_cleanup_sessions = True

    def start_interactive_optimization(
        self,
        context_data: Dict[str, Any],
        preferred_strategy: Optional[StrategyType] = None,
        session_id: Optional[str] = None,
    ) -> InteractiveSession:
        """
        Start a new interactive optimization session.

        Args:
            context_data: Context to optimize
            preferred_strategy: User's preferred optimization strategy
            session_id: Optional custom session ID

        Returns:
            InteractiveSession: New optimization session
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = f"opt-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{len(self.active_sessions):03d}"

        # Clean up old sessions if needed
        if (
            self.auto_cleanup_sessions
            and len(self.active_sessions) >= self.max_active_sessions
        ):
            self._cleanup_old_sessions()

        # Create new session
        session = InteractiveSession(
            session_id=session_id,
            context_data=context_data,
            selected_strategy=preferred_strategy,
            manipulation_plan=None,
            preview=None,
            user_selections={},
            current_step=WorkflowStep.ANALYSIS,
            started_at=datetime.now().isoformat(),
            metadata={
                "context_size": len(str(context_data)),
                "context_keys": (
                    list(context_data.keys()) if isinstance(context_data, dict) else []
                ),
                "preferred_strategy": (
                    preferred_strategy.value if preferred_strategy else None
                ),
            },
        )

        self.active_sessions[session_id] = session
        return session

    def recommend_strategy(
        self, session_id: str, user_preferences: Optional[Dict[str, Any]] = None
    ) -> StrategyType:
        """
        Recommend an optimization strategy based on context and user preferences.

        Args:
            session_id: Active session ID
            user_preferences: User preferences and constraints

        Returns:
            StrategyType: Recommended optimization strategy
        """
        self._get_session(session_id)

        # Simple strategy recommendation based on user preferences
        # TODO: Implement async personalized strategy when caller supports it
        if user_preferences:
            preferred_strategy = user_preferences.get("strategy", "balanced").lower()
            if preferred_strategy == "conservative":
                return StrategyType.CONSERVATIVE
            elif preferred_strategy == "aggressive":
                return StrategyType.AGGRESSIVE
            elif preferred_strategy == "focus":
                return StrategyType.FOCUS
            elif preferred_strategy == "balanced":
                return StrategyType.BALANCED

        # Default to balanced strategy
        return StrategyType.BALANCED

    def generate_optimization_plan(
        self, session_id: str, strategy: Optional[StrategyType] = None
    ) -> ManipulationPlan:
        """
        Generate an optimization plan for the given strategy.

        Args:
            session_id: Active session ID
            strategy: Optimization strategy to use

        Returns:
            ManipulationPlan: Generated manipulation plan
        """
        session = self._get_session(session_id)

        # Use provided strategy or session default
        selected_strategy = (
            strategy or session.selected_strategy or StrategyType.BALANCED
        )
        session.selected_strategy = selected_strategy
        session.current_step = WorkflowStep.STRATEGY_SELECTION

        # Generate plan based on strategy
        if selected_strategy == StrategyType.CONSERVATIVE:
            plan = self._generate_conservative_plan(session.context_data)
        elif selected_strategy == StrategyType.BALANCED:
            plan = self._generate_balanced_plan(session.context_data)
        elif selected_strategy == StrategyType.AGGRESSIVE:
            plan = self._generate_aggressive_plan(session.context_data)
        elif selected_strategy == StrategyType.FOCUS:
            plan = self._generate_focus_plan(session.context_data)
        else:
            raise ValueError(f"Unsupported strategy type: {selected_strategy}")

        session.manipulation_plan = plan
        session.current_step = WorkflowStep.PREVIEW_GENERATION
        return plan

    def generate_preview(
        self, session_id: str, preview_format: PreviewFormat = PreviewFormat.TEXT
    ) -> PlanPreview:
        """
        Generate preview of optimization changes.

        Args:
            session_id: Active session ID
            preview_format: Format for preview output

        Returns:
            PlanPreview: Preview of planned changes
        """
        session = self._get_session(session_id)

        if not session.manipulation_plan:
            raise ValueError("No manipulation plan available. Generate plan first.")

        # Generate preview using preview generator
        preview = self.preview_generator.preview_plan(
            plan=session.manipulation_plan, context_data=session.context_data
        )

        session.preview = preview
        session.current_step = WorkflowStep.USER_CONFIRMATION
        return preview

    def request_user_approval(
        self,
        session_id: str,
        confirmation_level: ConfirmationLevel = ConfirmationLevel.DETAILED,
    ) -> ConfirmationResult:
        """
        Request user approval for the optimization plan.

        Args:
            session_id: Active session ID
            confirmation_level: Level of confirmation detail required

        Returns:
            ConfirmationResult: User's approval decision
        """
        session = self._get_session(session_id)

        if not session.manipulation_plan or not session.preview:
            raise ValueError(
                "Plan and preview must be generated before requesting approval."
            )

        # Request confirmation using confirmation workflow manager
        response = self.confirmation_manager.request_plan_confirmation(
            plan=session.manipulation_plan,
            context_data=session.context_data,
            force_level=confirmation_level,
        )

        return response.result

    def apply_selective_changes(
        self, session_id: str, selected_operations: List[str]
    ) -> WorkflowResult:
        """
        Apply only the selected operations from the optimization plan.

        Args:
            session_id: Active session ID
            selected_operations: List of operation IDs to apply

        Returns:
            WorkflowResult: Results of selective application
        """
        session = self._get_session(session_id)

        if not session.manipulation_plan:
            raise ValueError("No manipulation plan available.")

        session.current_step = WorkflowStep.CHANGE_SELECTION

        # Filter operations to only selected ones
        selected_ops = [
            op
            for op in session.manipulation_plan.operations
            if op.operation_id in selected_operations
        ]

        # Create filtered plan
        filtered_plan = ManipulationPlan(
            plan_id=f"{session.manipulation_plan.plan_id}-selective",
            total_operations=len(selected_ops),
            operations=selected_ops,
            estimated_total_reduction=sum(
                op.estimated_token_impact for op in selected_ops
            ),
            estimated_execution_time=session.manipulation_plan.estimated_execution_time
            * (len(selected_ops) / len(session.manipulation_plan.operations)),
            safety_level=session.manipulation_plan.safety_level,
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat(),
        )

        # Execute the filtered plan
        return self._execute_plan_with_transaction(
            session, filtered_plan, selected_operations
        )

    def execute_full_plan(self, session_id: str) -> WorkflowResult:
        """
        Execute the complete optimization plan.

        Args:
            session_id: Active session ID

        Returns:
            WorkflowResult: Results of full plan execution
        """
        session = self._get_session(session_id)

        if not session.manipulation_plan:
            raise ValueError("No manipulation plan available.")

        # Execute all operations
        all_operation_ids = [
            op.operation_id for op in session.manipulation_plan.operations
        ]
        return self._execute_plan_with_transaction(
            session, session.manipulation_plan, all_operation_ids
        )

    def cancel_session(self, session_id: str) -> bool:
        """
        Cancel an active optimization session.

        Args:
            session_id: Session ID to cancel

        Returns:
            bool: True if session was successfully cancelled
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]

            # Create cancellation result
            result = WorkflowResult(
                workflow_id=session_id,
                success=False,
                strategy_used=session.selected_strategy or StrategyType.BALANCED,
                operations_planned=(
                    len(session.manipulation_plan.operations)
                    if session.manipulation_plan
                    else 0
                ),
                operations_executed=0,
                operations_rejected=0,
                execution_time=0.0,
                user_satisfaction=None,
                changes_applied=[],
                error_messages=["Session cancelled by user"],
                created_at=datetime.now().isoformat(),
            )

            self.session_history.append(result)
            del self.active_sessions[session_id]
            return True

        return False

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status of an optimization session.

        Args:
            session_id: Session ID to query

        Returns:
            Dict containing session status information
        """
        session = self._get_session(session_id)

        return {
            "session_id": session.session_id,
            "current_step": session.current_step.value,
            "strategy": (
                session.selected_strategy.value if session.selected_strategy else None
            ),
            "operations_planned": (
                len(session.manipulation_plan.operations)
                if session.manipulation_plan
                else 0
            ),
            "preview_available": session.preview is not None,
            "started_at": session.started_at,
            "metadata": session.metadata,
        }

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active optimization sessions.

        Returns:
            List of session status dictionaries
        """
        return [
            self.get_session_status(session_id)
            for session_id in self.active_sessions.keys()
        ]

    def get_workflow_history(self, limit: int = 50) -> List[WorkflowResult]:
        """
        Get history of completed workflows.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of WorkflowResult objects
        """
        return self.session_history[-limit:] if limit else self.session_history

    # Private methods

    def _get_session(self, session_id: str) -> InteractiveSession:
        """Get session by ID or raise error."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found or expired.")
        return self.active_sessions[session_id]

    def _cleanup_old_sessions(self):
        """Clean up oldest sessions to make room for new ones."""
        if len(self.active_sessions) < self.max_active_sessions:
            return

        # Sort by creation time and remove oldest
        sessions_by_age = sorted(
            self.active_sessions.items(), key=lambda x: x[1].started_at
        )

        # Remove oldest sessions until we're under the limit
        sessions_to_remove = len(self.active_sessions) - self.max_active_sessions + 1
        for session_id, session in sessions_by_age[:sessions_to_remove]:
            self.cancel_session(session_id)

    def _execute_plan_with_transaction(
        self,
        session: InteractiveSession,
        plan: ManipulationPlan,
        selected_operations: List[str],
    ) -> WorkflowResult:
        """Execute a plan within a transaction for safety."""
        session.current_step = WorkflowStep.EXECUTION
        start_time = datetime.now()

        try:
            # Execute within transaction for safety
            with self.transaction_manager.transaction(
                context_data=session.context_data,
                description=f"Interactive optimization: {session.selected_strategy.value}",
            ) as tx:

                # Add operations to transaction
                for operation in plan.operations:
                    if operation.operation_id in selected_operations:
                        tx.add_operation(operation)

                # Execute operations
                execution_results = tx.execute_operations(
                    manipulation_engine=self.manipulation_engine
                )

                # Transaction will auto-commit if successful

            session.current_step = WorkflowStep.VERIFICATION
            execution_time = (datetime.now() - start_time).total_seconds()

            # Create success result
            result = WorkflowResult(
                workflow_id=session.session_id,
                success=True,
                strategy_used=session.selected_strategy,
                operations_planned=len(plan.operations),
                operations_executed=len(execution_results),
                operations_rejected=len(plan.operations) - len(selected_operations),
                execution_time=execution_time,
                user_satisfaction=None,  # Will be collected separately
                changes_applied=execution_results,
                error_messages=[],
                created_at=datetime.now().isoformat(),
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            # Create failure result
            result = WorkflowResult(
                workflow_id=session.session_id,
                success=False,
                strategy_used=session.selected_strategy,
                operations_planned=len(plan.operations),
                operations_executed=0,
                operations_rejected=len(plan.operations),
                execution_time=execution_time,
                user_satisfaction=None,
                changes_applied=[],
                error_messages=[str(e)],
                created_at=datetime.now().isoformat(),
            )

        # Add to history and cleanup
        self.session_history.append(result)
        if session.session_id in self.active_sessions:
            del self.active_sessions[session.session_id]

        return result

    # Strategy-specific plan generation methods

    def _generate_conservative_plan(
        self, context_data: Dict[str, Any]
    ) -> ManipulationPlan:
        """Generate conservative optimization plan with minimal changes."""
        # Conservative: Only safe, obvious optimizations
        operations = []

        # Only remove completed todos and resolved errors (safest operations)
        if isinstance(context_data, dict):
            for key, value in context_data.items():
                if isinstance(value, str):
                    # Remove obviously completed todos
                    if any(
                        marker in value.lower()
                        for marker in ["✅", "completed", "done", "resolved"]
                    ):
                        operations.append(
                            ManipulationOperation(
                                operation_id=f"conservative-remove-{key}",
                                operation_type="remove",
                                target_keys=[key],
                                operation_data={"removal_reason": "completed_item"},
                                estimated_token_impact=-self._get_accurate_token_count(value),
                                confidence_score=0.9,
                                reasoning=f"Remove completed item: {key}",
                                requires_confirmation=True,
                            )
                        )

        return ManipulationPlan(
            plan_id=f"conservative-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=sum(
                op.estimated_token_impact for op in operations
            ),
            estimated_execution_time=0.1 * len(operations),
            safety_level="high",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat(),
        )

    def _generate_balanced_plan(self, context_data: Dict[str, Any]) -> ManipulationPlan:
        """Generate balanced optimization plan with moderate changes."""
        # Create a basic analysis result using the helper method
        analysis_result = self._create_basic_analysis_result(
            context_data, health_score=70, optimization_potential=0.6
        )

        return self.manipulation_engine.create_manipulation_plan(
            context_data, analysis_result, safety_level="balanced"
        )

    def _generate_aggressive_plan(
        self, context_data: Dict[str, Any]
    ) -> ManipulationPlan:
        """Generate aggressive optimization plan with maximum optimization."""
        # Create analysis result indicating aggressive optimization potential
        analysis_result = self._create_basic_analysis_result(
            context_data, health_score=40, optimization_potential=0.8
        )

        return self.manipulation_engine.create_manipulation_plan(
            context_data, analysis_result, safety_level="aggressive"
        )

    def _generate_focus_plan(self, context_data: Dict[str, Any]) -> ManipulationPlan:
        """Generate focus-only plan with reordering but no content removal."""
        operations = []

        # Focus mode: Only reordering operations, no content removal
        if isinstance(context_data, dict):
            keys = list(context_data.keys())
            if len(keys) > 1:
                # Create reordering operation based on priority analysis
                operations.append(
                    ManipulationOperation(
                        operation_id=f"focus-reorder-{datetime.now().strftime('%H%M%S')}",
                        operation_type="reorder",
                        target_keys=keys,
                        operation_data={"reorder_strategy": "priority_based"},
                        estimated_token_impact=0,  # No content change, just reordering
                        confidence_score=0.8,
                        reasoning="Reorder content based on priority analysis",
                        requires_confirmation=True,
                    )
                )

        return ManipulationPlan(
            plan_id=f"focus-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            total_operations=len(operations),
            operations=operations,
            estimated_total_reduction=0,  # Focus mode doesn't reduce content
            estimated_execution_time=0.05 * len(operations),
            safety_level="low_risk",
            requires_user_approval=True,
            created_timestamp=datetime.now().isoformat(),
        )

    def _create_basic_analysis_result(
        self,
        context_data: Dict[str, Any],
        health_score: int = 70,
        optimization_potential: float = 0.6,
    ) -> "ContextAnalysisResult":
        """Create a basic ContextAnalysisResult for testing purposes."""
        from ..core.context_analyzer import ContextAnalysisResult
        from ..core.focus_scorer import FocusMetrics
        from ..core.redundancy_detector import RedundancyReport
        from ..core.recency_analyzer import RecencyReport
        from ..core.priority_analyzer import PriorityReport

        # Create basic metric instances with default values
        focus_metrics = FocusMetrics(
            focus_score=health_score,
            priority_alignment_score=70,
            current_work_ratio=0.6,
            attention_clarity_score=65,
            total_content_items=len(context_data),
            work_related_items=max(1, int(len(context_data) * 0.7)),
            high_priority_items=max(1, int(len(context_data) * 0.3)),
            active_task_items=max(1, int(len(context_data) * 0.4)),
            noise_items=int(len(context_data) * 0.2),
            context_coherence_score=65,
            task_clarity_score=70,
            goal_alignment_score=68,
            important_items_in_top_quarter=max(1, int(len(context_data) * 0.25)),
            current_work_in_top_half=max(1, int(len(context_data) * 0.5)),
            noise_in_bottom_half=max(1, int(len(context_data) * 0.3)),
            focus_keywords_found=["current", "todo", "working"],
            distraction_keywords_found=["old", "archived", "deprecated"],
            analysis_method_breakdown={"keyword": 50, "position": 30, "content": 20},
            focus_analysis_duration=0.05,
        )

        redundancy_report = RedundancyReport(
            duplicate_content_percentage=15.0,
            stale_content_percentage=10.0,
            redundant_files_count=2,
            obsolete_todos_count=3,
            duplicate_items=[],
            obsolete_items=[],
            redundant_file_groups=[],
            stale_error_messages=[],
            total_items_analyzed=len(context_data),
            total_estimated_tokens=len(str(context_data)),
            redundancy_analysis_duration=0.03,
            safe_to_remove=[],
            consolidation_candidates=[],
        )

        recency_report = RecencyReport(
            fresh_context_percentage=30.0,
            recent_context_percentage=40.0,
            aging_context_percentage=20.0,
            stale_context_percentage=10.0,
            fresh_items=[],
            recent_items=[],
            aging_items=[],
            stale_items=[],
            estimated_session_start=datetime.now().isoformat(),
            session_duration_minutes=60.0,
            session_activity_score=0.8,
            total_items_categorized=len(context_data),
            items_with_timestamps=int(len(context_data) * 0.7),
            analysis_timestamp=datetime.now().isoformat(),
            recency_analysis_duration=0.04,
        )

        priority_report = PriorityReport(
            priority_alignment_score=70,
            current_work_focus_percentage=65.0,
            urgent_items_ratio=0.2,
            blocking_items_count=1,
            critical_items=[],
            high_priority_items=[],
            medium_priority_items=[],
            low_priority_items=[],
            noise_items=[],
            items_with_deadlines=[],
            blocking_dependencies=[],
            priority_conflicts=[],
            reorder_recommendations=[],
            focus_improvement_actions=[],
            priority_cleanup_opportunities=[],
            total_items_analyzed=len(context_data),
            items_with_priority_signals=max(1, int(len(context_data) * 0.6)),
            priority_analysis_duration=0.06,
        )

        return ContextAnalysisResult(
            health_score=health_score,
            focus_metrics=focus_metrics,
            redundancy_report=redundancy_report,
            recency_report=recency_report,
            priority_report=priority_report,
            total_tokens=len(str(context_data)),
            total_chars=len(str(context_data)),
            context_categories={
                "files": len([k for k in context_data.keys() if "file" in k.lower()])
            },
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration=0.1,
            performance_metrics={},
            optimization_potential=optimization_potential,
            critical_context_ratio=0.7,
            cleanup_impact_estimate=int(
                len(str(context_data)) * optimization_potential * 0.1
            ),
        )


# Convenience functions


def start_interactive_optimization(
    context_data: Dict[str, Any], preferred_strategy: Optional[StrategyType] = None
) -> Tuple[InteractiveWorkflowManager, InteractiveSession]:
    """
    Convenience function to start an interactive optimization session.

    Args:
        context_data: Context to optimize
        preferred_strategy: Preferred optimization strategy

    Returns:
        Tuple of (workflow_manager, session)
    """
    manager = InteractiveWorkflowManager()
    session = manager.start_interactive_optimization(context_data, preferred_strategy)
    return manager, session


def quick_optimization_preview(
    context_data: Dict[str, Any], strategy: StrategyType = StrategyType.BALANCED
) -> PlanPreview:
    """
    Quick preview of optimization changes without full interactive session.

    Args:
        context_data: Context to preview
        strategy: Optimization strategy to use

    Returns:
        PlanPreview: Preview of planned changes
    """
    manager = InteractiveWorkflowManager()
    session = manager.start_interactive_optimization(context_data, strategy)

    # Generate plan and preview
    manager.generate_optimization_plan(session.session_id, strategy)
    preview = manager.generate_preview(session.session_id)

    # Cleanup session
    manager.cancel_session(session.session_id)

    return preview
