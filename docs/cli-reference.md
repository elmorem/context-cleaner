# Context Cleaner CLI Reference

Complete reference for all Context Cleaner command-line interface commands and options.

## 📚 **Table of Contents**

1. [Global Options](#global-options)
2. [Core Commands](#core-commands)
3. [Analytics Commands](#analytics-commands-new-v020)
4. [Session Management](#session-management)
5. [Monitoring Commands](#monitoring-commands)
6. [Data Management](#data-management)
7. [Privacy Commands](#privacy-commands)
8. [Examples & Use Cases](#examples--use-cases)

## 🔧 **Global Options**

Available for all commands:

```bash
context-cleaner [GLOBAL_OPTIONS] COMMAND [ARGS]...

Global Options:
  --config, -c PATH       Configuration file path
  --data-dir PATH         Data directory path (overrides config)
  --verbose, -v           Enable verbose output
  --help                  Show help message and exit
  --version               Show version and exit
```

### **Streaming Supervisor Shutdown** ⭐ NEW

`context-cleaner stop` now attempts to contact the long-running supervisor.
When reachable, the CLI streams structured shutdown updates in real time—the
output shows how many services remain, which ones are transitioning, and any
required-service errors. If the supervisor cannot be reached, the CLI
automatically falls back to the legacy orchestrator-based shutdown.

Use `--verbose` to see the detailed streaming updates.

### **Examples:**
```bash
# Use custom configuration file
context-cleaner --config ~/my-config.yaml run

# Use custom data directory
context-cleaner --data-dir ~/my-analytics-data run

# Enable verbose output for debugging
context-cleaner --verbose health-check --detailed
```

## 🚀 **Core Commands**

### **`stop`** ⭐ ENHANCED v0.3.0
Comprehensive service shutdown with intelligent process discovery and orchestrated cleanup.

**Features:**
- **Orchestrated Shutdown**: Dependency-aware cleanup with proper signal handling
- **Live Supervisor Streaming**: Real-time shutdown progress when supervisor is available
- **Process Discovery**: Automatically finds and stops ALL Context Cleaner processes
- **Registry Management**: Optional cleanup of process registry entries
- **Comprehensive Coverage**: Docker, JSONL processing, dashboard, and monitoring services

```bash
context-cleaner stop [OPTIONS]

Options:
  --force                Skip confirmation prompts
  --docker-only          Only stop Docker services
  --processes-only       Only stop background processes
  --no-discovery         Skip process discovery (use basic method)
  --show-discovery       Preview discovered processes before stopping
  --registry-cleanup     Remove stale registry entries after shutdown
  --use-script           Run stop-context-cleaner.sh script for cleanup
  --service SERVICE      Target specific services (repeat for multiple)
  --no-dependents        Don't stop dependent services with --service
  --help                 Show help message
```

**Supervisor streaming:**
```
$ context-cleaner --verbose stop
🔧 PHASE 2: Orchestrated Service Shutdown
⏳ Supervisor progress: 2 service(s) still running
⏳ Supervisor progress: 1 service(s) still running
✅ Supervisor reports shutdown complete
```

If the supervisor can't be reached, the command falls back to the legacy
orchestrator shutdown and prints the traditional progress messages.

**Examples:**
```bash
# Full orchestrated shutdown (recommended)
context-cleaner stop

# Preview what will be stopped
context-cleaner stop --show-discovery

# Force shutdown without confirmations
context-cleaner stop --force

# Stop only Docker services
context-cleaner stop --docker-only

# Stop only background processes
context-cleaner stop --processes-only

# Cleanup with registry maintenance
context-cleaner stop --registry-cleanup

# Use comprehensive cleanup script
context-cleaner stop --use-script
```

**Targeted shutdown:**
```bash
# Stop specific service with dependents
context-cleaner stop --service dashboard

# Stop specific service without dependents
context-cleaner stop --service jsonl_bridge --no-dependents

# Stop multiple specific services
context-cleaner stop --service dashboard --service bridge
```

### **`run`** ⭐ UPDATED
Full-service orchestrator entry point. Bootstraps the supervisor, orchestrator,
Docker services, JSONL bridge, dashboard, and watchdog monitoring in one command.

```bash
context-cleaner run [OPTIONS]

Options:
  --dashboard-port, -p INTEGER   Dashboard port (default: 8110)
  --no-browser                   Don't open browser automatically
  --status-only                  Show service status and exit
  --json                         With --status-only, output machine-readable JSON
  --config-file PATH             Load custom configuration file
  --dev-mode                     Enable development mode with verbose logging
  --help                         Show help message
```

**Examples:**
```bash
# Start everything (default behaviour)
context-cleaner run

# Quick status snapshot without launching services
context-cleaner run --status-only

# Structured status output for tooling / dashboards
context-cleaner run --status-only --json | jq '.watchdog'
```

**Status output:**

- Text mode highlights orchestrator state, each managed service (with health icons),
  and—when the supervisor is reachable—the watchdog summary (heartbeat, last restart,
  recent history). If the supervisor is offline, the watchdog block is omitted.
- JSON mode returns a schema with `orchestrator`, `services`, `services_summary`,
  and `watchdog` keys so CI tooling or dashboards can consume the data directly.

### **Dashboard access**
The standalone `dashboard` command has been retired. Launch the web dashboard
through the unified `run` entry point and tailor behaviour with the supported
flags:

```bash
# Launch dashboard with orchestration (default port 8110)
context-cleaner run

# Use a different port without editing config
context-cleaner run --dashboard-port 8080

# Start quietly and open the URL yourself
context-cleaner run --no-browser

# Enable verbose logs and developer tooling
context-cleaner run --dev-mode
```

Need to bind to another host? Update `dashboard.host` in
`~/.context_cleaner/config.yaml` or export `CONTEXT_CLEANER_HOST=0.0.0.0`
before invoking `context-cleaner run`.

### **`optimize`**
Context optimization and health analysis (equivalent to `/clean-context`).

```bash
context-cleaner optimize [OPTIONS]

Options:
  --dashboard            Show optimization dashboard
  --quick               Quick optimization with safe defaults
  --preview             Preview changes without applying
  --aggressive          Use aggressive optimization strategy
  --focus               Use focus optimization strategy  
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Preview optimization without changes
context-cleaner optimize --preview

# Quick optimization with safe defaults
context-cleaner optimize --quick

# Show optimization dashboard
context-cleaner optimize --dashboard

# Aggressive optimization with JSON output
context-cleaner optimize --aggressive --format json
```

## 📊 **Analytics Commands** ⭐ NEW v0.2.0

### **`health-check`**
Perform comprehensive system health check and validation.

```bash
context-cleaner health-check [OPTIONS]

Options:
  --detailed            Show detailed diagnostics
  --fix-issues          Attempt to fix identified issues automatically
  --format TEXT         Output format (text/json)
  --help               Show help message
```

**Examples:**
```bash
# Basic health check
context-cleaner health-check

# Detailed diagnostics with auto-fix
context-cleaner health-check --detailed --fix-issues

# JSON output for automation
context-cleaner health-check --format json
```

**Sample Output:**
```
🔍 Context Cleaner Health Check
================================

✅ Configuration: Valid
✅ Data Directory: Accessible (/Users/user/.context_cleaner/data)  
✅ Storage System: Operational (3.2MB used)
✅ Analytics Engine: Running
✅ Session Tracking: Active
⚠️  Dashboard: Not running (start with 'context-cleaner run')

📊 SYSTEM STATUS: HEALTHY
🔧 Issues Found: 0
💡 Recommendations: Start dashboard for full monitoring
```

### **`export-analytics`**
Export comprehensive analytics data for analysis or backup.

```bash
context-cleaner export-analytics [OPTIONS]

Options:
  --output, -o PATH      Output file path (auto-generated if not specified)
  --days INTEGER         Number of days to export (default: 30)
  --include-sessions     Include individual session details
  --format TEXT         Output format (json) 
  --help                Show help message
```

**Examples:**
```bash
# Export last 30 days to auto-generated filename
context-cleaner export-analytics

# Export last 90 days with session details
context-cleaner export-analytics --days 90 --include-sessions --output full-report.json

# Export specific timeframe
context-cleaner export-analytics --days 14 --output sprint-analytics.json
```

**Sample Output:**
```
📊 Exporting analytics data for last 30 days...
✅ Analytics data exported to: context_cleaner_analytics_20250831_142530.json

📈 Export Summary:
   • Total Sessions: 45
   • Success Rate: 89.3%
   • Time Period: 2025-08-01 to 2025-08-31
   • File Size: 125.3 KB
```

### **`effectiveness`**
Display optimization effectiveness statistics and user impact metrics.

```bash
context-cleaner effectiveness [OPTIONS]

Options:
  --days INTEGER         Number of days to analyze (default: 30)
  --strategy TEXT        Filter by optimization strategy
  --detailed            Show detailed effectiveness breakdown
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Basic effectiveness stats for last 30 days
context-cleaner effectiveness

# Analyze specific strategy performance
context-cleaner effectiveness --strategy BALANCED --days 60

# Detailed breakdown with JSON output
context-cleaner effectiveness --detailed --format json
```

**Sample Output:**
```
📈 OPTIMIZATION EFFECTIVENESS REPORT
====================================
📅 Analysis Period: Last 30 days
🎯 Total Optimization Sessions: 45
⚡ Success Rate: 89.3%
💰 Estimated Time Saved: 12.5 hours
📊 Average Productivity Improvement: +23.4%
🌟 User Satisfaction: 4.2/5.0

💡 TOP STRATEGIES:
   1. Balanced Mode: 67% of sessions, 4.3/5 satisfaction
   2. Focus Mode: 22% of sessions, 4.5/5 satisfaction  
   3. Aggressive Mode: 11% of sessions, 3.8/5 satisfaction

🎯 RECOMMENDATIONS:
   • Continue using Balanced mode for general optimization
   • Use Focus mode for complex debugging sessions
   • Consider more frequent optimization for 15% productivity boost
```

## 🔮 **Advanced Analytics Commands** ⭐ NEW v0.3.0

### **`analytics`**
Enterprise-grade analytics with predictive forecasting and business intelligence.

```bash
context-cleaner analytics [OPTIONS] COMMAND [ARGS]...

Commands:
  forecast          Generate predictive forecasts using ML models
  content-analysis  Perform semantic content intelligence analysis
  executive-report  Generate business intelligence summary
  benchmarks        Industry benchmark comparison report
  status            Show analytics system status
  warnings          Check for early warning alerts
```

**Examples:**
```bash
# Generate daily forecast
context-cleaner analytics forecast --horizon day

# Analyze conversation content
context-cleaner analytics content-analysis --conversation-id abc123

# Executive summary report
context-cleaner analytics executive-report

# Industry benchmarks
context-cleaner analytics benchmarks

# Check system status
context-cleaner analytics status
```

## 🔗 **Data Bridge & Token Analysis** ⭐ NEW v0.3.0

### **`bridge`**
Token Analysis Bridge Service for historical data recovery.

```bash
context-cleaner bridge [OPTIONS] COMMAND [ARGS]...

Commands:
  backfill      Execute historical data backfill (2.768B tokens)
  info          Display bridge service information
  status        Show current bridge service status
  sync          Start incremental synchronization for new data
  sync-status   Show synchronization service status
  validate      Validate end-to-end data flow integrity
```

**Examples:**
```bash
# Check bridge status
context-cleaner bridge status

# Start backfill process
context-cleaner bridge backfill

# Start incremental sync
context-cleaner bridge sync

# Validate data flow
context-cleaner bridge validate

# View service info
context-cleaner bridge info
```

### **`token-analysis`**
Enhanced token analysis using Anthropic's count-tokens API.

```bash
context-cleaner token-analysis [OPTIONS] COMMAND [ARGS]...

Commands:
  comprehensive  Run comprehensive analysis (addresses 90% undercount)
  session        Analyze token usage for specific session
  dashboard      Test dashboard integration
```

**Examples:**
```bash
# Comprehensive analysis
context-cleaner token-analysis comprehensive

# Analyze specific session
context-cleaner token-analysis session --session-id abc123

# Test dashboard
context-cleaner token-analysis dashboard
```

### **`migration`**
Migration commands for historical JSONL data to ClickHouse.

```bash
context-cleaner migration [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose  Enable verbose logging

Commands:
  discover-jsonl      Discover and catalog JSONL files
  migrate-historical  Migrate historical data to ClickHouse
  migration-status    Show migration status and progress
  resume-migration    Resume migration from checkpoint
  validate-migration  Validate migration data integrity
  manage              Manage migration data and checkpoints
```

**Examples:**
```bash
# Discover JSONL files
context-cleaner migration discover-jsonl

# Start migration
context-cleaner migration migrate-historical --verbose

# Check migration status
context-cleaner migration migration-status

# Resume interrupted migration
context-cleaner migration resume-migration

# Validate migrated data
context-cleaner migration validate-migration
```

## 📄 **JSONL Processing** ⭐ NEW v0.3.0

### **`jsonl`**
Process and analyze JSONL content files.

```bash
context-cleaner jsonl [OPTIONS] COMMAND [ARGS]...

Commands:
  conversation       Get complete conversation for session
  process-directory  Process all JSONL files in directory
  process-file       Process single JSONL file
  search             Search through processed content
  stats              Get comprehensive statistics
  status             Check processing system status
```

**Examples:**
```bash
# Process single file
context-cleaner jsonl process-file --file path/to/session.jsonl

# Process directory
context-cleaner jsonl process-directory --dir ~/.claude/sessions

# Get conversation
context-cleaner jsonl conversation --session-id abc123

# Search content
context-cleaner jsonl search --query "error handling"

# View statistics
context-cleaner jsonl stats

# Check status
context-cleaner jsonl status
```

## 🔧 **Debug & Diagnostics** ⭐ NEW v0.3.0

### **`debug`**
Debug commands for process registry and service orchestration.

```bash
context-cleaner debug [OPTIONS] COMMAND [ARGS]...

Commands:
  cleanup-stale      Clean up stale registry entries
  discover-services  Discover running Context Cleaner processes
  health-check       Perform health checks on registered processes
  list-processes     List running processes and metadata
  process-tree       Show process tree for Context Cleaner
  processes          List running processes
  registry-prune     Remove stale registry entries
  registry-stats     Show registry statistics and health
  test-registry      Test registry operations (development)
```

**Examples:**
```bash
# List all processes
context-cleaner debug list-processes

# Show process tree
context-cleaner debug process-tree

# Health check all services
context-cleaner debug health-check

# Clean up stale entries
context-cleaner debug cleanup-stale

# View registry stats
context-cleaner debug registry-stats

# Discover services
context-cleaner debug discover-services

# Prune registry
context-cleaner debug registry-prune --type all
```

### **`update-data`**
Diagnose and fix widget data staleness issues.

```bash
context-cleaner update-data [OPTIONS]

Options:
  -p, --dashboard-port INTEGER  Dashboard port to check
  --host TEXT                   Dashboard host
  --check-only                  Only diagnose, don't fix
  --clear-cache                 Force cache refresh
  --output PATH                 Save detailed report to JSON
  --format [text|json]          Output format
```

**Examples:**
```bash
# Diagnose and fix issues
context-cleaner update-data

# Check only (no fixes)
context-cleaner update-data --check-only

# Clear cache and refresh
context-cleaner update-data --clear-cache

# Save detailed report
context-cleaner update-data --output diagnostic-report.json

# Check specific port
context-cleaner update-data --dashboard-port 8110
```

**Common Issues Detected:**
- Telemetry services not initialized
- Docker containers offline
- Stale widget cache
- Missing data connections
- Service health problems

## 👥 **Session Management**

### **`session start`**
Start a new productivity tracking session.

```bash
context-cleaner session start [OPTIONS]

Options:
  --session-id TEXT      Custom session identifier
  --project-path PATH    Project directory path
  --model TEXT           AI model being used (e.g., claude-3-5-sonnet)
  --version TEXT         Context Cleaner version override
  --help                 Show help message
```

**Examples:**
```bash
# Start session with auto-generated ID
context-cleaner session start

# Start named session for specific project
context-cleaner session start --session-id "api-refactor" --project-path ./my-api

# Track specific AI model usage
context-cleaner session start --model "claude-3-5-sonnet" --project-path ./frontend
```

### **`session end`**
End the current or specified tracking session.

```bash
context-cleaner session end [OPTIONS]

Options:
  --session-id TEXT      Session ID to end (current if not specified)
  --help                 Show help message
```

**Examples:**
```bash
# End current session
context-cleaner session end

# End specific session
context-cleaner session end --session-id "api-refactor"
```

### **`session stats`**
Show productivity statistics and session analytics.

```bash
context-cleaner session stats [OPTIONS]

Options:
  --days INTEGER         Number of days to analyze (default: 7)
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Show stats for last week
context-cleaner session stats

# Monthly stats in JSON format
context-cleaner session stats --days 30 --format json
```

### **`session list`**
List recent tracking sessions.

```bash
context-cleaner session list [OPTIONS]

Options:
  --limit INTEGER        Maximum number of sessions to show (default: 10)
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# List last 10 sessions
context-cleaner session list

# List last 20 sessions in JSON format
context-cleaner session list --limit 20 --format json
```

## 📡 **Monitoring Commands**

### **`monitor start`**
Start real-time session monitoring and observation.

```bash
context-cleaner monitor start [OPTIONS]

Options:
  --watch-dirs PATH      Directories to monitor (multiple allowed)
  --no-observer         Disable file system observer
  --help                Show help message
```

**Examples:**
```bash
# Monitor current directory
context-cleaner monitor start

# Monitor specific directories
context-cleaner monitor start --watch-dirs ./src --watch-dirs ./tests

# Monitor without file observer (lower resource usage)
context-cleaner monitor start --no-observer
```

### **`monitor status`**
Show monitoring status and statistics.

```bash
context-cleaner monitor status [OPTIONS]

Options:
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Show monitoring status
context-cleaner monitor status

# Status in JSON format
context-cleaner monitor status --format json
```

### **`monitor live`**
Show live dashboard with real-time updates.

```bash
context-cleaner monitor live [OPTIONS]

Options:
  --refresh INTEGER     Refresh interval in seconds (default: 5)
  --help               Show help message
```

**Examples:**
```bash
# Live dashboard with 5-second refresh
context-cleaner monitor live

# Fast refresh every 2 seconds
context-cleaner monitor live --refresh 2
```

## 📊 **Data Management**

### **`analyze`**
Analyze productivity trends and generate insights.

```bash
context-cleaner analyze [OPTIONS]

Options:
  --days INTEGER         Number of days to analyze (default: 7)
  --format TEXT         Output format (text/json)  
  --output, -o PATH     Output file path
  --help                Show help message
```

**Examples:**
```bash
# Analyze last week
context-cleaner analyze --days 7

# Monthly analysis with JSON output
context-cleaner analyze --days 30 --format json --output monthly-report.json
```

### **`export`**
Export all productivity data.

```bash
context-cleaner export [OPTIONS]

Options:
  --format TEXT         Output format (json)
  --output, -o PATH     Output file path (auto-generated if not specified)
  --help                Show help message
```

**Examples:**
```bash
# Export all data to auto-generated file
context-cleaner export

# Export to specific file
context-cleaner export --output my-productivity-data.json
```

### **`config-show`**
Show current configuration.

```bash
context-cleaner config-show [OPTIONS]

Options:
  --help    Show help message
```

**Example:**
```bash
context-cleaner config-show
```

## 🔐 **Privacy Commands**

### **`privacy show-info`**
Show information about data collection and privacy.

```bash
context-cleaner privacy show-info [OPTIONS]

Options:
  --help    Show help message
```

### **`privacy delete-all`**
Permanently delete all collected productivity data.

```bash
context-cleaner privacy delete-all [OPTIONS]

Options:
  --help    Show help message
```

**⚠️ Warning:** This action is irreversible and will delete all your productivity tracking data.

## 🎯 **Examples & Use Cases**

### **Daily Development Workflow**
```bash
# Morning: Start tracking
context-cleaner session start --project-path ./my-project

# Throughout the day: Use optimization as needed
context-cleaner optimize --quick

# End of day: Review productivity
context-cleaner effectiveness --days 1
context-cleaner run

# End session
context-cleaner session end
```

### **Project Analysis**
```bash
# Analyze project productivity over 2 weeks
context-cleaner session stats --days 14

# Export detailed analytics for stakeholders
context-cleaner export-analytics --days 14 --include-sessions --output project-metrics.json

# Check optimization effectiveness by strategy
context-cleaner effectiveness --strategy BALANCED --days 14
```

### **System Maintenance**
```bash
# Regular health check
context-cleaner health-check --detailed

# Fix any issues found
context-cleaner health-check --fix-issues

# Export backup of analytics data
context-cleaner export-analytics --days 90 --output backup-$(date +%Y%m%d).json
```

### **Automation & CI/CD**
```bash
# Health check in CI pipeline
context-cleaner health-check --format json | jq '.status'

# Export metrics for analysis
context-cleaner session stats --days 7 --format json > weekly-metrics.json

# Automated optimization check
context-cleaner optimize --preview --format json > optimization-preview.json
```

### **Team Collaboration**
```bash
# Export anonymized productivity metrics
context-cleaner export-analytics --days 30 --output team-metrics.json

# Compare strategy effectiveness across team
context-cleaner effectiveness --detailed --format json > strategy-analysis.json

# Monitor team productivity trends
context-cleaner session stats --days 30 --format json
```

## 🔄 **Command Chaining**

Context Cleaner commands can be chained for powerful workflows:

```bash
# Start session, run health check, and launch dashboard
context-cleaner session start --project-path . && \
context-cleaner health-check && \
context-cleaner run

# Export analytics and immediately analyze them
context-cleaner export-analytics --output latest.json && \
jq '.effectiveness_summary.success_rate' latest.json

# Monitor and track in background
context-cleaner session start --session-id "monitoring" && \
context-cleaner monitor start --watch-dirs ./src &
```

## ❓ **Getting Help**

### **Command-Specific Help**
```bash
# Get help for any command
context-cleaner COMMAND --help

# Examples:
context-cleaner effectiveness --help
context-cleaner export-analytics --help
context-cleaner session start --help
```

### **Global Help**
```bash
# Show all available commands
context-cleaner --help

# Show version information
context-cleaner --version
```

## 🔧 **Troubleshooting**

### **Common Issues**

**Permission Errors:**
```bash
# Fix data directory permissions
chmod 700 ~/.context_cleaner/
chmod 600 ~/.context_cleaner/data/*
```

**Port Already in Use:**
```bash
# Use different port for dashboard
context-cleaner run --dashboard-port 8111
```

**Configuration Issues:**
```bash
# Show current configuration to debug
context-cleaner config-show

# Use custom config file
context-cleaner --config ./debug-config.yaml health-check
```

**Data Directory Issues:**
```bash
# Use custom data directory
context-cleaner --data-dir ./temp-analytics health-check

# Reset data directory permissions
context-cleaner privacy delete-all  # ⚠️ Destructive
```

For more troubleshooting help, see the [Troubleshooting Guide](../TROUBLESHOOTING.md).

---

**Context Cleaner CLI Reference** - Complete command documentation for v0.3.0

*Need more help? Check out the [User Guide](quickstart.md) or [Configuration Reference](configuration.md).*
