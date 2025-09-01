#!/bin/bash

set -e  # Exit on any error

echo "🚀 Claude Code Telemetry Setup Installer"
echo "========================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Verify we're in the right directory
if [[ ! -f "docker-compose.yml" ]] || [[ ! -f "otel-simple.yaml" ]]; then
    echo "❌ Required files not found. Please run this script from the context-cleaner directory."
    exit 1
fi

echo "✅ Required configuration files found"
echo ""

# Stop any existing containers
echo "🛑 Stopping any existing telemetry containers..."
docker compose down 2>/dev/null || true

# Start the infrastructure
echo "🚀 Starting OpenTelemetry infrastructure..."
docker compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if containers are running
if ! docker compose ps | grep -q "Up"; then
    echo "❌ Failed to start containers. Check docker compose logs:"
    docker compose logs
    exit 1
fi

echo "✅ Containers are running"

# Test ClickHouse connection
echo "🔍 Testing ClickHouse connection..."
if docker exec clickhouse-otel clickhouse-client --query "SELECT 1" &> /dev/null; then
    echo "✅ ClickHouse is accessible"
else
    echo "❌ ClickHouse connection failed"
    exit 1
fi

# Check OpenTelemetry Collector
echo "🔍 Testing OpenTelemetry Collector..."
sleep 5
if docker logs otel-collector 2>&1 | grep -q "Everything is ready"; then
    echo "✅ OpenTelemetry Collector is ready"
else
    echo "❌ OpenTelemetry Collector has issues. Check logs:"
    docker logs otel-collector --tail 10
    exit 1
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "📊 Infrastructure Status:"
echo "  • ClickHouse Database: Running on ports 8123/9000"
echo "  • OpenTelemetry Collector: Running on ports 4317/4318" 
echo "  • Data retention: 72 hours"
echo ""

# Set up environment variables
echo "🔧 Setting up environment variables..."
source ./setup-telemetry.sh

echo "🔄 Next Steps:"
echo "  1. Restart your Claude Code session to enable telemetry:"
echo "     exit   # Exit current Claude session"
echo "     source ./setup-telemetry.sh"
echo "     claude # Start new Claude session with telemetry"
echo ""
echo "  2. Verify telemetry data collection:"
echo "     docker logs -f otel-collector"
echo ""
echo "  3. Query collected data:"
echo "     docker exec clickhouse-otel clickhouse-client --query \"SELECT count() FROM otel.otel_traces\""
echo ""

echo "📚 Useful Commands:"
echo "  • View infrastructure status: docker compose ps"
echo "  • Stop infrastructure: docker compose down"
echo "  • View collector logs: docker logs otel-collector"
echo "  • Access ClickHouse: docker exec -it clickhouse-otel clickhouse-client"
echo ""

echo "✨ Happy telemetry collecting!"