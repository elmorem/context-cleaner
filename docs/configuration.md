# Context Cleaner Configuration Reference

Complete configuration reference for Context Cleaner v0.3.0, including all settings, environment variables, and customization options.

## 📋 **Configuration Overview**

Context Cleaner supports multiple configuration methods:

1. **Default Configuration**: Built-in secure defaults (no configuration required)
2. **Configuration Files**: YAML or JSON files for persistent settings
3. **Environment Variables**: System environment overrides
4. **Command-Line Options**: Runtime parameter overrides

**Configuration Priority** (highest to lowest):
1. Command-line options (`--port`, `--data-dir`, etc.)
2. Environment variables (`CONTEXT_CLEANER_*`)
3. Configuration file (`~/.context_cleaner/config.yaml`)
4. Built-in defaults

## 🔧 **Default Configuration**

Context Cleaner works out-of-the-box with these secure defaults:

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

# Effectiveness Tracking (NEW v0.2.0)
tracking:
  enabled: true
  sampling_rate: 1.0
  session_timeout_minutes: 30
  data_retention_days: 90
  anonymize_data: true

# Privacy & Security (ENHANCED v0.2.0)
privacy:
  local_only: true
  encrypt_storage: true
  auto_cleanup_days: 90
  require_consent: true

# Data Storage
data_directory: "~/.context_cleaner/data"
log_level: "INFO"
```

## 📄 **Configuration Files**

### **YAML Configuration** (Recommended)
Create `~/.context_cleaner/config.yaml`:

```yaml
# Context Cleaner Configuration v0.2.0

# Analysis Engine Settings
analysis:
  health_thresholds:
    excellent: 95      # Excellent health score threshold
    good: 80           # Good health score threshold  
    fair: 60           # Fair health score threshold
  max_context_size: 200000        # Maximum context size in characters
  token_estimation_factor: 0.3    # Token estimation multiplier
  circuit_breaker_threshold: 3    # Consecutive failures before circuit break

# Web Dashboard Settings
dashboard:
  port: 8549                      # Dashboard web port
  host: "0.0.0.0"                # Bind to all interfaces
  auto_refresh: true              # Enable auto-refresh
  cache_duration: 600             # Cache duration in seconds
  max_concurrent_users: 25        # Maximum concurrent dashboard users

# Effectiveness Tracking Settings (NEW)
tracking:
  enabled: true                   # Enable effectiveness tracking
  sampling_rate: 1.0              # Sampling rate (0.0-1.0, 1.0 = 100%)
  session_timeout_minutes: 45     # Session timeout in minutes
  data_retention_days: 120        # Days to retain analytics data
  anonymize_data: true            # Anonymize sensitive data

# Privacy & Security Settings (ENHANCED)
privacy:
  local_only: true                # Keep all data local (no network)
  encrypt_storage: true           # Encrypt stored data
  auto_cleanup_days: 120          # Auto-cleanup after days
  require_consent: true           # Require user consent for tracking

# Storage Configuration
data_directory: "/custom/path/to/data"    # Custom data directory
log_level: "DEBUG"                        # Logging level (DEBUG/INFO/WARNING/ERROR)
```

### **JSON Configuration** (Alternative)
Create `~/.context_cleaner/config.json`:

```json
{
  "analysis": {
    "health_thresholds": {
      "excellent": 90,
      "good": 70,
      "fair": 50
    },
    "max_context_size": 150000,
    "token_estimation_factor": 0.25,
    "circuit_breaker_threshold": 5
  },
  "dashboard": {
    "port": 8548,
    "host": "localhost",
    "auto_refresh": true,
    "cache_duration": 300,
    "max_concurrent_users": 10
  },
  "tracking": {
    "enabled": true,
    "sampling_rate": 1.0,
    "session_timeout_minutes": 30,
    "data_retention_days": 90,
    "anonymize_data": true
  },
  "privacy": {
    "local_only": true,
    "encrypt_storage": true,
    "auto_cleanup_days": 90,
    "require_consent": true
  },
  "data_directory": "~/.context_cleaner/data",
  "log_level": "INFO"
}
```

## 🌍 **Environment Variables**

Override any configuration setting using environment variables:

### **Core Settings**
```bash
# Data and logging
export CONTEXT_CLEANER_DATA_DIR="/custom/data/path"
export CONTEXT_CLEANER_LOG_LEVEL="DEBUG"

# Dashboard settings
export CONTEXT_CLEANER_PORT=8549
export CONTEXT_CLEANER_HOST="0.0.0.0"

