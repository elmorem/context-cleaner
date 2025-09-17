"""
Dashboard Data Models and Enums

Phase 2.2 Target: Extract data models, enums, and data structures
Original lines: 212-769 (~300 lines)
Target reduction: Consolidate 17 stub classes into factory pattern

Contains:
- WidgetType, UpdateFrequency, WidgetConfig, DataSource classes
- HealthColor, ContextCategory, FocusMetrics enums
- RecencyIndicators, SizeOptimizationMetrics models
- ComprehensiveHealthReport data structures
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# PHASE 2.2: This module will contain all data models and enums
# Currently placeholder - will be populated during extraction

class ModuleStatus:
    """Track module extraction status"""
    EXTRACTION_STATUS = "pending"
    ORIGINAL_LINES = 557  # Lines 212-769
    TARGET_LINES = 300
    REDUCTION_TARGET = "Consolidate stub classes into factory pattern"

logger.info(f"dashboard_models module initialized - Status: {ModuleStatus.EXTRACTION_STATUS}")