import os
import socket
import threading
import pytest

from context_cleaner.ipc.transport.unix import UnixSocketTransport
from context_cleaner.ipc.protocol import SupervisorResponse
from context_cleaner.ipc.protocol import SupervisorRequest, RequestAction


@pytest.mark.skipif(os.name == "nt", reason="Unix socket transport not available on Windows")
def test_unix_transport_requires_connection(tmp_path):
    socket_path = tmp_path / "sock"
    transport = UnixSocketTransport(str(socket_path))
    with pytest.raises(Exception):
        transport.send_request(SupervisorRequest(action=RequestAction.PING))


@pytest.mark.skipif(os.name == "nt", reason="Unix socket transport not available on Windows")
def test_unix_transport_round_trip(tmp_path):
    short_path = "/tmp/context-cleaner-test.sock"

    ready = threading.Event()

    def server():
        try:
            os.unlink(short_path)
        except FileNotFoundError:
            pass
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as srv:
            srv.bind(short_path)
            srv.listen(1)
            ready.set()
            conn, _ = srv.accept()
            with conn:
                header = conn.recv(4)
                size = int.from_bytes(header, "big")
                payload = conn.recv(size)
                assert payload
                response = SupervisorResponse(
                    request_id="test", status="ok", result={"message": "pong"}
                ).to_json().encode("utf-8")
                frame = len(response).to_bytes(4, "big") + response
                conn.sendall(frame)

    thread = threading.Thread(target=server, daemon=True)
    thread.start()

    transport = UnixSocketTransport(short_path)
    ready.wait(timeout=1)
    transport.connect()
    transport.send_request(SupervisorRequest(action=RequestAction.PING))
    response = transport.receive_response()
    assert response.status == "ok"
    assert response.result["message"] == "pong"
    transport.close()
    thread.join(timeout=1)
    try:
        os.unlink(short_path)
    except FileNotFoundError:
        pass
