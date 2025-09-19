"""Debug transport for in-process testing."""

from __future__ import annotations

from collections import deque
from typing import Deque, Iterable

from .base import Transport, TransportError
from ..protocol import SupervisorRequest, SupervisorResponse, StreamChunk


class DebugTransport(Transport):
    """In-memory transport useful for unit tests."""

    def __init__(self, endpoint: str = "debug://") -> None:
        super().__init__(endpoint)
        self.sent_requests: Deque[SupervisorRequest] = deque()
        self._responses: Deque[SupervisorResponse] = deque()
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False
        self.sent_requests.clear()
        self._responses.clear()

    def queue_response(self, response: SupervisorResponse) -> None:
        self._responses.append(response)

    def send_request(self, message: SupervisorRequest) -> None:
        if not self._connected:
            raise TransportError("Transport not connected")
        self.sent_requests.append(message)

    def receive_response(self) -> SupervisorResponse:
        if not self._connected:
            raise TransportError("Transport not connected")
        if not self._responses:
            raise TransportError("No responses queued")
        return self._responses.popleft()

    def receive_stream(self) -> Iterable[StreamChunk]:
        raise TransportError("Streaming not supported in debug transport")

