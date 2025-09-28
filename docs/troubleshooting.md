# Context Cleaner Troubleshooting Guide

Comprehensive troubleshooting guide for Context Cleaner v0.2.0, including solutions for common issues and debugging steps.

## 🔍 **Quick Diagnosis**

### **Run Health Check First**
Before diving into specific issues, always start with the built-in health check:

```bash
# Basic health check
context-cleaner health-check

# Detailed diagnostics
context-cleaner health-check --detailed

# Auto-fix common issues
context-cleaner health-check --fix-issues

# JSON output for programmatic analysis  
context-cleaner health-check --format json > health-report.json
```

### **Check System Status**
```bash
# Verify installation
context-cleaner --version

# Show current configuration
context-cleaner config-show

# List recent sessions
context-cleaner session list --limit 5
```

## 🚨 **Installation Issues**

### **Installation Failed**
```bash
# Problem: pip install context-cleaner fails
# Solutions:

# 1. Upgrade pip and try again
pip install --upgrade pip
pip install context-cleaner

# 2. Use explicit Python version
python3 -m pip install context-cleaner

# 3. Install from source if PyPI issues
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner
pip install -e .

# 4. Check Python version compatibility
python --version  # Must be 3.8+
```

### **Command Not Found**
```bash
# Problem: context-cleaner command not found after installation

# 1. Check if installed correctly
pip list | grep context-cleaner

# 2. Find installation path
python -c "import context_cleaner; print(context_cleaner.__file__)"

# 3. Add to PATH if needed (Linux/Mac)
export PATH="$PATH:$(python -m site --user-base)/bin"

# 4. Windows users - check Scripts directory
# Add C:\Users\USERNAME\AppData\Roaming\Python\PythonXX\Scripts to PATH
```

### **Permission Errors During Installation**
```bash
# Problem: Permission denied during pip install

# 1. Use user installation
pip install --user context-cleaner

# 2. Use virtual environment (recommended)
python -m venv context-cleaner-env
source context-cleaner-env/bin/activate  # Linux/Mac
# context-cleaner-env\Scripts\activate.bat  # Windows
pip install context-cleaner
```

## 🔧 **Configuration Issues**

### **Data Directory Problems**
```bash
# Problem: Cannot create or access data directory

# 1. Check permissions on home directory
ls -la ~/
chmod 755 ~/

# 2. Manually create directory with correct permissions
mkdir -p ~/.context_cleaner/data
chmod 700 ~/.context_cleaner
chmod 700 ~/.context_cleaner/data

# 3. Use custom data directory
context-cleaner --data-dir ./my-analytics-data run

# 4. Check disk space
df -h ~/.context_cleaner

# 5. Verify ownership
ls -la ~/.context_cleaner/
```

### **Configuration File Issues**
```bash
# Problem: Invalid configuration or YAML syntax errors

# 1. Show current configuration
context-cleaner config-show

# 2. Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('~/.context_cleaner/config.yaml'))"

# 3. Reset to defaults (removes custom config)
rm ~/.context_cleaner/config.yaml
context-cleaner run

# 4. Use environment variables instead
export CONTEXT_CLEANER_PORT=8111
export CONTEXT_CLEANER_DATA_DIR=~/custom-data
```

### **Port Conflicts**
```bash
# Problem: Dashboard port already in use

# 1. Use different port
context-cleaner run --dashboard-port 8111

# 2. Kill process using port 8110
lsof -ti:8110 | xargs kill -9  # Linux/Mac
netstat -ano | findstr :8110   # Windows

# 3. Set permanent custom port
export CONTEXT_CLEANER_PORT=8111
```

## 📊 **Analytics & Tracking Issues**

### **No Analytics Data Available**
```bash
# Problem: effectiveness command shows "No data available"

# 1. Verify tracking is enabled
context-cleaner config-show | grep -A 5 "tracking:"

# 2. Check if sessions exist
context-cleaner session list
ls -la ~/.context_cleaner/data/

# 3. Start a test session
context-cleaner session start --session-id "test-session"
context-cleaner optimize --preview
context-cleaner effectiveness --days 1

# 4. Check file permissions
ls -la ~/.context_cleaner/data/effectiveness/
```

