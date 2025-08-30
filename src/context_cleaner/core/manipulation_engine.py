#!/usr/bin/env python3
"""
Context Manipulation Engine

Provides core context manipulation operations including:
- Content removal (duplicates, obsolete todos, stale errors)
- Content consolidation (similar todos, repeated explanations) 
- Content reordering (priority-based reorganization)
- Content summarization (verbose conversations, repeated patterns)

Integrates with existing analysis infrastructure from PR15/16.
Operations are atomic and can be validated before application.
"""

import json
import logging
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from copy import deepcopy

from .context_analyzer import ContextAnalysisResult
from .redundancy_detector import RedundancyReport  
from .priority_analyzer import PriorityReport

logger = logging.getLogger(__name__)


@dataclass
class ManipulationOperation:
    """Represents a single context manipulation operation."""
    
    operation_id: str  # Unique identifier for this operation
    operation_type: str  # remove, consolidate, reorder, summarize
    target_keys: List[str]  # Context keys affected by this operation
    operation_data: Dict[str, Any]  # Operation-specific data
    estimated_token_impact: int  # Estimated token change (negative = reduction)
    confidence_score: float  # Confidence in operation safety (0-1)
    reasoning: str  # Human-readable explanation
    requires_confirmation: bool  # Whether this operation needs user approval


@dataclass 
class ManipulationPlan:
    """Complete plan for context manipulation operations."""
    
    plan_id: str  # Unique identifier for this plan
    total_operations: int  # Number of operations in plan
    operations: List[ManipulationOperation]  # Individual operations
    estimated_total_reduction: int  # Total estimated token reduction
    estimated_execution_time: float  # Estimated time to execute plan
    safety_level: str  # conservative, balanced, aggressive
    requires_user_approval: bool  # Whether plan needs approval
    created_timestamp: str  # When plan was created
    

@dataclass
class ManipulationResult:
    """Result of executing a manipulation plan."""
    
    plan_id: str  # Associated plan ID
    execution_success: bool  # Whether execution succeeded
    operations_executed: int  # Number of operations completed
    operations_failed: int  # Number of operations that failed
    actual_token_reduction: int  # Actual tokens reduced
    execution_time: float  # Actual execution time
    modified_context: Dict[str, Any]  # The modified context data
    operation_results: List[Dict[str, Any]]  # Results for each operation
    error_messages: List[str]  # Any error messages
    executed_timestamp: str  # When execution completed


