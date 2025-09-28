#!/usr/bin/env python3
"""
Integration Verification Script
Validates that Context Cleaner with Claude Code integration is working correctly.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report success/failure."""
    print(f"🔍 Testing: {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            return True
        else:
            print(f"❌ {description} - FAILED")
            print(f"   Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - FAILED")
        print(f"   Exception: {e}")
        return False

def main():
    """Run all verification tests."""
    print("🚀 Context Cleaner Integration Verification")
    print("=" * 50)
    
    tests = [
        ("context-cleaner --help", "CLI Help Command"),
        ("context-cleaner optimize --help", "Optimize Command Help"),
        ("context-cleaner optimize --dashboard --format json", "JSON Dashboard Output"),
        ("context-cleaner optimize --quick", "Quick Optimization"),
        ("context-cleaner optimize --preview", "Preview Mode"),
        ("context-cleaner run --help", "Run Command Help"),
        ("context-cleaner run --status-only --json", "Run Status JSON"),
        ("context-cleaner analyze --help", "Analysis Command Help"),
    ]
    
    passed = 0
    total = len(tests)
    
    for cmd, description in tests:
        if run_command(cmd, description):
            passed += 1
    
    print()
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Integration is working correctly!")
        print()
        print("🎯 Available Commands:")
        print("   context-cleaner optimize --dashboard --format json  # Dashboard data feed")
        print("   context-cleaner optimize --quick      # Fast cleanup")
        print("   context-cleaner optimize --preview    # Preview changes")
        print("   context-cleaner run --status-only --json  # Service status snapshot")
        print("   context-cleaner analyze              # Productivity analysis")
        print()
        print("🔗 For Claude Code integration, run:")
        print("   python install_claude_integration.py")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
