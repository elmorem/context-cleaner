# Service Management Refactor Plan

## Why This Refactor
- Current shutdown path reconstructs state heuristically (`context-cleaner stop`) and routinely misses processes.
- `ServiceOrchestrator.stop_all_services()` no-ops for fresh instances; real runtime state lives only in the long-running process.
- A single long-lived supervisor with an IPC control channel lets us ask the active orchestrator to shut itself down reliably.

## High-Level Objectives
1. Run all managed services (Docker, bridge, dashboard, etc.) under a single supervisor process that persists for the session.
2. Expose a control endpoint (e.g., Unix domain socket / named pipe) so CLI commands can issue structured requests (`shutdown`, `status`, `restart`).
3. Retire heuristic stop routines; keep a guarded fallback that escalates to discovery only when the supervisor is unreachable.
4. Extend observability/test coverage so regressions in service lifecycle handling are caught automatically.

## Implementation Phases

### Phase 0 – Discovery & Design
- Inventory every service currently started via `ServiceOrchestrator` or ancillary scripts; record command, requirements, health check expectations.
- Decide on IPC transport with a cross-platform abstraction: Unix domain sockets on POSIX, named pipes or loopback TCP on Windows, with identical protocol semantics across platforms.
- Define request/response schema (JSON payloads with `action`, `arguments`, `status`, `error`).
- Decide supervisor lifecycle: dedicated process vs in-process server thread. (Target: keep everything inside the existing orchestrator process started by `context-cleaner run`.)
- Update architectural diagrams / README summary to reflect supervisor concept.

### Phase 1 – Supervisor Skeleton
- Implement Proto parsing and transport framing for Unix/tcp endpoints.
- Provide stub transport for Windows with detailed TODO comments and signal future implementation.
- Create a `ServiceSupervisor` (or similar) module that:
  - Owns `ServiceOrchestrator` instance and recorded service state.
  - Listens on the chosen IPC endpoint.
  - Dispatches commands asynchronously (shutdown, status, reload config).
- Ensure the supervisor publishes endpoint metadata (socket path, PID) into the process registry for discovery by CLI commands.
- Handle graceful shutdown of the listener on exit.

### Phase 2 – Integrate With `context-cleaner run`
- Modify `context-cleaner run` to:
  - Spawn / initialize the supervisor before starting services.
  - Block on supervisor.run_forever(), letting the dashboard run inside the same process or as a managed child.
  - Register cleanup handlers so Ctrl+C triggers supervisor shutdown.
- Update run logging to emit the control endpoint location for support tooling.

### Phase 3 – Update `context-cleaner stop`
- Replace the current multi-phase heuristic with:
  - Discover supervisor endpoint via registry/config.
  - Connect and send `shutdown` request (optionally `force` flag).
  - Stream shutdown progress feedback from supervisor until completion/timeout.
  - If IPC connection fails, fall back to the existing discovery-based shutdown (after warning the user).
- Ensure exit codes reflect success/failure of the supervisor-driven shutdown.

### Phase 4 – Orchestrator Enhancements
- Expose async-safe methods on `ServiceOrchestrator` for `shutdown_all()` that the supervisor can await (rather than rebuilding a fresh orchestrator).
- Provide hooks for partial shutdown (Docker only, processes only) to match existing CLI flags.
- Make sure services launched externally (dashboard subprocess, etc.) are registered so the supervisor can terminate them deterministically.
- Introduce a lightweight watchdog (separate process or system service) that monitors the supervisor and restarts it with preserved state if a failure is detected.

### Phase 5 – Registry & Metadata Updates
- Extend `ProcessRegistry` schema to store supervisor records (process type `supervisor`, socket path, start time).
- Record child service metadata (ports, container IDs) so the supervisor can use structured info instead of rediscovery.
- Add cleanup routines that remove supervisor entries once shutdown completes.

### Phase 6 – Testing & Validation
- Add unit tests for the IPC protocol (request parsing, command routing, error handling).
- Integration tests:
  - Launch `context-cleaner run` in background, issue `context-cleaner stop`, assert clean exit and absence of lingering processes/ports.
  - Simulate supervisor crash; verify the watchdog restarts it and the CLI receives confirmation, then fall back to discovery only if restart fails.
  - Test cross-platform behavior (Windows named pipe/TCP fallback if applicable).
- Update telemetry/orchestration tests to expect supervisor-led shutdown.

### Phase 7 – Documentation & Tooling
- Document new architecture in README / docs (`docs/` folder) and include troubleshooting steps for supervisor issues.
- Update `stop-context-cleaner.sh` (if kept) to call the IPC endpoint first, then drop back to brute-force termination.
- Provide developer instructions for restarting the supervisor during local development.