class ManipulationEngine:
    """
    Core Context Manipulation Engine
    
    Performs actual context modifications based on analysis results.
    Integrates with existing ContextAnalyzer, RedundancyDetector, etc.
    """
    
    # Operation limits for safety
    MAX_OPERATIONS_PER_PLAN = 100
    MAX_SINGLE_OPERATION_IMPACT = 10000  # Max tokens to modify in one operation
    MIN_CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence for auto-execution
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize manipulation engine with safety settings."""
        self.config = config or {}
        
        # Safety settings
        self.max_operations = self.config.get('max_operations', self.MAX_OPERATIONS_PER_PLAN)
        self.confidence_threshold = self.config.get('confidence_threshold', self.MIN_CONFIDENCE_THRESHOLD)
        self.require_confirmation_by_default = self.config.get('require_confirmation', True)
        
        logger.info("ManipulationEngine initialized with safety constraints")

    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        return hashlib.md5(f"{time.time()}{hash(id(self))}".encode()).hexdigest()[:8]
    
    def _calculate_content_tokens(self, content: Any) -> int:
        """Estimate token count for content."""
        try:
            if isinstance(content, (dict, list)):
                content_str = json.dumps(content, default=str)
            else:
                content_str = str(content)
            return len(content_str) // 4  # Rough token estimate
        except Exception:
            return 0

    def _create_remove_operation(
        self,
        target_keys: List[str], 
        content_data: Dict[str, Any],
        reasoning: str,
        confidence: float = 0.8
    ) -> ManipulationOperation:
        """Create a content removal operation."""
        
        # Calculate token impact
        token_impact = 0
        for key in target_keys:
            if key in content_data:
                token_impact -= self._calculate_content_tokens(content_data[key])
        
        return ManipulationOperation(
            operation_id=self._generate_operation_id(),
            operation_type="remove",
            target_keys=target_keys,
            operation_data={
                "removal_type": "safe_delete",
                "backup_data": {key: content_data.get(key) for key in target_keys}
            },
            estimated_token_impact=token_impact,
            confidence_score=confidence,
            reasoning=reasoning,
            requires_confirmation=confidence < self.confidence_threshold
        )

    def _create_consolidate_operation(
        self,
        target_keys: List[str],
        content_data: Dict[str, Any], 
        consolidation_strategy: str,
        reasoning: str,
        confidence: float = 0.7
    ) -> ManipulationOperation:
        """Create a content consolidation operation."""
        
        # Calculate token impact (usually reduction from combining similar content)
        original_tokens = sum(
            self._calculate_content_tokens(content_data.get(key, "")) 
            for key in target_keys
        )
        
        # Estimate consolidated size (typically 60-80% of original)
        estimated_consolidated_tokens = int(original_tokens * 0.7)
        token_impact = estimated_consolidated_tokens - original_tokens
        
        return ManipulationOperation(
            operation_id=self._generate_operation_id(),
            operation_type="consolidate", 
            target_keys=target_keys,
            operation_data={
                "strategy": consolidation_strategy,
                "original_content": {key: content_data.get(key) for key in target_keys}
            },
            estimated_token_impact=token_impact,
            confidence_score=confidence,
            reasoning=reasoning,
            requires_confirmation=confidence < self.confidence_threshold or len(target_keys) > 3
        )

    def _create_reorder_operation(
        self,
        target_keys: List[str],
        content_data: Dict[str, Any],
        new_order: List[str], 
        reasoning: str,
        confidence: float = 0.9
    ) -> ManipulationOperation:
        """Create a content reordering operation."""
        
        return ManipulationOperation(
            operation_id=self._generate_operation_id(),
            operation_type="reorder",
            target_keys=target_keys,
            operation_data={
                "new_order": new_order,
                "original_order": target_keys
            },
            estimated_token_impact=0,  # Reordering doesn't change token count
            confidence_score=confidence,
            reasoning=reasoning,
            requires_confirmation=False  # Reordering is generally safe
        )

    def _create_summarize_operation(
        self,
        target_keys: List[str],
        content_data: Dict[str, Any],
        summarization_type: str,
        reasoning: str, 
        confidence: float = 0.6
    ) -> ManipulationOperation:
        """Create a content summarization operation."""
        
        # Calculate token impact (reduction from summarization)
        original_tokens = sum(
            self._calculate_content_tokens(content_data.get(key, ""))
            for key in target_keys
        )
        
        # Estimate summary size (typically 30-50% of original)
        estimated_summary_tokens = int(original_tokens * 0.4)
        token_impact = estimated_summary_tokens - original_tokens
        
        return ManipulationOperation(
            operation_id=self._generate_operation_id(),
            operation_type="summarize",
            target_keys=target_keys,
            operation_data={
                "summarization_type": summarization_type,
                "original_content": {key: content_data.get(key) for key in target_keys}
            },
            estimated_token_impact=token_impact,
            confidence_score=confidence,
            reasoning=reasoning,
            requires_confirmation=True  # Summarization always needs confirmation
        )

    def generate_removal_operations(
        self, 
        context_data: Dict[str, Any],
        redundancy_report: RedundancyReport
    ) -> List[ManipulationOperation]:
        """Generate operations to remove redundant/obsolete content."""
        operations = []
        
        try:
            # Simple duplicate detection based on content similarity
            # Since we don't have the exact structure from RedundancyReport, implement basic duplicate detection
            
            content_to_keys = {}  # Map content to keys that contain it
            for key, value in context_data.items():
                content_str = str(value).strip().lower()
                if content_str:
                    if content_str not in content_to_keys:
                        content_to_keys[content_str] = []
                    content_to_keys[content_str].append(key)
            
            # Find exact duplicates
            for content, keys in content_to_keys.items():
                if len(keys) > 1:  # Duplicate content found
                    # Keep the first key, remove the rest
                    keys_to_remove = keys[1:]
                    operations.append(
                        self._create_remove_operation(
                            target_keys=keys_to_remove,
                            content_data=context_data,
                            reasoning=f"Removing {len(keys_to_remove)} exact duplicate(s) of content",
                            confidence=0.95
                        )
                    )
            
            # Find obsolete items (items with completion markers)
            obsolete_patterns = [r'completed', r'done', r'fixed', r'resolved', r'✅', r'☑']
            obsolete_keys = []
            
            for key, value in context_data.items():
                content_str = str(value).lower()
                if any(pattern in content_str for pattern in obsolete_patterns):
                    obsolete_keys.append(key)
            
            if obsolete_keys:
                operations.append(
                    self._create_remove_operation(
                        target_keys=obsolete_keys,
                        content_data=context_data,
                        reasoning=f"Removing {len(obsolete_keys)} obsolete/completed items",
                        confidence=0.85
                    )
                )
            
            # Find resolved errors (error messages that mention being fixed)
            resolved_error_keys = []
            for key, value in context_data.items():
                if 'error' in key.lower():
                    content_str = str(value).lower()
                    if any(word in content_str for word in ['fixed', 'resolved', 'solved']):
                        resolved_error_keys.append(key)
            
            if resolved_error_keys:
                operations.append(
                    self._create_remove_operation(
                        target_keys=resolved_error_keys,
                        content_data=context_data,
                        reasoning=f"Removing {len(resolved_error_keys)} resolved error message(s)",
                        confidence=0.80
                    )
                )
                
        except Exception as e:
            logger.error(f"Error generating removal operations: {e}")
        
        return operations

    def generate_consolidation_operations(
        self,
        context_data: Dict[str, Any], 
        redundancy_report: RedundancyReport
    ) -> List[ManipulationOperation]:
        """Generate operations to consolidate similar content."""
        operations = []
        
        try:
            # Find similar file references to consolidate
            file_refs = {}  # Map file paths to keys containing them
            
            for key, value in context_data.items():
                content_str = str(value)
                if 'file' in key.lower() and ('/' in content_str or '\\' in content_str):
                    # Extract file path
                    file_path = content_str.strip()
                    if file_path not in file_refs:
                        file_refs[file_path] = []
                    file_refs[file_path].append(key)
            
            # Consolidate duplicate file references
            for file_path, keys in file_refs.items():
                if len(keys) > 1:  # Multiple references to same file
                    operations.append(
                        self._create_consolidate_operation(
                            target_keys=keys,
                            content_data=context_data,
                            consolidation_strategy="merge_file_references",
                            reasoning=f"Consolidating {len(keys)} references to file: {file_path}",
                            confidence=0.8
                        )
                    )
            
            # Find similar todos/tasks to consolidate (basic similarity check)
            todo_keys = [key for key in context_data.keys() if 'todo' in key.lower() or 'task' in key.lower()]
            
            if len(todo_keys) > 1:
                # Group similar todos (very simple - by common keywords)
                todo_groups = {}
                for key in todo_keys:
                    content = str(context_data[key]).lower()
                    # Extract key words (simple approach)
                    key_words = [word for word in content.split() if len(word) > 4][:3]  # First 3 significant words
                    if key_words:
                        group_key = ' '.join(key_words)
                        if group_key not in todo_groups:
                            todo_groups[group_key] = []
                        todo_groups[group_key].append(key)
                
                # Create consolidation operations for groups with multiple items
                for group_desc, keys in todo_groups.items():
                    if len(keys) > 1:
                        operations.append(
                            self._create_consolidate_operation(
                                target_keys=keys,
                                content_data=context_data,
                                consolidation_strategy="merge_similar_todos",
                                reasoning=f"Consolidating {len(keys)} similar todos about: {group_desc}",
                                confidence=0.7
                            )
                        )
                        
        except Exception as e:
            logger.error(f"Error generating consolidation operations: {e}")
        
        return operations

    def generate_reorder_operations(
        self,
        context_data: Dict[str, Any],
        priority_report: PriorityReport
    ) -> List[ManipulationOperation]:
        """Generate operations to reorder content by priority."""
        operations = []
        
        try:
            # Extract keys that can be meaningfully reordered
            reorderable_keys = []
            for key in context_data.keys():
                # Focus on content types that benefit from priority ordering
                if any(keyword in key.lower() for keyword in ['todo', 'task', 'message', 'conversation']):
                    reorderable_keys.append(key)
            
            if len(reorderable_keys) > 1:
                # Create priority mapping from PriorityReport
                priority_scores = {}
                
                # Extract priority scores from high_priority_items (which is a list of PriorityItem)
                for item in priority_report.high_priority_items:
                    # Match by content similarity to assign priority scores
                    for key in reorderable_keys:
                        if key in context_data and item.content and str(context_data[key]) in item.content:
                            priority_scores[key] = item.priority_score
                
                # Sort by priority scores (higher scores first), then by length
                priority_order = sorted(reorderable_keys, key=lambda k: (
                    -priority_scores.get(k, 50),  # Higher priority first (negative for desc sort)
                    -len(str(context_data.get(k, "")))  # Shorter items first if equal priority
                ))
                
                if priority_order != reorderable_keys:  # Only if order would change
                    operations.append(
                        self._create_reorder_operation(
                            target_keys=reorderable_keys,
                            content_data=context_data,
                            new_order=priority_order,
                            reasoning=f"Reordering {len(reorderable_keys)} items by priority (high priority first)",
                            confidence=0.9
                        )
                    )
                    
        except Exception as e:
            logger.error(f"Error generating reorder operations: {e}")
        
        return operations

    def generate_summarization_operations(
        self,
        context_data: Dict[str, Any],
        redundancy_report: RedundancyReport
    ) -> List[ManipulationOperation]:
        """Generate operations to summarize verbose content.""" 
        operations = []
        
        try:
            # Identify verbose content that could benefit from summarization
            for key, value in context_data.items():
                content_str = str(value)
                content_tokens = self._calculate_content_tokens(content_str)
                
                # Consider content for summarization if it's very long
                if content_tokens > 1000:  # Large content
                    # Check if it contains repetitive patterns
                    if len(set(content_str.split())) / len(content_str.split()) < 0.3:  # High repetition
                        operations.append(
                            self._create_summarize_operation(
                                target_keys=[key],
                                content_data=context_data,
                                summarization_type="repetitive_content",
                                reasoning=f"Summarizing verbose content ({content_tokens} tokens) with high repetition",
                                confidence=0.6
                            )
                        )
                
                # Look for conversation-like content that could be summarized
                if "conversation" in key.lower() or "message" in key.lower():
                    if content_tokens > 2000:  # Very long conversations
                        operations.append(
                            self._create_summarize_operation(
                                target_keys=[key],
                                content_data=context_data,
                                summarization_type="conversation_summary", 
                                reasoning=f"Summarizing long conversation ({content_tokens} tokens)",
                                confidence=0.5  # Lower confidence for conversations
                            )
                        )
                        
        except Exception as e:
            logger.error(f"Error generating summarization operations: {e}")
        
        return operations

    def create_manipulation_plan(
        self,
        context_data: Dict[str, Any],
        analysis_result: ContextAnalysisResult,
        safety_level: str = "balanced"
    ) -> ManipulationPlan:
        """
        Create comprehensive manipulation plan based on analysis results.
        
        Args:
            context_data: The context data to manipulate
            analysis_result: Results from ContextAnalyzer 
            safety_level: conservative, balanced, or aggressive
            
        Returns:
            ManipulationPlan with recommended operations
        """
        plan_start_time = time.time()
        
        try:
            all_operations = []
            used_keys = set()  # Track keys already used by operations
            
            # Generate removal operations (safe deletions) - highest priority
            removal_ops = self.generate_removal_operations(
                context_data, 
                analysis_result.redundancy_report
            )
            
            # Add removal operations and track their keys
            for op in removal_ops:
                # Check if any keys are already used
                if not any(key in used_keys for key in op.target_keys):
                    all_operations.append(op)
                    used_keys.update(op.target_keys)
            
            # Generate consolidation operations based on safety level
            if safety_level in ["balanced", "aggressive"]:
                consolidation_ops = self.generate_consolidation_operations(
                    context_data,
                    analysis_result.redundancy_report
                )
                
                # Add consolidation operations that don't conflict
                for op in consolidation_ops:
                    if not any(key in used_keys for key in op.target_keys):
                        all_operations.append(op)
                        used_keys.update(op.target_keys)
            
            # Generate reorder operations (generally safe)
            reorder_ops = self.generate_reorder_operations(
                context_data,
                analysis_result.priority_report  
            )
            
            # Add reorder operations that don't conflict
            for op in reorder_ops:
                if not any(key in used_keys for key in op.target_keys):
                    all_operations.append(op)
                    used_keys.update(op.target_keys)
            
            # Generate summarization operations only for aggressive mode
            if safety_level == "aggressive":
                summarization_ops = self.generate_summarization_operations(
                    context_data,
                    analysis_result.redundancy_report
                )
                
                # Add summarization operations that don't conflict
                for op in summarization_ops:
                    if not any(key in used_keys for key in op.target_keys):
                        all_operations.append(op)
                        used_keys.update(op.target_keys)
            
            # Apply safety level constraints
            if safety_level == "conservative":
                # Only high-confidence operations
                all_operations = [op for op in all_operations if op.confidence_score >= 0.9]
            elif safety_level == "balanced":  
                # Medium-high confidence operations
                all_operations = [op for op in all_operations if op.confidence_score >= 0.7]
            # aggressive mode keeps all operations
            
            # Limit total operations for safety
            if len(all_operations) > self.max_operations:
                # Keep highest confidence operations
                all_operations.sort(key=lambda op: op.confidence_score, reverse=True)
                all_operations = all_operations[:self.max_operations]
            
            # Calculate plan metrics
            total_reduction = sum(
                abs(op.estimated_token_impact) for op in all_operations
                if op.estimated_token_impact < 0
            )
            
            requires_approval = any(op.requires_confirmation for op in all_operations)
            
            # Estimate execution time (rough approximation)
            estimated_time = len(all_operations) * 0.1  # ~0.1s per operation
            
            plan = ManipulationPlan(
                plan_id=self._generate_operation_id() + "-plan",
                total_operations=len(all_operations),
                operations=all_operations,
                estimated_total_reduction=total_reduction,
                estimated_execution_time=estimated_time,
                safety_level=safety_level,
                requires_user_approval=requires_approval,
                created_timestamp=datetime.now().isoformat()
            )
            
            plan_duration = time.time() - plan_start_time
            logger.info(
                f"Manipulation plan created: {len(all_operations)} operations, "
                f"{total_reduction} token reduction, {safety_level} mode, "
                f"planning took {plan_duration:.3f}s"
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Error creating manipulation plan: {e}")
            return ManipulationPlan(
                plan_id=self._generate_operation_id() + "-error",
                total_operations=0,
                operations=[],
                estimated_total_reduction=0,
                estimated_execution_time=0,
                safety_level=safety_level,
                requires_user_approval=True,
                created_timestamp=datetime.now().isoformat()
            )

    def execute_operation(
        self,
        operation: ManipulationOperation,
        context_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Execute a single manipulation operation.
        
        Returns:
            Tuple of (modified_context, operation_result)
        """
        operation_start = time.time()
        
        try:
            modified_context = deepcopy(context_data)
            
            if operation.operation_type == "remove":
                # Remove specified keys
                removed_items = {}
                for key in operation.target_keys:
                    if key in modified_context:
                        removed_items[key] = modified_context.pop(key)
                
                result = {
                    "operation_id": operation.operation_id,
                    "success": True,
                    "items_removed": len(removed_items),
                    "removed_keys": list(removed_items.keys()),
                    "execution_time": time.time() - operation_start
                }
                
            elif operation.operation_type == "consolidate":
                # Consolidate content (simplified implementation)
                consolidated_content = []
                original_keys = []
                
                for key in operation.target_keys:
                    if key in modified_context:
                        consolidated_content.append(str(modified_context[key]))
                        original_keys.append(key)
                
                if consolidated_content:
                    # Create consolidated key name  
                    consolidated_key = f"consolidated_{original_keys[0]}"
                    consolidated_value = " | ".join(consolidated_content)
                    
                    # Remove original keys and add consolidated content
                    for key in original_keys:
                        modified_context.pop(key, None)
                    modified_context[consolidated_key] = consolidated_value
                
                result = {
                    "operation_id": operation.operation_id,
                    "success": True,
                    "items_consolidated": len(original_keys),
                    "consolidated_key": consolidated_key,
                    "execution_time": time.time() - operation_start
                }
                
            elif operation.operation_type == "reorder":
                # Reorder content keys
                new_order = operation.operation_data.get("new_order", [])
                reordered_context = {}
                
                # Add keys in new order
                for key in new_order:
                    if key in modified_context:
                        reordered_context[key] = modified_context[key]
                
                # Add any remaining keys
                for key, value in modified_context.items():
                    if key not in reordered_context:
                        reordered_context[key] = value
                
                modified_context = reordered_context
                
                result = {
                    "operation_id": operation.operation_id,
                    "success": True,
                    "items_reordered": len(new_order),
                    "new_order": new_order,
                    "execution_time": time.time() - operation_start
                }
                
            elif operation.operation_type == "summarize":
                # Summarize content (placeholder - would need actual summarization logic)
                for key in operation.target_keys:
                    if key in modified_context:
                        original_content = str(modified_context[key])
                        # Placeholder summarization - just truncate for now
                        if len(original_content) > 500:
                            summarized = original_content[:400] + "... [SUMMARIZED]"
                            modified_context[key] = summarized
                
                result = {
                    "operation_id": operation.operation_id,
                    "success": True,
                    "items_summarized": len(operation.target_keys),
                    "summarization_type": operation.operation_data.get("summarization_type"),
                    "execution_time": time.time() - operation_start
                }
                
            else:
                raise ValueError(f"Unknown operation type: {operation.operation_type}")
            
            return modified_context, result
            
        except Exception as e:
            logger.error(f"Operation {operation.operation_id} failed: {e}")
            return context_data, {
                "operation_id": operation.operation_id,
                "success": False,
                "error": str(e),
                "execution_time": time.time() - operation_start
            }

    def execute_plan(
        self,
        plan: ManipulationPlan,
        context_data: Dict[str, Any],
        execute_all: bool = False
    ) -> ManipulationResult:
        """
        Execute a manipulation plan.
        
        Args:
            plan: The manipulation plan to execute
            context_data: Context data to modify  
            execute_all: If False, skip operations requiring confirmation
            
        Returns:
            ManipulationResult with execution details
        """
        execution_start = time.time()
        
        try:
            modified_context = deepcopy(context_data)
            operation_results = []
            operations_executed = 0
            operations_failed = 0
            actual_token_reduction = 0
            error_messages = []
            
            for operation in plan.operations:
                # Skip operations requiring confirmation unless execute_all is True
                if operation.requires_confirmation and not execute_all:
                    continue
                
                # Execute the operation
                modified_context, operation_result = self.execute_operation(
                    operation,
                    modified_context
                )
                
                operation_results.append(operation_result)
                
                if operation_result.get("success", False):
                    operations_executed += 1
                    # Calculate actual token reduction
                    if operation.estimated_token_impact < 0:
                        actual_token_reduction += abs(operation.estimated_token_impact)
                else:
                    operations_failed += 1
                    error_msg = operation_result.get("error", "Unknown error")
                    error_messages.append(f"Operation {operation.operation_id}: {error_msg}")
            
            execution_time = time.time() - execution_start
            
            result = ManipulationResult(
                plan_id=plan.plan_id,
                execution_success=operations_failed == 0,
                operations_executed=operations_executed,
                operations_failed=operations_failed,
                actual_token_reduction=actual_token_reduction,
                execution_time=execution_time,
                modified_context=modified_context,
                operation_results=operation_results,
                error_messages=error_messages,
                executed_timestamp=datetime.now().isoformat()
            )
            
            logger.info(
                f"Plan {plan.plan_id} executed: {operations_executed} successful, "
                f"{operations_failed} failed, {actual_token_reduction} tokens reduced, "
                f"took {execution_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            return ManipulationResult(
                plan_id=plan.plan_id,
                execution_success=False,
                operations_executed=0,
                operations_failed=len(plan.operations),
                actual_token_reduction=0,
                execution_time=time.time() - execution_start,
                modified_context=context_data,
                operation_results=[],
                error_messages=[str(e)],
                executed_timestamp=datetime.now().isoformat()
            )


