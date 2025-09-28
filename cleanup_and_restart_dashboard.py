#!/usr/bin/env python3
"""Deprecated dashboard cleanup helper."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    🧹 Dashboard cleanup script deprecated

    Use the modern service commands instead:

        context-cleaner stop
        context-cleaner run --dashboard-port 8110

    The orchestrator now handles process discovery, port conflicts, and
    restarts. Manual cleanup via `cleanup_and_restart_dashboard.py` is no
    longer supported.
    """
)


def _warn() -> None:
    warnings.warn(
        "cleanup_and_restart_dashboard.py is deprecated; use the `context-cleaner stop`/`run` commands.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
