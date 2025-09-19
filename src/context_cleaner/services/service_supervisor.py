"""Supervisor service skeleton for managing IPC requests."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Optional

from context_cleaner.services.service_orchestrator import ServiceOrchestrator
from context_cleaner.ipc.protocol import SupervisorRequest, SupervisorResponse, RequestAction

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
        self._connections.clear()

    async def handle_request(self, request: SupervisorRequest) -> SupervisorResponse:
        LOGGER.debug("Handling request %s", request.action)
        if request.action is RequestAction.PING:
            return SupervisorResponse(request_id=request.request_id, status="ok", result={"message": "pong"})
        if request.action is RequestAction.STATUS:
            status = self._orchestrator.get_service_status()
            return SupervisorResponse(request_id=request.request_id, status="ok", result=status)
        if request.action is RequestAction.SHUTDOWN:
            asyncio.create_task(self._orchestrator.stop_all_services())
            return SupervisorResponse(request_id=request.request_id, status="in-progress", result={"message": "shutdown-started"})
        return SupervisorResponse(
            request_id=request.request_id,
            status="error",
            error={"code": "unsupported-action", "message": request.action.value},
        )

