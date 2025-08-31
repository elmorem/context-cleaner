# Context Cleaner Analytics Guide

Complete guide to Context Cleaner's analytics and effectiveness tracking features introduced in v0.2.0.

## 📊 **Overview**

Context Cleaner's analytics system provides comprehensive insights into your AI-assisted development productivity through:

- **Effectiveness Tracking**: Before/after metrics showing optimization impact
- **User Satisfaction Monitoring**: Rating system with feedback collection  
- **Strategy Performance Analysis**: Comparing different optimization approaches
- **ROI Demonstration**: Quantifiable productivity improvements and time savings
- **Export Capabilities**: Comprehensive data backup and external analysis

## 🎯 **Key Concepts**

### **Effectiveness Metrics**
- **Success Rate**: Percentage of optimizations that improve productivity
- **Time Saved**: Estimated hours saved through context optimization
- **Productivity Improvement**: Before/after productivity score changes
- **User Satisfaction**: 1-5 rating scale with optional feedback
- **Strategy Effectiveness**: Performance comparison across optimization modes

### **Optimization Strategies**
- **Conservative**: Safe, minimal changes with high confidence
- **Balanced**: Moderate optimization balancing safety and impact
- **Aggressive**: Maximum optimization with higher risk tolerance
- **Focus**: Targeted optimization for specific context issues

### **Session Tracking**
- **Optimization Sessions**: Individual context cleaning operations
- **Development Sessions**: Broader work periods with multiple optimizations
- **Cross-Session Analytics**: Patterns and trends across multiple sessions

## 🚀 **Getting Started**

### **Enable Effectiveness Tracking**
Effectiveness tracking is enabled by default. Verify in your configuration:

```yaml
# ~/.context_cleaner/config.yaml
tracking:
  enabled: true
  sampling_rate: 1.0
  session_timeout_minutes: 30
  data_retention_days: 90
  anonymize_data: true
```

### **Start Your First Tracked Session**
```bash
# Begin tracking for a project
context-cleaner session-start --project-path ./my-project --session-id "feature-dev"

# Perform some optimization
context-cleaner optimize --quick

# View immediate effectiveness feedback
context-cleaner effectiveness --days 1
```

## 📈 **Analytics Commands Deep Dive**

### **1. Effectiveness Statistics**

**Basic Usage:**
```bash
context-cleaner effectiveness --days 30
```

**Advanced Options:**
```bash
# Analyze specific strategy performance
context-cleaner effectiveness --strategy BALANCED --days 60

# Detailed breakdown with all metrics
context-cleaner effectiveness --detailed --days 90

# JSON output for external analysis
context-cleaner effectiveness --format json > effectiveness-report.json
```

**Understanding the Output:**
```
📈 OPTIMIZATION EFFECTIVENESS REPORT
====================================
📅 Analysis Period: Last 30 days
🎯 Total Optimization Sessions: 45        # Number of optimizations performed
⚡ Success Rate: 89.3%                    # Percentage that improved productivity
💰 Estimated Time Saved: 12.5 hours       # Conservative time savings estimate
📊 Average Productivity Improvement: +23.4% # Mean productivity score increase
🌟 User Satisfaction: 4.2/5.0            # Average user rating

💡 TOP STRATEGIES:
   1. Balanced Mode: 67% of sessions, 4.3/5 satisfaction
   2. Focus Mode: 22% of sessions, 4.5/5 satisfaction  
   3. Aggressive Mode: 11% of sessions, 3.8/5 satisfaction
```

### **2. Analytics Export**

**Full Export:**
```bash
# Export comprehensive analytics with session details
context-cleaner export-analytics --days 90 --include-sessions --output full-report.json
```

