# Claude Code Telemetry Setup

This document outlines the OpenTelemetry infrastructure we've set up for collecting structured telemetry data from Claude Code sessions.

## Infrastructure Components

### 1. ClickHouse Database
- **Container**: `clickhouse-otel`
- **Ports**: 8123 (HTTP), 9000 (Native)
- **Database**: `otel` with pre-configured tables for traces, metrics, and logs
- **Status**: ✅ Running and healthy

### 2. OpenTelemetry Collector
- **Container**: `otel-collector` 
- **Ports**: 4317 (gRPC), 4318 (HTTP)
- **Configuration**: Simple debug exporter for initial testing
- **Status**: ✅ Running and ready to receive data

### 3. Environment Configuration
- **Script**: `setup-telemetry.sh`
- **Variables Set**:
  - `CLAUDE_CODE_ENABLE_TELEMETRY=1`
  - `OTEL_METRICS_EXPORTER=otlp`
  - `OTEL_LOGS_EXPORTER=otlp`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317`
  - `OTEL_METRIC_EXPORT_INTERVAL=10000` (10 seconds)
  - `OTEL_LOGS_EXPORT_INTERVAL=5000` (5 seconds)

## Current Status

### ✅ Completed
1. **ClickHouse Database**: Running with proper OpenTelemetry schema
2. **OpenTelemetry Collector**: Configured and running with debug exporter
3. **Environment Variables**: Script created and configured
4. **Docker Infrastructure**: All services running via Docker Compose

### 🔄 Next Steps

1. **Restart Claude Code Session**: For telemetry to work, Claude Code needs to be restarted with the environment variables loaded:
   ```bash
   # Close current Claude Code session
   # In a new terminal:
   source /Users/markelmore/_code/context-cleaner/setup-telemetry.sh
   claude
   ```

2. **Verify Telemetry Data Flow**: Once restarted, perform Claude Code operations and monitor:
   ```bash
   # Monitor collector logs for incoming data
   docker logs -f otel-collector
   ```

3. **Enhance Collector Configuration**: Add file exporter and ClickHouse integration:
   ```yaml
   exporters:
     file:
       path: /tmp/claude-telemetry.jsonl
     clickhouse:
       endpoint: tcp://clickhouse:9000
       database: otel
   ```

4. **Dashboard Integration**: Update our existing dashboard to query telemetry data instead of parsing cache files

## Benefits of Telemetry vs Cache Parsing

### Current Approach (Cache Parsing)
- ❌ Requires parsing complex JSONL files
- ❌ Limited to post-session analysis
- ❌ Manual categorization of token types
- ❌ Performance overhead from file I/O

### Telemetry Approach
- ✅ Structured, real-time data streams
- ✅ Standardized OpenTelemetry format
- ✅ Rich semantic attributes
- ✅ Efficient querying via SQL (ClickHouse)
- ✅ Built-in categorization and metadata
- ✅ Industry-standard observability stack

## Commands Reference

### Start Infrastructure
```bash
cd /Users/markelmore/_code/context-cleaner
docker compose up -d
```

### Enable Telemetry
```bash
source setup-telemetry.sh
```

### Monitor Data
```bash
# Collector logs
docker logs -f otel-collector

# ClickHouse data
docker exec -it clickhouse-otel clickhouse-client --query "SELECT * FROM otel.traces LIMIT 5"
```

### Stop Infrastructure
```bash
docker compose down
```

## File Structure
```
context-cleaner/
├── docker-compose.yml              # Infrastructure setup
├── otel-simple.yaml               # Minimal collector config
├── otel-clickhouse-init.sql       # Database schema
├── setup-telemetry.sh             # Environment setup
└── TELEMETRY-SETUP.md             # This documentation
```

## Architecture Diagram

```
Claude Code → OpenTelemetry → Collector → ClickHouse
    ↓             (gRPC)         ↓           ↓
Telemetry     Port 4317      Debug        SQL
Data                         Logger      Database
```

The infrastructure is ready and waiting for telemetry data. The next step is restarting Claude Code with telemetry enabled to begin collecting structured data for our dashboard analytics.