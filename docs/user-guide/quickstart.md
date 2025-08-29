# Quick Start Guide

Get up and running with Context Cleaner in less than 5 minutes!

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- Claude Code installed (for integration features)

### Install Context Cleaner
```bash
pip install context-cleaner
```

### Verify Installation
```bash
context-cleaner --version
# Output: Context Cleaner 0.1.0
```

## 🔧 Initial Setup

### 1. Claude Code Integration (Recommended)
```bash
# Automatically set up Claude Code integration
context-cleaner install --claude-integration
```

This creates:
- `/clean-context` command in Claude Code
- Productivity tracking hooks
- Configuration files

### 2. Verify Integration
```bash
# Test the Claude Code integration
python ~/.claude/commands/clean-context.py --help
```

## 📊 Basic Usage

### 1. Context Optimization
```bash
# Preview context optimization (safe, no changes made)
context-cleaner optimize --preview

# Quick optimization with safe defaults
context-cleaner optimize --quick

# Show context health dashboard
context-cleaner optimize --dashboard
```

### 2. Productivity Analysis
```bash
# View recent productivity insights
context-cleaner analyze --days 7

# Export analysis as JSON
context-cleaner analyze --days 7 --format json
```

### 3. Web Dashboard
```bash
# Launch interactive dashboard
context-cleaner dashboard

# Dashboard opens at: http://localhost:8546
# Use --no-browser to prevent auto-opening
```

## 🎯 Your First Productivity Session

### Step 1: Start Tracking
```bash
# Begin productivity tracking for current session
context-cleaner start
```

### Step 2: Work on Your Project
- Use Claude Code as normal
- Context Cleaner automatically tracks your activity
- Privacy-first: all data stays on your machine

### Step 3: View Insights
```bash
# Check your productivity metrics
context-cleaner analyze --days 1

# Example output:
# 📊 PRODUCTIVITY ANALYSIS REPORT
# ========================================
# 📅 Analysis Period: Last 1 days
# 🎯 Average Productivity Score: 85.3/100
# 📈 Total Sessions: 23
# ⚡ Optimization Events: 12
# 🌟 Most Productive Day: Tuesday
```

### Step 4: Optimize Context
```bash
# Use Claude Code integration
/clean-context --quick

# Or use direct command
context-cleaner optimize --quick
```

## 📈 Dashboard Overview

Launch the dashboard to see:

```bash
context-cleaner dashboard
```

### Dashboard Features:
- **📊 Productivity Charts**: Real-time productivity trends
- **🔥 Heatmaps**: Activity patterns and peak performance times  
- **📈 Trend Analysis**: Historical data with forecasting
- **⚡ Performance Metrics**: System performance and optimization impact
- **🎯 Recommendations**: AI-powered productivity suggestions

## ⚙️ Configuration

### View Current Configuration
```bash
context-cleaner config-show
```

### Key Settings
```json
{
  "tracking": {
    "enabled": true,
    "session_timeout": 1800,
    "auto_optimize": false
  },
  "privacy": {
    "data_retention_days": 90,
    "anonymous_analytics": true
  },
  "performance": {
    "max_memory_mb": 50,
    "max_cpu_percent": 15
  }
}
```

## 🔐 Privacy & Security

Context Cleaner is designed with privacy-first principles:

- **🏠 Local Only**: All data processing happens on your machine
- **🔒 Encrypted Storage**: AES-256 encryption for all stored data
- **👤 Anonymous**: No personal information collected
- **🎛️ User Control**: Complete control over data retention and deletion

### Privacy Commands
```bash
# View privacy settings
context-cleaner privacy --status

# Export your data
context-cleaner export --format json

# Delete all data
context-cleaner privacy --delete-all
```

## 🎨 Customization

### Dashboard Themes
```bash
# Dark theme (default)
context-cleaner dashboard --theme dark

# Light theme  
context-cleaner dashboard --theme light
```

### Custom Port
```bash
# Use custom port for dashboard
context-cleaner dashboard --port 8547
```

### Analysis Periods
```bash
# Analyze different time periods
context-cleaner analyze --days 1    # Last day
context-cleaner analyze --days 7    # Last week
context-cleaner analyze --days 30   # Last month
```

## 🚀 Next Steps

Now that you're set up, explore more advanced features:

1. **[CLI Reference](cli-reference.md)** - Complete command documentation
2. **[Configuration Guide](configuration.md)** - Customize your setup
3. **[Integration Examples](../examples/integrations.md)** - Advanced Claude Code integration
4. **[Advanced Analytics](../examples/advanced-analytics.md)** - Deep productivity insights

## ❓ Need Help?

- **Issues?** See our [Troubleshooting Guide](../../TROUBLESHOOTING.md)
- **Questions?** Check the [FAQ](faq.md)
- **Bugs?** Report on [GitHub Issues](https://github.com/context-cleaner/context-cleaner/issues)

## 🎯 Common Use Cases

### For Daily Development
```bash
# Morning routine: start tracking
context-cleaner start

# Work with Claude Code using /clean-context as needed
# Context Cleaner tracks automatically in background

# End of day: view productivity insights  
context-cleaner analyze --days 1
context-cleaner dashboard  # Visual review
```

### For Project Analysis
```bash
# Analyze productivity for specific project period
context-cleaner analyze --days 14 --format json > project-metrics.json

# Export all data for external analysis
context-cleaner export --format csv
```

### For Performance Optimization
```bash
# Monitor system performance impact
context-cleaner monitor --performance

# Get optimization recommendations
context-cleaner optimize --preview --format json
```

---

**🎉 Congratulations!** You're now ready to track and optimize your AI-assisted development productivity with Context Cleaner.

*Next: Explore the [CLI Reference](cli-reference.md) for complete command documentation.*