import os

import pytest

from context_cleaner.ipc.client import SupervisorClient, default_supervisor_endpoint


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only behaviour")
def test_default_supervisor_endpoint_posix(monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/tmp/test-runtime")
    endpoint = default_supervisor_endpoint()
    assert endpoint.startswith("/tmp/test-runtime/context-cleaner/")
    assert endpoint.endswith("supervisor.sock")


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only behaviour")
def test_supervisor_client_uses_unix_transport():
    client = SupervisorClient(endpoint="/tmp/context-cleaner/supervisor.sock")
    transport = client._build_transport()
    assert transport.__class__.__name__ == "UnixSocketTransport"
