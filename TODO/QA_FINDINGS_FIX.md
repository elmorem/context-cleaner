# QA Findings – Follow-Up Plan

1. Temporarily disable or aggressively throttle the API/UI Consistency Checker to confirm it is the source of the FD exhaustion and watchdog restarts.
2. Refactor the checker for production use:
   - Reuse a single `aiohttp.ClientSession` per sweep instead of creating one per endpoint.
   - Fetch the dashboard HTML once per loop and reuse it when computing UI status.
   - Replace the brittle "Loading..." heuristic with checks for concrete widget markers.
   - Lower the sweep frequency (e.g., run every 10–15 minutes or stagger endpoints).
3. Add lightweight FD instrumentation (`psutil.Process(os.getpid()).num_fds()`) around the checker loop and registry entry points to verify the fix and catch regressions.

>>>>>>>>>
Key Findings

api_ui_consistency_checker.py:696-717 runs a full API/UI sweep every cycle. For each of ~14 endpoints it makes two network hits: test_api_endpoint(...) plus check_ui_widget_status(...). Both spin up their own aiohttp.ClientSession (api_ui_consistency_checker.py:439, 548). With the current interval, each loop issues 30‑40 HTTP requests plus the port-readiness probes. Every one of those requests triggers heavy server work (see project_summary_analytics parsing hundreds of JSONL files in your logs), so the checker itself becomes a constant load generator.

The UI probe is flawed. check_ui_widget_status simply loads / and flags “Loading…” if that string exists (api_ui_consistency_checker.py:548-561). The dashboard HTML still contains the literal “Loading…” once fully rendered, so every endpoint ends up flagged as api_working_ui_loading. That is why you see 14 “critical issues” on every pass even though the API responses are healthy.

The monitoring loop routinely overruns its 45‑second budget (MONITOR_TIMEOUT in the logs) because it has to finish dozens of slow HTTP calls plus the server-side processing they trigger. When the loop overruns, it backs off and eventually re-enters recovery. During those recoveries, the watchdog reports missing supervisor registry entries and the orchestrator attempts restarts.

The [Errno 24] Too many open files coming from process_registry.py:239 is a secondary symptom. The orchestrator is trying to grab the SQLite lock while it already has a huge number of descriptors open (network sockets from the checker, subprocess pipes from docker health checks, etc.). Once the FD table is exhausted, os.open(processes.db.lock) fails, the watchdog cannot log heartbeats, and the supervisor looks “missing”.