"""Utilities for staging packaged telemetry resources."""

from __future__ import annotations

import importlib.resources as importlib_resources
from pathlib import Path
from typing import Iterable, Optional

TELEMETRY_PACKAGE = "context_cleaner.resources.telemetry"
TELEMETRY_RESOURCE_FILES: Iterable[str] = (
    "docker-compose.yml",
    "otel-simple.yaml",
    "otel-clickhouse-init.sql",
    "clickhouse-users.xml",
)

DEFAULT_DATA_DIR = Path.home() / ".context_cleaner" / "data"


def stage_telemetry_resources(config: Optional[object] = None, verbose: bool = False) -> Path:
    """Copy packaged telemetry assets to a writable directory and return the path."""

    data_directory = Path(
        getattr(config, "data_directory", DEFAULT_DATA_DIR)
    ).expanduser()
    base_directory = data_directory.parent if data_directory.name == "data" else data_directory
    destination = base_directory / "telemetry"
    destination.mkdir(parents=True, exist_ok=True)

    try:
        resource_root = importlib_resources.files(TELEMETRY_PACKAGE)
    except (ModuleNotFoundError, AttributeError) as exc:  # pragma: no cover - defensive
        if verbose:
            print(f"⚠️  Telemetry resources unavailable ({exc}); docker services may fail to start")
        return destination

    for filename in TELEMETRY_RESOURCE_FILES:
        source_path = resource_root / filename
        if not source_path.is_file():  # pragma: no cover - defensive
            if verbose:
                print(f"⚠️  Missing packaged telemetry file: {filename}")
            continue

        target_path = destination / filename
        try:
            source_bytes = source_path.read_bytes()
            if not target_path.exists() or target_path.read_bytes() != source_bytes:
                target_path.write_bytes(source_bytes)
        except Exception as exc:  # pragma: no cover - defensive
            if verbose:
                print(f"⚠️  Failed to stage telemetry resource '{filename}': {exc}")

    return destination


__all__ = ["stage_telemetry_resources", "TELEMETRY_RESOURCE_FILES", "TELEMETRY_PACKAGE"]
