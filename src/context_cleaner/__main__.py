#!/usr/bin/env python3
"""
Context Cleaner CLI entry point.
"""

import sys
from .cli.main import main

if __name__ == "__main__":
    sys.exit(main())