"""Client helper for communicating with the supervisor."""

from __future__ import annotations

import getpass
import os
import platform
from typing import Optional, Sequence

from .protocol import (
    ClientInfo,
    SupervisorRequest,
    SupervisorResponse,
    StreamChunk,
    RequestAction,
    AuthToken,
)
from .transport.base import Transport, TransportError
from .transport.unix import UnixSocketTransport
from .transport.windows import WindowsPipeTransport


def default_supervisor_endpoint() -> str:
    if os.name == "nt":
        return r"\\\\.\\pipe\\context_cleaner_supervisor"
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(runtime_dir, "context-cleaner", "supervisor.sock")


# Backwards compatibility for previous internal helper name
_default_endpoint = default_supervisor_endpoint


class SupervisorClient:
    """Thin client wrapper for supervisor communication."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        transport: Optional[Transport] = None,
        auth_token: Optional[str] = None,
    ) -> None:
        self.endpoint = endpoint or default_supervisor_endpoint()
        self._transport = transport or self._build_transport()
        self._auth_token = auth_token or os.environ.get("CONTEXT_CLEANER_SUPERVISOR_TOKEN")

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
            client_info=self._default_client_info(),
        )
        self._apply_auth(request)
        self._transport.send_request(request)
        return self._transport.receive_response()

    def send(self, request: SupervisorRequest) -> SupervisorResponse:
        if request.client_info is None:
            request.client_info = self._default_client_info()
        self._apply_auth(request)
        self._transport.send_request(request)
        return self._transport.receive_response()

    def stream_shutdown(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ):
        """Yield stream chunks followed by the final response for a shutdown request."""

        request = SupervisorRequest(
            action=RequestAction.SHUTDOWN,
            streaming=True,
            client_info=self._default_client_info(),
        )
        if docker_only and processes_only:
            raise ValueError("docker_only and processes_only are mutually exclusive")
        if docker_only:
            request.options["docker_only"] = True
        if processes_only:
            request.options["processes_only"] = True
        if services:
            request.options["services"] = [service for service in services if service]
        if include_dependents is not None:
            request.options["include_dependents"] = bool(include_dependents)
        self._apply_auth(request)
        self._transport.send_request(request)

        for chunk in self._transport.receive_stream():
            yield ("chunk", chunk)
            if chunk.final_chunk:
                break

        response = self._transport.receive_response()
        yield ("response", response)

    def shutdown_with_stream(
        self,
        *,
        docker_only: bool = False,
        processes_only: bool = False,
        services: Optional[Sequence[str]] = None,
        include_dependents: bool = True,
    ) -> tuple[SupervisorResponse, list[StreamChunk]]:
        chunks: list[StreamChunk] = []
        response: SupervisorResponse | None = None

        for kind, event in self.stream_shutdown(
            docker_only=docker_only,
            processes_only=processes_only,
            services=services,
            include_dependents=include_dependents,
        ):
            if kind == "chunk":
                chunks.append(event)
            else:
                response = event

        if response is None:
            raise TransportError("Supervisor did not send a shutdown response")
        return response, chunks

    def __enter__(self) -> "SupervisorClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _default_client_info(self) -> ClientInfo:
        return ClientInfo(
            pid=os.getpid(),
            user=getpass.getuser(),
            version=platform.version(),
        )

    def _apply_auth(self, request: SupervisorRequest) -> None:
        if self._auth_token and request.auth is None:
            request.auth = AuthToken(token=self._auth_token)
