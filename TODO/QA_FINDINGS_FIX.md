# QA Findings – Follow-Up Plan

1. Temporarily disable or aggressively throttle the API/UI Consistency Checker to confirm it is the source of the FD exhaustion and watchdog restarts.
2. Refactor the checker for production use:
   - Reuse a single `aiohttp.ClientSession` per sweep instead of creating one per endpoint.
   - Fetch the dashboard HTML once per loop and reuse it when computing UI status.
   - Replace the brittle "Loading..." heuristic with checks for concrete widget markers.
   - Lower the sweep frequency (e.g., run every 10–15 minutes or stagger endpoints).
3. Add lightweight FD instrumentation (`psutil.Process(os.getpid()).num_fds()`) around the checker loop and registry entry points to verify the fix and catch regressions.

>>>>>>>>>
