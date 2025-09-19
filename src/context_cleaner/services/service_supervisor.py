"""Supervisor service skeleton for managing IPC requests."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Optional

from context_cleaner.services.service_orchestrator import ServiceOrchestrator
from context_cleaner.ipc.protocol import SupervisorRequest, SupervisorResponse, RequestAction, ErrorCode

LOGGER = logging.getLogger(__name__)


@dataclass
class SupervisorConfig:
    """Configuration for the supervisor."""

    endpoint: str
    max_connections: int = 8
    auth_token: Optional[str] = None


class ServiceSupervisor:
    """Skeleton implementation of the IPC supervisor."""

    def __init__(self, orchestrator: ServiceOrchestrator, config: SupervisorConfig) -> None:
        self._orchestrator = orchestrator
        self._config = config
        self._stack = AsyncExitStack()
        self._running = False
        self._connections = set()
        self._connections_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._running:
            LOGGER.debug("Supervisor already running")
            return
        LOGGER.info("Starting supervisor on endpoint %s", self._config.endpoint)
        self._running = True
        # Listener implementation will be filled in later.

    async def stop(self) -> None:
        if not self._running:
            return
        LOGGER.info("Stopping supervisor")
        self._running = False
        await self._stack.aclose()
        async with self._connections_lock:
            self._connections.clear()

    async def handle_request(self, request: SupervisorRequest) -> SupervisorResponse:
        if not self._running:
            return self._error_response(
                request,
                code=ErrorCode.INTERNAL,
                message="supervisor-not-running",
            )

        auth_error = self._authorize(request)
        if auth_error:
            return auth_error

        token = object()
        if not await self._register_connection(token):
            return self._error_response(
                request,
                code=ErrorCode.CONCURRENCY_LIMIT,
                message="max-connections-exceeded",
            )

        LOGGER.debug("Handling request %s", request.action)
        try:
            if request.action is RequestAction.PING:
                return SupervisorResponse(
                    request_id=request.request_id,
                    status="ok",
                    result={"message": "pong"},
                )
            if request.action is RequestAction.STATUS:
                status = self._orchestrator.get_service_status()
                return SupervisorResponse(request_id=request.request_id, status="ok", result=status)
            if request.action is RequestAction.SHUTDOWN:
                asyncio.create_task(self._orchestrator.stop_all_services())
                return SupervisorResponse(
                    request_id=request.request_id,
                    status="in-progress",
                    result={"message": "shutdown-started"},
                )
            return self._error_response(
                request,
                code=ErrorCode.INVALID_ARGUMENT,
                message=request.action.value,
            )
        finally:
            await self._release_connection(token)

    async def _register_connection(self, token: object) -> bool:
        async with self._connections_lock:
            if len(self._connections) >= max(1, self._config.max_connections):
                return False
            self._connections.add(token)
            return True

    async def _release_connection(self, token: object) -> None:
        async with self._connections_lock:
            self._connections.discard(token)

    def _authorize(self, request: SupervisorRequest) -> Optional[SupervisorResponse]:
        if not self._config.auth_token:
            return None
        if not request.auth or request.auth.token != self._config.auth_token:
            LOGGER.warning("Unauthorized request for action %s", request.action)
            return self._error_response(
                request,
                code=ErrorCode.UNAUTHORIZED,
                message="invalid-auth-token",
            )
        return None

    def _error_response(self, request: SupervisorRequest, *, code: ErrorCode, message: str) -> SupervisorResponse:
        return SupervisorResponse(
            request_id=request.request_id,
            status="error",
            error={
                "code": code.value,
                "message": message,
            },
        )
