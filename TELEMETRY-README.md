# Claude Code Telemetry System

A production-ready OpenTelemetry infrastructure for collecting and analyzing Claude Code usage data.

## Quick Start

```bash
# 1. Install and start telemetry infrastructure
./install-telemetry.sh

# 2. Restart Claude Code with telemetry enabled
exit
source ./setup-telemetry.sh  
claude
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
- `setup-telemetry.sh` - Environment configuration
- `install-telemetry.sh` - Automated installer

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