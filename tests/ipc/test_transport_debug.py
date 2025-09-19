import pytest

from context_cleaner.ipc.transport.debug import DebugTransport
from context_cleaner.ipc.protocol import SupervisorRequest, SupervisorResponse, RequestAction


def test_debug_transport_flow():
    transport = DebugTransport()
    request = SupervisorRequest(action=RequestAction.STATUS)
    response = SupervisorResponse(request_id=request.request_id, status="ok", result={"hello": "world"})

    with pytest.raises(Exception):
        transport.send_request(request)

    transport.connect()
    transport.queue_response(response)
    transport.send_request(request)
    received = transport.receive_response()
    assert received.result["hello"] == "world"

    transport.close()
    with pytest.raises(Exception):
        transport.receive_response()

