# Supervisor Architecture & Operations

This document describes the supervisor/watchdog subsystem introduced in the
service-management refactor. It covers architecture, lifecycle, registry
metadata, and operational troubleshooting.

## Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│ context-cleaner run                                                        │
│                                                                            │
│  ┌─────────────┐        ┌────────────────┐        ┌─────────────────────┐  │
│  │ CLI thread  │ ─────▶ │ ServiceSupervisor │ ───▶ │ ServiceOrchestrator │  │
│  │ (click)     │        │  (async event    │      │  (service lifecycle)│  │
│  └─────────────┘        │   loop + IPC)   │      └─────────────────────┘  │
│          ▲              └───────┬─────────┘                ▲             │
│          │                      │                          │             │
│  SupervisorClient               │                      ProcessRegistry    │
│  (run --status-only)            │                          │             │
│          │                      │                          │             │
│          └───────────── Watchdog (background thread) ──────┘             │
└────────────────────────────────────────────────────────────────────────────┘
```

* The supervisor hosts the IPC endpoint (`unix://.../supervisor.sock` on POSIX).
* All structured shutdown/status requests go through the supervisor.
* The watchdog runs in a background thread monitoring registry heartbeats and
  triggering restarts when the supervisor stops responding.
* The process registry stores supervisor metadata as well as child service
  entries (including container IDs, ports, and structured `metadata`).

## Registry Metadata

Supervisor entries are registered with `service_type="supervisor"`. Relevant
environment fields include:

* `IPC_ENDPOINT` – socket path (POSIX) or named pipe/TCP info (Windows).
* `HEARTBEAT_AT` – last heartbeat timestamp.
* `HEARTBEAT_INTERVAL` / `HEARTBEAT_TIMEOUT` – configuration hints for the watchdog.
* `AUDIT_LOG` – path to `logs/supervisor/audit.log`.

Service entries (e.g. `dashboard`, `jsonl_bridge`) now include:

* `container_id`, `container_state` – for Docker-managed services.
* `metadata` – JSON payload (port, URL, `was_attached`, metrics, etc.).

These fields allow the supervisor to avoid rediscovery and present accurate
status data via `context-cleaner run --status-only --json`.

## Status Output

`context-cleaner run --status-only` now prints a “Watchdog” section when the
supervisor is reachable. For tooling, `--status-only --json` returns:

```json
{
  "orchestrator": {...},
  "services": {...},
  "services_summary": {...},
  "watchdog": {
    "running": true,
    "last_heartbeat_at": "2025-09-24T07:07:59.396239Z",
    "last_restart_reason": null,
    "last_restart_success": null,
    "restart_attempts": 0,
    "restart_history": []
  }
}
```

The CLI documentation in `docs/cli-reference.md` captures the exact options.

## Troubleshooting

See `docs/troubleshooting.md` (Supervisor & Watchdog section) for:

* Handling “supervisor unavailable” messages.
* Interpreting watchdog restart telemetry.
* Cleaning stale registry entries.

## Development Tips

* Mocking: use `tests/cli/test_run_stop_integration.py` as a reference for how
  to stub `ServiceOrchestrator` and `SupervisorClient` in tests.
* Registry schema: `ProcessEntry` lives in
  `src/context_cleaner/services/process_registry.py`. Any new fields should be
  added via `_ensure_column` to keep migrations idempotent.
* Watchdog configuration: `ServiceWatchdogConfig` exposes poll interval,
  restart backoff, and max attempts. These defaults are tested in
  `tests/services/test_watchdog_supervisor_integration.py`.
* Transport abstraction: `SupervisorClient` automatically selects the correct
  transport (`UnixSocketTransport` on POSIX; TCP/named pipe placeholders on
  Windows). Tests covering endpoint detection live in
  `tests/ipc/test_client_transport.py`.

## Manual Restart Procedures

During development you may want to restart only the supervisor without a full
system reboot.

1. **Graceful shutdown**
   ```bash
   context-cleaner stop --force --no-discovery
   ```

2. **Remove stale socket (if present)**
   ```bash
   rm -f $(python -c "from context_cleaner.ipc.client import default_supervisor_endpoint; print(default_supervisor_endpoint())")
   ```

3. **Restart orchestrated services**
   ```bash
   context-cleaner run
   ```

4. **Verify**
   ```bash
   context-cleaner run --status-only --json | jq '.watchdog'
   ```

If you are attaching a debugger or hot-reloading supervisor code, you can
instantiate `ServiceSupervisor` directly from a Python REPL:

```python
import asyncio
from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.services.service_orchestrator import ServiceOrchestrator

orchestrator = ServiceOrchestrator(verbose=True)
supervisor = ServiceSupervisor(orchestrator, SupervisorConfig(endpoint="/tmp/cc-supervisor.sock"))
asyncio.run(supervisor.start())
```

Make sure to call `asyncio.run(supervisor.stop())` (or kill the loop) before
exiting the session to keep the registry clean.
