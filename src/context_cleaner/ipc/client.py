"""Client helper for communicating with the supervisor."""

from __future__ import annotations

import getpass
import os
import platform
from typing import Optional

from .protocol import ClientInfo, SupervisorRequest, SupervisorResponse, RequestAction
from .transport.base import Transport, TransportError
from .transport.unix import UnixSocketTransport
from .transport.windows import WindowsPipeTransport


def _default_endpoint() -> str:
    if os.name == "nt":
        return r"\\\\.\\pipe\\context_cleaner_supervisor"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(runtime_dir, "context-cleaner", "supervisor.sock")


class SupervisorClient:
    """Thin client wrapper for supervisor communication."""

    def __init__(self, endpoint: Optional[str] = None, transport: Optional[Transport] = None) -> None:
        self.endpoint = endpoint or _default_endpoint()
        self._transport = transport or self._build_transport()

    def _build_transport(self) -> Transport:
        if os.name == "nt":
            return WindowsPipeTransport(self.endpoint)
        return UnixSocketTransport(self.endpoint)

    def connect(self) -> None:
        self._transport.connect()

    def close(self) -> None:
        self._transport.close()

    def ping(self) -> SupervisorResponse:
        request = SupervisorRequest(
            action=RequestAction.PING,
            client_info=ClientInfo(
                pid=os.getpid(),
                user=getpass.getuser(),
                version=platform.version(),
            ),
        )
        self._transport.send_request(request)
        return self._transport.receive_response()

    def send(self, request: SupervisorRequest) -> SupervisorResponse:
        self._transport.send_request(request)
        return self._transport.receive_response()

    def __enter__(self) -> "SupervisorClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