### **Export Analytics Fails**
```bash
# Problem: export-analytics command fails or produces empty files

# 1. Check data directory contents
ls -la ~/.context_cleaner/data/effectiveness/

# 2. Test with different output location
context-cleaner export-analytics --output /tmp/test-export.json

# 3. Try smaller date range
context-cleaner export-analytics --days 1

# 4. Check available disk space
df -h ~/.context_cleaner

# 5. Validate existing data integrity
context-cleaner health-check --detailed | grep -i "data"
```

### **Effectiveness Statistics Incorrect**
```bash
# Problem: effectiveness statistics seem wrong or inconsistent

# 1. Check for data corruption
context-cleaner health-check --detailed --fix-issues

# 2. Review session data manually
ls -la ~/.context_cleaner/data/effectiveness/
cat ~/.context_cleaner/data/effectiveness/optimization_sessions.jsonl | tail -5

# 3. Verify time ranges
context-cleaner effectiveness --days 7 --detailed

# 4. Clear cache and rebuild
rm -rf ~/.context_cleaner/data/cache/
context-cleaner run
```

## 🌐 **Dashboard Issues**

### **Dashboard Won't Start**
```bash
# Problem: dashboard command fails or doesn't open browser

# 1. Check port availability
netstat -tuln | grep 8110  # Linux
netstat -an | findstr :8110  # Windows

# 2. Start with verbose logging
context-cleaner --verbose run

# 3. Try different host/port
CONTEXT_CLEANER_HOST=127.0.0.1 context-cleaner run --dashboard-port 8111

# 4. Start without browser auto-open
context-cleaner run --no-browser

# 5. Check firewall settings (Windows)
# Allow Python/context-cleaner through Windows Firewall
```

### **Dashboard Loads But Shows No Data**
```bash
# Problem: Dashboard interface loads but analytics panels are empty

# 1. Verify data exists
context-cleaner effectiveness --days 7

# 2. Check browser console for errors
# Open browser dev tools (F12) and look for JavaScript errors

# 3. Clear browser cache
# Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)

# 4. Try different browser
# Chrome, Firefox, Safari, Edge

# 5. Check data permissions
chmod -R 600 ~/.context_cleaner/data/
```

### **Dashboard Performance Issues**
```bash
# Problem: Dashboard is slow or unresponsive

# 1. Check system resources
top | grep python  # Linux/Mac
# Task Manager on Windows

# 2. Reduce data load
context-cleaner run --no-docker --no-jsonl

# 3. Clear old analytics data
context-cleaner export-analytics --days 90 --output backup.json
# Then remove old data files

# 4. Monitor resource usage
context-cleaner monitor status
```

## 🔒 **Security & Privacy Issues**

### **Permission Denied Errors**
```bash
# Problem: Cannot read/write analytics files

# 1. Fix data directory permissions
chmod 700 ~/.context_cleaner/
chmod -R 600 ~/.context_cleaner/data/

# 2. Check file ownership
ls -la ~/.context_cleaner/
chown -R $(whoami) ~/.context_cleaner/

# 3. SELinux issues (CentOS/RHEL/Fedora)
setsebool -P httpd_can_network_connect 1
setsebool -P httpd_read_user_content 1
```

### **Data Sanitization Issues**
```bash
# Problem: Concerned about sensitive data in analytics

# 1. Verify sanitization is working
context-cleaner health-check --detailed | grep -i "security"

# 2. Export and inspect data
context-cleaner export-analytics --output inspect.json
grep -E "(email|password|token|key)" inspect.json || echo "No sensitive data found"

# 3. Enable stricter privacy settings
export CONTEXT_CLEANER_LOCAL_ONLY=true

# 4. Review privacy controls
context-cleaner privacy show-info
```

### **File Corruption Concerns**
```bash
# Problem: Worried about data integrity

# 1. Run comprehensive health check
context-cleaner health-check --detailed --fix-issues

# 2. Verify JSON file integrity
find ~/.context_cleaner/data -name "*.json" -exec python -m json.tool {} \; > /dev/null && echo "All JSON files valid"

# 3. Check for race condition protection
ps aux | grep context-cleaner  # Should not see multiple instances

# 4. Backup and restore test
context-cleaner export-analytics --output backup-test.json
context-cleaner privacy delete-all
# Restore from backup if needed
```

