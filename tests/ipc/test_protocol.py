import json
from context_cleaner.ipc.protocol import (
    SupervisorRequest,
    SupervisorResponse,
    RequestAction,
    ClientInfo,
    StreamChunk,
)


def test_request_serialisation_roundtrip():
    request = SupervisorRequest(
        action=RequestAction.STATUS,
        client_info=ClientInfo(pid=1234, user="tester", version="1.2.3"),
        options={"force": True},
        streaming=True,
        timeout_ms=30_000,
    )

    payload = request.to_json()
    data = json.loads(payload)

    assert data["action"] == "status"
    assert data["options"]["force"] is True
    assert data["streaming"] is True
    assert data["timeout_ms"] == 30_000
    assert data["client_info"]["pid"] == 1234


def test_request_from_json_roundtrip():
    request = SupervisorRequest(
        action=RequestAction.SHUTDOWN,
        client_info=ClientInfo(pid=1, user="cli", version="0.1.0"),
        timeout_ms=10_000,
    )
    loaded = SupervisorRequest.from_json(request.to_json())

    assert loaded.action is RequestAction.SHUTDOWN
    assert loaded.client_info is not None
    assert loaded.client_info.user == "cli"
    assert loaded.timeout_ms == 10_000


def test_stream_chunk_serialisation_roundtrip():
    chunk = StreamChunk(
        request_id="abc",
        server_timestamp=SupervisorResponse(request_id="abc", status="ok").server_timestamp,
        payload=b"{\"stage\":\"progress\"}",
        final_chunk=False,
    )
    loaded = StreamChunk.from_json(chunk.to_json())
    assert loaded.request_id == chunk.request_id
    assert loaded.payload == chunk.payload
    assert loaded.final_chunk is False