### Phase 8 – Rollout & Cleanup
- Behind a feature flag/env var gate the new path while testing.
- Once stable, retire large chunks of the heuristic discovery code, keeping only minimal fallback.
- Ensure release notes capture the breaking-change risk (users must use the new CLI for shutdown).

## Risks & Mitigations
- **Cross-platform IPC parity** → ship a common protocol with OS-specific transports (Unix domain socket, Windows named pipe/TCP) hidden behind one adapter, and run CI on Windows/macOS/Linux to guarantee identical behaviour.
- **Supervisor crash leaving services orphaned** → pair the supervisor with the watchdog process from Phase 4 plus heartbeat entries in the registry so stuck states trigger automatic restart or fallback shutdown.
- **Dashboard lifecycle complexity** → run it as a managed subprocess so PID tracking is reliable.

## Open Questions
- (Resolved) Metrics exposure is out-of-scope for the initial rollout; revisit after supervisor IPC is stable.

## Next Steps
1. Schedule design review to finalize IPC spec and supervisor responsibilities.
2. Create implementation tickets per phase.
3. Begin with Phase 0 discovery so the team shares the same inventory before coding.

## Design Review Prep

### Supervisor Responsibilities (to ratify)
- **Lifecycle ownership**: initialize `ServiceOrchestrator`, start/stop services, coordinate graceful shutdown on IPC `shutdown` request, and publish health heartbeats for the watchdog (Phase 4B).
- **State tracking**: maintain in-memory map and persisted registry entries for managed PIDs, container IDs, allocated ports, configuration flags (no-docker/no-jsonl), and last-operation summary. Updates must stay in sync with `ProcessRegistry` writes and include occurrence timestamps.
- **Connection management**: accept a bounded number of concurrent connections, enforce keep-alive timeouts, support orderly shutdown notifications, and provide reconnection guidance to CLI clients.
- **Command handling**: process IPC requests sequentially per connection with idempotent operations, structured progress callbacks for long-running work, and categorical error codes.
- **Failure handling**: detect orchestrator/service exceptions, escalate to watchdog restart (Phase 4B), and surface last error context and restart counter through `status` replies.
- **Security & audit**: validate client identity, enforce authentication tokens, rate-limit privileged commands, verify process ownership, and append every command to an append-only audit log.

### IPC Specification (revised draft)
- **Protocol envelope**: default to Protocol Buffers messages defined in `ipc/supervisor.proto`, with optional JSON debug mode for tooling.
- **Message schema**:
  ```protobuf
  message SupervisorRequest {
    string protocol_version = 1;        // e.g., "1.0"
    string request_id = 2;              // UUIDv4
    google.protobuf.Timestamp timestamp = 3;
    RequestAction action = 4;           // shutdown, status, ping, restart_service, reload_config
    map<string, google.protobuf.Value> options = 5;   // flags such as force, docker_only
    map<string, google.protobuf.Value> filters = 6;   // service filters, future use
    bool streaming = 7;                 // client supports streaming responses
    uint32 timeout_ms = 8;              // 0 = server default
    ClientInfo client_info = 9;         // pid, user, version, capabilities
    AuthToken auth = 10;                // access token + metadata
  }
  ```
  Responses mirror `{ request_id, status, progress, result, error { code, message, details }, server_timestamp }` and support streaming chunks when `streaming=true`.
- **Connection lifecycle**: supervisor exposes a framed streaming channel (Unix domain socket / named pipe / TLS loopback). Clients authenticate during handshake, must send heartbeats every 15 s, and reconnect with exponential backoff.
- **Error taxonomy**: standardized codes (`UNAUTHORIZED`, `INVALID_ARGUMENT`, `NOT_FOUND`, `TIMEOUT`, `INTERNAL`, `CONCURRENCY_LIMIT`, etc.) documented for CLI handling.
- **Version negotiation**: first handshake message exchanges `protocol_version` and supported features to allow future extensions.

### Transport Considerations
- **POSIX**: Unix domain sockets stored under `${XDG_RUNTIME_DIR}` with 600 permissions; handle cleanup on crash.
- **Windows**: prefer named pipes for same-user scenarios, fall back to loopback TCP with TLS when UAC elevation or service account boundaries apply. Document UAC prompts, service-install option, and antivirus exclusions.
- **WSL / hybrid environments**: detect WSL2, choose TCP transport to avoid cross-namespace socket issues, and warn about firewall/antivirus interference.
- **Path & resource limits**: cap socket path lengths, validate pipe names, and surface actionable errors when limits are hit.

