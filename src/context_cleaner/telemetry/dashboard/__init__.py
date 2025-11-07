"""Telemetry Dashboard Components"""

from .widgets import (
    TelemetryWidgetManager,
    TelemetryWidgetType,
    WidgetData,
    ErrorMonitorData,
    CostTrackerData,
    TimeoutRiskData,
    ToolOptimizerData,
    ModelEfficiencyData,
)

# Context Rot Meter components
try:
    from ..context_rot.widget import ContextRotMeterData

    CONTEXT_ROT_DATA_AVAILABLE = True
except ImportError:
    CONTEXT_ROT_DATA_AVAILABLE = False

    class ContextRotMeterData:
        pass


__all__ = [
    "TelemetryWidgetManager",
    "TelemetryWidgetType",
    "WidgetData",
    "ErrorMonitorData",
    "CostTrackerData",
    "TimeoutRiskData",
    "ToolOptimizerData",
    "ModelEfficiencyData",
    "ContextRotMeterData",
]
