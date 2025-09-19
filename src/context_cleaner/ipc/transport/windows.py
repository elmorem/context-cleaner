"""Windows named pipe transport placeholder."""

from __future__ import annotations

from typing import Iterable

from .base import Transport, TransportError
from ..protocol import SupervisorRequest, SupervisorResponse, StreamChunk


class WindowsPipeTransport(Transport):
    """Transport using Windows named pipes.

    The concrete implementation will be provided in a follow-up iteration when
    Windows testing infrastructure is available. For now this class provides the
    API surface expected by the IPC client.
    """

    def connect(self) -> None:  # pragma: no cover - platform specific
        raise TransportError("Windows named pipe transport not implemented yet")

    def close(self) -> None:  # pragma: no cover - platform specific
        return None

    def send_request(self, message: SupervisorRequest) -> None:  # pragma: no cover - platform specific
        raise TransportError("Windows named pipe transport not implemented yet")

    def receive_response(self) -> SupervisorResponse:  # pragma: no cover - platform specific
        raise TransportError("Windows named pipe transport not implemented yet")

    def receive_stream(self) -> Iterable[StreamChunk]:  # pragma: no cover - platform specific
        raise TransportError("Windows named pipe transport not implemented yet")

