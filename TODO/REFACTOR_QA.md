# Refactor Manual QA Checklist

## Preflight
- `git pull --rebase`, reinstall editable package, rebuild dashboard assets.
- Clear registry (`context-cleaner debug registry-prune --service-type supervisor`) and data dir if necessary.
- Ensure `CONTEXT_CLEANER_ENABLE_SUPERVISOR_ORCHESTRATION=true` unless testing flag-off path.

## 1. Baseline Startup
- Run `context-cleaner run`; expect supervisor/watchdog initialization with no warnings.
- Confirm dashboard auto-opens (or reachable at configured port) and CLI logs mention IPC endpoint.

## 2. Status Output
- Text mode: `context-cleaner run --status-only` → verify watchdog block (heartbeat, restart data).
- JSON mode: `context-cleaner run --status-only --json | jq '.'` → ensure `orchestrator`, `services`, `services_summary`, `watchdog` keys present.

## 3. Targeted Shutdown
- `context-cleaner stop --service dashboard --no-dependents --force --no-discovery`
- Confirm dashboard stops, registry metadata for dashboard cleared, no other services touched.

## 4. Full Stop
- `context-cleaner stop --force --no-discovery`
- Ensure CLI reports orchestrated shutdown, registry empty, docker ports released.

## 5. Watchdog Restart Drill
- Start services (`context-cleaner run`).
- Kill supervisor PID (see `context-cleaner debug list-processes --service-type supervisor` for PID).
- Watchdog should restart supervisor; validate via status JSON and `logs/supervisor/audit.log`.
- Optional: Omit restart callback to ensure watchdog disables after max attempts and logs warning.

## 6. Feature Flag Off Regression
- `export CONTEXT_CLEANER_ENABLE_SUPERVISOR_ORCHESTRATION=false`.
- Re-run `context-cleaner run`, `--status-only`, `stop` → confirm supervisor calls skipped, CLI explains fallback.

## 7. Ctrl+C Handling
- `context-cleaner run`; press Ctrl+C once services are up.
- Verify graceful shutdown: CLI message, registry cleared, docker containers stopped.

## 8. Orchestrator Missing Scenario
- Temporarily move `src/context_cleaner/services/service_orchestrator.py` (simulate missing module).
- `context-cleaner stop` should now error immediately with guidance (no legacy fallback).
- Restore file afterward.

## 9. Registry / Metadata Spot Checks
- After run, `context-cleaner debug list-processes --format json` → verify container IDs, metadata payloads present for each service.
- After stop, registry should be empty (`context-cleaner debug registry-stats`).

## 10. UI Widget Verification
With services running, check each dashboard widget:
- API endpoints (curl or browser network tab):
  - `/api/telemetry-widget/context-rot-meter`
  - `/api/telemetry-widget/code-pattern-analysis`
  - `/api/telemetry-widget/content-search-widget`
  - `/api/telemetry-widget/conversation-timeline`
  - `/api/telemetry-widget/health-summary`
  - Any additional widgets (telemetry/data widgets).
- UI view:
  - Verify charts render correctly, values match API responses, color coding correct.
  - Confirm live updates (socket events) refresh without console errors.
  - Check loading/fallback states (no blank panels).

## 11. Error Injection
- Stop ClickHouse container or rename connection env var; verify widgets display “No data” state and CLI stop still completes.
- Restart containers, ensure status returns to healthy.

## 12. Windows / TCP Note (if available)
- On Windows VM (or WSL2), set flag ON; observe supervisor unimplemented path logs, ensure fallback documentation accurate.
- Ensure `CONTEXT_CLEANER_ENABLE_SUPERVISOR_ORCHESTRATION=false` path still works on Windows.

## 13. Release Notes Prep
- Note user-facing changes: new flag, JSON status, watchdog telemetry, requirement to use CLI for shutdown.
- Gather screenshots/log snippets for docs as needed.

