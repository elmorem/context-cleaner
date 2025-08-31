# Context Cleaner

[![PyPI version](https://badge.fury.io/py/context-cleaner.svg)](https://badge.fury.io/py/context-cleaner)
[![Python Support](https://img.shields.io/pypi/pyversions/context-cleaner.svg)](https://pypi.org/project/context-cleaner/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Advanced productivity tracking and context optimization for AI-assisted development**

Context Cleaner is a comprehensive productivity tracking tool designed specifically for developers using AI coding assistants like Claude Code. It provides intelligent context health monitoring, performance analytics, and optimization recommendations to maximize development productivity.

## 🎯 **Key Features**

### **📊 Effectiveness Tracking & Analytics** ⭐ NEW in v0.2.0
- **Before/after metrics** with quantifiable productivity improvements
- **User satisfaction tracking** with 1-5 rating system and feedback collection
- **Strategy effectiveness analysis** across Conservative/Balanced/Aggressive/Focus modes
- **ROI demonstration** with time-saved calculations and optimization impact
- **Export capabilities** for comprehensive analytics data backup and analysis

### **🔍 Advanced Context Optimization**
- **Multi-strategy optimization** with Conservative, Balanced, Aggressive, and Focus modes
- **Context health scoring** (0-100 scale) based on size, structure, and complexity
- **Interactive optimization** with operation approval/rejection workflow
- **Performance correlation analysis** between context optimization and productivity
- **Real-time context monitoring** with automatic boundary detection

### **📈 Interactive Dashboard**
- **Web-based visualization** of productivity trends and session analytics
- **Real-time metrics** with automatic refresh and live updates
- **Effectiveness insights** with specific optimization recommendations
- **Mobile-responsive design** for monitoring on any device
- **Enhanced controls** for manipulation operations and analytics review

### **🛡️ Privacy-First Architecture**
- **Local-only processing** - all data stays on your machine
- **PII sanitization** - automatic removal of emails, SSNs, credentials, and sensitive data
- **Secure file storage** with atomic operations and file locking
- **Complete data ownership** with easy export and deletion
- **Transparent operation** with open-source codebase

### **🔧 Developer-Friendly CLI**
- **Comprehensive command set** with 15+ commands for all productivity needs
- **Multiple output formats** (JSON, text) for integration and automation
- **Session management** with start/end tracking and detailed analytics
- **System health monitoring** with diagnostics and issue resolution
- **Flexible configuration** via files, environment variables, or CLI flags

## 🚀 **Quick Start**

### **Installation**
```bash
# Install from PyPI
pip install context-cleaner

# Or install from source
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner
pip install -e .
```

### **Basic Usage**
```bash
# Start productivity tracking
context-cleaner start

# Launch interactive dashboard
context-cleaner dashboard

# Run system health check
context-cleaner health-check

# View effectiveness statistics
context-cleaner effectiveness --days 7

# Export analytics data
context-cleaner export-analytics --output my-analytics.json
```

### **Dashboard Access**
After running `context-cleaner dashboard`, visit `http://localhost:8548` to access your productivity insights through an intuitive web interface with enhanced analytics and effectiveness tracking.

## 📊 **New Analytics Features** ⭐

### **Effectiveness Tracking**
```bash
# View optimization effectiveness stats
context-cleaner effectiveness --days 30

# Example output:
# 📈 OPTIMIZATION EFFECTIVENESS REPORT
# ====================================
# 📅 Analysis Period: Last 30 days
# 🎯 Total Optimization Sessions: 45
# ⚡ Success Rate: 89.3%
# 💰 Estimated Time Saved: 12.5 hours
# 📊 Average Productivity Improvement: +23.4%
# 🌟 User Satisfaction: 4.2/5.0
# 
# 💡 TOP STRATEGIES:
#    1. Balanced Mode: 67% of sessions, 4.3/5 satisfaction
#    2. Focus Mode: 22% of sessions, 4.5/5 satisfaction  
#    3. Aggressive Mode: 11% of sessions, 3.8/5 satisfaction
```

### **Comprehensive Analytics Export**
```bash
# Export all analytics data
context-cleaner export-analytics --days 90 --output analytics-backup.json

# Export with session details
context-cleaner export-analytics --include-sessions --output detailed-report.json
```

### **System Health Monitoring**
```bash
# Basic health check
context-cleaner health-check

# Detailed diagnostics
context-cleaner health-check --detailed

# Auto-fix common issues
context-cleaner health-check --fix-issues

# JSON output for automation
context-cleaner health-check --format json
```

## 📚 **Complete CLI Reference**

### **Core Commands**
```bash
context-cleaner [OPTIONS] COMMAND [ARGS]...

# Primary Commands:
  start              Start productivity tracking
  dashboard          Launch web dashboard  
  optimize           Context optimization and health analysis
  
# New Analytics Commands (v0.2.0):
  health-check       Perform system health check and validation
  export-analytics   Export comprehensive analytics data  
  effectiveness      Display optimization effectiveness statistics
  
# Session Management:
  session-start      Start new tracking session
  session-end        End current tracking session
  session-stats      Show session statistics
  session-list       List recent sessions
  
# Monitoring:  
  monitor            Start real-time monitoring
  monitor-status     Show monitoring status
  live-dashboard     Live dashboard with real-time updates
  
# Data Management:
  analyze            Analyze productivity trends
  export             Export all data
  privacy            Privacy and data management
  config-show        Show current configuration
```

### **Session Management Examples**
```bash
# Start named session for specific project
context-cleaner session-start --session-id "api-refactor" --project-path ./my-project

# View session statistics
context-cleaner session-stats --days 7

# List recent sessions
context-cleaner session-list --limit 10

# End current session
context-cleaner session-end
```

### **Advanced Monitoring**
```bash
# Start real-time monitoring
context-cleaner monitor --watch-dirs ./src ./tests

# Check monitoring status
context-cleaner monitor-status

# Launch live dashboard with 10-second refresh
context-cleaner live-dashboard --refresh 10
```

## 📈 **Dashboard Features**

### **Enhanced Analytics Dashboard**
- **Effectiveness Overview** - Success rates, time saved, and ROI metrics
- **Strategy Performance** - Comparative analysis of optimization approaches
- **User Satisfaction Trends** - Rating patterns and feedback analysis
- **Before/After Comparisons** - Quantifiable productivity improvements
- **Interactive Controls** - Operation triggers and real-time adjustments

### **Productivity Metrics**
- **Current productivity score** with 7-day trend analysis
- **Session statistics** including count, duration, and effectiveness
- **Optimization events** with detailed success/failure tracking
- **Health trend indicators** showing improvement/decline patterns
- **Time-series charts** with productivity correlation analysis

### **Actionable Insights**
- **Personalized recommendations** based on effectiveness data
- **Optimal strategy suggestions** for different context types
- **Performance alerts** when productivity patterns change
- **ROI calculations** demonstrating Context Cleaner's value

## 🔧 **Configuration**

### **Configuration File** (~/.context_cleaner/config.yaml)
```yaml
# Analysis Configuration
analysis:
  health_thresholds:
    excellent: 90
    good: 70
    fair: 50
  max_context_size: 100000
  token_estimation_factor: 0.25
  circuit_breaker_threshold: 5

# Dashboard Configuration  
dashboard:
  port: 8548
  host: localhost
  auto_refresh: true
  cache_duration: 300
  max_concurrent_users: 10

# Effectiveness Tracking (NEW)
tracking:
  enabled: true
  sampling_rate: 1.0
  session_timeout_minutes: 30
  data_retention_days: 90
  anonymize_data: true

# Privacy & Security (ENHANCED)
privacy:
  local_only: true
  encrypt_storage: true
  auto_cleanup_days: 90
  require_consent: true

# Data Directory
data_directory: "~/.context_cleaner/data"
log_level: "INFO"
```

### **Environment Variables**
```bash
export CONTEXT_CLEANER_PORT=8080
export CONTEXT_CLEANER_HOST=localhost
export CONTEXT_CLEANER_DATA_DIR=~/my-context-data
export CONTEXT_CLEANER_LOG_LEVEL=DEBUG
export CONTEXT_CLEANER_LOCAL_ONLY=true
```

## 🔒 **Privacy & Security**

### **Enhanced Security Features** ⭐ NEW
- **PII Sanitization**: Automatic removal of emails, SSNs, credit cards, and credentials
- **Content Hashing**: Secure data integrity without storing raw content
- **Atomic File Operations**: Race-condition protection with file locking
- **Secure Permissions**: All data files use 0o600 permissions (owner-only access)
- **Input Validation**: Comprehensive sanitization and size limits

### **Data Protection**
- **Local Storage**: All data in `~/.context_cleaner/data/` with secure permissions
- **No Telemetry**: Zero external network requests or data transmission
- **At-Rest Encryption**: Optional AES-256 encryption for sensitive data
- **Data Retention**: Configurable automatic cleanup after specified period
- **Resource Limits**: Built-in protection against resource exhaustion

### **Privacy Controls**
```bash
# View privacy information
context-cleaner privacy show-info

# Export all your data
context-cleaner export --format json --output my-data.json

# Permanently delete all data
context-cleaner privacy delete-all
```

## 🏗️ **Architecture**

### **Core Components**
```
Context Cleaner v0.2.0 Architecture
├── 📊 Analytics Engine (ENHANCED)
│   ├── ProductivityAnalyzer - Core analysis algorithms  
│   ├── EffectivenessTracker - Before/after metrics & ROI
│   ├── TrendCalculator - Time-series analysis
│   └── CrossSessionAnalytics - Multi-session insights
├── 📈 Dashboard System (ENHANCED)
│   ├── Web Server - FastAPI-based interface
│   ├── Data Visualization - Interactive charts & effectiveness
│   ├── Real-time Updates - Live metric streaming
│   └── Enhanced Controls - Operation triggers & analytics
├── 🗃️ Data Management (SECURED)
│   ├── Session Tracking - Development session boundaries
│   ├── Secure Storage - Atomic operations & file locking
│   ├── PII Sanitization - Automated sensitive data removal
│   └── Privacy Controls - Data export/deletion with encryption
└── 🔧 CLI Interface (EXPANDED)
    ├── Command Processing - 15+ commands with validation
    ├── Output Formatting - JSON/text formats for automation
    ├── Session Management - Start/end/stats tracking
    └── Health Monitoring - System diagnostics & auto-repair
```

## 🧪 **Development**

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner

# Install development dependencies
pip install -e .[dev]

# Run full test suite (146 tests)
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only  
pytest -m security       # Security tests (NEW)

# Code quality
black src/ tests/
flake8 src/ tests/
mypy src/
```

### **Testing**
```bash
# Full test suite with coverage
pytest --cov=context_cleaner --cov-report=html

# Test new analytics features
pytest tests/cli/test_pr20_analytics_integration.py -v

# Security and performance tests
pytest tests/cli/test_pr20_analytics_integration.py::TestSecurityAndPerformanceFixes -v
```

## 📄 **What's New in v0.2.0**

### **🔥 Major Features**
- **Effectiveness Tracking System**: Quantifiable before/after productivity metrics
- **User Satisfaction Monitoring**: Rating system with feedback collection
- **Strategy Analysis**: Performance comparison across optimization modes  
- **ROI Demonstration**: Time-saved calculations and productivity improvements
- **Enhanced CLI**: 3 new commands (`health-check`, `export-analytics`, `effectiveness`)

### **🛡️ Security Improvements**  
- **PII Sanitization**: Automatic sensitive data removal before storage
- **Atomic File Operations**: Race-condition prevention with exclusive locking
- **Secure Storage**: Enhanced file permissions and data integrity protection
- **Content Hashing**: Secure data handling without raw content storage

### **⚡ Performance Optimizations**
- **Session Indexing**: O(1) lookups instead of O(n) file scans
- **LRU Caching**: Optimized frequent data access patterns
- **Optimized I/O**: Index-based filtering and reduced file operations
- **Memory Management**: Efficient resource usage and cleanup

### **🧪 Production Readiness**
- **Enhanced Error Handling**: Consistent exception management without sys.exit()
- **Comprehensive Testing**: 29 tests including security and performance validation
- **Resource Management**: Proper cleanup and context manager usage
- **Documentation**: Complete overhaul with accurate examples and guides

## 🤝 **Support**

### **Documentation**
- [Installation Guide](docs/user-guide/quickstart.md)
- [CLI Reference](docs/cli-reference.md) 
- [Analytics Guide](docs/analytics-guide.md)
- [Configuration Reference](docs/configuration.md)

### **Community**
- [GitHub Issues](https://github.com/context-cleaner/context-cleaner/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/context-cleaner/context-cleaner/discussions) - Questions and support
- [Documentation](https://context-cleaner.readthedocs.io) - Comprehensive guides

## 🎯 **Roadmap**

### **Version 0.3.0** (Next Release)
- **Machine Learning Analytics**: AI-powered productivity insights and forecasting
- **Team Collaboration**: Aggregated (anonymized) team productivity metrics
- **IDE Integration**: Direct integration with popular development environments
- **Advanced Visualizations**: Enhanced charts and productivity correlation analysis

### **Future Versions**
- **Cross-Project Analytics**: Multi-repository productivity tracking
- **Custom Metrics**: User-defined productivity indicators and thresholds
- **API Integration**: Webhooks and external service connectivity
- **Performance Benchmarking**: Industry-wide anonymous productivity comparisons

---

**Context Cleaner v0.2.0** - Transforming AI-assisted development through intelligent productivity tracking, effectiveness measurement, and optimization.

*Built with ❤️ for developers who want to understand and improve their coding productivity.*