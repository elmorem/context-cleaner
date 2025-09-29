#!/bin/bash

set -e

echo "⚠️  install-telemetry.sh is deprecated."
echo "   Use 'context-cleaner telemetry init' instead."

if command -v context-cleaner >/dev/null 2>&1; then
  context-cleaner telemetry init "$@"
else
  echo "❌ The context-cleaner CLI is not available on PATH. Install via 'pip install context-cleaner'."
  exit 1
fi
