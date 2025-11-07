"""Utilities for applying Eventlet monkey patches only when needed."""

from __future__ import annotations

import logging
import os
import sys
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


def _should_patch_threads(default: bool | None) -> bool:
    """Determine whether Eventlet should patch the threading module."""

    env_value = os.getenv("CONTEXT_CLEANER_EVENTLET_PATCH_THREADS")
    if env_value is not None:
        normalized = env_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        logger.warning(
            "Unrecognised CONTEXT_CLEANER_EVENTLET_PATCH_THREADS=%s; using fallback",
            env_value,
        )

    if default is None:
        default = True

    return default


def ensure_eventlet_monkey_patch(*, patch_threads: bool | None = None) -> None:
    """Apply ``eventlet.monkey_patch`` exactly once when Eventlet mode is active."""

    if get_socketio_async_mode() != "eventlet":
        logger.debug("Skipping Eventlet monkey patch; async_mode!=eventlet")
        return

    patch_threads = _should_patch_threads(patch_threads)

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

            if sys.platform == "darwin":
                os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

            if "EVENTLET_HUB" not in os.environ and sys.platform == "darwin":
                try:
                    eventlet.hubs.use_hub("selects")
                    logger.debug("Configured Eventlet to use 'selects' hub on macOS")
                except Exception as exc:
                    logger.debug("Failed to switch Eventlet hub: %s", exc)

            eventlet.monkey_patch(thread=patch_threads)
            logger.debug("Eventlet monkey patch applied (threads=%s)", patch_threads)

            # Guard against third-party gevent imports on Python 3.13+ where
            # get_ident may become unset during shutdown (raising TypeError).
            try:
                import gevent.thread as gevent_thread  # type: ignore

                original_get_ident = getattr(gevent_thread, "get_ident", None)

                if callable(original_get_ident):

                    def _safe_gevent_get_ident(*args, **kwargs):
                        try:
                            return original_get_ident(*args, **kwargs)
                        except TypeError:
                            return threading.get_ident()

                    gevent_thread.get_ident = _safe_gevent_get_ident  # type: ignore[attr-defined]
                    logger.debug(
                        "Patched gevent.thread.get_ident for Eventlet compatibility"
                    )
                else:
                    gevent_thread.get_ident = threading.get_ident  # type: ignore[attr-defined]
                    logger.debug(
                        "Set gevent.thread.get_ident fallback to threading.get_ident"
                    )
            except ImportError:
                pass

            _patched = True
        except Exception:
            # If eventlet isn't installed (e.g. during lightweight CLI use),
            # fall through silently so the caller can continue without
            # websocket support.
            logger.debug("Eventlet not available; monkey patch skipped")
            pass
