"""Supervisor service skeleton for managing IPC requests."""

from __future__ import annotations

import asyncio
import datetime as dt
import getpass
import json
import logging
import os
import platform
import uuid
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from context_cleaner.services.service_orchestrator import ServiceOrchestrator
from context_cleaner.ipc.protocol import (
    SupervisorRequest,
    SupervisorResponse,
    RequestAction,
    ErrorCode,
    ISO8601,
    StreamChunk,
)
from context_cleaner.services.process_registry import (
    ProcessEntry,
    get_process_registry,
)

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from context_cleaner.services.service_watchdog import ServiceWatchdog

LOGGER = logging.getLogger(__name__)


class AuditLogger:
    """Append-only audit logger for supervisor activity."""

    def __init__(self, log_path: Path) -> None:
        self._path = log_path
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "AuditLogger":
        await asyncio.to_thread(self._prepare)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def log(self, payload: dict) -> None:
        line = json.dumps(payload, separators=(",", ":"))
        async with self._lock:
            await asyncio.to_thread(self._append_line, line)

    def _prepare(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append_line(self, line: str) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    @property
    def path(self) -> Path:
        return self._path


@dataclass
class SupervisorConfig:
    """Configuration for the supervisor."""

    endpoint: str
    max_connections: int = 8
    auth_token: Optional[str] = None
    audit_log_path: Optional[str] = None
    heartbeat_interval_seconds: int = 10
    heartbeat_timeout_seconds: int = 30


class ServiceSupervisor:
    """Skeleton implementation of the IPC supervisor."""

    def __init__(self, orchestrator: ServiceOrchestrator, config: SupervisorConfig) -> None:
        self._orchestrator = orchestrator
        self._config = config
        self._stack = AsyncExitStack()
        self._running = False
        self._connections = set()
        self._connections_lock = asyncio.Lock()
        self._server: Optional[asyncio.AbstractServer] = None
        self._server_task: Optional[asyncio.Task[None]] = None
        self._audit_logger: Optional[AuditLogger] = None
        self._socket_path: Optional[Path] = None
        self._registry = get_process_registry()
        self._supervisor_registered = False
        self._start_time: Optional[dt.datetime] = None
        self._last_registry_environment: Optional[Dict[str, Any]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._last_heartbeat_at: Optional[dt.datetime] = None
        self._watchdog: Optional["ServiceWatchdog"] = None

    async def start(self) -> None:
        if self._running:
            LOGGER.debug("Supervisor already running")
            return
        LOGGER.info("Starting supervisor on endpoint %s", self._config.endpoint)
        self._running = True
        self._start_time = dt.datetime.now(dt.timezone.utc)

        audit_path = Path(self._config.audit_log_path or "logs/supervisor/audit.log")
        self._audit_logger = AuditLogger(audit_path)
        await self._stack.enter_async_context(self._audit_logger)

        self._supervisor_registered = await asyncio.to_thread(self._register_supervisor_process)
        if not self._supervisor_registered:
            LOGGER.warning("Failed to register supervisor process in registry")
        self._heartbeat_task = asyncio.create_task(self._emit_heartbeat_loop())
        self._stack.push_async_callback(self._cancel_heartbeat)

        if self._config.endpoint.startswith("ipc://"):
            LOGGER.debug("Supervisor running without network listener (debug endpoint)")
            return

        if os.name == "nt":  # pragma: no cover - platform specific
            raise RuntimeError("Windows supervisor listener not implemented yet")

        socket_path = Path(self._config.endpoint)
        if socket_path.exists():
            socket_path.unlink()
        socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._socket_path = socket_path
        server = await asyncio.start_unix_server(self._handle_connection, path=str(socket_path))
        self._server = server
        self._server_task = asyncio.create_task(server.serve_forever())
        self._stack.push_async_callback(self._shutdown_server)

    async def stop(self) -> None:
        if not self._running:
            return
        LOGGER.info("Stopping supervisor")
        self._running = False
        await self._stack.aclose()
        async with self._connections_lock:
            self._connections.clear()
        if self._supervisor_registered:
            await asyncio.to_thread(self._update_registry_status, "stopped")
            await asyncio.to_thread(self._unregister_supervisor_process)
            self._supervisor_registered = False
        self._heartbeat_task = None

    def register_watchdog(self, watchdog: Optional["ServiceWatchdog"]) -> None:
        """Associate a watchdog instance so status responses expose its telemetry."""

        self._watchdog = watchdog

    async def handle_request(
        self,
        request: SupervisorRequest,
        stream_writer: Optional[asyncio.StreamWriter] = None,
    ) -> SupervisorResponse:
        if not self._running:
            return self._error_response(
                request,
                code=ErrorCode.INTERNAL,
                message="supervisor-not-running",
            )

        auth_error = self._authorize(request)
        if auth_error:
            return auth_error

        token = object()
        if not await self._register_connection(token):
            return self._error_response(
                request,
                code=ErrorCode.CONCURRENCY_LIMIT,
                message="max-connections-exceeded",
            )

        LOGGER.debug("Handling request %s", request.action)
        try:
            if request.action is RequestAction.PING:
                return SupervisorResponse(
                    request_id=request.request_id,
                    status="ok",
                    result={"message": "pong"},
                )
            if request.action is RequestAction.STATUS:
                if self._supervisor_registered:
                    await asyncio.to_thread(self._update_registry_status, "running")
                status_payload = await self._build_status_payload(exclude_token=token)
                return SupervisorResponse(request_id=request.request_id, status="ok", result=status_payload)
            if request.action is RequestAction.SHUTDOWN:
                shutdown_kwargs, error = self._resolve_shutdown_options(request)
                if error:
                    return error
                if request.streaming and stream_writer is not None:
                    return await self._handle_shutdown_stream(request, stream_writer)
                asyncio.create_task(self._orchestrator.shutdown_all(**shutdown_kwargs))
                if self._supervisor_registered:
                    await asyncio.to_thread(self._update_registry_status, "stopping")
                active_filters = {k: v for k, v in shutdown_kwargs.items() if v}
                payload = {
                    "message": "shutdown-started",
                    "services": await asyncio.to_thread(self._orchestrator.get_service_status),
                }
                if active_filters:
                    payload["filters"] = active_filters
                return SupervisorResponse(
                    request_id=request.request_id,
                    status="in-progress",
                    result=payload,
                )
            return self._error_response(
                request,
                code=ErrorCode.INVALID_ARGUMENT,
                message=request.action.value,
            )
        finally:
            await self._release_connection(token)

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peername = writer.get_extra_info("peername")
        LOGGER.debug("Accepted supervisor connection from %s", peername)
        try:
            while True:
                try:
                    header = await reader.readexactly(4)
                except asyncio.IncompleteReadError:
                    break
                size = int.from_bytes(header, "big")
                payload = await reader.readexactly(size)
                raw_payload = payload.decode("utf-8")

                try:
                    request = SupervisorRequest.from_json(raw_payload)
                except ValueError as exc:
                    LOGGER.warning("Invalid request payload: %s", exc)
                    response = SupervisorResponse(
                        request_id=self._extract_request_id(raw_payload),
                        status="error",
                        error={
                            "code": ErrorCode.INVALID_ARGUMENT.value,
                            "message": "invalid-request",
                        },
                    )
                    await self._record_audit("invalid-request", response=response)
                    await self._send_response(writer, response)
                    continue

                await self._record_audit("request", request=request)
                response = await self.handle_request(request, writer)
                await self._record_audit("response", request=request, response=response)
                await self._send_response(writer, response)
        finally:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

    async def _send_response(self, writer: asyncio.StreamWriter, response: SupervisorResponse) -> None:
        payload = response.to_json().encode("utf-8")
        frame = len(payload).to_bytes(4, "big") + payload
        writer.write(frame)
        await writer.drain()

    async def _register_connection(self, token: object) -> bool:
        async with self._connections_lock:
            if len(self._connections) >= max(1, self._config.max_connections):
                return False
            self._connections.add(token)
            return True

    async def _release_connection(self, token: object) -> None:
        async with self._connections_lock:
            self._connections.discard(token)

    def _authorize(self, request: SupervisorRequest) -> Optional[SupervisorResponse]:
        if not self._config.auth_token:
            return None
        if not request.auth or request.auth.token != self._config.auth_token:
            LOGGER.warning("Unauthorized request for action %s", request.action)
            return self._error_response(
                request,
                code=ErrorCode.UNAUTHORIZED,
                message="invalid-auth-token",
            )
        return None

    def _error_response(self, request: SupervisorRequest, *, code: ErrorCode, message: str) -> SupervisorResponse:
        return SupervisorResponse(
            request_id=request.request_id,
            status="error",
            error={
                "code": code.value,
                "message": message,
            },
        )

    async def _record_audit(
        self,
        event: str,
        *,
        request: Optional[SupervisorRequest] = None,
        response: Optional[SupervisorResponse] = None,
    ) -> None:
        if not self._audit_logger:
            return
        entry = {
            "event": event,
            "timestamp": dt.datetime.now(dt.timezone.utc).strftime(ISO8601),
        }
        if request:
            entry.update(
                {
                    "request_id": request.request_id,
                    "action": request.action.value,
                }
            )
            if request.client_info:
                entry["client"] = {
                    "pid": request.client_info.pid,
                    "user": request.client_info.user,
                }
            entry["streaming"] = request.streaming
            if request.timeout_ms is not None:
                entry["timeout_ms"] = request.timeout_ms
        elif response:
            entry["request_id"] = response.request_id
        if response:
            entry["status"] = response.status
            if response.error:
                entry["error"] = response.error
        if request and response:
            entry["summary"] = f"{request.action.value}:{response.status}"
        elif request:
            entry["summary"] = request.action.value
        elif response:
            entry["summary"] = response.status
        await self._audit_logger.log(entry)

    async def _shutdown_server(self) -> None:
        if self._server_task:
            self._server_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._server_task
            self._server_task = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._socket_path and self._socket_path.exists():
            with suppress(OSError):
                self._socket_path.unlink()
        self._socket_path = None

    def _extract_request_id(self, payload: str) -> str:
        try:
            data = json.loads(payload)
            request_id = data.get("request_id")
        except json.JSONDecodeError:
            request_id = None
        return request_id or str(uuid.uuid4())

    def _register_supervisor_process(self) -> bool:
        if not self._registry:
            return False
        now = dt.datetime.now()
        environment = self._build_registry_environment()
        metadata = {
            "max_connections": self._config.max_connections,
            "auth_required": bool(self._config.auth_token),
        }
        entry = ProcessEntry(
            pid=os.getpid(),
            command_line="service_supervisor",
            service_type="supervisor",
            start_time=now,
            registration_time=now,
            status="running",
            parent_orchestrator=self._orchestrator.__class__.__name__,
            user_id=getpass.getuser(),
            host_identifier=platform.node(),
            registration_source="supervisor",
            working_directory=os.getcwd(),
            environment_vars=json.dumps(environment),
            resource_limits=json.dumps(metadata),
            health_check_config=json.dumps({"endpoint": self._config.endpoint}),
        )
        entry.parent_pid = os.getppid()
        registered = self._registry.register_process(entry)
        if registered:
            self._last_registry_environment = environment
        return registered

    def _update_registry_status(self, status: str) -> None:
        if not self._registry:
            return
        updated = self._registry.update_process_status(os.getpid(), status)
        if not updated:
            LOGGER.debug("Registry update for supervisor pid %s failed", os.getpid())

    def _unregister_supervisor_process(self) -> None:
        if not self._registry:
            return
        if not self._registry.unregister_process(os.getpid()):
            LOGGER.debug("Registry unregister for supervisor pid %s failed", os.getpid())
        self._last_registry_environment = None

    async def _build_status_payload(self, *, exclude_token: Optional[object] = None) -> Dict[str, Any]:
        orchestrator_status = await asyncio.to_thread(self._orchestrator.get_service_status)
        await asyncio.to_thread(
            self._update_registry_metadata,
            orchestrator_status.get("services_summary") if isinstance(orchestrator_status, dict) else None,
        )
        registry_snapshot = await asyncio.to_thread(self._collect_registry_snapshot)
        now = dt.datetime.now(dt.timezone.utc)
        uptime = None
        if self._start_time:
            uptime = max((now - self._start_time).total_seconds(), 0.0)
        active_connections = len(self._connections)
        if exclude_token is not None and exclude_token in self._connections:
            active_connections = max(active_connections - 1, 0)
        services_summary = orchestrator_status.get("services_summary", {}) if isinstance(orchestrator_status, dict) else {}
        by_status = services_summary.get("by_status", {}) if isinstance(services_summary, dict) else {}
        supervisor_info = {
            "pid": os.getpid(),
            "endpoint": self._config.endpoint,
            "start_time": self._start_time.strftime(ISO8601) if self._start_time else None,
            "uptime_seconds": uptime,
            "active_connections": active_connections,
            "max_connections": self._config.max_connections,
            "auth_required": bool(self._config.auth_token),
            "listener_active": self._server is not None,
            "audit_log": str(self._audit_logger.path) if self._audit_logger else None,
            "state": "running" if self._running else "stopped",
            "services_total": services_summary.get("total", 0),
            "services_running": by_status.get("running", 0) + by_status.get("attached", 0),
            "services_by_status": by_status,
            "services_transitioning": services_summary.get("transitioning", {}),
            "required_failed": services_summary.get("required_failed", []),
            "optional_failed": services_summary.get("optional_failed", []),
            "heartbeat_interval": self._config.heartbeat_interval_seconds,
            "heartbeat_timeout": self._config.heartbeat_timeout_seconds,
            "last_heartbeat_at": self._last_heartbeat_at.strftime(ISO8601) if self._last_heartbeat_at else None,
        }
        watchdog_info: Dict[str, Any] = {}
        if self._watchdog is not None:
            history = self._watchdog.restart_history
            max_history = 5
            watchdog_info = {
                "enabled": not self._watchdog.disabled,
                "running": self._watchdog.is_running,
                "last_heartbeat_at": self._watchdog.last_heartbeat_at.strftime(ISO8601) if self._watchdog.last_heartbeat_at else None,
                "last_restart_reason": self._watchdog.last_restart_reason,
                "last_restart_success": self._watchdog.last_restart_success,
                "last_restart_at": self._watchdog.last_restart_at.isoformat() if self._watchdog.last_restart_at else None,
                "restart_attempts": self._watchdog.restart_attempts,
                "restart_history": history[-max_history:],
            }
        return {
            "supervisor": supervisor_info,
            "orchestrator": orchestrator_status,
            "registry": registry_snapshot,
            "watchdog": watchdog_info,
        }

    def _collect_registry_snapshot(self) -> Dict[str, Any]:
        if not self._registry:
            return {"supervisor": []}
        try:
            supervisor_entries = self._registry.get_processes_by_type("supervisor")
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("Failed to collect supervisor registry snapshot: %s", exc)
            return {"supervisor": []}

        return {
            "supervisor": [self._serialize_registry_entry(entry) for entry in supervisor_entries],
        }

    def _serialize_registry_entry(self, entry: ProcessEntry) -> Dict[str, Any]:
        data = entry.to_dict()
        keys = (
            "pid",
            "service_type",
            "status",
            "host",
            "registration_time",
            "start_time",
            "last_health_check",
            "registration_source",
            "command_line",
            "port",
            "last_health_status",
            "parent_orchestrator",
            "container_id",
            "container_state",
            "metadata",
        )
        result = {key: data.get(key) for key in keys if data.get(key) not in (None, "", [])}
        for key in ("resource_limits", "health_check_config", "environment_vars"):
            value = data.get(key)
            if not value:
                continue
            try:
                result[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                result[key] = value
        for key in ("metadata",):
            value = data.get(key)
            if not value:
                continue
            try:
                result[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                result[key] = value
        return result

    async def _handle_shutdown_stream(
        self,
        request: SupervisorRequest,
        writer: asyncio.StreamWriter,
    ) -> SupervisorResponse:
        await self._record_audit("shutdown-stream-start", request=request)
        if self._supervisor_registered:
            await asyncio.to_thread(self._update_registry_status, "stopping")

        shutdown_kwargs, error = self._resolve_shutdown_options(request)
        if error:
            return error
        active_filters = {k: v for k, v in shutdown_kwargs.items() if v}

        before_status = await asyncio.to_thread(self._orchestrator.get_service_status)
        initial_chunk = {
            "stage": "initiated",
            "summary": before_status.get("services_summary"),
            "running_services": before_status.get("orchestrator", {}).get("services_running"),
            "required_failed": before_status.get("orchestrator", {}).get("required_failed"),
        }
        if active_filters:
            initial_chunk["filters"] = active_filters
        await self._send_stream_chunk(
            writer,
            request,
            initial_chunk,
            final=False,
        )

        shutdown_task = asyncio.create_task(self._orchestrator.shutdown_all(**shutdown_kwargs))
        progress_emitted = False
        last_snapshot = before_status
        shutdown_summary: Dict[str, Any] | None = None

        try:
            while not shutdown_task.done():
                await asyncio.sleep(0.2)
                progress_status = await asyncio.to_thread(self._orchestrator.get_service_status)
                last_snapshot = progress_status
                await self._record_stream_audit(request, progress_status, stage="progress")
                await self._send_stream_chunk(
                    writer,
                    request,
                    {
                        "stage": "progress",
                        "summary": progress_status.get("services_summary"),
                        "running_services": progress_status.get("orchestrator", {}).get("services_running"),
                        "transitioning": progress_status.get("orchestrator", {}).get("transitioning"),
                        "required_failed": progress_status.get("orchestrator", {}).get("required_failed"),
                    },
                    final=False,
                )
                progress_emitted = True

            shutdown_summary = shutdown_task.result()
            success = shutdown_summary.get("success", False)
        except Exception as exc:  # pragma: no cover - defensive
            success = False
            LOGGER.exception("Supervisor shutdown stream failed: %s", exc)
        finally:
            result_status = await asyncio.to_thread(self._orchestrator.get_service_status)
            final_chunk = {
                "stage": "completed",
                "success": success,
                "summary": result_status.get("services_summary"),
                "running_services": result_status.get("orchestrator", {}).get("services_running"),
                "required_failed": result_status.get("orchestrator", {}).get("required_failed"),
                "transitioning": result_status.get("orchestrator", {}).get("transitioning"),
                "last_summary": last_snapshot.get("services_summary"),
                "progress_emitted": progress_emitted,
                "shutdown_summary": shutdown_summary,
            }
            if active_filters:
                final_chunk["filters"] = active_filters
            await self._send_stream_chunk(
                writer,
                request,
                final_chunk,
                final=True,
            )
            await self._record_stream_audit(request, result_status, stage="completed", success=success)

        status = "ok" if success else "error"
        payload = {
            "message": "shutdown-complete" if success else "shutdown-failed",
            "success": success,
            "summary": shutdown_summary,
        }
        if active_filters:
            payload["filters"] = active_filters
        response = SupervisorResponse(
            request_id=request.request_id,
            status=status,
            result=payload,
        )
        if self._supervisor_registered:
            await asyncio.to_thread(self._update_registry_status, "running" if success else "error")
        await self._record_audit("shutdown-stream-complete", request=request, response=response)
        return response

    async def _send_stream_chunk(
        self,
        writer: asyncio.StreamWriter,
        request: SupervisorRequest,
        data: Dict[str, Any],
        *,
        final: bool,
    ) -> None:
        chunk = StreamChunk(
            request_id=request.request_id,
            server_timestamp=dt.datetime.now(dt.timezone.utc),
            payload=json.dumps(data).encode("utf-8"),
            final_chunk=final,
        )
        payload = chunk.to_json().encode("utf-8")
        frame = len(payload).to_bytes(4, "big") + payload
        writer.write(frame)
        await writer.drain()
        await self._record_audit(
            "shutdown-stream-chunk",
            request=request,
            response=SupervisorResponse(
                request_id=request.request_id,
                status="stream-chunk",
                result={"data": data, "final": final},
            ),
        )

    async def _record_stream_audit(
        self,
        request: SupervisorRequest,
        snapshot: Dict[str, Any],
        *,
        stage: str,
        success: Optional[bool] = None,
    ) -> None:
        summary = snapshot.get("services_summary", {}) if isinstance(snapshot, dict) else {}
        orchestrator = snapshot.get("orchestrator", {}) if isinstance(snapshot, dict) else {}
        entry = {
            "event": "shutdown-stream-state",
            "timestamp": dt.datetime.now(dt.timezone.utc).strftime(ISO8601),
            "request_id": request.request_id,
            "stage": stage,
            "services_total": summary.get("total"),
            "running": orchestrator.get("services_running"),
            "required_failed": orchestrator.get("required_failed"),
            "transitioning": orchestrator.get("transitioning"),
            "success": success,
        }
        active_filters = {k: v for k, v in request.options.items() if v}
        if active_filters:
            entry["filters"] = active_filters
        if self._audit_logger:
            await self._audit_logger.log(entry)

    def _update_registry_metadata(self, summary: Optional[Dict[str, Any]]) -> None:
        if not self._registry or not self._supervisor_registered:
            return
        environment = self._build_registry_environment(summary)
        if environment == self._last_registry_environment:
            return
        updated = self._registry.update_process_metadata(
            os.getpid(),
            environment_vars=json.dumps(environment),
        )
        if updated:
            self._last_registry_environment = environment
        else:
            LOGGER.debug("Registry metadata update for supervisor pid %s failed", os.getpid())

    async def _emit_heartbeat_loop(self) -> None:
        interval = max(1, self._config.heartbeat_interval_seconds)
        while self._running:
            try:
                await asyncio.sleep(interval)
                await asyncio.to_thread(self._publish_heartbeat)
            except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
                break
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.debug("Heartbeat update failed: %s", exc)

    def _publish_heartbeat(self) -> None:
        if not self._registry or not self._supervisor_registered:
            return
        now = dt.datetime.now(dt.timezone.utc)
        base_environment = self._build_registry_environment()
        base_environment["HEARTBEAT_AT"] = now.strftime(ISO8601)
        updated = self._registry.update_process_metadata(
            os.getpid(),
            environment_vars=json.dumps(base_environment),
            last_health_check=now.isoformat(),
        )
        if updated:
            self._last_registry_environment = base_environment
            self._last_heartbeat_at = now

    async def _cancel_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task

    def _build_registry_environment(
        self,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc)
        environment: Dict[str, Any] = {
            "IPC_ENDPOINT": self._config.endpoint,
            "UPDATED_AT": now.strftime(ISO8601),
            "HEARTBEAT_AT": now.strftime(ISO8601),
            "HEARTBEAT_INTERVAL": self._config.heartbeat_interval_seconds,
            "HEARTBEAT_TIMEOUT": self._config.heartbeat_timeout_seconds,
        }
        if self._audit_logger:
            environment["AUDIT_LOG"] = str(self._audit_logger.path)
        if summary:
            environment["SERVICES_SUMMARY"] = summary
        return environment

    def _resolve_shutdown_options(
        self,
        request: SupervisorRequest,
    ) -> tuple[Dict[str, Any], Optional[SupervisorResponse]]:
        docker_only = bool(request.options.get("docker_only"))
        processes_only = bool(request.options.get("processes_only"))
        if docker_only and processes_only:
            return {}, self._error_response(
                request,
                code=ErrorCode.INVALID_ARGUMENT,
                message="conflicting-shutdown-filters",
            )
        filters: Dict[str, Any] = {
            "docker_only": docker_only,
            "processes_only": processes_only,
        }

        services_option = request.filters.get("services") or request.options.get("services")
        services_list: Optional[list[str]] = None
        if services_option is not None:
            if isinstance(services_option, str):
                if services_option:
                    # Support comma-delimited strings from CLI callers
                    services_list = [s.strip() for s in services_option.split(",") if s.strip()]
            elif isinstance(services_option, (list, tuple, set)):
                services_list = [str(item).strip() for item in services_option if str(item).strip()]
            else:
                return {}, self._error_response(
                    request,
                    code=ErrorCode.INVALID_ARGUMENT,
                    message="invalid-services-filter",
                )

            if services_list:
                filters["services"] = services_list

        include_dependents_value = request.options.get("include_dependents")
        if include_dependents_value is not None:
            filters["include_dependents"] = bool(include_dependents_value)

        return filters, None
