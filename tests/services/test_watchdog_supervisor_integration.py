import asyncio
import json
import os
from datetime import datetime, timezone, timedelta

import pytest

from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.services.service_watchdog import ServiceWatchdog, ServiceWatchdogConfig
from context_cleaner.services.process_registry import get_process_registry


class _StubOrchestrator:
    def get_service_status(self):
        return {
            "orchestrator": {
                "running": True,
                "services_running": 0,
                "uptime_seconds": 0.0,
                "shutdown_initiated": False,
            },
            "services_summary": {
                "total": 0,
                "by_status": {},
                "required_failed": [],
                "optional_failed": [],
                "transitioning": {"starting": [], "stopping": []},
                "running": [],
            },
        }


@pytest.mark.asyncio
async def test_watchdog_triggers_restart_for_stale_supervisor(monkeypatch, tmp_path):
    registry_path = tmp_path / "registry.db"
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(registry_path))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    supervisor = ServiceSupervisor(_StubOrchestrator(), SupervisorConfig(endpoint="ipc://watchdog-int"))
    await supervisor.start()

    restart_calls = []

    def restart_callback() -> None:
        restart_calls.append(datetime.now(timezone.utc))

    watchdog = ServiceWatchdog(
        registry=get_process_registry(),
        config=ServiceWatchdogConfig(
            poll_interval_seconds=0.05,
            restart_backoff_seconds=0.05,
            stale_grace_seconds=0,
        ),
        restart_callback=restart_callback,
    )
    supervisor.register_watchdog(watchdog)
    watchdog.start()

    await asyncio.sleep(0.2)
    assert restart_calls == []

    registry = get_process_registry()
    entry = registry.get_process(os.getpid())
    environment = json.loads(entry.environment_vars)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    iso = stale_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    environment["HEARTBEAT_AT"] = iso
    environment["UPDATED_AT"] = iso
    registry.update_process_metadata(os.getpid(), environment_vars=json.dumps(environment))

    timeout = datetime.now(timezone.utc) + timedelta(seconds=2)
    while not restart_calls and datetime.now(timezone.utc) < timeout:
        await asyncio.sleep(0.05)

    assert restart_calls, "Watchdog should initiate restart when heartbeat is stale"
    assert watchdog.last_restart_reason == "stale-heartbeat"
    assert watchdog.restart_attempts >= 1

    watchdog.stop()
    await supervisor.stop()