## ⚡ **Performance Issues**

### **High CPU Usage**
```bash
# Problem: context-cleaner using too much CPU

# 1. Check monitoring status
context-cleaner monitor status

# 2. Stop real-time monitoring if running
pkill -f "context-cleaner monitor"

# 3. Reduce sampling rate
# Edit ~/.context_cleaner/config.yaml
# tracking:
#   sampling_rate: 0.5  # Reduce from 1.0

# 4. Monitor resource usage
htop | grep context  # Linux
# Activity Monitor on Mac, Task Manager on Windows
```

### **High Memory Usage**
```bash
# Problem: Memory usage growing over time

# 1. Check for memory leaks
context-cleaner monitor status --format json | jq '.memory_usage'

# 2. Clear session cache
rm -rf ~/.context_cleaner/data/cache/

# 3. Reduce data retention period
# Edit config: data_retention_days: 30  # Reduce from 90

# 4. Restart monitoring
context-cleaner session end  # End current session
context-cleaner run  # Start fresh
```

### **Slow Analytics Queries**
```bash
# Problem: effectiveness and export commands are slow

# 1. Check data size
du -sh ~/.context_cleaner/data/effectiveness/

# 2. Reduce query scope
context-cleaner effectiveness --days 7  # Instead of 30

# 3. Rebuild session index
rm ~/.context_cleaner/data/effectiveness/sessions_index.json
context-cleaner run

# 4. Monitor I/O performance
iostat -x 1  # Linux
```

## 🧪 **Development & Testing Issues**

### **Test Failures**
```bash
# Problem: pytest tests failing during development

# 1. Install test dependencies
pip install -e .[dev]

# 2. Run specific test categories
pytest tests/cli/test_pr20_analytics_integration.py -v

# 3. Check test environment
pytest --version
python -m pytest --markers

# 4. Run tests in isolated environment
python -m venv test-env
source test-env/bin/activate
pip install -e .[dev]
pytest
```

### **Development Setup Issues**
```bash
# Problem: Cannot set up development environment

# 1. Clone with all dependencies
git clone https://github.com/context-cleaner/context-cleaner.git
cd context-cleaner
pip install -e .[dev]

# 2. Install pre-commit hooks
pre-commit install

# 3. Run code quality checks
black --check src/ tests/
flake8 src/ tests/
mypy src/

# 4. Verify development installation
context-cleaner --version
pytest --version
```

## 📱 **Platform-Specific Issues**

### **macOS Issues**
```bash
# Problem: Permission issues or signing warnings

# 1. Xcode command line tools
xcode-select --install

# 2. Python installation via Homebrew (recommended)
brew install python@3.9
pip3 install context-cleaner

# 3. Fix PATH issues
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 4. Gatekeeper issues
# System Preferences > Security & Privacy > Allow apps from App Store and identified developers
```

### **Windows Issues**
```bash
# Problem: Windows-specific installation or runtime issues

# 1. Use Windows Subsystem for Linux (WSL) if possible
wsl --install
# Then install in WSL environment

# 2. PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Long path support
# Enable via Group Policy or Registry for paths > 260 characters

# 4. Antivirus interference
# Add Python and pip to antivirus exclusions
```

### **Linux Distribution Issues**
```bash
# CentOS/RHEL/Fedora
sudo dnf install python3-pip python3-devel
pip3 install --user context-cleaner

# Ubuntu/Debian
sudo apt update
sudo apt install python3-pip python3-venv
pip3 install --user context-cleaner

# Arch Linux
sudo pacman -S python-pip
pip install --user context-cleaner

# Fix PATH issues
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 🔍 **Advanced Debugging**

### **Enable Debug Logging**
```bash
# Set debug log level
export CONTEXT_CLEANER_LOG_LEVEL=DEBUG

# Run command with verbose output
context-cleaner --verbose health-check --detailed

