import base64
import datetime as dt
import json

import pytest

from context_cleaner.ipc.protocol import (
    AuthToken,
    ClientInfo,
    ErrorCode,
    ProtocolVersion,
    RequestAction,
    StreamChunk,
    SupervisorRequest,
    SupervisorResponse,
)


def test_supervisor_request_round_trip() -> None:
    now = dt.datetime(2025, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    request = SupervisorRequest(
        action=RequestAction.SHUTDOWN,
        protocol_version=ProtocolVersion.V1_0,
        request_id="req-123",
        timestamp=now,
        options={"force": True},
        filters={"docker_only": False},
        streaming=True,
        timeout_ms=5000,
        client_info=ClientInfo(pid=42, user="tester", version="1.2.3", capabilities=["streaming"]),
        auth=AuthToken(token="secret", scheme="bearer"),
    )

    encoded = request.to_json()
    decoded = SupervisorRequest.from_json(encoded)

    assert decoded.action is RequestAction.SHUTDOWN
    assert decoded.protocol_version is ProtocolVersion.V1_0
    assert decoded.request_id == "req-123"
    assert decoded.timestamp == now
    assert decoded.options == {"force": True}
    assert decoded.filters == {"docker_only": False}
    assert decoded.streaming is True
    assert decoded.timeout_ms == 5000
    assert decoded.client_info is not None
    assert decoded.client_info.pid == 42
    assert decoded.client_info.capabilities == ["streaming"]
    assert decoded.auth is not None
    assert decoded.auth.token == "secret"


def test_supervisor_request_missing_auth_token_raises() -> None:
    payload = json.dumps(
        {
            "action": "ping",
            "auth": {"scheme": "bearer"},
        }
    )
    with pytest.raises(ValueError):
        SupervisorRequest.from_json(payload)


def test_stream_chunk_round_trip() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    chunk = StreamChunk(
        request_id="req-1",
        server_timestamp=now,
        payload=b"hello",
        final_chunk=True,
    )

    encoded = chunk.to_json()
    decoded = StreamChunk.from_json(encoded)

    assert decoded.request_id == "req-1"
    assert decoded.server_timestamp == now
    assert decoded.payload == b"hello"
    assert decoded.final_chunk is True


def test_supervisor_response_round_trip() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    response = SupervisorResponse(
        request_id="req-2",
        status="ok",
        protocol_version=ProtocolVersion.V1_0,
        server_timestamp=now,
        progress=0.5,
        result={"message": "pong"},
        error=None,
    )

    encoded = response.to_json()
    decoded = SupervisorResponse.from_json(encoded)

    assert decoded.request_id == "req-2"
    assert decoded.status == "ok"
    assert decoded.protocol_version is ProtocolVersion.V1_0
    assert decoded.server_timestamp == now
    assert decoded.progress == 0.5
    assert decoded.result == {"message": "pong"}


def test_stream_chunk_encodes_payload_as_base64() -> None:
    chunk = StreamChunk(
        request_id="abc",
        server_timestamp=dt.datetime.now(dt.timezone.utc),
        payload=b"binary-data",
        final_chunk=False,
    )

    data = json.loads(chunk.to_json())
    encoded_payload = data["payload"]
    assert base64.b64decode(encoded_payload.encode("ascii")) == b"binary-data"
