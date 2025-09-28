#!/usr/bin/env python3
"""Deprecated multi-directory monitoring helper."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    📁 Directory monitoring script deprecated

    Continuous monitoring is now available through the CLI:

        context-cleaner monitor start [--watch-dirs PATH ...]
        context-cleaner monitor status

    The standalone `monitor_directories.py` helper is no longer maintained.
    """
)


def _warn() -> None:
    warnings.warn(
        "monitor_directories.py is deprecated; use the `context-cleaner monitor` commands.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
