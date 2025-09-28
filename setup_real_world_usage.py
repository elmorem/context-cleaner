#!/usr/bin/env python3
"""Deprecated real-world setup helper."""

from __future__ import annotations

import sys
import textwrap
import warnings

_DEPRECATION_MESSAGE = textwrap.dedent(
    """
    ⚙️  Real-world setup script deprecated

    The new CLI orchestrator replaces `setup_real_world_usage.py`. To prepare a
    workstation, install the package and rely on the built-in commands:

        pip install context-cleaner
        context-cleaner run --status-only
        context-cleaner run

    Configuration templates, directory monitoring, and dashboard management now
    live inside the CLI (`context-cleaner config-show`, `context-cleaner monitor`,
    etc.).
    """
)


def _warn() -> None:
    warnings.warn(
        "setup_real_world_usage.py is deprecated; use the modern `context-cleaner` CLI commands.",
        DeprecationWarning,
        stacklevel=2,
    )


def main() -> int:
    _warn()
    print(_DEPRECATION_MESSAGE)
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    sys.exit(main())
