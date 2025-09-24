import asyncio
import base64
import json
import os
import shutil
import tempfile
from typing import Any, Dict, Optional, Sequence

import pytest

from datetime import datetime
import datetime as dt

from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.ipc.protocol import (
    SupervisorRequest,
    SupervisorResponse,
    StreamChunk,
    RequestAction,
    AuthToken,
)
from context_cleaner.ipc.client import SupervisorClient
from context_cleaner.ipc.transport.debug import DebugTransport
from context_cleaner.cli.main import _render_shutdown_chunk


class StubOrchestrator:
    def get_service_status(self):
        return {
            "orchestrator": {
                "running": True,
                "uptime": 0,
                "uptime_seconds": 0,
                "started_at": None,
                "shutdown_initiated": False,
                "services_running": 0,
                "required_failed": [],
                "transitioning": {"starting": [], "stopping": []},
            },
            "services": {},
            "services_summary": {
                "total": 0,
                "by_status": {},
                "required_failed": [],
                "optional_failed": [],
                "transitioning": {"starting": [], "stopping": []},
                "running": [],
            },
            "process_registry": {
                "total_registered": 0,
                "by_service_type": {},
                "registry_status": "accessible",
            },
        }

    async def shutdown_all(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ) -> Dict[str, Any]:
        await asyncio.sleep(0)
        return {
            "requested": [],
            "skipped": [],
            "stopped": [],
            "failed": [],
            "errors": {},
            "invalid": [],
            "success": True,
        }

    async def stop_all_services(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ) -> bool:
        summary = await self.shutdown_all(
            docker_only=docker_only,
            processes_only=processes_only,
            services=services,
            include_dependents=include_dependents,
        )
        return summary["success"]


@pytest.mark.asyncio
async def test_supervisor_ping_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)
    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(
            endpoint="ipc://test",
            audit_log_path=str(tmp_path / "audit.log"),
        ),
    )
    await supervisor.start()

    ping_response = await supervisor.handle_request(SupervisorRequest(action=RequestAction.PING))
    assert ping_response.status == "ok"
    assert ping_response.result["message"] == "pong"

    status_response = await supervisor.handle_request(SupervisorRequest(action=RequestAction.STATUS))
    assert status_response.status == "ok"
    supervisor_info = status_response.result["supervisor"]
    assert supervisor_info["endpoint"] == "ipc://test"
    assert supervisor_info["active_connections"] == 0
    assert supervisor_info["max_connections"] == 8
    assert supervisor_info["services_total"] == 0
    assert supervisor_info["services_by_status"] == {}
    assert supervisor_info["services_transitioning"] == {"starting": [], "stopping": []}
    orchestration_snapshot = status_response.result["orchestrator"]
    services_summary = orchestration_snapshot["services_summary"]
    assert services_summary["total"] == 0
    assert services_summary["by_status"] == {}
    registry_entries = status_response.result["registry"]["supervisor"]
    assert any(entry["pid"] == os.getpid() for entry in registry_entries)

    shutdown_response = await supervisor.handle_request(SupervisorRequest(action=RequestAction.SHUTDOWN))
    assert shutdown_response.status == "in-progress"
    shutdown_snapshot = shutdown_response.result["services"]
    assert "services_summary" in shutdown_snapshot
    assert shutdown_snapshot["services_summary"]["total"] == 0

    await supervisor.stop()


def test_render_shutdown_chunk_progress(capsys):
    chunk = StreamChunk(
        request_id="test",
        server_timestamp=dt.datetime.now(dt.timezone.utc),
        payload=json.dumps(
            {
                "stage": "progress",
                "running_services": 2,
                "transitioning": {"stopping": ["svcA", "svcB"]},
            }
        ).encode("utf-8"),
        final_chunk=False,
    )

    _render_shutdown_chunk(chunk, verbose=True)
    output = capsys.readouterr().out
    assert "Supervisor progress" in output
    assert "svcA" in output


