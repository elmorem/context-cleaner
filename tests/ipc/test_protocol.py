import json
from context_cleaner.ipc.protocol import (
    SupervisorRequest,
    RequestAction,
    ClientInfo,
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
    assert data["timeout"] == 30_000
    assert data["client_info"]["pid"] == 1234

