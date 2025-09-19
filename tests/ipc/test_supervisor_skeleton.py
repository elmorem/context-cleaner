import asyncio
import pytest

from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.ipc.protocol import SupervisorRequest, RequestAction


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

