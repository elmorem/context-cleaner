# Context Cleaner

[![PyPI version](https://badge.fury.io/py/context-cleaner.svg)](https://badge.fury.io/py/context-cleaner)
[![Python Support](https://img.shields.io/pypi/pyversions/context-cleaner.svg)](https://pypi.org/project/context-cleaner/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Advanced productivity tracking and context optimization for AI-assisted development**

Context Cleaner is a comprehensive productivity tracking tool designed specifically for developers using AI coding assistants like Claude Code. It provides intelligent context health monitoring, performance analytics, and optimization recommendations to maximize development productivity.

## 🎯 **Key Features**

### **📊 Productivity Tracking**
- **Development session monitoring** with automatic boundary detection
- **Context health scoring** (0-100 scale) based on size, structure, and complexity
- **Performance correlation analysis** between context optimization and productivity
- **Git integration** for commit pattern analysis and productivity metrics

### **🔍 Advanced Analytics**
- **Trend analysis** across days, weeks, and months
- **Pattern recognition** for optimal work schedules and session lengths
- **A/B testing framework** for different context optimization strategies
- **Productivity forecasting** based on historical data and patterns

### **📈 Interactive Dashboard**
- **Web-based visualization** of productivity trends and session analytics
- **Real-time metrics** with automatic refresh and live updates
- **Actionable insights** with specific optimization recommendations
- **Mobile-responsive design** for monitoring on any device

### **🛡️ Privacy-First Architecture**
- **Local-only processing** - all data stays on your machine
- **No external requests** - zero network dependencies
- **Complete data ownership** with easy export and deletion
- **Transparent operation** with open-source codebase

### **🔧 Developer-Friendly CLI**
- **Simple installation** via pip with zero configuration required
- **Flexible commands** for all productivity tracking and analysis needs
- **Multiple output formats** (JSON, YAML, text) for integration
- **Comprehensive help** and troubleshooting built-in

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

# Analyze recent productivity
context-cleaner analyze --days 7

# Export your data
context-cleaner export --output my-data.json
```

### **Dashboard Access**
After running `context-cleaner dashboard`, visit `http://localhost:8548` to access your productivity insights through an intuitive web interface.

## 📊 **Usage Examples**

### **Development Workflow Integration**
```bash
# Start tracking at beginning of work session
context-cleaner start

# View real-time productivity dashboard
context-cleaner dashboard --port 8080

# Get daily productivity summary
context-cleaner analyze --days 1 --format text

# Weekly productivity report in JSON
context-cleaner analyze --days 7 --format json --output weekly-report.json
```

### **Productivity Analysis**
```bash
# Comprehensive 30-day analysis
context-cleaner analyze --days 30

# Example output:
# 📊 PRODUCTIVITY ANALYSIS REPORT
# ================================
# 📅 Analysis Period: Last 30 days
# 🎯 Average Productivity Score: 87.3/100
# 📈 Total Sessions: 156
# ⚡ Optimization Events: 45
# 🌟 Most Productive Day: Tuesday
# 
# 💡 RECOMMENDATIONS:
#    1. Your productivity peaks at 3-4 PM - schedule complex tasks then
#    2. Context optimization events correlate with 18% productivity increase
#    3. Consider shorter sessions (< 90 minutes) for sustained performance
```

### **Data Management**
```bash
# Export all data for backup
context-cleaner export --format json --output backup-$(date +%Y%m%d).json

# Show privacy information
context-cleaner privacy show-info

# Delete all collected data
context-cleaner privacy delete-all
```

## 📈 **Dashboard Features**

### **Productivity Metrics Overview**
- **Current productivity score** with 7-day trend
- **Session statistics** including count, duration, and quality
- **Optimization events** tracking context improvements
- **Health trend indicators** showing improvement/decline patterns

### **Advanced Visualizations**
- **Time-series charts** showing productivity trends over time
- **Heatmaps** indicating peak performance hours and days
- **Session type analysis** (debugging, coding, exploration, optimization)
- **Correlation charts** between context health and productivity

### **Actionable Insights**
- **Personalized recommendations** based on individual productivity patterns
- **Optimal scheduling suggestions** for different types of development tasks
- **Context optimization timing** recommendations for maximum impact
- **Performance alerts** when productivity patterns change significantly

## 🔧 **Configuration**

### **Default Configuration**
Context Cleaner works out-of-the-box with sensible defaults, but can be customized via configuration files.

### **Configuration File** (Optional)
Create `~/.context_cleaner/config.yaml`:
```yaml
dashboard:
  port: 8548
  host: localhost
  auto_refresh: true
  cache_duration: 300

tracking:
  enabled: true
  sampling_rate: 1.0
  session_timeout_minutes: 30
  data_retention_days: 90

privacy:
  local_only: true
  encrypt_storage: true
  require_consent: true

analysis:
  health_thresholds:
    excellent: 90
    good: 70
    fair: 50
  max_context_size: 100000
```

### **Environment Variables**
```bash
export CONTEXT_CLEANER_PORT=8080
export CONTEXT_CLEANER_DATA_DIR=~/my-productivity-data
export CONTEXT_CLEANER_LOG_LEVEL=DEBUG
```

## 🧪 **Advanced Features**

### **Custom Analytics**
```python
from context_cleaner import ProductivityAnalyzer, ContextCleanerConfig

# Initialize with custom configuration
config = ContextCleanerConfig.default()
analyzer = ProductivityAnalyzer(config)

# Analyze context health
result = await analyzer.analyze_context_health(context_data)
print(f"Health Score: {result.health_score}/100")

# Analyze productivity session
metrics = analyzer.analyze_productivity_session(session_data)
print(f"Productivity Score: {metrics.productivity_score}/100")
```

### **Integration with Development Tools**
```bash
# Git hook integration (post-commit)
#!/bin/bash
context-cleaner analyze --days 1 --format json | jq '.avg_productivity_score'

# CI/CD integration
context-cleaner analyze --days 7 --format json > productivity-report.json
```

### **Custom Dashboard Themes**
The dashboard supports custom CSS themes and can be extended with additional charts and metrics.

## 🔒 **Privacy & Security**

### **Data Protection**
- **Local Storage**: All data is stored locally in `~/.context_cleaner/data/`
- **No Telemetry**: Zero external network requests or data transmission
- **Encryption**: Optional at-rest encryption for sensitive productivity data
- **Data Retention**: Configurable automatic cleanup after specified period

### **Privacy Controls**
- **Granular Tracking**: Choose exactly what metrics to collect
- **Easy Deletion**: One-command complete data removal
- **Data Export**: Full data portability in standard formats
- **Transparent Operation**: Open-source code for complete auditability

### **Security Features**
- **Input Validation**: Comprehensive sanitization of all data
- **Resource Limits**: Built-in protection against resource exhaustion  
- **Safe Defaults**: Conservative configuration prioritizing privacy
- **Error Isolation**: System continues working even with component failures

## 🏗️ **Architecture**

### **Core Components**
```
Context Cleaner Architecture
├── 📊 Analytics Engine
│   ├── ProductivityAnalyzer - Core analysis algorithms
│   ├── TrendCalculator - Time-series analysis  
│   └── ImpactEvaluator - Optimization effectiveness
├── 📈 Dashboard System
│   ├── Web Server - FastAPI-based interface
│   ├── Data Visualization - Interactive charts
│   └── Real-time Updates - Live metric streaming
├── 🗃️ Data Management
│   ├── Session Tracking - Development session boundaries
│   ├── Storage System - Local SQLite database
│   └── Privacy Controls - Data export/deletion
└── 🔧 CLI Interface
    ├── Command Processing - Argument parsing and validation
    ├── Output Formatting - Text/JSON/YAML formats
    └── Configuration - Settings and preferences
```

### **Data Flow**
1. **Data Collection** - Monitor development sessions and context changes
2. **Analysis Processing** - Calculate health scores and productivity metrics  
3. **Pattern Recognition** - Identify trends and optimization opportunities
4. **Insight Generation** - Create actionable recommendations
5. **Visualization** - Present insights through dashboard or CLI

## 📚 **API Reference**

### **Command Line Interface**
```bash
context-cleaner [OPTIONS] COMMAND [ARGS]...

Commands:
  start              Start productivity tracking
  dashboard          Launch web dashboard
  analyze            Analyze productivity trends  
  export             Export all data
  privacy            Privacy and data management
  config-show        Show current configuration
```

### **Python API**
```python
from context_cleaner import ContextCleanerConfig, ProductivityAnalyzer

# Configuration
config = ContextCleanerConfig.from_file('config.yaml')
config = ContextCleanerConfig.from_env()  # Environment variables
config = ContextCleanerConfig.default()   # Sensible defaults

# Analytics
analyzer = ProductivityAnalyzer(config)
result = await analyzer.analyze_context_health(data)
metrics = analyzer.analyze_productivity_session(session_data)

# Dashboard
from context_cleaner import ProductivityDashboard
dashboard = ProductivityDashboard(config)
dashboard.start_server(host="localhost", port=8548)
```

## 🧪 **Development**

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner

# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Code formatting
black src/
flake8 src/

# Type checking
mypy src/
```

### **Testing**
```bash
# Run all tests
pytest

# Run specific test categories  
pytest -m unit      # Unit tests only
pytest -m integration  # Integration tests only

# Coverage report
pytest --cov=context_cleaner --cov-report=html
```

### **Contributing**
We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/awesome-feature`
3. Make changes and add tests
4. Run test suite: `pytest`
5. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 **Support**

### **Documentation**
- [Installation Guide](docs/installation.md)
- [Usage Examples](docs/usage.md)
- [API Reference](docs/api_reference.md)
- [Privacy Policy](docs/privacy_policy.md)

### **Community**
- [GitHub Issues](https://github.com/context-cleaner/context-cleaner/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/context-cleaner/context-cleaner/discussions) - Questions and community support
- [Documentation](https://context-cleaner.readthedocs.io) - Comprehensive guides and tutorials

### **Commercial Support**
For enterprise support, custom integrations, and consulting services, please contact us at team@context-cleaner.dev.

## 🎯 **Roadmap**

### **Version 0.2.0** (Next Release)
- **Advanced ML Analytics**: Machine learning-powered productivity insights
- **Team Features**: Aggregated (anonymized) team productivity metrics  
- **IDE Integration**: Direct integration with popular development environments
- **Extended Git Integration**: Branch-based productivity tracking

### **Version 0.3.0** (Future)
- **Cross-Project Analytics**: Multi-repository productivity tracking
- **Advanced Forecasting**: Predictive productivity modeling
- **Custom Metrics**: User-defined productivity indicators
- **API Integration**: Webhooks and external service integration

### **Long-term Vision**
- **AI-Powered Coaching**: Personalized productivity improvement recommendations
- **Collaboration Analytics**: Pair programming and code review productivity
- **Performance Benchmarking**: Industry-wide anonymous productivity comparisons
- **Ecosystem Integration**: Seamless integration with development tool ecosystems

---

**Context Cleaner** - Transforming AI-assisted development through intelligent productivity tracking and optimization.

*Built with ❤️ for developers who want to understand and improve their coding productivity.*