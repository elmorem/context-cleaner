"""Utilities for safely applying Eventlet monkey patches exactly once."""

from __future__ import annotations

import threading

_patch_lock = threading.Lock()
_patched = False


def ensure_eventlet_monkey_patch(*, patch_threads: bool = False) -> None:
    """Apply ``eventlet.monkey_patch`` exactly once.

    Args:
        patch_threads: Whether Eventlet should patch the ``threading`` module.
            Defaults to ``False`` to keep native threads available for asyncio
            helpers.
    """
    global _patched
    if _patched:
        return

    with _patch_lock:
        if _patched:
            return
        try:
            import eventlet  # type: ignore

            eventlet.monkey_patch(thread=patch_threads)
            _patched = True
        except Exception:
            # If eventlet isn't installed (e.g. during lightweight CLI use),
            # fall through silently so the caller can continue without
            # websocket support.
            pass