**Export Structure:**
```json
{
  "export_metadata": {
    "export_timestamp": "2025-08-31T14:25:30",
    "days_analyzed": 30,
    "total_sessions": 45,
    "format": "json",
    "context_cleaner_version": "0.2.0"
  },
  "effectiveness_summary": {
    "total_sessions": 45,
    "success_rate": 0.893,
    "estimated_time_saved_hours": 12.5,
    "average_productivity_improvement": 23.4,
    "user_satisfaction_average": 4.2,
    "strategy_breakdown": {
      "BALANCED": {"count": 30, "satisfaction": 4.3},
      "FOCUS": {"count": 10, "satisfaction": 4.5},
      "AGGRESSIVE": {"count": 5, "satisfaction": 3.8}
    }
  },
  "all_sessions": [
    {
      "session_id": "opt_1693478400123",
      "timestamp": "2025-08-31T10:00:00",
      "strategy_type": "BALANCED",
      "outcome": "success",
      "metrics": {
        "original_size_bytes": 15432,
        "optimized_size_bytes": 12108,
        "size_reduction_percentage": 21.5,
        "productivity_improvement": 18.2,
        "user_satisfaction_rating": 4
      }
    }
  ]
}
```

### **3. Health Monitoring**

**Comprehensive Health Check:**
```bash
context-cleaner health-check --detailed --fix-issues
```

**Health Check Categories:**
- **Configuration Validation**: Settings and file permissions
- **Data Integrity**: Storage consistency and corruption detection
- **Performance Metrics**: System resource usage and bottlenecks
- **Security Status**: PII sanitization and secure storage verification
- **Service Health**: Dashboard and monitoring service status

## 📊 **Analytics Dashboard**

### **Accessing Enhanced Dashboard**
```bash
# Launch dashboard with analytics features
context-cleaner dashboard --interactive --operations
```

### **Dashboard Sections**

**1. Effectiveness Overview**
- Real-time success rates and productivity improvements
- Time saved calculations and ROI demonstration
- Strategy performance comparison charts

**2. User Satisfaction Trends**  
- Rating patterns over time
- Feedback sentiment analysis
- Satisfaction correlation with productivity

**3. Before/After Comparisons**
- Context size reduction visualizations
- Health score improvements
- Focus score enhancements

**4. Interactive Controls**
- Trigger optimization operations
- Adjust strategy parameters
- Export analytics data

## 🔍 **Deep Analytics**

### **Strategy Effectiveness Analysis**

**Compare Strategy Performance:**
```bash
# Analyze each strategy separately
context-cleaner effectiveness --strategy CONSERVATIVE --days 30 --format json > conservative.json
context-cleaner effectiveness --strategy BALANCED --days 30 --format json > balanced.json
context-cleaner effectiveness --strategy AGGRESSIVE --days 30 --format json > aggressive.json
context-cleaner effectiveness --strategy FOCUS --days 30 --format json > focus.json

# Combine for comparison
jq -s '{"conservative": .[0], "balanced": .[1], "aggressive": .[2], "focus": .[3]}' \
  conservative.json balanced.json aggressive.json focus.json > strategy-comparison.json
```

**Key Metrics to Compare:**
- Success rate by strategy
- User satisfaction ratings
- Average productivity improvement
- Time savings per strategy
- Usage frequency and patterns

### **Productivity Correlation Analysis**

**Export Data for External Analysis:**
```bash
# Export detailed session data
context-cleaner export-analytics --include-sessions --days 90 --output sessions.json

# Extract key metrics
jq '.all_sessions[] | {
  timestamp: .timestamp,
  strategy: .strategy_type,
  success: (.outcome == "success"),
  improvement: .metrics.productivity_improvement,
  satisfaction: .metrics.user_satisfaction_rating,
  size_reduction: .metrics.size_reduction_percentage
}' sessions.json > metrics.jsonl
```

### **Time-Based Analysis**

**Weekly/Monthly Trends:**
```bash
# Weekly effectiveness trends
for week in {1..4}; do
  start_day=$((($week - 1) * 7 + 1))
  end_day=$(($week * 7))
  context-cleaner effectiveness --days 7 --format json > "week${week}.json"
done

# Monthly comparison
context-cleaner effectiveness --days 30 --format json > this-month.json
context-cleaner effectiveness --days 60 --format json > last-two-months.json
```

## 🔐 **Privacy & Security**

### **Data Sanitization**
Context Cleaner automatically sanitizes sensitive data before storage:

**Removed Automatically:**
- Email addresses
- Social Security Numbers
- Credit card numbers  
- API keys and tokens
- File paths with usernames
- IP addresses