### Security & Operational Controls
- Authentication tokens rotated via config; CLI stores scoped token in OS keychain.
- Rate limiting per client (token bucket, default 10 privileged commands/minute).
- Command allowlist with role-based enforcement (future-friendly but implemented minimally now).
- Audit log written to `logs/supervisor/audit.jsonl` with timestamp, client info, command, outcome.
- Optional integration with OS process ownership checks (ensure caller PID belongs to same user session).

### Error Handling & Observability
- Central error-handling layer maps exceptions to taxonomy codes and ensures consistent logging.
- Structured JSON logs containing request_id, action, duration, result, error_code, connection metadata.
- Health endpoint (read-only) for diagnostics, exposing uptime, connection counts, backlog size.
- Metrics deferred (out-of-scope), but hooks left for future instrumentation.

### Watchdog Strategy (Phase 4B, separate epic)
- Heartbeat every 5 seconds with 30-second grace window.
- Exponential backoff on restart attempts (1s, 5s, 15s) with max 3 retries before manual intervention flag is raised.
- Persist supervisor state snapshot (registry pointer, pending operations) before restart to minimize recovery time.
- Watchdog lives in separate package/epic; supervisor supplies heartbeat artifacts from Phase 4A onward to enable future drop-in.

### Testing & Validation Enhancements
- **Performance targets**: sustain 1000 IPC requests/sec, supervisor memory < 200MB over 24h idle, startup latency < 5s with 50 managed services.
- **Chaos matrix**: simulate supervisor crash during startup, disk-full during registry writes, network partition mid-shutdown, registry corruption recovery flow.
- **Cross-platform cadence**: run smoke suites on Windows/macOS/Linux starting Phase 2 (CI + nightly), not deferred to late stages.
- **Security tests**: fuzz IPC inputs, verify rate limiting, token misuse, and privilege escalation attempts.

### Operational Runbooks
- Provide troubleshooting guide covering connection failures, auth errors, watchdog restarts, audit log interpretation, and fallback procedures.
- Document recovery workflows for registry corruption and manual supervisor replacement.

## Phase 0 Deliverables

### Service Inventory
- ClickHouse database (Docker `clickhouse`): required, provides telemetry storage, health check `_check_clickhouse_health`, startup timeout 180s.
- OTEL collector (Docker `otel-collector`): optional, depends on ClickHouse, startup timeout 90s.
- JSONL bridge service (`context_cleaner.cli.main bridge sync`): required when ClickHouse available; monitors JSONL files.
- Dashboard web server (`ComprehensiveHealthDashboard`): required, launched in process; exposes sockets via Flask/SocketIO.
- API/UI consistency checker: optional monitor depending on dashboard.
- Telemetry collector: optional data ingestion service.
- Ancillary scripts (monitoring, bridge, start_context_cleaner.py) currently unmanaged but interact with same resources.

### IPC Transport Decision Notes
- POSIX: Unix domain sockets under `$XDG_RUNTIME_DIR/context-cleaner/supervisor.sock`, permissions 600, cleanup via `atexit` handler.
- Windows: prefer `\.\pipe\context_cleaner_supervisor` named pipe; fall back to TLS loopback TCP when elevated contexts or service accounts required.
- WSL2 / mixed environments: detect via `/proc/version`; default to loopback TCP to avoid namespace issues; document firewall/antivirus considerations.
- All transports share Proto-based framing with length-prefix to avoid partial reads.

### Security Posture Summary
- Authentication: HMAC-signed tokens stored per-user (macOS Keychain, Windows DPAPI, Linux secret store).
- Rate limiting: token bucket (10 privileged commands/min, 100 status requests/min).
- Audit logging: JSONL append with request metadata (timestamp, client, action, outcome).
- Command authorization: same-user PID verification; future hooks for role separation.

### Architecture Updates
- Add supervisor component to diagrams: sits between CLI and orchestrator, exposes IPC endpoint, records state in ProcessRegistry.
- Document state flow: supervisor -> orchestrator (async APIs) -> services, plus registry updates.
- Identify fallback path: CLI -> supervisor; if unavailable -> legacy discovery fallback (deprecated).
- Diagram annotation notes:
  - Add supervisor node between CLI and ServiceOrchestrator with IPC link.
  - Depict IPC transport paths (UDS, named pipe/TCP) and auth/rate-limiting controls.
  - Show optional watchdog component receiving supervisor heartbeats (Phase 4B).
  - Highlight ProcessRegistry updates storing supervisor and service metadata.

