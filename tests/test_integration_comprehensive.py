"""Modern integration smoke tests for core workflows."""

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

import importlib

cli_main_module = importlib.import_module("context_cleaner.cli.main")
from context_cleaner.cli.main import main
import context_cleaner.cli.optimization_commands as optimization_commands
import context_cleaner.tracking.session_tracker as session_tracker_module
from context_cleaner.tracking.session_tracker import SessionTracker
from context_cleaner.tracking.models import EventType
from context_cleaner.monitoring.performance_optimizer import PerformanceOptimizer, PerformanceSnapshot
from context_cleaner.feedback.feedback_collector import FeedbackCollector


@pytest.fixture
def cli_runner():
    """Provide a Click CLI runner for invoking the main entry point."""
    return CliRunner()


def test_cli_help_lists_modern_commands(cli_runner):
    """The CLI help exposes the orchestrator-era command surface."""
    result = cli_runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Context Cleaner" in result.output
    assert "run" in result.output
    assert "session" in result.output
    assert "optimize" in result.output


def test_cli_optimize_preview_delegates_to_handler(cli_runner, monkeypatch):
    """`context-cleaner optimize --preview` forwards to the modern handler."""
    handler_instance = MagicMock()

    def handler_factory(*_args, **_kwargs):
        return handler_instance

    monkeypatch.setattr(
        optimization_commands,
        "OptimizationCommandHandler",
        handler_factory,
    )

    result = cli_runner.invoke(main, ["optimize", "--preview"])

    assert result.exit_code == 0
    handler_instance.handle_preview_mode.assert_called_once()


def test_cli_session_start_uses_tracker(cli_runner, monkeypatch):
    """`context-cleaner session start` provisions a tracking session."""
    tracker_instance = MagicMock()
    tracker_instance.start_session.return_value = MagicMock(
        session_id="session-123",
        project_path=Path.cwd(),
        model_name="claude-3",
    )

    monkeypatch.setattr(
        session_tracker_module,
        "SessionTracker",
        lambda *_args, **_kwargs: tracker_instance,
    )

    result = cli_runner.invoke(main, ["session", "start", "--project-path", str(Path.cwd())])

    assert result.exit_code == 0
    tracker_instance.start_session.assert_called_once()


def test_cli_session_stats_renders_summary(cli_runner, monkeypatch):
    """`context-cleaner session stats -f json` surfaces productivity metrics."""
    summary = {
        "session_count": 2,
        "total_time_hours": 5.5,
        "average_productivity_score": 78,
        "recommendations": ["Keep sessions under 90 minutes"],
    }
    tracker_instance = MagicMock()
    tracker_instance.get_productivity_summary.return_value = summary

    monkeypatch.setattr(
        session_tracker_module,
        "SessionTracker",
        lambda *_args, **_kwargs: tracker_instance,
    )

    result = cli_runner.invoke(main, ["session", "stats", "-f", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_count"] == 2
    tracker_instance.get_productivity_summary.assert_called_once()


def test_productivity_workflow_generates_modern_metrics(test_config, tmp_path):
    """End-to-end workflow produces analyzer insights and performance data."""
    # Align configuration with the temporary workspace to avoid polluting real data.
    config = test_config
    config.data_directory = str(tmp_path)

    tracker = SessionTracker(config)
    monitor = PerformanceOptimizer(config)
    feedback = FeedbackCollector(config)

    session = tracker.start_session()

    tracker.track_context_event(
        EventType.CONTEXT_CHANGE,
        context_size=1800,
        metadata={"notes": "initial assessment"},
        after_health_score=72,
    )

    with monitor.track_operation("context_analysis", context_tokens=1800):
        time.sleep(0.05)

    tracker.track_context_event(
        EventType.OPTIMIZATION_EVENT,
        optimization_type="balancing",
        duration_ms=120.0,
        after_health_score=78,
    )

    tracker.end_session(session.session_id)

    session_data = tracker.load_session(session.session_id)
    monitor.snapshots.append(
        PerformanceSnapshot(
            timestamp=datetime.now(),
            cpu_percent=12.0,
            memory_mb=42.0,
            disk_io_read_mb=0.1,
            disk_io_write_mb=0.05,
            operation_type="system_monitoring",
            operation_duration_ms=0.0,
        )
    )
    performance = monitor.get_performance_summary(hours=1)
    summary = tracker.get_productivity_summary(days=1)

    if performance.get("recommendations"):
        feedback.report_performance_issue("context_analysis", duration_ms=120.0, context_size=1800)

    feedback_summary = feedback.get_feedback_summary(days=1)

    assert session_data is not None
    assert summary["session_count"] >= 1
    assert "performance" in performance
    assert performance["performance"]["health_score"] <= 100
    assert "operations" in performance
    assert feedback_summary["total_items"] >= 0
