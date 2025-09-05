# Context Cleaner Real-World Usage Guide

## Overview
Context Cleaner is now ready for real-world usage with all Phase 1-3 features:

### ✅ Phase 1: Critical Telemetry Infrastructure
- Session tracking and analytics
- ClickHouse data storage (optional)
- Performance monitoring

### ✅ Phase 2: Enhanced Analytics & Dashboard  
- Cost optimization engine
- Error recovery management
- Real-time dashboard widgets
- Advanced telemetry analytics

### ✅ Phase 3: Advanced Orchestration & ML Learning
- Multi-agent workflow coordination
- ML-powered pattern recognition
- Intelligent agent selection
- Performance optimization recommendations

## Quick Start

### **🎯 Unified Dashboard Launch (Recommended)**
```bash
# Primary method - CLI dashboard
context-cleaner dashboard

# Alternative - Direct script
python start_context_cleaner.py
```

### **🌐 Access Everything in One Place**
**Dashboard URL**: http://localhost:8081

The unified dashboard provides complete visibility across all Context Cleaner features:
- **Overview**: System health summary and key performance indicators
- **Telemetry**: Phase 1-3 real-time monitoring widgets
- **Orchestration**: ML-powered agent coordination and workflow optimization  
- **Analytics**: Context health metrics and performance trends with comprehensive legends
- **Performance**: Real-time system resources, cache, and database monitoring

### **🔄 Additional Features**
```bash
# Monitor multiple directories (background process)
python monitor_directories.py

# Traditional CLI commands (optional)  
context-cleaner start
context-cleaner health-check
```

## Configuration

Edit `context_cleaner_config.json` to customize:

- **Monitored directories**: Add your project paths
- **Dashboard settings**: Port, refresh rates
- **Orchestration**: Agent selection strategies
- **Performance**: Cache sizes, thread counts

## Dashboard Features

### Real-Time Widgets
- **Error Monitor**: API error tracking and recovery
- **Cost Tracker**: Usage cost and burn rate monitoring  
- **Timeout Risk**: Performance risk assessment
- **Tool Optimizer**: Tool usage pattern analysis
- **Model Efficiency**: AI model performance comparison

### Phase 3 Orchestration Widgets
- **Orchestration Status**: Multi-agent workflow monitoring
- **Agent Utilization**: Performance and load balancing
- **Workflow Performance**: ML optimization insights

## Directory Monitoring

The system can monitor multiple directories simultaneously:

```json
"directories": {
  "monitored_paths": [
    "~/code",
    "~/projects", 
    "~/workspace"
  ]
}
```

## Advanced Features

### ML-Powered Learning
- Automatic workflow pattern recognition
- Performance prediction models
- Continuous optimization recommendations

### Intelligent Agent Selection  
- Multi-criteria decision making
- Context-aware agent matching
- Performance-based selection

### Cost Optimization
- Real-time cost tracking
- Budget monitoring and alerts
- Model efficiency recommendations

## Troubleshooting

1. **Dashboard not loading**: Check port 8080 availability
2. **Telemetry issues**: Verify configuration file
3. **Performance slow**: Adjust cache sizes and thread counts

## Configuration Generated
- Config file: `/Users/markelmore/_code/context-cleaner/context_cleaner_config.json`
- Startup script: `/Users/markelmore/_code/context-cleaner/start_context_cleaner.py`  
- Directory monitor: `/Users/markelmore/_code/context-cleaner/monitor_directories.py`

Setup completed at: 2025-09-03 15:36:28
