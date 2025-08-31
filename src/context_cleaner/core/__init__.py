"""
Core Context Analysis and Manipulation Components

This package contains the core functionality for Context Cleaner:
- Advanced context analysis with sophisticated metrics
- Context health assessment and scoring  
- Content manipulation and optimization engines
- Focus analysis and priority assessment
- Enhanced manipulation validation and safety checks
- Backup and rollback system with operation history
- Transaction-based atomic operations with rollback capabilities
- Dry-run preview system with before/after visualization
- Multi-layered risk assessment and safety validation
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
    RiskLevel,
    SafetyAction,
    RiskAssessment,
    SafetyConstraints,
    OperationHistory,
    validate_operation,
    validate_plan, 
    verify_manipulation_integrity
)
from .backup_manager import (
    BackupManager,
    BackupType,
    BackupStatus,
    BackupMetadata,
    BackupEntry,
    RestoreResult,
    create_safety_backup,
    restore_from_backup
)
from .transaction_manager import (
    TransactionManager,
    Transaction,
    TransactionState,
    TransactionIsolation,
    TransactionResult,
    TransactionMetadata,
    execute_atomic_operations
)
from .preview_generator import (
    PreviewGenerator,
    PreviewFormat,
    ChangeType,
    ChangeDetail,
    OperationPreview,
    PlanPreview,
    preview_single_operation,
    preview_manipulation_plan
)
from .confirmation_workflows import (
    ConfirmationWorkflowManager,
    ConfirmationProvider,
    ConsoleConfirmationProvider,
    ConfirmationLevel,
    ConfirmationResult,
    ConfirmationRequest,
    ConfirmationResponse,
    confirm_operation,
    confirm_plan
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
    
    # Enhanced validation system
    "ManipulationValidator", 
    "ValidationResult",
    "IntegrityCheck",
    "RiskLevel",
    "SafetyAction", 
    "RiskAssessment",
    "SafetyConstraints",
    "OperationHistory",
    "validate_operation",
    "validate_plan",
    "verify_manipulation_integrity",
    
    # Backup and rollback system
    "BackupManager",
    "BackupType",
    "BackupStatus", 
    "BackupMetadata",
    "BackupEntry",
    "RestoreResult",
    "create_safety_backup",
    "restore_from_backup",
    
    # Transaction system
    "TransactionManager",
    "Transaction",
    "TransactionState",
    "TransactionIsolation",
    "TransactionResult", 
    "TransactionMetadata",
    "execute_atomic_operations",
    
    # Preview system
    "PreviewGenerator",
    "PreviewFormat",
    "ChangeType",
    "ChangeDetail",
    "OperationPreview", 
    "PlanPreview",
    "preview_single_operation",
    "preview_manipulation_plan",
    
    # Confirmation workflows
    "ConfirmationWorkflowManager",
    "ConfirmationProvider",
    "ConsoleConfirmationProvider",
    "ConfirmationLevel",
    "ConfirmationResult",
    "ConfirmationRequest",
    "ConfirmationResponse",
    "confirm_operation",
    "confirm_plan",
]
