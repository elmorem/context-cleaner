# Context Cleaner - Installation & Troubleshooting Guide

This comprehensive guide helps resolve common installation and runtime issues with Context Cleaner.

## 🚀 Quick Installation Verification

### 1. Verify Installation
```bash
# Check if Context Cleaner is installed
context-cleaner --version

# Expected output: Context Cleaner 0.1.0
```

### 2. Test Basic Functionality
```bash
# Test basic optimization (safe preview mode)
context-cleaner optimize --preview

# Expected output: Preview completed - no changes applied
```

### 3. Verify Claude Code Integration
```bash
# Test Claude Code command wrapper
python ~/.claude/commands/clean-context.py --help

# Expected output: Context optimization and health analysis usage info
```

---

## 📋 Common Installation Issues

### Issue 1: "command not found: context-cleaner"

**Symptoms:**
- `bash: context-cleaner: command not found`
- Package appears installed but CLI not accessible

**Solutions:**

#### Solution A: PATH Issues
```bash
# Check if Context Cleaner is in Python scripts directory
python -c "import context_cleaner; print(context_cleaner.__file__)"

# Add Python scripts to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$(python -m site --user-base)/bin"

# Or on macOS with Homebrew Python:
export PATH="$PATH:/opt/homebrew/bin"
```

#### Solution B: Virtual Environment Issues
```bash
# If using virtual environment, ensure it's activated
source venv/bin/activate  # or your venv path

# Reinstall in active environment
pip install --upgrade context-cleaner
```

#### Solution C: Permission Issues
```bash
# Install with user flag to avoid permission issues
pip install --user context-cleaner

# Or use sudo (not recommended)
sudo pip install context-cleaner
```

### Issue 2: Import Errors During Installation

**Symptoms:**
- `ModuleNotFoundError` during installation
- Dependency conflicts
- Build failures

**Solutions:**

#### Solution A: Update pip and setuptools
```bash
# Update core installation tools
pip install --upgrade pip setuptools wheel

# Clear pip cache
pip cache purge

# Reinstall Context Cleaner
pip install context-cleaner
```

#### Solution B: Dependency Conflicts
```bash
# Check for conflicting packages
pip check

# Create clean virtual environment
python -m venv context_cleaner_env
source context_cleaner_env/bin/activate
pip install context-cleaner
```

#### Solution C: Python Version Compatibility
```bash
# Check Python version (requires 3.8+)
python --version

# If using older Python, use pyenv or conda:
conda create -n context_cleaner python=3.11
conda activate context_cleaner
pip install context-cleaner
```

### Issue 3: Claude Code Integration Failures

**Symptoms:**
- `/clean-context` command not found
- Integration script fails
- Hook installation errors

**Solutions:**

#### Solution A: Manual Integration Setup
```bash
# Run integration installer directly
python -c "
import subprocess
import context_cleaner
from pathlib import Path
install_script = Path(context_cleaner.__file__).parent.parent / 'install_claude_integration.py'
subprocess.run(['python', str(install_script)])
"
```

#### Solution B: Check Claude Code Installation
```bash
# Verify Claude Code is installed
ls ~/.claude/

# Expected: commands/, hooks/, and other Claude Code directories
```

#### Solution C: Manual Hook Setup
```bash
# Create hooks directory if missing
mkdir -p ~/.claude/hooks/utils

# Create commands directory if missing  
mkdir -p ~/.claude/commands

# Re-run integration
context-cleaner install --claude-integration
```

---

## ⚡ Runtime Issues

### Issue 4: Performance Problems

**Symptoms:**
- Slow analysis (>5 seconds)
- High memory usage (>100MB)
- System responsiveness issues

**Solutions:**

#### Solution A: Reduce Analysis Scope
```bash
# Use quick mode for faster analysis
context-cleaner optimize --quick

# Check current performance
context-cleaner analyze --format json | grep performance
```

#### Solution B: Clear Cache and Data
```bash
# Clear analysis cache
rm -rf ~/.context_cleaner/cache/

# Reset to default configuration
context-cleaner config-show --reset
```

#### Solution C: System Resource Check
```bash
# Check available memory
free -h  # Linux
vm_stat  # macOS

# Check disk space
df -h

# Close other applications if resources are limited
```

### Issue 5: Permission and Access Issues

**Symptoms:**
- "Permission denied" errors
- Cannot create data directories
- Access denied to configuration files

**Solutions:**