**Verification:**
```bash
# Check health status includes security verification
context-cleaner health-check --detailed --format json | jq '.security_status'
```

### **Secure Export**
```bash
# Export with enhanced security verification
context-cleaner export-analytics --output secure-backup.json

# Verify no sensitive data in export
grep -E "(email|password|key|token)" secure-backup.json || echo "Export is clean"
```

## 🎯 **Best Practices**

### **1. Regular Effectiveness Monitoring**
```bash
# Weekly effectiveness review
context-cleaner effectiveness --days 7

# Monthly deep analysis
context-cleaner effectiveness --detailed --days 30 --format json > monthly-review.json
```

### **2. Strategy Optimization**
```bash
# A/B test strategies over time
# Week 1: Use Balanced mode primarily
# Week 2: Use Focus mode for comparison
# Week 3: Compare results

context-cleaner effectiveness --strategy BALANCED --days 7 > balanced-week.txt
context-cleaner effectiveness --strategy FOCUS --days 7 > focus-week.txt
```

### **3. Data Backup and Retention**
```bash
# Monthly analytics backup
context-cleaner export-analytics --days 30 --include-sessions \
  --output "analytics-backup-$(date +%Y-%m).json"

# Quarterly comprehensive export
context-cleaner export-analytics --days 90 --include-sessions \
  --output "quarterly-analytics-$(date +%Y-Q%q).json"
```

### **4. Performance Monitoring**
```bash
# Monitor system health weekly
context-cleaner health-check --detailed > health-$(date +%Y-%m-%d).log

# Track resource usage
context-cleaner monitor-status --format json > monitor-status.json
```

## 📋 **Common Analytics Workflows**

### **Daily Developer Workflow**
```bash
#!/bin/bash
# daily-analytics.sh

# Start day with health check
context-cleaner health-check --fix-issues

# Start tracking session
context-cleaner session-start --project-path "$(pwd)" --session-id "daily-$(date +%Y%m%d)"

# At end of day, review effectiveness
context-cleaner effectiveness --days 1

# Export daily data
context-cleaner export-analytics --days 1 --output "daily-$(date +%Y%m%d).json"

# End session
context-cleaner session-end
```

### **Weekly Team Review**
```bash
#!/bin/bash
# weekly-team-analytics.sh

# Generate weekly effectiveness report
context-cleaner effectiveness --days 7 --detailed > weekly-effectiveness.txt

# Export comprehensive analytics
context-cleaner export-analytics --days 7 --include-sessions --output weekly-analytics.json

# Generate strategy performance comparison
for strategy in CONSERVATIVE BALANCED AGGRESSIVE FOCUS; do
  context-cleaner effectiveness --strategy $strategy --days 7 --format json > "weekly-${strategy,,}.json"
done

echo "Weekly analytics generated in weekly-*.json files"
```

### **Monthly Project Analysis**
```bash
#!/bin/bash
# monthly-project-analysis.sh

PROJECT_NAME="${1:-$(basename $(pwd))}"
MONTH_DIR="analytics-$(date +%Y-%m)"

mkdir -p "$MONTH_DIR"
cd "$MONTH_DIR"

# Comprehensive monthly export
context-cleaner export-analytics --days 30 --include-sessions --output "${PROJECT_NAME}-monthly.json"

# Effectiveness analysis
context-cleaner effectiveness --days 30 --detailed --format json > "${PROJECT_NAME}-effectiveness.json"

# Health and performance report
context-cleaner health-check --detailed --format json > "${PROJECT_NAME}-health.json"

# Generate summary report
cat > "${PROJECT_NAME}-monthly-summary.md" << EOF
# ${PROJECT_NAME} - Monthly Analytics Summary

**Period:** $(date -d '30 days ago' +%Y-%m-%d) to $(date +%Y-%m-%d)

## Key Metrics
- Total Sessions: $(jq '.export_metadata.total_sessions' "${PROJECT_NAME}-monthly.json")
- Success Rate: $(jq '.effectiveness_summary.success_rate * 100' "${PROJECT_NAME}-effectiveness.json")%
- Time Saved: $(jq '.effectiveness_summary.estimated_time_saved_hours' "${PROJECT_NAME}-effectiveness.json") hours
- User Satisfaction: $(jq '.effectiveness_summary.user_satisfaction_average' "${PROJECT_NAME}-effectiveness.json")/5.0

## Recommendations
- Continue using top-performing strategies
- Monitor productivity trends for optimization opportunities
- Regular health checks to maintain system performance

Generated: $(date)
EOF

echo "Monthly analysis complete in $MONTH_DIR/"
```

