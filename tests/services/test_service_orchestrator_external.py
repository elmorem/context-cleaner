import asyncio
import logging
import os
from unittest.mock import MagicMock

import pytest

from context_cleaner.services.service_orchestrator import (
    ServiceOrchestrator,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
)


@pytest.mark.asyncio
async def test_register_external_service_tracks_state_and_stop_callback():
    orchestrator = ServiceOrchestrator.__new__(ServiceOrchestrator)
    orchestrator.logger = logging.getLogger("test")
    orchestrator.services = {
        "dashboard": ServiceDefinition(
            name="dashboard",
            description="Dashboard",
            start_command=None,
            stop_command=None,
            dependencies=[],
            required=True,
            category="internal",
        )
    }
    orchestrator.service_states = {"dashboard": ServiceState(name="dashboard")}
    orchestrator.process_registry = MagicMock()
    orchestrator.process_registry.unregister_process.return_value = True
    orchestrator.verbose = False

    stop_called = False

    def stop_callback():
        nonlocal stop_called
        stop_called = True

    orchestrator.register_external_service(
        "dashboard",
        pid=os.getpid(),
        stop_callback=stop_callback,
        metadata={"port": 8110, "url": "http://localhost:8110"},
    )

    state = orchestrator.service_states["dashboard"]
    assert state.status is ServiceStatus.RUNNING
    assert state.health_status is True
    assert state.metrics["port"] == 8110
    assert state.metrics["url"] == "http://localhost:8110"
    assert state.stop_callback is stop_callback

    await orchestrator._stop_dashboard_service()
    assert stop_called is True
    assert state.status is ServiceStatus.STOPPED
    assert state.health_status is False