@pytest.mark.asyncio
async def test_supervisor_requires_auth_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)
    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(
            endpoint="ipc://test",
            auth_token="secret",
            audit_log_path=str(tmp_path / "audit.log"),
        ),
    )
    await supervisor.start()

    request = SupervisorRequest(action=RequestAction.STATUS)
    unauthorized = await supervisor.handle_request(request)
    assert unauthorized.status == "error"
    assert unauthorized.error["code"] == "unauthorized"

    authorized_request = SupervisorRequest(
        action=RequestAction.STATUS,
        auth=AuthToken(token="secret"),
    )
    ok = await supervisor.handle_request(authorized_request)
    assert ok.status == "ok"

    await supervisor.stop()


@pytest.mark.asyncio
async def test_supervisor_enforces_connection_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)
    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(
            endpoint="ipc://test",
            max_connections=1,
            audit_log_path=str(tmp_path / "audit.log"),
        ),
    )
    await supervisor.start()

    release_event = asyncio.Event()
    original_release = supervisor._release_connection

    async def blocking_release(token):
        await release_event.wait()
        await original_release(token)

    supervisor._release_connection = blocking_release  # type: ignore[assignment]

    first_request = SupervisorRequest(action=RequestAction.STATUS)
    task = asyncio.create_task(supervisor.handle_request(first_request))

    # Allow the first request to register its connection
    await asyncio.sleep(0)

    second_request = SupervisorRequest(action=RequestAction.STATUS)
    response = await supervisor.handle_request(second_request)
    assert response.status == "error"
    assert response.error["code"] == "concurrency-limit"

    release_event.set()
    await task

    supervisor._release_connection = original_release  # type: ignore[assignment]

    await supervisor.stop()


class _DummyEvent:
    def __init__(self) -> None:
        self._flag = False

    def is_set(self) -> bool:
        return self._flag

    def set(self) -> None:
        self._flag = True


class StreamingStubOrchestrator:
    def __init__(self) -> None:
        self.running = True
        self.started_at = datetime.now()
        self.shutdown_event = _DummyEvent()
        self._stage = "running"
        self.last_shutdown_kwargs: Dict[str, Any] = {
            "docker_only": False,
            "processes_only": False,
            "services": None,
            "include_dependents": True,
        }

    def get_service_status(self):
        running_services = 2 if self._stage == "running" else 0
        summary = {
            "total": 2,
            "by_status": {"running": running_services} if running_services else {"stopped": 2},
            "required_failed": [],
            "optional_failed": [],
            "transitioning": {"starting": [], "stopping": []},
            "running": ["svc1", "svc2"] if running_services else [],
        }
        return {
            "orchestrator": {
                "running": self.running,
                "uptime": 0,
                "uptime_seconds": 0,
                "started_at": self.started_at.isoformat(),
                "shutdown_initiated": self.shutdown_event.is_set(),
                "services_running": running_services,
                "required_failed": [],
                "transitioning": {"starting": [], "stopping": []},
                "services_summary": summary,
            },
            "services": {},
            "services_summary": summary,
            "process_registry": {
                "total_registered": 0,
                "by_service_type": {},
                "registry_status": "accessible",
            },
        }

    async def shutdown_all(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ):
        self.last_shutdown_kwargs = {
            "docker_only": docker_only,
            "processes_only": processes_only,
            "services": services,
            "include_dependents": include_dependents,
        }
        self._stage = "stopping"
        await asyncio.sleep(0)
        self._stage = "stopped"
        self.running = False
        self.shutdown_event.set()
        return {
            "requested": ["svc1", "svc2"],
            "skipped": [],
            "stopped": ["svc1", "svc2"],
            "failed": [],
            "errors": {},
            "success": True,
        }

    async def stop_all_services(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ) -> bool:
        summary = await self.shutdown_all(
            docker_only=docker_only,
            processes_only=processes_only,
            services=services,
            include_dependents=include_dependents,
        )
        return summary["success"]


