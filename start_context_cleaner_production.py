#!/usr/bin/env python3
"""Deprecated production launcher for Context Cleaner services."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    🚫 Legacy entry point removed

    `start_context_cleaner_production.py` has been retired. To start Context
    Cleaner with the current orchestration stack, use:

        context-cleaner run [OPTIONS]

    Need production-style settings? Combine the new flags instead:
      • `--no-browser` to suppress auto-open
      • `--dashboard-port 8110` (or any port you require)
      • `--dev-mode` for verbose diagnostics during staging

    The CLI now manages Gunicorn, Docker services, JSONL processors, and the
    dashboard for you.
    """
)


def _warn() -> None:
    warnings.warn(
        "start_context_cleaner_production.py is deprecated; use `context-cleaner run` instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
