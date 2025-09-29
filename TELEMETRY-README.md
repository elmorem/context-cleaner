# Claude Code Telemetry System

A production-ready OpenTelemetry infrastructure for collecting and analyzing Claude Code usage data.

## Quick Start

```bash
# 1. Install Context Cleaner and initialise telemetry
pip install context-cleaner
context-cleaner telemetry init

# 2. Apply environment variables for Claude Code (bash/zsh)
source ~/.context_cleaner/telemetry/telemetry-env.sh

# 3. Restart Claude Code (or your shell) and launch the dashboard
claude
context-cleaner run
```

## What It Does

**Note**: This is a LOCAL telemetry system that collects Claude Code usage data on YOUR machine. No data is sent externally. This system replaces manual cache file parsing with real-time structured telemetry:

- **Before**: Parse 64k+ token JSONL files manually
- **After**: Query structured data from ClickHouse database

## Infrastructure

- **ClickHouse Database**: Stores traces, metrics, and logs (72h retention)
- **OpenTelemetry Collector**: Receives and processes telemetry data
- **Docker**: Containerized setup for easy deployment

## Architecture

```
Claude Code → OpenTelemetry Collector → ClickHouse → Dashboard
    ↓           (gRPC port 4317)        ↓         ↓
Telemetry       Batch Processing      SQL     Enhanced
Operations      + Compression        Queries   Analytics
```

## Data Collection

Once running, you'll collect:

- **Traces**: Individual operations with duration and token usage
- **Metrics**: Performance counters and operation frequencies  
- **Logs**: Structured events with context and metadata

## Verification

```bash
# Check if data is flowing
docker exec clickhouse-otel clickhouse-client --query "SELECT count() FROM otel.otel_traces"

# Sample trace data  
docker exec clickhouse-otel clickhouse-client --query "SELECT ServiceName, SpanName, Duration FROM otel.otel_traces LIMIT 5"
```

## Management

```bash
# View status
cd ~/.context_cleaner/telemetry
docker compose ps

# Monitor logs
docker logs -f otel-collector

# Stop infrastructure
docker compose down
```

## Files Created

- `docker-compose.yml` - Infrastructure configuration
- `otel-simple.yaml` - OpenTelemetry Collector config
- `clickhouse-users.xml` - ClickHouse authentication
- `otel-clickhouse-init.sql` - Database schema
- `telemetry-env.sh` - Environment configuration helper

## Integration

The system is designed to work with the existing dashboard in:
`src/context_cleaner/dashboard/comprehensive_health_dashboard.py`

Replace the `_analyze_token_usage()` method to query ClickHouse instead of parsing cache files.

## Benefits

- ✅ Real-time data collection
- ✅ Industry-standard OpenTelemetry format
- ✅ Efficient SQL queries vs file parsing
- ✅ Unlimited historical data (with retention policies)
- ✅ Built-in data compression and optimization
- ✅ Easy installation and automation