#### Solution A: Fix Directory Permissions
```bash
# Create data directory with correct permissions
mkdir -p ~/.context_cleaner
chmod 755 ~/.context_cleaner

# Fix Claude Code directory permissions
chmod 755 ~/.claude
chmod 755 ~/.claude/commands
chmod 755 ~/.claude/hooks
```

#### Solution B: Run with Explicit Data Directory
```bash
# Use custom data directory
export CONTEXT_CLEANER_DATA_DIR="$HOME/context_cleaner_data"
mkdir -p "$CONTEXT_CLEANER_DATA_DIR"
context-cleaner optimize --quick
```

### Issue 6: Dashboard Access Issues

**Symptoms:**
- Dashboard won't start
- "Address already in use" errors
- Browser doesn't open automatically

**Solutions:**

#### Solution A: Use Different Port
```bash
# Try different port
context-cleaner run --dashboard-port 8111 --no-browser

# Then manually open: http://localhost:8111
```

#### Solution B: Kill Existing Processes
```bash
# Find and kill processes using default port
lsof -ti:8110 | xargs kill -9

# Restart dashboard orchestration
context-cleaner run
```

---

## 🔍 Diagnostic Commands

### System Information
```bash
# Complete system diagnostic
context-cleaner --version
python --version
pip list | grep context-cleaner

# Check installation location
python -c "import context_cleaner; print(context_cleaner.__file__)"

# Verify all dependencies
pip check context-cleaner
```

### Configuration Diagnosis
```bash
# Show current configuration
context-cleaner config-show

# Test configuration validity
context-cleaner config-show --validate

# Reset to defaults if needed
context-cleaner config-show --reset
```

### Performance Diagnosis
```bash
# Quick performance test
time context-cleaner optimize --preview

# Memory usage check
context-cleaner analyze --format json | jq '.performance'

# Recent error summary
context-cleaner analyze --errors --days 1
```

---

## 🛠️ Advanced Troubleshooting

### Enable Debug Logging
```bash
# Set debug environment variable
export CONTEXT_CLEANER_DEBUG=1

# Run command with verbose output
context-cleaner --verbose optimize --preview

# Check logs
tail -f ~/.context_cleaner/logs/context_cleaner.log
```

### Clean Reinstallation
```bash
# Complete removal and reinstall
pip uninstall context-cleaner
pip cache purge
rm -rf ~/.context_cleaner

# Reinstall from scratch
pip install context-cleaner
context-cleaner install --claude-integration
```

### Compatibility Testing
```bash
# Test with minimal environment
python -m venv test_env
source test_env/bin/activate
pip install context-cleaner

# Run basic tests
context-cleaner optimize --preview
context-cleaner run --no-browser &
curl http://localhost:8110/health
```

---

## 📞 Getting Help

### Before Reporting Issues

1. **Run diagnostics:**
   ```bash
   context-cleaner --version
   context-cleaner config-show
   python --version
   pip list | grep context-cleaner
   ```

2. **Check recent errors:**
   ```bash
   context-cleaner analyze --errors --days 1 --format json
   ```

3. **Try clean reinstallation** (steps above)

### Reporting Bugs

When reporting issues, please include:

- **System Information:**
  - Operating System and version
  - Python version
  - Context Cleaner version

- **Installation Method:**
  - pip, conda, or from source
  - Virtual environment details

- **Error Details:**
  - Complete error messages
  - Command that caused the issue
  - Output from diagnostic commands

- **Steps to Reproduce:**
  - Exact commands run
  - Expected vs actual behavior

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Complete API reference and guides
- **Privacy**: All diagnostics are local-only, no data transmitted

---

## ✅ Verification Checklist

After resolving issues, verify everything works:

- [ ] `context-cleaner --version` shows correct version
- [ ] `context-cleaner optimize --preview` completes successfully
- [ ] `context-cleaner run --no-browser` starts without errors
- [ ] `python ~/.claude/commands/clean-context.py --help` shows usage
- [ ] No error messages in `~/.context_cleaner/logs/`
- [ ] Performance is acceptable (< 2 seconds for basic operations)

---

## 🔒 Privacy Notes

Context Cleaner is designed with privacy-first principles:

- **Local Processing**: All analysis happens on your machine
- **No External Transmission**: No data sent to external servers
- **Encrypted Storage**: All data encrypted locally with AES-256
- **User Control**: Complete control over data retention and deletion

Troubleshooting commands are safe to run and don't compromise privacy.

---

*Last updated: v0.1.0 - August 29, 2025*
