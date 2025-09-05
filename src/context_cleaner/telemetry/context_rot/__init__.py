"""Context Rot Meter - Real-time conversation quality monitoring with ML enhancements."""

from .analyzer import ContextRotAnalyzer
from .security import SecureContextRotAnalyzer, PrivacyConfig
from .monitor import ProductionReadyContextRotMonitor
from .widget import ContextRotWidget, ContextRotMeterData

# Phase 2: ML Enhancement Exports
try:
    from .ml_analysis import (
        MLFrustrationDetector, 
        SentimentPipeline, 
        ConversationFlowAnalyzer,
        FrustrationAnalysis,
        SentimentScore
    )
    from .adaptive_thresholds import (
        AdaptiveThresholdManager,
        UserBaselineTracker, 
        ThresholdOptimizer,
        ThresholdConfig,
        UserBaseline
    )
    ML_COMPONENTS_AVAILABLE = True
except ImportError:
    ML_COMPONENTS_AVAILABLE = False

__all__ = [
    'ContextRotAnalyzer',
    'SecureContextRotAnalyzer', 
    'PrivacyConfig',
    'ProductionReadyContextRotMonitor',
    'ContextRotWidget',
    'ContextRotMeterData'
]

# Add ML components to exports if available
if ML_COMPONENTS_AVAILABLE:
    __all__.extend([
        'MLFrustrationDetector',
        'SentimentPipeline',
        'ConversationFlowAnalyzer', 
        'FrustrationAnalysis',
        'SentimentScore',
        'AdaptiveThresholdManager',
        'UserBaselineTracker',
        'ThresholdOptimizer',
        'ThresholdConfig',
        'UserBaseline'
    ])