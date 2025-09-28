#!/usr/bin/env python3
"""Deprecated entry point for the legacy Context Cleaner dashboard launcher."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    🚫 Legacy entry point removed

    `start_context_cleaner.py` has been retired. The unified service orchestrator
    now lives behind the CLI:

        context-cleaner run [OPTIONS]

    Use `context-cleaner stop` for shutdown and pass `--dashboard-port` or
    other flags directly to `context-cleaner run` when you need custom behaviour.
    """
)


def _warn() -> None:
    """Emit a deprecation warning when imported."""
    warnings.warn(
        "start_context_cleaner.py is deprecated; use `context-cleaner run` instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    """Print deprecation guidance and exit with non-zero status."""
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
