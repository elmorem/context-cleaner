"""
Core Context Analysis and Manipulation Components

This package contains the core functionality for Context Cleaner:
- Advanced context analysis with sophisticated metrics
- Context health assessment and scoring  
- Content manipulation and optimization engines
- Focus analysis and priority assessment
- Manipulation validation and safety checks
"""

from .context_analyzer import ContextAnalyzer, ContextAnalysisResult
from .redundancy_detector import RedundancyDetector, RedundancyReport
from .recency_analyzer import RecencyAnalyzer, RecencyReport
from .focus_scorer import FocusScorer, FocusMetrics
from .priority_analyzer import PriorityAnalyzer, PriorityReport
from .manipulation_engine import (
    ManipulationEngine, 
    ManipulationOperation, 
    ManipulationPlan, 
    ManipulationResult,
    create_manipulation_plan,
    execute_manipulation_plan
)
from .manipulation_validator import (
    ManipulationValidator,
    ValidationResult,
    IntegrityCheck,
    validate_operation,
    validate_plan, 
    verify_manipulation_integrity
)

__all__ = [
    # Analysis components
    "ContextAnalyzer",
    "ContextAnalysisResult", 
    "RedundancyDetector",
    "RedundancyReport",
    "RecencyAnalyzer", 
    "RecencyReport",
    "FocusScorer",
    "FocusMetrics",
    "PriorityAnalyzer",
    "PriorityReport",
    
    # Manipulation engine
    "ManipulationEngine",
    "ManipulationOperation",
    "ManipulationPlan",
    "ManipulationResult",
    "create_manipulation_plan",
    "execute_manipulation_plan",
    
    # Validation system
    "ManipulationValidator", 
    "ValidationResult",
    "IntegrityCheck",
    "validate_operation",
    "validate_plan",
    "verify_manipulation_integrity",
]