class MemoryStreamWriter:
    def __init__(self) -> None:
        self.frames = []

    def write(self, data: bytes) -> None:
        self.frames.append(bytes(data))

    async def drain(self) -> None:  # pragma: no cover - trivial
        return None


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="Unix sockets not available on Windows")
async def test_supervisor_unix_listener_round_trip(monkeypatch):
    socket_dir = tempfile.mkdtemp(prefix="cc-supervisor-", dir="/tmp")
    endpoint = os.path.join(socket_dir, "ipc.sock")
    audit_log_path = os.path.join(socket_dir, "audit.log")
    registry_path = os.path.join(socket_dir, "registry.db")
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", registry_path)
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(
            endpoint=endpoint,
            audit_log_path=audit_log_path,
        ),
    )
    audit_entries = []
    try:
        try:
            await supervisor.start()
        except PermissionError as exc:
            await supervisor.stop()
            shutil.rmtree(socket_dir, ignore_errors=True)
            pytest.skip(f"Unable to start supervisor listener: {exc}")

        with SupervisorClient(endpoint=endpoint) as client:
            response = client.ping()
            assert response.status == "ok"
            status_response = client.send(SupervisorRequest(action=RequestAction.STATUS))
            assert status_response.status == "ok"
            assert "orchestrator" in status_response.result
            supervisor_info = status_response.result["supervisor"]
            assert supervisor_info["endpoint"] == endpoint
            assert "services_total" in supervisor_info
            registry_entries = status_response.result["registry"]["supervisor"]
            assert any(entry["pid"] == os.getpid() for entry in registry_entries)
            assert status_response.result["supervisor"]["audit_log"] == audit_log_path
            services_summary = status_response.result["orchestrator"]["services_summary"]
            assert "by_status" in services_summary
        await asyncio.sleep(0)
    finally:
        await supervisor.stop()
        if os.path.exists(audit_log_path):
            with open(audit_log_path, "r", encoding="utf-8") as handle:
                audit_entries = [json.loads(line) for line in handle if line.strip()]
        shutil.rmtree(socket_dir, ignore_errors=True)

    assert audit_entries, "Audit log should contain entries"
    assert any(entry.get("event") == "request" for entry in audit_entries)
    assert any(entry.get("event") == "response" for entry in audit_entries)
    assert any("summary" in entry for entry in audit_entries)


