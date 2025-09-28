#!/usr/bin/env python3
"""Deprecated real-world directory monitoring helper."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    📂 Real directory monitor deprecated

    Use the orchestrated monitor subcommands to watch project directories:

        context-cleaner monitor start --watch-dirs /path/to/project
        context-cleaner monitor status --format json

    `monitor_real_directories.py` has reached end-of-life and no longer runs the
    dashboard or analytics stack directly.
    """
)


def _warn() -> None:
    warnings.warn(
        "monitor_real_directories.py is deprecated; use the `context-cleaner monitor` commands.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