# Check logs
tail -f ~/.context_cleaner/logs/context-cleaner.log
```

### **Trace File Operations**
```bash
# Linux: Monitor file operations
strace -e file context-cleaner run 2>&1 | grep context_cleaner

# macOS: Use fs_usage
sudo fs_usage -w -f filesys | grep context_cleaner

# Check open file handles
lsof | grep context_cleaner
```

### **Network Debugging**
```bash
# Monitor network connections (should be minimal)
netstat -tuln | grep python

# Verify no external connections (privacy check)
tcpdump -i any host not 127.0.0.1 and host not localhost
# Should show no traffic from context-cleaner
```

### **Memory Profiling**
```python
# Create debug script: debug_memory.py
import tracemalloc
import context_cleaner

tracemalloc.start()

# Run your Context Cleaner operations here
# ...

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

## 🆘 **Getting Help**

### **Gather Debug Information**
When reporting issues, include this diagnostic information:

```bash
#!/bin/bash
# debug-info.sh - Gather comprehensive debug information

echo "=== Context Cleaner Debug Information ==="
echo "Date: $(date)"
echo

echo "=== System Information ==="
uname -a
python --version
pip --version
echo

echo "=== Context Cleaner Status ==="
context-cleaner --version
context-cleaner health-check --detailed --format json > health.json
echo "Health check saved to health.json"
echo

echo "=== Configuration ==="
context-cleaner config-show
echo

echo "=== Recent Sessions ==="
context-cleaner session list --limit 5 --format json
echo

echo "=== Data Directory ==="
ls -la ~/.context_cleaner/
du -sh ~/.context_cleaner/data/
echo

echo "=== System Resources ==="
ps aux | grep context-cleaner | grep -v grep
df -h ~/.context_cleaner/
echo

echo "Debug information collected!"
echo "Please include health.json and this output when reporting issues."
```

### **Community Support**
- **GitHub Issues**: [Report bugs and feature requests](https://github.com/context-cleaner/context-cleaner/issues)
- **GitHub Discussions**: [Community support and questions](https://github.com/context-cleaner/context-cleaner/discussions)
- **Documentation**: [Complete guides and references](https://context-cleaner.readthedocs.io)

### **Professional Support**
For enterprise support, custom integrations, and consulting services, contact team@context-cleaner.dev

---

**Context Cleaner Troubleshooting Guide** - Comprehensive problem-solving for v0.2.0

*Still having issues? Check the [FAQ](faq.md) or [CLI Reference](cli-reference.md) for additional help.*
# ✅ **Supervisor & Watchdog**

### **Supervisor unavailable / fallback triggered**

**Symptom:** `context-cleaner run` prints `⚠️ Supervisor unavailable; using fallback event loop handling` and watchdog telemetry is missing.

**Checklist:**

1. **Stale socket file** – remove the unix socket and retry:
   ```bash
   rm -f $(python -c "from context_cleaner.ipc.client import default_supervisor_endpoint; print(default_supervisor_endpoint())")
   ```
2. **Previous supervisor still running** – stop all services:
   ```bash
   context-cleaner stop --force --no-discovery
   ```
3. **Permissions** – ensure `$XDG_RUNTIME_DIR/context-cleaner` exists and is writable.
4. **Retry** – launch again with `context-cleaner run` once the above checks pass.

### **Watchdog reports stale heartbeat**

`context-cleaner run --status-only --json` exposes restart telemetry under the `watchdog` key.

- If `running: false` or `last_heartbeat_at` is older than 30s, inspect the restart history:
  ```bash
  context-cleaner run --status-only --json | jq '.watchdog'
  ```
- The watchdog automatically attempts up to three restarts with backoff. If restarts fail, clean up manually:
  ```bash
  context-cleaner stop --force
  context-cleaner run
  ```
- To prune stale registry entries:
  ```bash
  context-cleaner debug registry prune --type supervisor
  ```

### **Checking supervisor health**

- Text mode: `context-cleaner run --status-only` now prints a human-readable watchdog section.
- JSON mode: `context-cleaner run --status-only --json | jq '.watchdog'`.
- Audit log: review `logs/supervisor/audit.log` for recent activity.
