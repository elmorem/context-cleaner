# Release Readiness Plan

## Blockers (Must Fix Before Tagging)

1. **Package container assets and load them dynamically**
   - Move `docker-compose.yml`, `otel-simple.yaml`, `otel-clickhouse-init.sql`, `clickhouse-users.xml`, and any other runtime configs into a package-accessible directory (e.g., `src/context_cleaner/resources/telemetry/`).
   - Update `MANIFEST.in` and `pyproject.toml` to include these resources in wheels/sdists.
   - Refactor `ServiceOrchestrator` (see `src/context_cleaner/services/service_orchestrator.py:294-332` and related helpers) to load assets via `importlib.resources` and copy them to a writable location (e.g., `~/.context_cleaner/telemetry/`) at runtime.
   - Ensure `context-cleaner run` works from a fresh `pip install` with no git checkout present.

2. **Replace ad-hoc telemetry installers with a packaged CLI workflow**
   - Introduce a `context-cleaner telemetry init` (or similar) command that:
     - Verifies Docker and Docker Compose availability.
     - Copies packaged config files to the user data directory.
     - Brings up ClickHouse/OTEL containers via the orchestrator.
     - Configures Claude/OTEL env vars automatically (cross-platform support).
   - Deprecate/remove references to `install-telemetry.sh` and `setup-telemetry.sh` in docs and CLI help.
   - Confirm new command runs after `pip install` without requiring shell scripts.

3. **Improve Docker prerequisite handling**
   - Add pre-flight checks (CLI + docs) that detect missing/disabled Docker and provide actionable messaging instead of hanging on docker commands.
   - Decide on behavior when Docker is unavailable: fail fast with guidance or offer limited/no-telemetry mode.

4. **Package dependency audit & smoke test**
   - Double-check runtime imports match `pyproject.toml` dependencies; add any missing requirements.
   - Build wheel/sdist (`hatch build`), then in a clean venv run:
     - `pip install context-cleaner-*.whl`
     - `context-cleaner run --status-only --json`
     - `context-cleaner telemetry init`
     - `context-cleaner run`
   - Capture and fix any errors from the smoke test.

## High-Priority Enhancements

1. **Refresh docs for orchestrated workflow**
   - Rewrite README quick-start/CLI reference to remove `start`/`dashboard` commands and point to the new telemetry init + `context-cleaner run` flow.
   - Update troubleshooting, telemetry guides, and Markdown docs under `docs/` to remove references to shell scripts and align with the new commands/ports (8110/8111).

2. **Windows support for telemetry configuration**
   - Provide PowerShell-friendly env setup or ensure the new CLI handles env vars automatically on Windows.
   - Document any Windows-specific steps (firewall prompts, Docker Desktop requirements).

3. **Bundle dashboard assets & templates**
   - Verify all static/template files used by the dashboard are included in package data.
   - Run `context-cleaner run` from an installed wheel to confirm no 404s for dashboard assets.

4. **Clean up legacy scripts with hard-coded paths**
   - Move developer-only tools (`analyze_local_tokens.py`, `verify_token_counts.py`, etc.) out of the distribution or parameterize them to avoid embedding `/Users/markelmore/...` paths.

## Documentation & Release Preparation

1. Update CHANGELOG and release notes with the new setup flow, deprecated commands, and telemetry improvements.
2. Bump `project.version` once blockers are resolved and all tests pass.
3. Ensure CI runs full test suite (unit + integration) on a Docker-enabled runner pre-release.
4. After packaging fixes, repeat the integration verification script (`python verify_integration.py`) in a clean environment to confirm success.

## Verification Checklist (Day-of Release)

- [ ] `pip install context-cleaner` succeeds on macOS/Linux/Windows test machines.
- [ ] `context-cleaner telemetry init` sets up containers and env vars without manual scripts.
- [ ] `context-cleaner run --status-only --json` returns healthy status.
- [ ] `context-cleaner run` launches the dashboard with packaged assets.
- [ ] Documentation published and accurately reflects the new workflow.
- [ ] CHANGELOG/release notes finalized and version bumped.
