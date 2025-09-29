#!/bin/bash

# Deprecated helper retained for backwards compatibility
echo "⚠️  setup-telemetry.sh is deprecated."
echo "   Source ~/.context_cleaner/telemetry/telemetry-env.sh instead."

ENV_FILE="$HOME/.context_cleaner/telemetry/telemetry-env.sh"

if [ -f "$ENV_FILE" ]; then
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  echo "✅ Loaded telemetry environment from $ENV_FILE"
else
  echo "❌ Expected telemetry env file at $ENV_FILE. Run 'context-cleaner telemetry init' first."
  exit 1
fi