@pytest.mark.asyncio
async def test_supervisor_shutdown_stream(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    orchestrator = StreamingStubOrchestrator()
    supervisor = ServiceSupervisor(
        orchestrator,
        SupervisorConfig(endpoint="ipc://stream-test", audit_log_path=str(tmp_path / "audit.log")),
    )
    await supervisor.start()

    writer = MemoryStreamWriter()
    request = SupervisorRequest(action=RequestAction.SHUTDOWN, streaming=True)
    response = await supervisor.handle_request(request, writer)

    assert response.status == "ok"
    assert response.result["message"] == "shutdown-complete"
    assert "summary" in response.result
    assert response.result["summary"]["success"] is True

    stages = []
    finals = []
    payloads = []
    for frame in writer.frames:
        size = int.from_bytes(frame[:4], "big")
        payload = frame[4 : 4 + size].decode("utf-8")
        data = json.loads(payload)
        assert data["message_type"] == "stream-chunk"
        chunk_body = json.loads(base64.b64decode(data["payload"]).decode("utf-8"))
        payloads.append(chunk_body)
        stages.append(chunk_body.get("stage"))
        finals.append(data.get("final_chunk", False))

    assert stages[0] == "initiated"
    assert stages[-1] == "completed"
    assert finals[-1] is True
    assert "shutdown_summary" in payloads[-1]
    assert payloads[-1]["shutdown_summary"]["success"] is True

    await supervisor.stop()


@pytest.mark.asyncio
async def test_supervisor_shutdown_stream_with_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    orchestrator = StreamingStubOrchestrator()
    supervisor = ServiceSupervisor(
        orchestrator,
        SupervisorConfig(endpoint="ipc://stream-filter-test", audit_log_path=str(tmp_path / "audit.log")),
    )
    await supervisor.start()

    writer = MemoryStreamWriter()
    request = SupervisorRequest(action=RequestAction.SHUTDOWN, streaming=True)
    request.options["docker_only"] = True
    response = await supervisor.handle_request(request, writer)

    assert orchestrator.last_shutdown_kwargs == {
        "docker_only": True,
        "processes_only": False,
        "services": None,
        "include_dependents": True,
    }
    assert response.status == "ok"
    assert response.result["filters"] == {"docker_only": True}

    decoded_chunks = []
    for frame in writer.frames:
        size = int.from_bytes(frame[:4], "big")
        payload = frame[4 : 4 + size].decode("utf-8")
        data = json.loads(payload)
        chunk_body = json.loads(base64.b64decode(data["payload"]).decode("utf-8"))
        decoded_chunks.append(chunk_body)

    assert any(chunk.get("filters") == {"docker_only": True} for chunk in decoded_chunks)

    await supervisor.stop()


@pytest.mark.asyncio
async def test_supervisor_shutdown_with_service_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    orchestrator = StreamingStubOrchestrator()
    supervisor = ServiceSupervisor(
        orchestrator,
        SupervisorConfig(endpoint="ipc://service-filter-test", audit_log_path=str(tmp_path / "audit.log")),
    )
    await supervisor.start()

    request = SupervisorRequest(action=RequestAction.SHUTDOWN)
    request.options["services"] = ["dashboard"]
    request.options["include_dependents"] = False
    response = await supervisor.handle_request(request)

    assert response.status == "in-progress"
    assert response.result["message"] == "shutdown-started"

    # Let the orchestrator coroutine run
    await asyncio.sleep(0)

    assert orchestrator.last_shutdown_kwargs == {
        "docker_only": False,
        "processes_only": False,
        "services": ["dashboard"],
        "include_dependents": False,
    }

    await supervisor.stop()


def test_client_stream_shutdown_mutually_exclusive():
    client = SupervisorClient(transport=DebugTransport())

    with pytest.raises(ValueError):
        list(client.stream_shutdown(docker_only=True, processes_only=True))


@pytest.mark.asyncio
async def test_client_shutdown_with_stream(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTEXT_CLEANER_PROCESS_REGISTRY_DB", str(tmp_path / "registry.db"))
    monkeypatch.setattr("context_cleaner.services.process_registry._registry", None)
    monkeypatch.setattr("context_cleaner.services.process_registry._discovery_engine", None)

    orchestrator = StreamingStubOrchestrator()
    supervisor = ServiceSupervisor(
        orchestrator,
        SupervisorConfig(endpoint="ipc://client-stream", audit_log_path=str(tmp_path / "audit.log")),
    )
    await supervisor.start()

    transport = DebugTransport()
    client = SupervisorClient(transport=transport)
    client.connect()

    # Simulate stream chunks and final response
    request_id = "req-client-stream"
    stage_chunk = StreamChunk(
        request_id=request_id,
        server_timestamp=dt.datetime.now(dt.timezone.utc),
        payload=json.dumps({"stage": "progress"}).encode("utf-8"),
        final_chunk=False,
    )
    final_chunk = StreamChunk(
        request_id=request_id,
        server_timestamp=dt.datetime.now(dt.timezone.utc),
        payload=json.dumps({"stage": "completed"}).encode("utf-8"),
        final_chunk=True,
    )
    transport.queue_stream_chunk(stage_chunk)
    transport.queue_stream_chunk(final_chunk)
    transport.queue_response(SupervisorResponse(request_id=request_id, status="ok"))

    response, chunks = client.shutdown_with_stream(services=["dashboard"], include_dependents=False)
    assert response.status == "ok"
    assert len(chunks) == 2
    assert chunks[-1].final_chunk is True

    sent_request = transport.sent_requests.popleft()
    assert sent_request.options.get("services") == ["dashboard"]
    assert sent_request.options.get("include_dependents") is False

    await supervisor.stop()