# Privacy settings
export CONTEXT_CLEANER_LOCAL_ONLY=true
export CONTEXT_CLEANER_ENCRYPT_STORAGE=true
```

### **Analytics Settings** ⭐ NEW v0.2.0
```bash
# Effectiveness tracking
export CONTEXT_CLEANER_TRACKING_ENABLED=true
export CONTEXT_CLEANER_SAMPLING_RATE=1.0
export CONTEXT_CLEANER_SESSION_TIMEOUT=45
export CONTEXT_CLEANER_DATA_RETENTION_DAYS=120

# Analysis parameters
export CONTEXT_CLEANER_MAX_CONTEXT_SIZE=200000
export CONTEXT_CLEANER_TOKEN_ESTIMATION_FACTOR=0.3
```

### **Security Settings** ⭐ ENHANCED v0.2.0
```bash
# Privacy controls
export CONTEXT_CLEANER_ANONYMIZE_DATA=true
export CONTEXT_CLEANER_REQUIRE_CONSENT=true
export CONTEXT_CLEANER_AUTO_CLEANUP_DAYS=90
```

### **Environment Variable Naming Convention**
```
CONTEXT_CLEANER_<SECTION>_<SETTING>

Examples:
analysis.max_context_size       → CONTEXT_CLEANER_MAX_CONTEXT_SIZE
dashboard.port                  → CONTEXT_CLEANER_PORT  
tracking.enabled                → CONTEXT_CLEANER_TRACKING_ENABLED
privacy.local_only              → CONTEXT_CLEANER_LOCAL_ONLY
```

## ⚙️ **Configuration Sections**

### **Analysis Configuration**
Controls context analysis and optimization behavior:

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `health_thresholds.excellent` | 90 | Score threshold for excellent health | 80-100 |
| `health_thresholds.good` | 70 | Score threshold for good health | 50-95 |
| `health_thresholds.fair` | 50 | Score threshold for fair health | 25-80 |
| `max_context_size` | 100000 | Maximum context size in characters | 10000-1000000 |
| `token_estimation_factor` | 0.25 | Token estimation multiplier | 0.1-1.0 |
| `circuit_breaker_threshold` | 5 | Failures before circuit break | 1-20 |

**Example:**
```yaml
analysis:
  health_thresholds:
    excellent: 95  # Stricter excellent threshold
    good: 75       # Stricter good threshold
    fair: 55       # Stricter fair threshold
  max_context_size: 150000  # Allow larger contexts
  circuit_breaker_threshold: 3  # Fail faster
```

### **Dashboard Configuration**
Controls web dashboard behavior:

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `port` | 8548 | Web server port | 1024-65535 |
| `host` | localhost | Bind address | IP address or hostname |
| `auto_refresh` | true | Enable auto-refresh | true/false |
| `cache_duration` | 300 | Cache duration in seconds | 60-3600 |
| `max_concurrent_users` | 10 | Maximum concurrent users | 1-100 |

**Example:**
```yaml
dashboard:
  port: 8080              # Standard HTTP port
  host: "0.0.0.0"         # Bind to all interfaces
  auto_refresh: false     # Disable auto-refresh for performance
  cache_duration: 600     # 10-minute cache
  max_concurrent_users: 50  # Support more users
```

### **Tracking Configuration** ⭐ NEW v0.2.0
Controls effectiveness tracking and analytics:

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `enabled` | true | Enable effectiveness tracking | true/false |
| `sampling_rate` | 1.0 | Sampling rate for tracking | 0.0-1.0 |
| `session_timeout_minutes` | 30 | Session timeout | 5-480 |
| `data_retention_days` | 90 | Days to retain data | 7-365 |
| `anonymize_data` | true | Anonymize sensitive data | true/false |

**Example:**
```yaml
tracking:
  enabled: true
  sampling_rate: 0.8        # Track 80% of operations
  session_timeout_minutes: 60  # 1-hour sessions
  data_retention_days: 30   # Keep 30 days only
  anonymize_data: true      # Always anonymize
```

### **Privacy Configuration** ⭐ ENHANCED v0.2.0
Controls privacy and security settings:

| Setting | Default | Description | Valid Values |
|---------|---------|-------------|--------------|
| `local_only` | true | Keep all processing local | true/false |
| `encrypt_storage` | true | Encrypt stored data | true/false |
| `auto_cleanup_days` | 90 | Auto-cleanup after days | 7-365 |
| `require_consent` | true | Require user consent | true/false |

**Example:**
```yaml
privacy:
  local_only: true          # Never send data externally
  encrypt_storage: true     # Always encrypt
  auto_cleanup_days: 60     # Cleanup after 60 days
  require_consent: false    # Auto-consent for team use
