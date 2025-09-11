"""
Entry point for the Context Cleaner CLI when run as a module.

This allows running the CLI with:
    python -m src.context_cleaner.cli

Without the RuntimeWarning that occurs when using:
    python -m src.context_cleaner.cli.main
"""

from .main import main

if __name__ == "__main__":
    main()