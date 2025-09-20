"""Debug transport for in-process testing."""

from __future__ import annotations

from collections import deque
from typing import Deque, Iterable, Optional

from .base import Transport, TransportError
from ..protocol import SupervisorRequest, SupervisorResponse, StreamChunk


class DebugTransport(Transport):
    """In-memory transport useful for unit tests."""

    def __init__(self, endpoint: str = "debug://") -> None:
        super().__init__(endpoint)
        self.sent_requests: Deque[SupervisorRequest] = deque()
        self._responses: Deque[SupervisorResponse] = deque()
        self._stream_chunks: Deque[StreamChunk] = deque()
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def close(self) -> None:
        self._connected = False
        self.sent_requests.clear()
        self._responses.clear()
        self._stream_chunks.clear()

    def queue_response(self, response: SupervisorResponse) -> None:
        self._responses.append(response)

    def queue_stream_chunk(self, chunk: StreamChunk) -> None:
        self._stream_chunks.append(chunk)

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
        if not self._connected:
            raise TransportError("Transport not connected")
        while self._stream_chunks:
            yield self._stream_chunks.popleft()