```

## 🎯 **Configuration Profiles**

### **Development Profile**
Optimized for development and debugging:

```yaml
# ~/.context_cleaner/config-dev.yaml
analysis:
  health_thresholds:
    excellent: 85
    good: 65
    fair: 45
  max_context_size: 200000

dashboard:
  port: 8547
  host: localhost
  auto_refresh: true
  cache_duration: 60      # Short cache for development

tracking:
  enabled: true
  sampling_rate: 1.0      # Track everything
  session_timeout_minutes: 15  # Short sessions
  data_retention_days: 30

privacy:
  local_only: true
  encrypt_storage: false  # Faster for development
  require_consent: false

log_level: "DEBUG"
```

**Usage:**
```bash
context-cleaner --config ~/.context_cleaner/config-dev.yaml dashboard
```

### **Production Profile**
Optimized for production use:

```yaml
# ~/.context_cleaner/config-prod.yaml
analysis:
  health_thresholds:
    excellent: 92
    good: 75
    fair: 58
  max_context_size: 100000
  circuit_breaker_threshold: 3

dashboard:
  port: 8548
  host: "127.0.0.1"      # Localhost only
  auto_refresh: false     # Disable for performance
  cache_duration: 900     # 15-minute cache
  max_concurrent_users: 5

tracking:
  enabled: true
  sampling_rate: 0.9      # 90% sampling for performance
  session_timeout_minutes: 45
  data_retention_days: 120

privacy:
  local_only: true
  encrypt_storage: true
  auto_cleanup_days: 120
  require_consent: true

log_level: "WARNING"      # Minimal logging
```

### **Team Profile**
Optimized for team environments:

```yaml
# ~/.context_cleaner/config-team.yaml
analysis:
  max_context_size: 150000    # Allow larger team contexts

dashboard:
  port: 8548
  host: "0.0.0.0"            # Allow network access
  max_concurrent_users: 25    # Support team members

tracking:
  enabled: true
  sampling_rate: 1.0
  data_retention_days: 180    # Longer retention for trends
  anonymize_data: true        # Always anonymize for teams

privacy:
  local_only: true            # Keep data local per machine
  encrypt_storage: true       # Always encrypt
  require_consent: false      # Pre-consented for team

log_level: "INFO"
```

## 📱 **Platform-Specific Configuration**

### **macOS Configuration**
```yaml
# Optimized for macOS
data_directory: "~/Library/Application Support/ContextCleaner/data"

dashboard:
  host: "127.0.0.1"  # Localhost only for Gatekeeper
  
privacy:
  encrypt_storage: true  # Required for App Store compliance

analysis:
  max_context_size: 120000  # Conservative for M1/M2 memory
```

### **Windows Configuration**
```yaml
# Optimized for Windows
data_directory: "%LOCALAPPDATA%\\ContextCleaner\\data"

dashboard:
  port: 8548
  host: "localhost"

analysis:
  max_context_size: 100000  # Conservative for varied hardware

privacy:
  encrypt_storage: true     # Windows Defender compatibility
```

### **Linux Server Configuration**
```yaml
# Optimized for Linux servers
data_directory: "/opt/context-cleaner/data"

dashboard:
  port: 8548
  host: "0.0.0.0"          # Allow network access
  max_concurrent_users: 50

tracking:
  sampling_rate: 0.8       # Reduce load on servers
  data_retention_days: 365 # Longer retention

privacy:
  encrypt_storage: true
  auto_cleanup_days: 365
```

## 🔍 **Configuration Validation**

### **Validate Configuration**
```bash
# Show current configuration (validates on load)
context-cleaner config-show

# Test configuration with health check
context-cleaner health-check --detailed

# Validate specific config file
context-cleaner --config ./my-config.yaml config-show
```

### **Configuration Schema Validation**
Context Cleaner automatically validates configuration against its schema:

```bash
# This will show validation errors if configuration is invalid
context-cleaner --config invalid-config.yaml start

# Example error output:
# ❌ Configuration Error: 
# - analysis.max_context_size: Must be between 10000 and 1000000
# - dashboard.port: Must be between 1024 and 65535
# - tracking.sampling_rate: Must be between 0.0 and 1.0
```

### **Common Validation Errors**
```yaml
# ❌ INVALID CONFIGURATIONS

