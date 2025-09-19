#!/bin/bash

# Stop all context-cleaner processes
echo "Stopping all context-cleaner processes..."

# Kill processes by name
pkill -f "context-cleaner" 2>/dev/null || true
pkill -f "context_cleaner" 2>/dev/null || true

# Kill processes on common ports
for port in 5555 6666 7777 8080 8110 8111 8112 8200 8300 8400 8500 8600 8700 8800 9000 9001 9500; do
  pid=$(lsof -ti :$port 2>/dev/null)
  if [ ! -z "$pid" ]; then
    echo "Killing process $pid on port $port"
    kill -9 "$pid" 2>/dev/null || true
  fi
done

echo "All context-cleaner processes stopped."