## 🔧 **Troubleshooting Analytics**

### **No Data Available**
```bash
# Check if tracking is enabled
context-cleaner config-show | grep -A 5 "tracking:"

# Verify data directory
ls -la ~/.context_cleaner/data/

# Start a test session
context-cleaner session-start --session-id "test"
context-cleaner optimize --preview
context-cleaner effectiveness --days 1
```

### **Export Issues**
```bash
# Check data directory permissions
context-cleaner health-check --detailed | grep -i permission

# Try exporting to different location
context-cleaner export-analytics --output /tmp/test-export.json

# Verify JSON format
jq . export-file.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

### **Performance Issues**
```bash
# Check system health
context-cleaner health-check --detailed

# Monitor resource usage
context-cleaner monitor-status

# Clear analytics cache if needed
rm -rf ~/.context_cleaner/data/cache/
```

## 📚 **External Analysis Tools**

### **Python Analysis Example**
```python
import json
import pandas as pd
import matplotlib.pyplot as plt

# Load analytics data
with open('analytics-export.json', 'r') as f:
    data = json.load(f)

# Create DataFrame from sessions
sessions = pd.DataFrame(data['all_sessions'])

# Analyze productivity trends
sessions['timestamp'] = pd.to_datetime(sessions['timestamp'])
sessions['productivity_improvement'] = sessions['metrics'].apply(
    lambda x: x.get('productivity_improvement', 0)
)

# Plot trends
plt.figure(figsize=(12, 6))
sessions.groupby(sessions['timestamp'].dt.date)['productivity_improvement'].mean().plot()
plt.title('Daily Average Productivity Improvement')
plt.xlabel('Date')
plt.ylabel('Productivity Improvement (%)')
plt.show()

# Strategy effectiveness
strategy_stats = sessions.groupby('strategy_type').agg({
    'productivity_improvement': ['mean', 'count'],
    'metrics': lambda x: sum(1 for m in x if m.get('user_satisfaction_rating', 0) >= 4)
}).round(2)

print("Strategy Effectiveness Analysis:")
print(strategy_stats)
```

### **R Analysis Example**
```r
library(jsonlite)
library(dplyr)
library(ggplot2)

# Load analytics data
data <- fromJSON("analytics-export.json")
sessions <- data$all_sessions

# Extract metrics
metrics <- sessions %>%
  mutate(
    timestamp = as.POSIXct(timestamp),
    productivity_improvement = sapply(metrics, function(x) x$productivity_improvement %||% 0),
    user_satisfaction = sapply(metrics, function(x) x$user_satisfaction_rating %||% NA),
    size_reduction = sapply(metrics, function(x) x$size_reduction_percentage %||% 0)
  )

# Strategy comparison
strategy_comparison <- metrics %>%
  group_by(strategy_type) %>%
  summarise(
    sessions = n(),
    avg_improvement = mean(productivity_improvement, na.rm = TRUE),
    avg_satisfaction = mean(user_satisfaction, na.rm = TRUE),
    avg_size_reduction = mean(size_reduction, na.rm = TRUE)
  )

# Visualization
ggplot(metrics, aes(x = strategy_type, y = productivity_improvement)) +
  geom_boxplot() +
  labs(
    title = "Productivity Improvement by Strategy",
    x = "Optimization Strategy",
    y = "Productivity Improvement (%)"
  )
```

---

**Context Cleaner Analytics Guide** - Comprehensive analytics and effectiveness tracking for v0.2.0

*Ready to dive deeper? Check out the [CLI Reference](cli-reference.md) or [Configuration Guide](configuration.md).*