"""Transport abstractions for IPC communication."""

from __future__ import annotations

import abc
from typing import Iterable

from ..protocol import SupervisorRequest, SupervisorResponse, StreamChunk


class TransportError(RuntimeError):
    """Raised when a transport operation fails."""


class Transport(abc.ABC):
    """Abstract base class for IPC transports."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish a connection to the supervisor endpoint."""

    @abc.abstractmethod
    def close(self) -> None:
        """Close the transport connection."""

    @abc.abstractmethod
    def send_request(self, message: SupervisorRequest) -> None:
        """Send a request message."""

    @abc.abstractmethod
    def receive_response(self) -> SupervisorResponse:
        """Receive a response message."""

    def receive_stream(self) -> Iterable[StreamChunk]:
        """Iterate over streaming chunks. Optional override."""

        raise NotImplementedError

