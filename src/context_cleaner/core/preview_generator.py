#!/usr/bin/env python3
"""
Preview Generator

Provides dry-run preview capabilities for context manipulation operations:
- Before/after visualization of proposed changes
- Detailed diff generation with highlighting
- Impact analysis and change summaries
- Interactive preview with operation details
- Multiple output formats (text, HTML, JSON)
- Safety warnings and risk indicators

Integrates with ManipulationValidator and BackupManager for safe previews.
"""

import json
import logging
import difflib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from copy import deepcopy
from enum import Enum

from .manipulation_engine import ManipulationOperation, ManipulationPlan
from .manipulation_validator import (
    ManipulationValidator,
    ValidationResult,
    RiskAssessment,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class PreviewFormat(Enum):
    """Output formats for previews."""

    TEXT = "text"
    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"


class ChangeType(Enum):
    """Types of changes that can be previewed."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    UNCHANGED = "unchanged"


@dataclass
class ChangeDetail:
    """Details of a specific change."""

    change_type: ChangeType
    key: str
    original_value: Optional[Any] = None
    new_value: Optional[Any] = None
    size_change: int = 0  # Character difference
    confidence: float = 0.0  # Confidence in change safety
    risk_level: RiskLevel = RiskLevel.LOW
    description: str = ""


@dataclass
class OperationPreview:
    """Preview of a single operation."""

    operation: ManipulationOperation
    changes: List[ChangeDetail]
    validation_result: Optional[ValidationResult] = None
    risk_assessment: Optional[RiskAssessment] = None
    estimated_impact: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PlanPreview:
    """Complete preview of a manipulation plan."""

    plan: ManipulationPlan
    operation_previews: List[OperationPreview]
    summary: Dict[str, Any]
    total_changes: int
    total_size_reduction: int
    overall_risk: RiskLevel
    preview_timestamp: str
    requires_confirmation: bool = False


class PreviewGenerator:
    """
    Dry-Run Preview Generator

    Generates comprehensive previews of manipulation operations without
    actually executing them, providing visual diffs and impact analysis.
    """

    def __init__(
        self,
        validator: Optional[ManipulationValidator] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize preview generator."""
        self.validator = validator or ManipulationValidator()
        self.config = config or {}

        # Configuration
        self.max_preview_size = self.config.get(
            "max_preview_size", 10000
        )  # Max chars to preview
        self.show_unchanged_context = self.config.get("show_unchanged_context", False)
        self.highlight_risks = self.config.get("highlight_risks", True)
        self.include_validation = self.config.get("include_validation", True)
        self.truncate_long_values = self.config.get("truncate_long_values", True)
        self.max_value_length = self.config.get("max_value_length", 500)

        logger.info("PreviewGenerator initialized")

    def _truncate_value(self, value: Any) -> str:
        """Truncate long values for preview display."""
        value_str = str(value)
        if self.truncate_long_values and len(value_str) > self.max_value_length:
            return value_str[: self.max_value_length] + "... (truncated)"
        return value_str

    def _calculate_change_confidence(
        self, operation: ManipulationOperation, key: str, context_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a specific change."""
        try:
            base_confidence = operation.confidence_score

            # Adjust based on content analysis
            if key in context_data:
                content = str(context_data[key])

                # Higher confidence for obviously safe operations
                if operation.operation_type == "remove":
                    if any(
                        word in content.lower()
                        for word in ["duplicate", "redundant", "obsolete"]
                    ):
                        base_confidence = min(1.0, base_confidence + 0.1)

                # Lower confidence for critical content
                if any(
                    word in content.lower()
                    for word in ["critical", "important", "key", "essential"]
                ):
                    base_confidence = max(0.0, base_confidence - 0.2)

            return max(0.0, min(1.0, base_confidence))

        except Exception as e:
            logger.warning(f"Error calculating change confidence: {e}")
            return operation.confidence_score

    def _simulate_operation_execution(
        self, operation: ManipulationOperation, context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate operation execution to generate preview."""
        simulated_context = deepcopy(context_data)

        try:
            if operation.operation_type == "remove":
                # Remove specified keys
                for key in operation.target_keys:
                    if key in simulated_context:
                        del simulated_context[key]

            elif operation.operation_type == "consolidate":
                # Consolidate multiple keys into one
                if len(operation.target_keys) > 1:
                    consolidated_content = []
                    for key in operation.target_keys:
                        if key in simulated_context:
                            consolidated_content.append(
                                f"{key}: {simulated_context[key]}"
                            )
                            del simulated_context[key]

                    # Create consolidated key
                    consolidated_key = f"consolidated_{operation.target_keys[0]}"
                    simulated_context[consolidated_key] = "\n".join(
                        consolidated_content
                    )

            elif operation.operation_type == "summarize":
                # Summarize content (simulate by shortening)
                for key in operation.target_keys:
                    if key in simulated_context:
                        original = str(simulated_context[key])
                        if len(original) > 200:
                            # Simulate summarization
                            summary = (
                                original[:100] + "...[summarized]..." + original[-50:]
                            )
                            simulated_context[key] = summary

            elif operation.operation_type == "reorder":
                # Reordering doesn't change content, just structure
                # For preview purposes, we'll keep it the same
                pass

            return simulated_context

        except Exception as e:
            logger.error(f"Error simulating operation: {e}")
            return simulated_context

    def _generate_change_details(
        self,
        original_context: Dict[str, Any],
        modified_context: Dict[str, Any],
        operation: ManipulationOperation,
    ) -> List[ChangeDetail]:
        """Generate detailed change information."""
        changes = []
        all_keys = set(original_context.keys()) | set(modified_context.keys())

        for key in all_keys:
            original_value = original_context.get(key)
            new_value = modified_context.get(key)

            # Determine change type
            if key not in original_context:
                change_type = ChangeType.ADDED
                size_change = len(str(new_value))
                description = f"Added new key '{key}'"

            elif key not in modified_context:
                change_type = ChangeType.REMOVED
                size_change = -len(str(original_value))
                description = f"Removed key '{key}'"

            elif str(original_value) != str(new_value):
                change_type = ChangeType.MODIFIED
                size_change = len(str(new_value)) - len(str(original_value))
                description = f"Modified key '{key}'"

            else:
                change_type = ChangeType.UNCHANGED
                size_change = 0
                description = f"Key '{key}' unchanged"

                # Skip unchanged keys unless configured to show them
                if not self.show_unchanged_context:
                    continue

            # Calculate confidence and risk for this change
            confidence = self._calculate_change_confidence(
                operation, key, original_context
            )

            # Assess risk level based on change type and content
            if change_type == ChangeType.REMOVED and key in operation.target_keys:
                risk_level = RiskLevel.MEDIUM if confidence > 0.7 else RiskLevel.HIGH
            elif change_type == ChangeType.MODIFIED:
                risk_level = RiskLevel.LOW if confidence > 0.8 else RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW

            change_detail = ChangeDetail(
                change_type=change_type,
                key=key,
                original_value=original_value,
                new_value=new_value,
                size_change=size_change,
                confidence=confidence,
                risk_level=risk_level,
                description=description,
            )

            changes.append(change_detail)

        return changes

    def preview_operation(
        self,
        operation: ManipulationOperation,
        context_data: Dict[str, Any],
        include_validation: Optional[bool] = None,
    ) -> OperationPreview:
        """Generate preview for a single operation."""
        preview_start = datetime.now()

        try:
            # Simulate operation execution
            modified_context = self._simulate_operation_execution(
                operation, context_data
            )

            # Generate change details
            changes = self._generate_change_details(
                context_data, modified_context, operation
            )

            # Perform validation if requested
            validation_result = None
            risk_assessment = None

            if include_validation or (
                include_validation is None and self.include_validation
            ):
                if hasattr(self.validator, "validate_operation_enhanced"):
                    validation_result, risk_assessment = (
                        self.validator.validate_operation_enhanced(
                            operation, context_data, enable_risk_assessment=True
                        )
                    )
                else:
                    validation_result = self.validator.validate_operation(
                        operation, context_data
                    )

            # Calculate impact metrics
            total_size_change = sum(change.size_change for change in changes)
            affected_keys = [
                change.key
                for change in changes
                if change.change_type != ChangeType.UNCHANGED
            ]

            estimated_impact = {
                "affected_keys": len(affected_keys),
                "total_size_change": total_size_change,
                "size_reduction_percentage": (
                    (
                        abs(total_size_change)
                        / sum(len(str(v)) for v in context_data.values())
                    )
                    * 100
                    if context_data
                    else 0
                ),
                "risk_score": (
                    sum(
                        1
                        for change in changes
                        if change.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                    )
                    / len(changes)
                    if changes
                    else 0
                ),
            }

            # Generate warnings
            warnings = []
            if total_size_change < 0 and abs(total_size_change) > 1000:
                warnings.append(
                    f"Large content reduction: {abs(total_size_change)} characters"
                )

            high_risk_changes = [
                c
                for c in changes
                if c.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            ]
            if high_risk_changes:
                warnings.append(f"{len(high_risk_changes)} high-risk changes detected")

            if validation_result and validation_result.validation_errors:
                warnings.extend(validation_result.validation_errors)

            preview = OperationPreview(
                operation=operation,
                changes=changes,
                validation_result=validation_result,
                risk_assessment=risk_assessment,
                estimated_impact=estimated_impact,
                warnings=warnings,
            )

            execution_time = (datetime.now() - preview_start).total_seconds()
            logger.debug(f"Generated operation preview in {execution_time:.3f}s")

            return preview

        except Exception as e:
            logger.error(f"Failed to generate operation preview: {e}")
            # Return minimal preview with error
            return OperationPreview(
                operation=operation,
                changes=[],
                warnings=[f"Preview generation failed: {e}"],
            )

    def preview_plan(
        self,
        plan: ManipulationPlan,
        context_data: Dict[str, Any],
        include_validation: Optional[bool] = None,
    ) -> PlanPreview:
        """Generate comprehensive preview for a manipulation plan."""
        preview_start = datetime.now()

        try:
            operation_previews = []
            cumulative_context = deepcopy(context_data)
            total_changes = 0
            total_size_reduction = 0
            max_risk_level = RiskLevel.LOW
            all_warnings = []

            # Generate preview for each operation
            for operation in plan.operations:
                op_preview = self.preview_operation(
                    operation, cumulative_context, include_validation=include_validation
                )

                operation_previews.append(op_preview)

                # Update metrics
                total_changes += len(
                    [
                        c
                        for c in op_preview.changes
                        if c.change_type != ChangeType.UNCHANGED
                    ]
                )
                total_size_reduction += sum(
                    c.size_change for c in op_preview.changes if c.size_change < 0
                )

                # Track highest risk level
                for change in op_preview.changes:
                    if change.risk_level.value > max_risk_level.value:
                        max_risk_level = change.risk_level

                all_warnings.extend(op_preview.warnings)

                # Apply operation to cumulative context for next operation
                cumulative_context = self._simulate_operation_execution(
                    operation, cumulative_context
                )

            # Generate summary
            original_size = sum(len(str(v)) for v in context_data.values())
            final_size = sum(len(str(v)) for v in cumulative_context.values())
            actual_size_reduction = original_size - final_size
            reduction_percentage = (
                (actual_size_reduction / original_size * 100)
                if original_size > 0
                else 0
            )

            summary = {
                "total_operations": len(plan.operations),
                "total_keys_affected": len(
                    set(
                        key
                        for op_preview in operation_previews
                        for change in op_preview.changes
                        for key in [change.key]
                        if change.change_type != ChangeType.UNCHANGED
                    )
                ),
                "original_size": original_size,
                "final_size": final_size,
                "size_reduction": actual_size_reduction,
                "reduction_percentage": reduction_percentage,
                "estimated_execution_time": plan.estimated_execution_time,
                "confidence_score": (
                    sum(op.confidence_score for op in plan.operations)
                    / len(plan.operations)
                    if plan.operations
                    else 0
                ),
                "risk_distribution": {
                    "low": sum(
                        1
                        for op_preview in operation_previews
                        for change in op_preview.changes
                        if change.risk_level == RiskLevel.LOW
                    ),
                    "medium": sum(
                        1
                        for op_preview in operation_previews
                        for change in op_preview.changes
                        if change.risk_level == RiskLevel.MEDIUM
                    ),
                    "high": sum(
                        1
                        for op_preview in operation_previews
                        for change in op_preview.changes
                        if change.risk_level == RiskLevel.HIGH
                    ),
                    "critical": sum(
                        1
                        for op_preview in operation_previews
                        for change in op_preview.changes
                        if change.risk_level == RiskLevel.CRITICAL
                    ),
                },
            }

            # Determine if confirmation is required
            requires_confirmation = (
                plan.requires_user_approval
                or max_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
                or reduction_percentage > 50
                or any("error" in warning.lower() for warning in all_warnings)
            )

            plan_preview = PlanPreview(
                plan=plan,
                operation_previews=operation_previews,
                summary=summary,
                total_changes=total_changes,
                total_size_reduction=abs(total_size_reduction),
                overall_risk=max_risk_level,
                preview_timestamp=preview_start.isoformat(),
                requires_confirmation=requires_confirmation,
            )

            execution_time = (datetime.now() - preview_start).total_seconds()
            logger.info(f"Generated plan preview in {execution_time:.3f}s")

            return plan_preview

        except Exception as e:
            logger.error(f"Failed to generate plan preview: {e}")
            # Return minimal preview with error
            return PlanPreview(
                plan=plan,
                operation_previews=[],
                summary={"error": f"Preview generation failed: {e}"},
                total_changes=0,
                total_size_reduction=0,
                overall_risk=RiskLevel.HIGH,
                preview_timestamp=preview_start.isoformat(),
                requires_confirmation=True,
            )

    def generate_diff(
        self,
        original_context: Dict[str, Any],
        modified_context: Dict[str, Any],
        format_type: PreviewFormat = PreviewFormat.TEXT,
    ) -> str:
        """Generate a diff between original and modified contexts."""
        try:
            if format_type == PreviewFormat.JSON:
                return json.dumps(
                    {
                        "original": original_context,
                        "modified": modified_context,
                        "diff_generated_at": datetime.now().isoformat(),
                    },
                    indent=2,
                )

            # For text/markdown/HTML formats, generate unified diff
            original_lines = []
            modified_lines = []

            all_keys = sorted(
                set(original_context.keys()) | set(modified_context.keys())
            )

            for key in all_keys:
                original_value = original_context.get(key, "[KEY NOT FOUND]")
                modified_value = modified_context.get(key, "[KEY REMOVED]")

                original_lines.append(f"{key}: {self._truncate_value(original_value)}")
                modified_lines.append(f"{key}: {self._truncate_value(modified_value)}")

            # Generate unified diff
            diff_lines = list(
                difflib.unified_diff(
                    original_lines,
                    modified_lines,
                    fromfile="Original Context",
                    tofile="Modified Context",
                    lineterm="",
                )
            )

            if format_type == PreviewFormat.HTML:
                # Convert to HTML
                html_diff = difflib.HtmlDiff()
                return html_diff.make_file(
                    original_lines,
                    modified_lines,
                    "Original Context",
                    "Modified Context",
                )

            elif format_type == PreviewFormat.MARKDOWN:
                # Convert to markdown
                markdown_lines = ["```diff"]
                markdown_lines.extend(diff_lines)
                markdown_lines.append("```")
                return "\n".join(markdown_lines)

            else:  # TEXT format
                return "\n".join(diff_lines)

        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            return f"Error generating diff: {e}"

    def format_preview(
        self,
        preview: Union[OperationPreview, PlanPreview],
        format_type: PreviewFormat = PreviewFormat.TEXT,
        include_details: bool = True,
    ) -> str:
        """Format preview for display in specified format."""
        try:
            if format_type == PreviewFormat.JSON:
                # Convert to JSON-serializable format
                if isinstance(preview, PlanPreview):
                    preview_dict = {
                        "plan_id": preview.plan.plan_id,
                        "total_operations": len(preview.operation_previews),
                        "summary": preview.summary,
                        "overall_risk": preview.overall_risk.value,
                        "requires_confirmation": preview.requires_confirmation,
                        "preview_timestamp": preview.preview_timestamp,
                    }
                    if include_details:
                        preview_dict["operations"] = []
                        for op_preview in preview.operation_previews:
                            op_dict = {
                                "operation_id": op_preview.operation.operation_id,
                                "operation_type": op_preview.operation.operation_type,
                                "target_keys": op_preview.operation.target_keys,
                                "changes": len(op_preview.changes),
                                "warnings": op_preview.warnings,
                            }
                            preview_dict["operations"].append(op_dict)
                else:
                    preview_dict = {
                        "operation_id": preview.operation.operation_id,
                        "operation_type": preview.operation.operation_type,
                        "changes": len(preview.changes),
                        "warnings": preview.warnings,
                        "estimated_impact": preview.estimated_impact,
                    }

                return json.dumps(preview_dict, indent=2)

            elif format_type == PreviewFormat.MARKDOWN:
                return self._format_markdown_preview(preview, include_details)

            elif format_type == PreviewFormat.HTML:
                return self._format_html_preview(preview, include_details)

            else:  # TEXT format
                return self._format_text_preview(preview, include_details)

        except Exception as e:
            logger.error(f"Failed to format preview: {e}")
            return f"Error formatting preview: {e}"

    def _format_text_preview(
        self, preview: Union[OperationPreview, PlanPreview], include_details: bool
    ) -> str:
        """Format preview as plain text."""
        lines = []

        if isinstance(preview, PlanPreview):
            lines.append("=== MANIPULATION PLAN PREVIEW ===")
            lines.append(f"Plan ID: {preview.plan.plan_id}")
            lines.append(f"Operations: {len(preview.operation_previews)}")
            lines.append(f"Overall Risk: {preview.overall_risk.value.upper()}")
            lines.append(
                f"Requires Confirmation: {'YES' if preview.requires_confirmation else 'NO'}"
            )
            lines.append("")

            # Summary
            lines.append("--- SUMMARY ---")
            for key, value in preview.summary.items():
                lines.append(f"{key}: {value}")
            lines.append("")

            if include_details:
                lines.append("--- OPERATIONS ---")
                for i, op_preview in enumerate(preview.operation_previews, 1):
                    lines.append(
                        f"{i}. {op_preview.operation.operation_type.upper()} - {op_preview.operation.operation_id}"
                    )
                    lines.append(
                        f"   Target Keys: {', '.join(op_preview.operation.target_keys)}"
                    )
                    lines.append(f"   Changes: {len(op_preview.changes)}")
                    if op_preview.warnings:
                        lines.append(f"   Warnings: {len(op_preview.warnings)}")
                        for warning in op_preview.warnings:
                            lines.append(f"     - {warning}")
                    lines.append("")

        else:  # OperationPreview
            lines.append("=== OPERATION PREVIEW ===")
            lines.append(f"Operation ID: {preview.operation.operation_id}")
            lines.append(f"Type: {preview.operation.operation_type}")
            lines.append(f"Target Keys: {', '.join(preview.operation.target_keys)}")
            lines.append(f"Changes: {len(preview.changes)}")
            lines.append("")

            if preview.warnings:
                lines.append("--- WARNINGS ---")
                for warning in preview.warnings:
                    lines.append(f"⚠️  {warning}")
                lines.append("")

            if include_details and preview.changes:
                lines.append("--- CHANGES ---")
                for change in preview.changes:
                    if change.change_type == ChangeType.UNCHANGED:
                        continue

                    symbol = {
                        ChangeType.ADDED: "➕",
                        ChangeType.REMOVED: "➖",
                        ChangeType.MODIFIED: "🔄",
                        ChangeType.MOVED: "📁",
                    }.get(change.change_type, "❓")

                    lines.append(f"{symbol} {change.description}")
                    if change.size_change != 0:
                        lines.append(f"   Size change: {change.size_change:+d} chars")
                    lines.append(f"   Confidence: {change.confidence:.2f}")
                    lines.append(f"   Risk: {change.risk_level.value}")
                    lines.append("")

        return "\n".join(lines)

    def _format_markdown_preview(
        self, preview: Union[OperationPreview, PlanPreview], include_details: bool
    ) -> str:
        """Format preview as markdown."""
        lines = []

        if isinstance(preview, PlanPreview):
            lines.append("# Manipulation Plan Preview")
            lines.append(f"**Plan ID:** {preview.plan.plan_id}")
            lines.append(f"**Operations:** {len(preview.operation_previews)}")
            lines.append(f"**Overall Risk:** {preview.overall_risk.value.upper()}")
            lines.append(
                f"**Requires Confirmation:** {'YES' if preview.requires_confirmation else 'NO'}"
            )
            lines.append("")

            lines.append("## Summary")
            for key, value in preview.summary.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

            if include_details:
                lines.append("## Operations")
                for i, op_preview in enumerate(preview.operation_previews, 1):
                    lines.append(
                        f"### {i}. {op_preview.operation.operation_type.upper()}"
                    )
                    lines.append(
                        f"- **Operation ID:** {op_preview.operation.operation_id}"
                    )
                    lines.append(
                        f"- **Target Keys:** {', '.join(op_preview.operation.target_keys)}"
                    )
                    lines.append(f"- **Changes:** {len(op_preview.changes)}")
                    if op_preview.warnings:
                        lines.append("- **Warnings:**")
                        for warning in op_preview.warnings:
                            lines.append(f"  - ⚠️ {warning}")
                    lines.append("")

        else:  # OperationPreview
            lines.append("# Operation Preview")
            lines.append(f"**Operation ID:** {preview.operation.operation_id}")
            lines.append(f"**Type:** {preview.operation.operation_type}")
            lines.append(f"**Target Keys:** {', '.join(preview.operation.target_keys)}")
            lines.append("")

            if preview.warnings:
                lines.append("## Warnings")
                for warning in preview.warnings:
                    lines.append(f"⚠️ {warning}")
                lines.append("")

            if include_details and preview.changes:
                lines.append("## Changes")
                for change in preview.changes:
                    if change.change_type == ChangeType.UNCHANGED:
                        continue

                    symbol = {
                        ChangeType.ADDED: "➕",
                        ChangeType.REMOVED: "➖",
                        ChangeType.MODIFIED: "🔄",
                        ChangeType.MOVED: "📁",
                    }.get(change.change_type, "❓")

                    lines.append(f"### {symbol} {change.description}")
                    if change.size_change != 0:
                        lines.append(f"**Size change:** {change.size_change:+d} chars")
                    lines.append(f"**Confidence:** {change.confidence:.2f}")
                    lines.append(f"**Risk:** {change.risk_level.value}")
                    lines.append("")

        return "\n".join(lines)

    def _format_html_preview(
        self, preview: Union[OperationPreview, PlanPreview], include_details: bool
    ) -> str:
        """Format preview as HTML."""
        # Basic HTML formatting - could be enhanced with CSS
        html = ["<div class='manipulation-preview'>"]

        if isinstance(preview, PlanPreview):
            html.append("<h2>Manipulation Plan Preview</h2>")
            html.append(f"<p><strong>Plan ID:</strong> {preview.plan.plan_id}</p>")
            html.append(
                f"<p><strong>Operations:</strong> {len(preview.operation_previews)}</p>"
            )

            risk_class = f"risk-{preview.overall_risk.value}"
            html.append(
                f"<p><strong>Overall Risk:</strong> <span class='{risk_class}'>{preview.overall_risk.value.upper()}</span></p>"
            )

            confirmation_class = (
                "confirmation-required"
                if preview.requires_confirmation
                else "no-confirmation"
            )
            html.append(
                f"<p><strong>Requires Confirmation:</strong> <span class='{confirmation_class}'>{'YES' if preview.requires_confirmation else 'NO'}</span></p>"
            )

            html.append("<h3>Summary</h3>")
            html.append("<ul>")
            for key, value in preview.summary.items():
                html.append(f"<li><strong>{key}:</strong> {value}</li>")
            html.append("</ul>")

        else:  # OperationPreview
            html.append("<h2>Operation Preview</h2>")
            html.append(
                f"<p><strong>Operation ID:</strong> {preview.operation.operation_id}</p>"
            )
            html.append(
                f"<p><strong>Type:</strong> {preview.operation.operation_type}</p>"
            )
            html.append(
                f"<p><strong>Target Keys:</strong> {', '.join(preview.operation.target_keys)}</p>"
            )

            if preview.warnings:
                html.append("<h3>Warnings</h3>")
                html.append("<ul class='warnings'>")
                for warning in preview.warnings:
                    html.append(f"<li>⚠️ {warning}</li>")
                html.append("</ul>")

        html.append("</div>")

        return "\n".join(html)


# Convenience functions
def preview_single_operation(
    operation: ManipulationOperation,
    context_data: Dict[str, Any],
    format_type: PreviewFormat = PreviewFormat.TEXT,
) -> str:
    """Convenience function to preview a single operation."""
    generator = PreviewGenerator()
    preview = generator.preview_operation(operation, context_data)
    return generator.format_preview(preview, format_type)


def preview_manipulation_plan(
    plan: ManipulationPlan,
    context_data: Dict[str, Any],
    format_type: PreviewFormat = PreviewFormat.TEXT,
) -> str:
    """Convenience function to preview a manipulation plan."""
    generator = PreviewGenerator()
    preview = generator.preview_plan(plan, context_data)
    return generator.format_preview(preview, format_type)


if __name__ == "__main__":
    # Test preview system
    print("Testing Preview Generator...")

    from .manipulation_engine import ManipulationOperation

    # Test context data
    test_context = {
        "important_item": "This is critical information",
        "duplicate_item": "This appears multiple times",
        "temp_item": "This is temporary data",
        "config_setting": {"mode": "production", "debug": False},
    }

    # Create test operation
    test_operation = ManipulationOperation(
        operation_id="preview-test-001",
        operation_type="remove",
        target_keys=["temp_item", "duplicate_item"],
        operation_data={"removal_type": "safe_delete"},
        estimated_token_impact=-50,
        confidence_score=0.85,
        reasoning="Removing temporary and duplicate items",
        requires_confirmation=False,
    )

    generator = PreviewGenerator()

    # Generate operation preview
    preview = generator.preview_operation(test_operation, test_context)
    print(f"✅ Generated preview with {len(preview.changes)} changes")

    # Format as text
    text_output = generator.format_preview(preview, PreviewFormat.TEXT)
    print("\n--- TEXT FORMAT ---")
    print(text_output[:500] + "..." if len(text_output) > 500 else text_output)

    # Generate diff
    modified_context = generator._simulate_operation_execution(
        test_operation, test_context
    )
    diff_output = generator.generate_diff(
        test_context, modified_context, PreviewFormat.TEXT
    )
    print("\n--- DIFF OUTPUT ---")
    print(diff_output[:300] + "..." if len(diff_output) > 300 else diff_output)