# Port out of range
dashboard:
  port: 80  # Error: Must be 1024+ for non-root users

# Invalid threshold ordering
analysis:
  health_thresholds:
    excellent: 60  # Error: Must be > good threshold
    good: 70
    fair: 80       # Error: Must be < good threshold

# Invalid sampling rate
tracking:
  sampling_rate: 1.5  # Error: Must be 0.0-1.0

# Invalid data retention
tracking:
  data_retention_days: 0  # Error: Must be 7-365
```

## 🛠️ **Advanced Configuration**

### **Multiple Configuration Files**
```bash
# Base configuration
context-cleaner --config base-config.yaml \
  --config override-config.yaml \
  dashboard

# Environment-specific overrides
context-cleaner --config config.yaml \
  --config config-$(hostname).yaml \
  start
```

### **Dynamic Configuration**
```bash
# Configuration with environment variable substitution
data_directory: "${HOME}/.context_cleaner/data"
dashboard:
  port: "${CONTEXT_CLEANER_PORT:-8548}"
  host: "${CONTEXT_CLEANER_HOST:-localhost}"
```

### **Configuration Templates**
Generate configuration templates:

```bash
# Generate default configuration file
context-cleaner config-show > ~/.context_cleaner/config.yaml

# Create profile-specific configurations
context-cleaner config-show | \
  sed 's/port: 8548/port: 8547/' | \
  sed 's/log_level: INFO/log_level: DEBUG/' > config-dev.yaml
```

## 🧪 **Testing Configuration**

### **Configuration Test Script**
```bash
#!/bin/bash
# test-config.sh - Test configuration settings

echo "Testing Context Cleaner Configuration"
echo "======================================"

# Test basic configuration loading
echo "1. Testing configuration loading..."
context-cleaner config-show > /dev/null && echo "✅ Configuration loads" || echo "❌ Configuration error"

# Test health check
echo "2. Testing health check..."
context-cleaner health-check --format json > health.json
if [[ $(jq -r '.status' health.json) == "HEALTHY" ]]; then
  echo "✅ System healthy"
else
  echo "❌ Health check failed"
  jq '.issues' health.json
fi

# Test dashboard port
echo "3. Testing dashboard port..."
PORT=$(context-cleaner config-show | grep -A5 dashboard | grep port | awk '{print $2}')
if nc -z localhost $PORT 2>/dev/null; then
  echo "⚠️  Port $PORT already in use"
else
  echo "✅ Port $PORT available"
fi

# Test data directory permissions
echo "4. Testing data directory..."
DATA_DIR=$(context-cleaner config-show | grep data_directory | awk '{print $2}' | tr -d '"')
if [[ -d "$DATA_DIR" && -w "$DATA_DIR" ]]; then
  echo "✅ Data directory accessible"
else
  echo "❌ Data directory issue: $DATA_DIR"
fi

echo "Configuration test complete!"
```

## 📚 **Configuration Examples**

### **Minimal Configuration**
```yaml
# Minimal config with just essentials
dashboard:
  port: 8549

tracking:
  data_retention_days: 30

log_level: WARNING
```

### **Performance-Optimized Configuration**
```yaml
# High-performance configuration
analysis:
  max_context_size: 50000  # Smaller contexts

dashboard:
  cache_duration: 1800     # 30-minute cache
  max_concurrent_users: 5  # Limit users

tracking:
  sampling_rate: 0.5       # Sample 50%
  session_timeout_minutes: 15

privacy:
  encrypt_storage: false   # Faster (less secure)
```

### **Security-Focused Configuration**
```yaml
# Maximum security configuration
analysis:
  circuit_breaker_threshold: 1  # Fail immediately

dashboard:
  host: "127.0.0.1"             # Localhost only
  max_concurrent_users: 1       # Single user

tracking:
  anonymize_data: true          # Always anonymize
  data_retention_days: 7        # Minimal retention

privacy:
  local_only: true              # Never network
  encrypt_storage: true         # Always encrypt
  auto_cleanup_days: 7          # Aggressive cleanup
  require_consent: true         # Always ask

log_level: "ERROR"              # Minimal logging
```

---

**Context Cleaner Configuration Reference** - Complete configuration guide for v0.3.0

*Need help with configuration? Check the [Troubleshooting Guide](troubleshooting.md) or [CLI Reference](cli-reference.md).*