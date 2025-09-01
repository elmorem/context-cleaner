"""
CLI Optimization Commands for PR19

This module provides the actual implementation for optimization commands
that replace the TODO placeholders in the main CLI interface.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import click

# Core optimization imports
from ..optimization.interactive_workflow import (
    InteractiveWorkflowManager,
    start_interactive_optimization,
    quick_optimization_preview,
)
from ..optimization.personalized_strategies import StrategyType
from ..optimization.change_approval import (
    ChangeApprovalSystem,
    ApprovalDecision,
    create_quick_approval,
    approve_all_operations,
)

# Core functionality imports
from ..core.preview_generator import PreviewFormat
from ..core.confirmation_workflows import ConfirmationLevel, ConfirmationResult

# Analytics imports for PR20
from ..analytics.effectiveness_tracker import EffectivenessTracker, OptimizationOutcome


class OptimizationCommandHandler:
    """
    Handles all optimization-related CLI commands with interactive workflows.

    Replaces TODO placeholders in main CLI with actual optimization functionality
    including multiple modes, interactive approval, and change previews.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, verbose: bool = False):
        """Initialize command handler."""
        self.config = config or {}
        self.verbose = verbose
        self.workflow_manager = InteractiveWorkflowManager()

        # PR20: Initialize effectiveness tracking
        self.effectiveness_tracker = EffectivenessTracker()

    def handle_dashboard_command(self, format: str = "web", host: str = "127.0.0.1", port: int = 8080, debug: bool = False) -> None:
        """
        Handle the dashboard optimization command.

        Launches the comprehensive health dashboard with all integrated features.
        Now uses the unified comprehensive dashboard instead of basic dashboard.
        """
        try:
            if format == "json":
                # For JSON format, provide summary data
                from ..dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
                import asyncio
                
                dashboard = ComprehensiveHealthDashboard(config=self.config)
                
                if self.verbose:
                    click.echo("📊 Generating comprehensive health report JSON...")
                
                # Run async method in thread for CLI
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                report = loop.run_until_complete(
                    dashboard.generate_comprehensive_health_report()
                )
                loop.close()
                
                from dataclasses import asdict
                data = asdict(report)
                click.echo(json.dumps(data, indent=2, default=str))
                
            else:
                # Launch comprehensive web dashboard
                from ..dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
                
                if self.verbose:
                    click.echo("🚀 Starting Context Cleaner Comprehensive Dashboard...")
                
                dashboard = ComprehensiveHealthDashboard(config=self.config)
                
                click.echo("📊 Context Cleaner Comprehensive Health Dashboard")
                click.echo("=" * 60)
                click.echo(f"🌐 Dashboard URL: http://{host}:{port}")
                click.echo("📈 Features Available:")
                click.echo("   • 📊 Advanced Analytics with Plotly visualizations")
                click.echo("   • ⚡ Real-time performance monitoring")
                click.echo("   • 🗄️ Cache intelligence & optimization insights")
                click.echo("   • 📈 Interactive session timeline")
                click.echo("   • 🔄 WebSocket real-time updates")
                click.echo("   • 📤 Data export capabilities")
                click.echo()
                click.echo("💡 All dashboard components now integrated into single interface!")
                click.echo("💡 Press Ctrl+C to stop the server")
                click.echo()
                
                try:
                    dashboard.start_server(
                        host=host,
                        port=port,
                        debug=debug,
                        open_browser=True
                    )
                except KeyboardInterrupt:
                    click.echo("\n👋 Comprehensive dashboard stopped")
                    
            if self.verbose:
                click.echo("✅ Comprehensive dashboard command completed")

        except Exception as e:
            click.echo(f"❌ Comprehensive dashboard failed to load: {e}", err=True)
            if self.verbose:
                import traceback
                click.echo(traceback.format_exc(), err=True)

    def handle_quick_optimization(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle quick optimization command with minimal user interaction.

        Performs balanced optimization with auto-approval for safe operations.
        """
        import time

        session_start_time = time.time()
        tracking_session_id = None

        try:
            if self.verbose:
                click.echo("🚀 Starting quick context optimization...")

            # Get context data (would typically come from Claude Code integration)
            if not context_data:
                context_data = self._get_current_context()

            if not context_data:
                click.echo("ℹ️  No context data found to optimize")
                return

            # PR20: Start effectiveness tracking
            tracking_session_id = (
                self.effectiveness_tracker.start_optimization_tracking(
                    context_data=context_data,
                    strategy_type="BALANCED",
                    context_source="cli_quick",
                )
            )

            # Start interactive session with balanced strategy
            manager, session = start_interactive_optimization(
                context_data, StrategyType.BALANCED
            )

            # Generate optimization plan
            plan = manager.generate_optimization_plan(session.session_id)

            if len(plan.operations) == 0:
                click.echo("✅ Context already well-optimized - no changes needed")

                # PR20: Track no-changes-needed outcome
                if tracking_session_id:
                    session_time = time.time() - session_start_time
                    self.effectiveness_tracker.complete_optimization_tracking(
                        session_id=tracking_session_id,
                        optimized_context=context_data,  # No changes made
                        outcome=OptimizationOutcome.NO_CHANGES_NEEDED,
                        operations_approved=0,
                        operations_rejected=0,
                        operations_modified=0,
                        total_operations=0,
                        session_time=session_time,
                    )
                return

            # Auto-approve safe operations for quick mode
            approval_system, approval_id = create_quick_approval(
                plan.operations, auto_approve_safe=True
            )

            # Apply approved operations
            approved_ops = approval_system.get_selected_operations(approval_id)

            if approved_ops:
                result = manager.apply_selective_changes(
                    session.session_id, approved_ops
                )

                # PR20: Complete effectiveness tracking with results
                if tracking_session_id:
                    session_time = time.time() - session_start_time
                    optimized_data = (
                        result.optimized_context
                        if hasattr(result, "optimized_context")
                        else context_data
                    )

                    self.effectiveness_tracker.complete_optimization_tracking(
                        session_id=tracking_session_id,
                        optimized_context=optimized_data,
                        outcome=OptimizationOutcome.SUCCESS,
                        operations_approved=result.operations_executed,
                        operations_rejected=result.operations_rejected,
                        operations_modified=0,
                        total_operations=len(plan.operations),
                        session_time=session_time,
                    )

                click.echo(f"✅ Quick optimization completed:")
                click.echo(f"   • {result.operations_executed} operations applied")
                click.echo(f"   • {result.operations_rejected} operations skipped")

                if result.operations_executed > 0:
                    # Estimate token savings
                    total_reduction = sum(
                        op.estimated_token_impact
                        for op in plan.operations
                        if op.operation_id in approved_ops
                    )
                    click.echo(
                        f"   • Estimated token reduction: {abs(total_reduction):,}"
                    )
            else:
                click.echo("✅ Quick optimization completed - no safe changes found")

                # PR20: Track case where no operations were approved
                if tracking_session_id:
                    session_time = time.time() - session_start_time
                    self.effectiveness_tracker.complete_optimization_tracking(
                        session_id=tracking_session_id,
                        optimized_context=context_data,
                        outcome=OptimizationOutcome.NO_CHANGES_NEEDED,
                        operations_approved=0,
                        operations_rejected=len(plan.operations),
                        operations_modified=0,
                        total_operations=len(plan.operations),
                        session_time=session_time,
                    )

        except Exception as e:
            click.echo(f"❌ Quick optimization failed: {e}", err=True)

            # PR20: Track failure in effectiveness system
            if tracking_session_id:
                try:
                    session_time = time.time() - session_start_time
                    self.effectiveness_tracker.complete_optimization_tracking(
                        session_id=tracking_session_id,
                        optimized_context=context_data or {},
                        outcome=OptimizationOutcome.FAILURE,
                        operations_approved=0,
                        operations_rejected=0,
                        operations_modified=0,
                        total_operations=0,
                        session_time=session_time,
                    )
                except Exception:
                    pass  # Don't fail on tracking errors

            if self.verbose:
                import traceback

                click.echo(traceback.format_exc(), err=True)

    def handle_preview_mode(
        self,
        context_data: Optional[Dict[str, Any]] = None,
        strategy: StrategyType = StrategyType.BALANCED,
        format: str = "text",
    ) -> None:
        """
        Handle preview mode command showing changes without applying them.

        Generates detailed preview of what optimization would do.
        """
        try:
            if self.verbose:
                click.echo("👁️ Generating context optimization preview...")

            # Get context data
            if not context_data:
                context_data = self._get_current_context()

            if not context_data:
                click.echo("ℹ️  No context data found to preview")
                return

            # Generate preview
            preview_format = (
                PreviewFormat.JSON if format == "json" else PreviewFormat.TEXT
            )
            preview = quick_optimization_preview(context_data, strategy)

            if format == "json":
                preview_data = {
                    "strategy": strategy.value,
                    "operations_planned": len(preview.operation_previews),
                    "estimated_reduction": preview.total_size_reduction,
                    "safety_level": (
                        preview.overall_risk.value
                        if hasattr(preview, "overall_risk")
                        else "unknown"
                    ),
                    "operations": [],
                }

                for op_preview in preview.operation_previews:
                    preview_data["operations"].append(
                        {
                            "operation_id": op_preview.operation.operation_id,
                            "type": op_preview.operation.operation_type,
                            "impact": op_preview.estimated_impact.get(
                                "token_reduction", 0
                            ),
                            "confidence": op_preview.operation.confidence_score,
                            "description": op_preview.operation.reasoning,
                        }
                    )

                click.echo(json.dumps(preview_data, indent=2))
            else:
                # Format text preview
                click.echo("📋 Optimization Preview")
                click.echo("=" * 50)
                click.echo(f"Strategy: {strategy.value.title()}")
                click.echo(f"Operations Planned: {len(preview.operation_previews)}")
                click.echo(
                    f"Estimated Token Reduction: {abs(preview.total_size_reduction):,}"
                )
                click.echo()

                if preview.operation_previews:
                    click.echo("Planned Changes:")
                    for i, op_preview in enumerate(preview.operation_previews, 1):
                        click.echo(
                            f"  {i}. {op_preview.operation.operation_type.upper()}: {op_preview.operation.reasoning}"
                        )
                        impact = (
                            op_preview.estimated_impact.get("token_reduction", 0)
                            if isinstance(op_preview.estimated_impact, dict)
                            else 0
                        )
                        click.echo(
                            f"     Impact: {impact:+d} tokens "
                            f"(Confidence: {op_preview.operation.confidence_score:.1%})"
                        )
                else:
                    click.echo(
                        "No optimization changes needed - context is already well-structured"
                    )

            click.echo("\n📋 Preview completed - no changes applied")

        except Exception as e:
            click.echo(f"❌ Preview generation failed: {e}", err=True)
            if self.verbose:
                import traceback

                click.echo(traceback.format_exc(), err=True)

    def handle_aggressive_optimization(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle aggressive optimization with maximum reduction and minimal confirmation.

        Uses aggressive strategy with user confirmation for high-impact changes.
        """
        try:
            if self.verbose:
                click.echo("⚡ Starting aggressive context optimization...")

            # Get context data
            if not context_data:
                context_data = self._get_current_context()

            if not context_data:
                click.echo("ℹ️  No context data found to optimize")
                return

            # Start interactive session with aggressive strategy
            manager, session = start_interactive_optimization(
                context_data, StrategyType.AGGRESSIVE
            )

            # Generate aggressive optimization plan
            plan = manager.generate_optimization_plan(
                session.session_id, StrategyType.AGGRESSIVE
            )

            if len(plan.operations) == 0:
                click.echo(
                    "✅ Context already optimized - no aggressive changes available"
                )
                return

            # Show preview and request confirmation for aggressive changes
            preview = manager.generate_preview(session.session_id)

            click.echo(f"⚡ Aggressive Optimization Plan:")
            click.echo(f"   • {len(plan.operations)} operations planned")
            click.echo(
                f"   • Estimated reduction: {abs(plan.estimated_total_reduction):,} tokens"
            )
            click.echo()

            # Request user confirmation
            if click.confirm("Apply aggressive optimization changes?", default=False):
                # Execute all operations
                result = manager.execute_full_plan(session.session_id)

                if result.success:
                    click.echo("✅ Aggressive optimization completed:")
                    click.echo(f"   • {result.operations_executed} operations applied")
                    click.echo(f"   • Execution time: {result.execution_time:.2f}s")
                else:
                    click.echo("❌ Aggressive optimization failed:")
                    for error in result.error_messages:
                        click.echo(f"   • {error}")
            else:
                click.echo("⏹️  Aggressive optimization cancelled by user")
                manager.cancel_session(session.session_id)

        except Exception as e:
            click.echo(f"❌ Aggressive optimization failed: {e}", err=True)
            if self.verbose:
                import traceback

                click.echo(traceback.format_exc(), err=True)

    def handle_focus_mode(self, context_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle focus mode optimization with priority reordering but no content removal.

        Focuses on improving context structure without removing content.
        """
        try:
            if self.verbose:
                click.echo("🎯 Starting focus context optimization...")

            # Get context data
            if not context_data:
                context_data = self._get_current_context()

            if not context_data:
                click.echo("ℹ️  No context data found to focus")
                return

            # Start interactive session with focus strategy
            manager, session = start_interactive_optimization(
                context_data, StrategyType.FOCUS
            )

            # Generate focus optimization plan
            plan = manager.generate_optimization_plan(
                session.session_id, StrategyType.FOCUS
            )

            if len(plan.operations) == 0:
                click.echo("✅ Context focus already optimal - no reordering needed")
                return

            # Focus mode is low-risk, so auto-apply
            result = manager.execute_full_plan(session.session_id)

            if result.success:
                click.echo("✅ Context refocused successfully:")
                click.echo(
                    f"   • {result.operations_executed} reordering operations applied"
                )
                click.echo(f"   • No content removed (focus mode)")
                click.echo(f"   • Execution time: {result.execution_time:.2f}s")
            else:
                click.echo("❌ Context refocus failed:")
                for error in result.error_messages:
                    click.echo(f"   • {error}")

        except Exception as e:
            click.echo(f"❌ Focus optimization failed: {e}", err=True)
            if self.verbose:
                import traceback

                click.echo(traceback.format_exc(), err=True)

    def handle_full_optimization(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle full interactive optimization workflow with user approval.

        Complete optimization workflow with user interaction and selective approval.
        """
        try:
            if self.verbose:
                click.echo("🔍 Starting full interactive optimization...")

            # Get context data
            if not context_data:
                context_data = self._get_current_context()

            if not context_data:
                click.echo("ℹ️  No context data found to optimize")
                return

            # Start interactive session
            manager, session = start_interactive_optimization(context_data)

            # Recommend strategy
            recommended_strategy = manager.recommend_strategy(session.session_id)
            click.echo(f"💡 Recommended strategy: {recommended_strategy.value.title()}")

            # Allow user to choose strategy
            strategy_choices = [
                s.value for s in StrategyType if s != StrategyType.WORKFLOW_SPECIFIC
            ]
            strategy_choice = click.prompt(
                "Choose optimization strategy",
                type=click.Choice(strategy_choices),
                default=recommended_strategy.value,
            )

            selected_strategy = StrategyType(strategy_choice)

            # Generate plan
            plan = manager.generate_optimization_plan(
                session.session_id, selected_strategy
            )

            if len(plan.operations) == 0:
                click.echo("✅ Context already well-optimized - no changes needed")
                return

            # Generate and show preview
            preview = manager.generate_preview(session.session_id)

            click.echo(f"\n📊 Optimization Analysis:")
            click.echo(f"   • Strategy: {selected_strategy.value.title()}")
            click.echo(f"   • Operations planned: {len(plan.operations)}")
            click.echo(
                f"   • Estimated reduction: {abs(plan.estimated_total_reduction):,} tokens"
            )

            # Simple approval for CLI (full interactive mode would use web interface)
            if click.confirm("\nProceed with optimization?", default=True):
                # For CLI simplicity, apply all operations
                result = manager.execute_full_plan(session.session_id)

                if result.success:
                    click.echo("✅ Context optimization completed successfully:")
                    click.echo(f"   • {result.operations_executed} operations applied")
                    click.echo(f"   • Execution time: {result.execution_time:.2f}s")

                    if result.operations_executed > 0:
                        click.echo(
                            "\n📊 Run 'context-cleaner dashboard' to view updated metrics"
                        )
                else:
                    click.echo("❌ Context optimization failed:")
                    for error in result.error_messages:
                        click.echo(f"   • {error}")
            else:
                click.echo("⏹️  Optimization cancelled by user")
                manager.cancel_session(session.session_id)

        except Exception as e:
            click.echo(f"❌ Full optimization failed: {e}", err=True)
            if self.verbose:
                import traceback

                click.echo(traceback.format_exc(), err=True)

    # Helper methods

    def _get_current_context(self) -> Optional[Dict[str, Any]]:
        """
        Get current context data for optimization.

        This would typically integrate with Claude Code to get actual context.
        For now, returns sample data for testing.
        """
        # TODO: Integrate with actual Claude Code context extraction
        # This is a placeholder that would be replaced with real context data

        sample_context = {
            "current_task": "Implementing PR19 optimization modes",
            "file_1": "Working on interactive workflow manager",
            "file_2": "Creating change approval system",
            "todo_1": "✅ Create optimization modes",
            "todo_2": "Implement CLI integration",
            "todo_3": "Add user confirmation workflows",
            "error_log": "Fixed import error in optimization module",
            "notes": "Need to test all optimization strategies",
        }

        return sample_context


# Convenience functions for CLI integration


def create_optimization_handler(
    config: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> OptimizationCommandHandler:
    """Create an optimization command handler."""
    return OptimizationCommandHandler(config, verbose)


def execute_quick_optimization(
    context_data: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> None:
    """Execute quick optimization command."""
    handler = OptimizationCommandHandler(verbose=verbose)
    handler.handle_quick_optimization(context_data)


def execute_preview_mode(
    context_data: Optional[Dict[str, Any]] = None,
    strategy: str = "balanced",
    format: str = "text",
    verbose: bool = False,
) -> None:
    """Execute preview mode command."""
    handler = OptimizationCommandHandler(verbose=verbose)
    strategy_type = StrategyType(strategy)
    handler.handle_preview_mode(context_data, strategy_type, format)


def execute_aggressive_optimization(
    context_data: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> None:
    """Execute aggressive optimization command."""
    handler = OptimizationCommandHandler(verbose=verbose)
    handler.handle_aggressive_optimization(context_data)


def execute_focus_mode(
    context_data: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> None:
    """Execute focus mode optimization command."""
    handler = OptimizationCommandHandler(verbose=verbose)
    handler.handle_focus_mode(context_data)


def execute_full_optimization(
    context_data: Optional[Dict[str, Any]] = None, verbose: bool = False
) -> None:
    """Execute full interactive optimization command."""
    handler = OptimizationCommandHandler(verbose=verbose)
    handler.handle_full_optimization(context_data)
