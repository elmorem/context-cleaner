"""Lightweight watchdog for monitoring the service supervisor."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional, List

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
        self._last_heartbeat_at: Optional[datetime] = None
        self._last_restart_reason: Optional[str] = None
        self._last_restart_success: Optional[bool] = None
        self._restart_history: List[dict[str, object]] = []

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
    # Monitoring inspection helpers
    # ------------------------------------------------------------------

    @property
    def last_heartbeat_at(self) -> Optional[datetime]:
        """Most recent supervisor heartbeat timestamp observed by the watchdog."""

        return self._last_heartbeat_at

    @property
    def last_restart_reason(self) -> Optional[str]:
        """Reason supplied for the most recent restart attempt."""

        return self._last_restart_reason

    @property
    def last_restart_success(self) -> Optional[bool]:
        """Whether the most recent restart attempt reported success."""

        return self._last_restart_success

    @property
    def restart_history(self) -> list[dict[str, object]]:
        """Structured history of restart attempts (most recent last)."""

        return list(self._restart_history)

    @property
    def restart_attempts(self) -> int:
        """Current restart attempt counter."""

        return self._restart_attempts

    @property
    def last_restart_at(self) -> Optional[datetime]:
        """Timestamp of the last restart attempt."""

        return self._last_restart_at

    @property
    def disabled(self) -> bool:
        """Whether the watchdog has disabled itself after exceeding limits."""

        return self._disabled

    @property
    def is_running(self) -> bool:
        """Whether the watchdog monitoring thread is active."""

        return self._thread is not None and self._thread.is_alive()

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
                    self._attempt_restart("stale-heartbeat")
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
            LOGGER.warning(
                "Watchdog detected supervisor process PID %s not alive", entry.pid
            )
            return False

        heartbeat_info = self._extract_heartbeat(entry)
        if heartbeat_info is None:
            LOGGER.warning(
                "Watchdog missing heartbeat metadata for supervisor PID %s", entry.pid
            )
            return False

        heartbeat_at, timeout_seconds = heartbeat_info
        now = datetime.now(timezone.utc)
        grace = max(0, self._config.stale_grace_seconds)
        self._last_heartbeat_at = heartbeat_at

        if heartbeat_at is None:
            LOGGER.warning(
                "Watchdog could not parse heartbeat timestamp for supervisor PID %s",
                entry.pid,
            )
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

    def _extract_heartbeat(
        self, entry: ProcessEntry
    ) -> Optional[tuple[Optional[datetime], int]]:
        environment_raw = entry.environment_vars or "{}"
        try:
            environment = json.loads(environment_raw)
        except json.JSONDecodeError:
            LOGGER.debug(
                "Failed to decode supervisor environment vars: %s", environment_raw
            )
            environment = {}

        heartbeat_value = environment.get("HEARTBEAT_AT") or environment.get(
            "UPDATED_AT"
        )
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

    def _attempt_restart(self, reason: str) -> None:
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
            self._last_restart_reason = reason
            LOGGER.warning(
                "Watchdog initiating supervisor restart (attempt %s, reason=%s)",
                self._restart_attempts,
                reason,
            )
            restart_record = {
                "attempt": self._restart_attempts,
                "reason": reason,
                "timestamp": now.isoformat(),
            }
            try:
                self._restart_callback()
                self._last_restart_success = True
                restart_record["success"] = True
            except Exception as exc:  # pragma: no cover - defensive
                self._last_restart_success = False
                restart_record["success"] = False
                restart_record["error"] = str(exc)
                LOGGER.error("Watchdog restart callback failed: %s", exc)
            finally:
                self._restart_history.append(restart_record)
