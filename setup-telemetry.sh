#!/bin/bash

# Claude Code Telemetry Configuration Script
echo "Setting up Claude Code telemetry..."

# Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# Configure OTLP exporters  
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp

# Set OTLP protocol and endpoint
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317

# Set service name and resource attributes
export OTEL_SERVICE_NAME=claude-code
export OTEL_RESOURCE_ATTRIBUTES="service.name=claude-code,service.version=1.0.98"

# Configure metrics temporality preference
export OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta

# Faster export intervals for development
export OTEL_METRIC_EXPORT_INTERVAL=10000  # 10 seconds
export OTEL_LOGS_EXPORT_INTERVAL=5000     # 5 seconds
export OTEL_BSP_SCHEDULE_DELAY=5000       # 5 seconds for traces

echo "Claude Code telemetry environment variables set:"
echo "  CLAUDE_CODE_ENABLE_TELEMETRY=$CLAUDE_CODE_ENABLE_TELEMETRY"
echo "  OTEL_METRICS_EXPORTER=$OTEL_METRICS_EXPORTER"
echo "  OTEL_LOGS_EXPORTER=$OTEL_LOGS_EXPORTER"
echo "  OTEL_TRACES_EXPORTER=$OTEL_TRACES_EXPORTER"
echo "  OTEL_EXPORTER_OTLP_PROTOCOL=$OTEL_EXPORTER_OTLP_PROTOCOL"
echo "  OTEL_EXPORTER_OTLP_ENDPOINT=$OTEL_EXPORTER_OTLP_ENDPOINT"
echo "  OTEL_SERVICE_NAME=$OTEL_SERVICE_NAME"
echo "  OTEL_RESOURCE_ATTRIBUTES=$OTEL_RESOURCE_ATTRIBUTES"
echo "  OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=$OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"
echo "  OTEL_METRIC_EXPORT_INTERVAL=$OTEL_METRIC_EXPORT_INTERVAL"
echo "  OTEL_LOGS_EXPORT_INTERVAL=$OTEL_LOGS_EXPORT_INTERVAL"
echo "  OTEL_BSP_SCHEDULE_DELAY=$OTEL_BSP_SCHEDULE_DELAY"
echo ""
echo "Telemetry is now enabled. Use Claude Code normally and check the OpenTelemetry Collector logs for telemetry data."
echo ""
echo "To make these settings permanent, add this script to your shell profile:"
echo "  echo 'source $(pwd)/setup-telemetry.sh' >> ~/.zshrc"