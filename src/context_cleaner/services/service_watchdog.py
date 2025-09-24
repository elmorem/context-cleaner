"""Lightweight watchdog for monitoring the service supervisor."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from context_cleaner.services.process_registry import (
    ProcessRegistryDatabase,
    ProcessEntry,
    get_process_registry,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class ServiceWatchdogConfig:
    """Configuration options for the supervisor watchdog."""

    poll_interval_seconds: int = 5
    restart_backoff_seconds: int = 15
    max_restart_attempts: int = 3
    stale_grace_seconds: int = 5


class ServiceWatchdog:
    """Periodically checks supervisor heartbeat and triggers restarts when stale."""

    def __init__(
        self,
        *,
        registry: Optional[ProcessRegistryDatabase] = None,
        config: Optional[ServiceWatchdogConfig] = None,
        restart_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._registry = registry or get_process_registry()
        self._config = config or ServiceWatchdogConfig()
        self._restart_callback = restart_callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._restart_attempts = 0
        self._last_restart_at: Optional[datetime] = None
        self._disabled = False
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start the watchdog monitoring loop."""

        if self._disabled:
            LOGGER.debug("Watchdog disabled; start() ignored")
            return False
        if self._registry is None:
            LOGGER.debug("Process registry unavailable; watchdog not started")
            return False
        if self._thread and self._thread.is_alive():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="context-cleaner-watchdog",
            daemon=True,
        )
        self._thread.start()
        LOGGER.debug("Service watchdog started")
        return True

    def stop(self) -> None:
        """Stop the watchdog monitoring loop."""

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        LOGGER.debug("Service watchdog stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        interval = max(1, self._config.poll_interval_seconds)
        while not self._stop_event.wait(interval):
            try:
                healthy = self._check_supervisor_health()
                if healthy:
                    self._restart_attempts = 0
                else:
                    self._attempt_restart()
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.debug("Watchdog iteration encountered error: %s", exc)

    def _check_supervisor_health(self) -> bool:
        if not self._registry:
            return False

        try:
            entries = self._registry.get_processes_by_type("supervisor")
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("Failed to query supervisor entries: %s", exc)
            return False

        if not entries:
            LOGGER.warning("Watchdog detected missing supervisor registry entry")
            return False

        entry = self._select_entry(entries)
        if entry is None:
            LOGGER.warning("Watchdog could not select supervisor entry from registry")
            return False

        if not entry.is_process_alive():
            LOGGER.warning("Watchdog detected supervisor process PID %s not alive", entry.pid)
            return False

        heartbeat_info = self._extract_heartbeat(entry)
        if heartbeat_info is None:
            LOGGER.warning("Watchdog missing heartbeat metadata for supervisor PID %s", entry.pid)
            return False

        heartbeat_at, timeout_seconds = heartbeat_info
        now = datetime.now(timezone.utc)
        grace = max(0, self._config.stale_grace_seconds)
        if heartbeat_at is None:
            LOGGER.warning("Watchdog could not parse heartbeat timestamp for supervisor PID %s", entry.pid)
            return False

        delta = (now - heartbeat_at).total_seconds()
        if delta > timeout_seconds + grace:
            LOGGER.warning(
                "Watchdog detected stale supervisor heartbeat (age=%.1fs, timeout=%ss)",
                delta,
                timeout_seconds,
            )
            return False

        return True

    def _select_entry(self, entries: list[ProcessEntry]) -> Optional[ProcessEntry]:
        if not entries:
            return None
        try:
            return max(entries, key=lambda entry: entry.registration_time)
        except Exception:  # pragma: no cover - defensive
            return entries[0]

    def _extract_heartbeat(self, entry: ProcessEntry) -> Optional[tuple[Optional[datetime], int]]:
        environment_raw = entry.environment_vars or "{}"
        try:
            environment = json.loads(environment_raw)
        except json.JSONDecodeError:
            LOGGER.debug("Failed to decode supervisor environment vars: %s", environment_raw)
            environment = {}

        heartbeat_value = environment.get("HEARTBEAT_AT") or environment.get("UPDATED_AT")
        timeout = environment.get("HEARTBEAT_TIMEOUT")

        timeout_seconds = max(self._config.poll_interval_seconds * 3, 5)
        if isinstance(timeout, (int, float)):
            timeout_seconds = int(timeout)
        else:
            try:
                timeout_seconds = int(timeout)
            except (TypeError, ValueError):
                timeout_seconds = max(self._config.poll_interval_seconds, 1) * 3

        heartbeat_at = None
        if isinstance(heartbeat_value, str):
            heartbeat_at = self._parse_timestamp(heartbeat_value)

        return heartbeat_at, max(1, timeout_seconds)

    def _parse_timestamp(self, value: str) -> Optional[datetime]:
        try:
            if value.endswith("Z"):
                value = value[:-1]
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _attempt_restart(self) -> None:
        if not self._restart_callback or self._disabled:
            return

        now = datetime.now(timezone.utc)
        if self._last_restart_at is not None:
            elapsed = (now - self._last_restart_at).total_seconds()
            if elapsed < self._config.restart_backoff_seconds:
                LOGGER.debug(
                    "Watchdog restart backoff active (%.1fs remaining)",
                    self._config.restart_backoff_seconds - elapsed,
                )
                return

        if self._restart_attempts >= self._config.max_restart_attempts:
            LOGGER.error("Watchdog reached max restart attempts; disabling watchdog")
            self._disabled = True
            return

        with self._lock:
            self._restart_attempts += 1
            self._last_restart_at = now
            LOGGER.warning("Watchdog initiating supervisor restart (attempt %s)", self._restart_attempts)
            try:
                self._restart_callback()
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.error("Watchdog restart callback failed: %s", exc)
