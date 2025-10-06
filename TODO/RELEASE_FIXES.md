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
   - Decide on behavior when Docker is unavailable: fail fast with guidance or offer limited/no-telemetry mode. (Decision: fail fast with guidance; no fallback mode required.)

4. **Package dependency audit & smoke test**
   - Double-check runtime imports match `pyproject.toml` dependencies; add any missing requirements. ✅ Added requests, redis, aiofiles, nltk, scikit-learn, textblob, python-dateutil, pytz.
   - Build wheel/sdist (`hatch build`), then in a clean venv run:
     - `pip install context-cleaner-*.whl` ✅ (.venv_smoke)
     - `context-cleaner run --status-only --json` ✅
     - `context-cleaner telemetry init` ✅ (completed with Docker running)
     - `context-cleaner run` ⚠️ long-running service; use manual invocation when ready for full integration
   - Capture and fix any errors from the smoke test. ✅ Gunicorn now included and stale PID cleanup added; latest `context-cleaner run --dev-mode --no-browser` completed with all services and widgets healthy (see run_dev.log).

## High-Priority Enhancements

1. **Refresh docs for orchestrated workflow** ✅
   - README, CLI reference, and troubleshooting guides now highlight `context-cleaner run` + `telemetry init` flow and remove legacy script references.

2. **Windows support for telemetry configuration** ✅
   - Documented PowerShell snippet for loading telemetry env vars and reiterated Docker Desktop requirements in README/telemetry guides.

3. **Bundle dashboard assets & templates** ✅
   - Verified packaged templates/static assets via importlib; wheel-backed `context-cleaner run` succeeds with dashboard widgets populated.

4. **Clean up legacy scripts with hard-coded paths** ✅
   - Developer utilities now derive Claude cache roots from `CLAUDE_PROJECT_ROOT`/`$HOME`; sample configs use `~` instead of absolute paths.

## Documentation & Release Preparation

1. Update CHANGELOG and release notes with the new setup flow, deprecated commands, and telemetry improvements. ✅
2. Bump `project.version` once blockers are resolved and all tests pass. ✅ (now 0.3.0)
3. Ensure CI runs full test suite (unit + integration) on a Docker-enabled runner pre-release. 🔄 Pending CI pipeline check
4. After packaging fixes, repeat the integration verification script (`python verify_integration.py`) in a clean environment to confirm success. ✅ (.venv_smoke)

## Verification Checklist (Day-of Release)

- [ ] `pip install context-cleaner` succeeds on macOS/Linux/Windows test machines.
- [ ] `context-cleaner telemetry init` sets up containers and env vars without manual scripts.
- [ ] `context-cleaner run --status-only --json` returns healthy status.
- [ ] `context-cleaner run` launches the dashboard with packaged assets.
- [ ] Documentation published and accurately reflects the new workflow.
- [ ] CHANGELOG/release notes finalized and version bumped.
