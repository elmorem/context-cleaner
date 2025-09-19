import asyncio
import pytest

from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.ipc.protocol import SupervisorRequest, RequestAction, AuthToken


class StubOrchestrator:
    def get_service_status(self):
        return {"orchestrator": {"running": True}, "services": {}}

    async def stop_all_services(self):
        await asyncio.sleep(0)
        return True


@pytest.mark.asyncio
async def test_supervisor_ping_and_shutdown():
    supervisor = ServiceSupervisor(StubOrchestrator(), SupervisorConfig(endpoint="ipc://test"))
    await supervisor.start()

    ping_response = await supervisor.handle_request(SupervisorRequest(action=RequestAction.PING))
    assert ping_response.status == "ok"
    assert ping_response.result["message"] == "pong"

    shutdown_response = await supervisor.handle_request(SupervisorRequest(action=RequestAction.SHUTDOWN))
    assert shutdown_response.status == "in-progress"

    await supervisor.stop()


@pytest.mark.asyncio
async def test_supervisor_requires_auth_token():
    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(endpoint="ipc://test", auth_token="secret"),
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
async def test_supervisor_enforces_connection_limit():
    supervisor = ServiceSupervisor(
        StubOrchestrator(),
        SupervisorConfig(endpoint="ipc://test", max_connections=1),
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
