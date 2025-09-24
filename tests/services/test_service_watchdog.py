import json
import os
import time
from datetime import datetime, timezone, timedelta

import pytest

from context_cleaner.services.service_watchdog import ServiceWatchdog, ServiceWatchdogConfig
from context_cleaner.services.process_registry import (
    ProcessEntry,
    get_process_registry,
)


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    # Reset cached registry so tests use the temp database
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    yield
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)


def _register_supervisor_entry(registry, heartbeat_offset_seconds: int = 0):
    now = datetime.now(timezone.utc)
    heartbeat_time = now - timedelta(seconds=heartbeat_offset_seconds)
    env = {
        "IPC_ENDPOINT": "ipc://watchdog-test",
        "UPDATED_AT": heartbeat_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "HEARTBEAT_AT": heartbeat_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "HEARTBEAT_INTERVAL": 10,
        "HEARTBEAT_TIMEOUT": 5,
    }
    entry = ProcessEntry(
        pid=os.getpid(),
        command_line="service_supervisor",
        service_type="supervisor",
        start_time=now,
        registration_time=now,
        environment_vars=json.dumps(env),
        working_directory=os.getcwd(),
        parent_orchestrator="ServiceOrchestrator",
        registration_source="watchdog-test",
    )
    registry.register_process(entry)
    return entry


def test_watchdog_triggers_restart_on_stale_heartbeat(monkeypatch):
    registry = get_process_registry()
    entry = _register_supervisor_entry(registry)

    restart_calls = []

    def restart_callback():
        restart_calls.append(time.time())

    config = ServiceWatchdogConfig(
        poll_interval_seconds=0.1,
        restart_backoff_seconds=0.1,
        max_restart_attempts=2,
        stale_grace_seconds=0,
    )
    watchdog = ServiceWatchdog(registry=registry, config=config, restart_callback=restart_callback)
    assert watchdog.start() is True

    try:
        # Allow a cycle to confirm healthy state does not trigger restart
        time.sleep(0.3)
        assert restart_calls == []

        # Update heartbeat to be stale and ensure watchdog reacts
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=20)
        env = {
            "IPC_ENDPOINT": "ipc://watchdog-test",
            "UPDATED_AT": stale_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "HEARTBEAT_AT": stale_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "HEARTBEAT_INTERVAL": 10,
            "HEARTBEAT_TIMEOUT": 5,
        }
        registry.update_process_metadata(entry.pid, environment_vars=json.dumps(env))

        timeout = time.time() + 1.0
        while not restart_calls and time.time() < timeout:
            time.sleep(0.05)
    finally:
        watchdog.stop()

    assert restart_calls, "Watchdog should trigger restart when heartbeat is stale"