# Convenience functions
def create_manipulation_plan(
    context_data: Dict[str, Any],
    analysis_result: ContextAnalysisResult,
    safety_level: str = "balanced"
) -> ManipulationPlan:
    """Convenience function to create manipulation plan."""
    engine = ManipulationEngine()
    return engine.create_manipulation_plan(context_data, analysis_result, safety_level)


def execute_manipulation_plan(
    plan: ManipulationPlan,
    context_data: Dict[str, Any],
    execute_all: bool = False
) -> ManipulationResult:
    """Convenience function to execute manipulation plan."""
    engine = ManipulationEngine()
    return engine.execute_plan(plan, context_data, execute_all)


if __name__ == "__main__":
    # Simple test
    print("Testing Context Manipulation Engine...")
    
    from .context_analyzer import analyze_context_sync
    from datetime import timedelta
    
    test_data = {
        "message_1": "Help me debug this function", 
        "message_2": "Help me debug this function",  # Duplicate
        "todo_1": "Fix authentication bug",
        "todo_2": "Fix authentication bug - COMPLETED",  # Obsolete
        "file_1": "/project/main.py",
        "file_2": "/project/main.py",  # Duplicate file
        "conversation": "User: How do I fix this? Assistant: You can fix it this way. User: How do I fix this? Assistant: You can fix it this way." * 50,  # Verbose
        "timestamp": datetime.now().isoformat()
    }
    
    # Analyze context
    analysis = analyze_context_sync(test_data)
    if not analysis:
        print("❌ Context analysis failed")
        exit(1)
    
    # Create manipulation plan
    plan = create_manipulation_plan(test_data, analysis, "balanced")
    print(f"\n✅ Created manipulation plan with {plan.total_operations} operations")
    print(f"Estimated reduction: {plan.estimated_total_reduction} tokens")
    
    # Execute plan
    result = execute_manipulation_plan(plan, test_data, execute_all=True)
    print(f"\n✅ Executed plan: {result.operations_executed} operations successful")
    print(f"Actual reduction: {result.actual_token_reduction} tokens")
    print(f"Execution time: {result.execution_time:.3f}s")
    
    if result.error_messages:
        print(f"Errors: {result.error_messages}")