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
context-cleaner --config ~/my-config.yaml dashboard

# Use custom data directory
context-cleaner --data-dir ~/my-analytics-data start

# Enable verbose output for debugging
context-cleaner --verbose health-check --detailed
```

## 🚀 **Core Commands**

### **`stop`** ⭐ UPDATED
Gracefully stop all Context Cleaner services. When the supervisor is running,
the CLI streams shutdown progress updates in real time.

```bash
context-cleaner stop [OPTIONS]

Options:
  --force                Skip confirmation prompts
  --docker-only          Only stop Docker services
  --processes-only       Only stop background processes
  --no-discovery         Skip process discovery
  --show-discovery       Preview discovered processes before stopping
  --registry-cleanup     Remove stale registry entries after shutdown
  --use-script           Run stop-context-cleaner.sh instead of supervisor IPC
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

### **`start`**
Start productivity tracking for the current development session.

```bash
context-cleaner start [OPTIONS]

Options:
  --help    Show help message
```

**Examples:**
```bash
# Basic start
context-cleaner start

# With verbose output
context-cleaner --verbose start
```

**Output:**
```
✅ Context Cleaner started
📊 Dashboard available at: http://localhost:8548
📈 Use 'context-cleaner dashboard' to view insights
```

### **`dashboard`**
Launch the productivity dashboard web interface.

```bash
context-cleaner dashboard [OPTIONS]

Options:
  --port, -p INTEGER      Dashboard port (overrides config)
  --host, -h TEXT         Dashboard host (overrides config)  
  --no-browser           Don't open browser automatically
  --interactive          Enable interactive dashboard mode
  --operations           Show available operations
  --help                 Show help message
```

**Examples:**
```bash
# Launch dashboard on default port (8548)
context-cleaner dashboard

# Use custom port
context-cleaner dashboard --port 8080

# Enable interactive mode with operations
context-cleaner dashboard --interactive --operations

# Launch without opening browser
context-cleaner dashboard --no-browser
```

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
⚠️  Dashboard: Not running (start with 'context-cleaner dashboard')

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

## 👥 **Session Management**

### **`session-start`**
Start a new productivity tracking session.

```bash
context-cleaner session-start [OPTIONS]

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
context-cleaner session-start

# Start named session for specific project
context-cleaner session-start --session-id "api-refactor" --project-path ./my-api

# Track specific AI model usage
context-cleaner session-start --model "claude-3-5-sonnet" --project-path ./frontend
```

### **`session-end`**
End the current or specified tracking session.

```bash
context-cleaner session-end [OPTIONS]

Options:
  --session-id TEXT      Session ID to end (current if not specified)
  --help                 Show help message
```

**Examples:**
```bash
# End current session
context-cleaner session-end

# End specific session
context-cleaner session-end --session-id "api-refactor"
```

### **`session-stats`**
Show productivity statistics and session analytics.

```bash
context-cleaner session-stats [OPTIONS]

Options:
  --days INTEGER         Number of days to analyze (default: 7)
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Show stats for last week
context-cleaner session-stats

# Monthly stats in JSON format
context-cleaner session-stats --days 30 --format json
```

### **`session-list`**
List recent tracking sessions.

```bash
context-cleaner session-list [OPTIONS]

Options:
  --limit INTEGER        Maximum number of sessions to show (default: 10)
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# List last 10 sessions
context-cleaner session-list

# List last 20 sessions in JSON format
context-cleaner session-list --limit 20 --format json
```

## 📡 **Monitoring Commands**

### **`monitor`**
Start real-time session monitoring and observation.

```bash
context-cleaner monitor [OPTIONS]

Options:
  --watch-dirs PATH      Directories to monitor (multiple allowed)
  --no-observer         Disable file system observer
  --help                Show help message
```

**Examples:**
```bash
# Monitor current directory
context-cleaner monitor

# Monitor specific directories
context-cleaner monitor --watch-dirs ./src --watch-dirs ./tests

# Monitor without file observer (lower resource usage)
context-cleaner monitor --no-observer
```

### **`monitor-status`**
Show monitoring status and statistics.

```bash
context-cleaner monitor-status [OPTIONS]

Options:
  --format TEXT         Output format (text/json)
  --help                Show help message
```

**Examples:**
```bash
# Show monitoring status
context-cleaner monitor-status

# Status in JSON format
context-cleaner monitor-status --format json
```

### **`live-dashboard`**
Show live dashboard with real-time updates.

```bash
context-cleaner live-dashboard [OPTIONS]

Options:
  --refresh INTEGER     Refresh interval in seconds (default: 5)
  --help               Show help message
```

**Examples:**
```bash
# Live dashboard with 5-second refresh
context-cleaner live-dashboard

# Fast refresh every 2 seconds
context-cleaner live-dashboard --refresh 2
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
context-cleaner session-start --project-path ./my-project

# Throughout the day: Use optimization as needed
context-cleaner optimize --quick

# End of day: Review productivity
context-cleaner effectiveness --days 1
context-cleaner dashboard

# End session
context-cleaner session-end
```

### **Project Analysis**
```bash
# Analyze project productivity over 2 weeks
context-cleaner session-stats --days 14

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
context-cleaner session-stats --days 7 --format json > weekly-metrics.json

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
context-cleaner session-stats --days 30 --format json
```

## 🔄 **Command Chaining**

Context Cleaner commands can be chained for powerful workflows:

```bash
# Start session, run health check, and launch dashboard
context-cleaner session-start --project-path . && \
context-cleaner health-check && \
context-cleaner dashboard

# Export analytics and immediately analyze them
context-cleaner export-analytics --output latest.json && \
jq '.effectiveness_summary.success_rate' latest.json

# Monitor and track in background
context-cleaner session-start --session-id "monitoring" && \
context-cleaner monitor --watch-dirs ./src &
```

## ❓ **Getting Help**

### **Command-Specific Help**
```bash
# Get help for any command
context-cleaner COMMAND --help

# Examples:
context-cleaner effectiveness --help
context-cleaner export-analytics --help
context-cleaner session-start --help
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
context-cleaner dashboard --port 8549
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

**Context Cleaner CLI Reference** - Complete command documentation for v0.2.0

*Need more help? Check out the [User Guide](quickstart.md) or [Configuration Reference](configuration.md).*
