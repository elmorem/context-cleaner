# Quick Start Guide

Get up and running with Context Cleaner v0.2.0 in less than 5 minutes! This guide covers installation, initial setup, and your first analytics session.

## 🚀 Installation

### Prerequisites
- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Claude Code** (for optimal integration features)
- **10MB+ disk space** for analytics data storage

### Install Context Cleaner
```bash
# Install latest version from PyPI
pip install context-cleaner

# Or install development version from source
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner
pip install -e .

# Verify installation
context-cleaner --version
# Output: Context Cleaner 0.2.0
```

### System Requirements Check
```bash
# Run initial health check to verify system compatibility
context-cleaner health-check

# Output should show:
# ✅ Configuration: Valid
# ✅ Data Directory: Accessible
# ✅ Analytics Engine: Ready
# ✅ Storage System: Operational
```

## 🔧 Initial Setup

### 1. First-Time Configuration
Context Cleaner works out-of-the-box with secure defaults. No configuration required!

```bash
# View default configuration
context-cleaner config-show

# Create data directory and initialize system
context-cleaner run
```

**What this creates:**
- `~/.context_cleaner/` - Main application directory
- `~/.context_cleaner/data/` - Analytics data storage (secure permissions)
- `~/.context_cleaner/config.yaml` - Configuration file (if needed)

### 2. Verify Setup
```bash
# Comprehensive system verification
context-cleaner health-check --detailed

# Should report:
# 📊 SYSTEM STATUS: HEALTHY
# 🔧 Issues Found: 0
# 💡 Recommendations: Ready for productivity tracking
```

## 📊 Basic Usage

### 1. Context Optimization with Tracking ⭐ NEW
```bash
# Preview context optimization (safe, no changes made)
context-cleaner optimize --preview

# Quick optimization with effectiveness tracking
context-cleaner optimize --quick

# Show enhanced dashboard with analytics
context-cleaner run --dev-mode
```

### 2. New Analytics Commands ⭐ v0.2.0
```bash
# View optimization effectiveness statistics
context-cleaner effectiveness --days 7

# Run comprehensive system health check
context-cleaner health-check --detailed

# Export comprehensive analytics data
context-cleaner export-analytics --output my-analytics.json
```

### 3. Enhanced Web Dashboard
```bash
# Launch interactive dashboard with analytics
context-cleaner run --dev-mode

# Dashboard with enhanced features at: http://localhost:8110
# Now includes effectiveness tracking and ROI metrics
```

## 🎯 Your First Analytics Session ⭐ NEW

### Step 1: Start Tracked Session
```bash
# Begin productivity tracking with session ID
context-cleaner session start --project-path ./my-project --session-id "first-session"

# Verify tracking is active
context-cleaner session list
```

### Step 2: Perform Optimizations with Tracking
```bash
# Run optimization - this will be tracked for effectiveness
context-cleaner optimize --quick

# Rate the optimization (1-5 scale) when prompted
# Context Cleaner now tracks before/after metrics automatically
```

### Step 3: View Effectiveness Insights
```bash
# Check your optimization effectiveness
context-cleaner effectiveness --days 1

# Example output:
# 📈 OPTIMIZATION EFFECTIVENESS REPORT
# ====================================
# 📅 Analysis Period: Last 1 days  
# 🎯 Total Optimization Sessions: 3
# ⚡ Success Rate: 100.0%
# 💰 Estimated Time Saved: 0.3 hours
# 📊 Average Productivity Improvement: +18.5%
# 🌟 User Satisfaction: 4.3/5.0
```

### Step 4: Export Your Data
```bash
# Export detailed analytics for review
context-cleaner export-analytics --include-sessions --output first-session-report.json

# End your tracking session
context-cleaner session end
```

## 📈 Enhanced Dashboard Overview ⭐ NEW

Launch the enhanced dashboard with analytics:

```bash
context-cleaner run --dev-mode
```

### New Dashboard Features v0.2.0:
- **📈 Effectiveness Overview**: Success rates, time saved, and ROI metrics
- **🎯 Strategy Performance**: Comparative analysis of optimization approaches  
- **🌟 User Satisfaction Trends**: Rating patterns and feedback analysis
- **📊 Before/After Comparisons**: Quantifiable productivity improvements
- **🔄 Interactive Controls**: Operation triggers and real-time adjustments
- **📉 Time-Series Charts**: Productivity correlation analysis with optimization events

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
context-cleaner run --no-browser  # set theme via dashboard settings

# Light theme  
context-cleaner run --no-browser  # set theme via dashboard settings
```

### Custom Port
```bash
# Use custom port for dashboard
context-cleaner run --dashboard-port 8111
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
context-cleaner run

# Work with Claude Code using /clean-context as needed
# Context Cleaner tracks automatically in background

# End of day: view productivity insights  
context-cleaner analyze --days 1
context-cleaner run  # Visual review
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
context-cleaner monitor status --format json

# Get optimization recommendations
context-cleaner optimize --preview --format json
```

---

**🎉 Congratulations!** You're now ready to track and optimize your AI-assisted development productivity with Context Cleaner.

*Next: Explore the [CLI Reference](cli-reference.md) for complete command documentation.*
