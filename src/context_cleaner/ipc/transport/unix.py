"""Unix domain socket transport implementation."""

from __future__ import annotations

import socket
from typing import Iterable

from .base import Transport, TransportError
from ..protocol import SupervisorRequest, SupervisorResponse, StreamChunk

BUFFER_SIZE = 65536


class UnixSocketTransport(Transport):
    """Transport using Unix domain sockets with length-prefixed frames."""

    def __init__(self, endpoint: str) -> None:
        super().__init__(endpoint)
        self._socket: socket.socket | None = None

    def connect(self) -> None:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.endpoint)
            self._socket = sock
        except OSError as exc:  # pragma: no cover - environment specific
            raise TransportError(f"Failed to connect to supervisor: {exc}") from exc

    def close(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _ensure_socket(self) -> socket.socket:
        if not self._socket:
            raise TransportError("Transport not connected")
        return self._socket

    def send_request(self, message: SupervisorRequest) -> None:
        data = message.to_json().encode("utf-8")
        frame = len(data).to_bytes(4, "big") + data
        sock = self._ensure_socket()
        try:
            sock.sendall(frame)
        except OSError as exc:  # pragma: no cover - environment specific
            raise TransportError(f"Failed to send request: {exc}") from exc

    def receive_response(self) -> SupervisorResponse:
        sock = self._ensure_socket()
        try:
            header = sock.recv(4)
            if len(header) < 4:
                raise TransportError("Incomplete response header")
            size = int.from_bytes(header, "big")
            payload = bytearray()
            while len(payload) < size:
                chunk = sock.recv(min(BUFFER_SIZE, size - len(payload)))
                if not chunk:
                    raise TransportError("Supervisor connection closed unexpectedly")
                payload.extend(chunk)
        except OSError as exc:  # pragma: no cover - environment specific
            raise TransportError(f"Failed to receive response: {exc}") from exc

        return SupervisorResponse.from_json(payload.decode("utf-8"))

    def receive_stream(self) -> Iterable[StreamChunk]:
        sock = self._ensure_socket()
        while True:
            try:
                header = sock.recv(4)
                if len(header) < 4:
                    raise TransportError("Incomplete stream header")
                size = int.from_bytes(header, "big")
                payload = bytearray()
                while len(payload) < size:
                    chunk = sock.recv(min(BUFFER_SIZE, size - len(payload)))
                    if not chunk:
                        raise TransportError(
                            "Supervisor connection closed during stream"
                        )
                    payload.extend(chunk)
            except OSError as exc:  # pragma: no cover - environment specific
                raise TransportError(f"Failed to receive stream chunk: {exc}") from exc

            data = payload.decode("utf-8")
            if '"message_type":"response"' in data:
                # Unexpected response frame encountered; push back by raising
                raise TransportError("Unexpected response frame in stream")

            chunk = StreamChunk.from_json(data)
            yield chunk
            if chunk.final_chunk:
                break
