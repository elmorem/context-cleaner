import pytest

from context_cleaner.ipc.client import SupervisorClient
from context_cleaner.ipc.protocol import (
    SupervisorRequest,
    RequestAction,
    SupervisorResponse,
    AuthToken,
)
from context_cleaner.ipc.transport.debug import DebugTransport


@pytest.fixture
def debug_transport():
    return DebugTransport()


def test_client_applies_explicit_auth_token(debug_transport):
    client = SupervisorClient(transport=debug_transport, auth_token="super-secret")
    client.connect()
    debug_transport.queue_response(SupervisorResponse(request_id="test", status="ok"))

    result = client.ping()

    assert result.status == "ok"
    sent_request = debug_transport.sent_requests.popleft()
    assert sent_request.auth is not None
    assert sent_request.auth.token == "super-secret"
    assert sent_request.client_info.user


def test_client_uses_env_token(monkeypatch, debug_transport):
    monkeypatch.setenv("CONTEXT_CLEANER_SUPERVISOR_TOKEN", "env-secret")
    client = SupervisorClient(transport=debug_transport)
    client.connect()
    debug_transport.queue_response(SupervisorResponse(request_id="test", status="ok"))

    client.ping()
    sent_request = debug_transport.sent_requests.popleft()
    assert sent_request.auth.token == "env-secret"


def test_client_preserves_existing_auth(debug_transport):
    client = SupervisorClient(transport=debug_transport, auth_token="unused")
    client.connect()
    request = SupervisorRequest(action=RequestAction.STATUS, auth=AuthToken(token="provided"))
    debug_transport.queue_response(SupervisorResponse(request_id=request.request_id, status="ok"))

    client.send(request)
    sent_request = debug_transport.sent_requests.popleft()
    assert sent_request.auth.token == "provided"