## Implementation PR Breakdown
1. **PR 1 – Discovery & Design Artifacts (Phase 0)**
   - Deliver service inventory, transport decision matrix, security posture summary, and updated architecture diagrams.
   - Tests: documentation only.

2. **PR 2 – IPC Protocol & Transport Foundation (Phase 1)**
   - Add `ipc/supervisor.proto`, implement framing layer, connection limits, auth token validation scaffold, and basic `ping` handling.
   - Include Windows named-pipe and POSIX socket adapters with placeholder platform quirks documented.
   - Tests: unit tests for protocol encoding/decoding, handshake, auth failures, rate limiting.

3. **PR 3 – Supervisor Core Service (Phase 1 cont.)**
   - Implement supervisor lifecycle, state tracking, command routing (`status`, `shutdown` skeleton), audit logging, and error taxonomy.
   - Tests: supervisor unit tests exercising command dispatch, audit log writes, error mapping.

4. **PR 4 – `context-cleaner run` Integration & Cross-Platform Smoke Tests (Phase 2)**
   - Wire supervisor startup into `run`, ensure graceful shutdown on Ctrl+C, publish connection metadata, and add automated smoke tests on Windows/macOS/Linux.
   - Tests: integration harness launching run command with mock IPC client; CI jobs for each OS.

5. **PR 5 – `context-cleaner stop` IPC Client Rewrite (Phase 3)**
   - Replace heuristic stop path with IPC client using new protocol, support streaming progress output, retain discovery fallback via `--fallback`.
   - Tests: CLI tests verifying success, authentication errors, fallback activation.

6. **PR 6 – Orchestrator Async APIs & Service Registration (Phase 4A)**
   - Expose awaitable `shutdown_all`, register external services/ports/container IDs, emit heartbeat data for future watchdog use.
   - Tests: orchestrator unit tests, integration test ensuring supervisor commands drive graceful shutdown.

7. **PR 7 – Watchdog Epic (Phase 4B, optional rollout)**
   - Implement watchdog process with heartbeat monitoring, exponential backoff, restart policy, and state preservation.
   - Tests: chaos tests killing supervisor, verifying restart attempts and escalation when limit reached.

8. **PR 8 – Registry Extensions & Recovery Paths (Phase 5)**
   - Migrate `ProcessRegistry` schema for supervisor entries, add corruption detection/recovery hooks, ensure cleanup routines.
   - Tests: migration tests, recovery flow simulations, disk-full scenario handling.

9. **PR 9 – Performance & Chaos Validation Suite (Phase 6)**
   - Build performance harness for throughput/memory targets, implement chaos scenarios (crash, disk full, network partition), and integrate into CI (nightly/weekly).
   - Tests: automated perf benchmarks with pass/fail gates, chaos scripts.

10. **PR 10 – Documentation, Runbooks & Tooling (Phase 7)**
    - Update README/docs, produce operational runbooks, revise `stop-context-cleaner.sh` to use IPC, add developer FAQ.
    - Tests: doc linting, shell script tests.

11. **PR 11 – Rollout & Legacy Cleanup (Phase 8)**
    - Enable feature flag by default, remove legacy discovery-heavy code, finalize release notes, and confirm graceful fallback story.
    - Tests: regression suite ensuring legacy paths removed; final smoke tests on all platforms.




## Phase 1 Planning Notes
- Module structure: create `context_cleaner.ipc` package with submodules `protocol.py`, `transport/__init__.py`, `transport/base.py`, `transport/unix.py`, `transport/windows.py`, and `client.py`.
- Proto location: store `.proto` definitions under `proto/context_cleaner/supervisor.proto`; generate Python stubs into `src/context_cleaner/ipc/proto` via build step (initial commit includes raw proto and placeholder generated module).
- Dependency additions: add `protobuf>=4.25.0` to project dependencies; ensure optional dev dependency for `mypy-protobuf` (future).
- Logging directory: `logs/supervisor/` (ensure created dynamically).
- Configuration: add new section to config to surface IPC endpoint paths; include defaults for POSIX and Windows.
- Tests: create `tests/ipc/test_protocol.py` for encoding/decoding skeleton and `tests/ipc/test_transport_unix.py` with placeholder tests (skipped on Windows).


## Phase 0 Artifact Summary
- Service inventory and dependency table (see "Service Inventory" section).
- IPC transport decision matrix with cross-platform considerations.
- Security posture overview (authentication, rate limiting, audit logging).
- Architecture diagram notes highlighting supervisor placement, IPC flow, watchdog hook, and registry interactions.
- Pending action: export updated architecture diagram (draw.io / diagrams.net) and attach to docs when ready.
