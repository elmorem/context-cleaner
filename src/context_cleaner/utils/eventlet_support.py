"""Utilities for applying Eventlet monkey patches only when needed."""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_patch_lock = threading.Lock()
_patched = False

_VALID_ASYNC_MODES = {
    "eventlet",
    "gevent",
    "gevent_uwsgi",
    "threading",
    "asyncio",
}


def get_socketio_async_mode() -> str:
    """Return the configured Socket.IO async mode.

    The mode can be controlled via the ``CONTEXT_CLEANER_SOCKETIO_ASYNC_MODE``
    environment variable. Values are case-insensitive and validated against the
    supported Flask-SocketIO async modes. Invalid values fall back to
    ``threading`` so the dashboard remains functional without additional
    dependencies.
    """

    mode = os.getenv("CONTEXT_CLEANER_SOCKETIO_ASYNC_MODE", "").strip().lower()
    if mode:
        if mode in _VALID_ASYNC_MODES:
            return mode
        logger.warning(
            "Unsupported CONTEXT_CLEANER_SOCKETIO_ASYNC_MODE=%s; falling back to 'threading'",
            mode,
        )

    # Default: prefer eventlet when available so we can run under Gunicorn
    try:
        import eventlet  # type: ignore # noqa: F401

        return "eventlet"
    except Exception:
        # Fall back to the safe built-in threading mode. Teams that prefer a
        # different async driver can opt-in via the environment variable above.
        return "threading"


def ensure_eventlet_monkey_patch(*, patch_threads: bool = True) -> None:
    """Apply ``eventlet.monkey_patch`` exactly once when Eventlet mode is active."""

    if get_socketio_async_mode() != "eventlet":
        logger.debug("Skipping Eventlet monkey patch; async_mode!=eventlet")
        return

    global _patched
    if _patched:
        logger.debug(
            "Eventlet monkey patch already applied; skipping (threads=%s)",
            patch_threads,
        )
        return

    with _patch_lock:
        if _patched:
            logger.debug(
                "Eventlet monkey patch already applied inside lock; skipping (threads=%s)",
                patch_threads,
            )
            return
        try:
            import eventlet  # type: ignore

            eventlet.monkey_patch(thread=patch_threads)
            logger.debug("Eventlet monkey patch applied (threads=%s)", patch_threads)
            _patched = True
        except Exception:
            # If eventlet isn't installed (e.g. during lightweight CLI use),
            # fall through silently so the caller can continue without
            # websocket support.
            logger.debug("Eventlet not available; monkey patch skipped")
            pass
