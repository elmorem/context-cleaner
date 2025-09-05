#!/usr/bin/env python3
"""
Test runner for Context Rot Meter comprehensive test suite.

This script provides different test execution modes:
- Unit tests only
- Integration tests only 
- Performance tests only
- All tests
- Production readiness tests
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

def run_command(command, description):
    """Run a command and capture results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('='*60)
    
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def run_unit_tests():
    """Run unit tests for all components."""
    test_files = [
        'tests/context_rot/test_security.py',
        'tests/context_rot/test_analyzer.py',
        'tests/context_rot/test_ml_analysis.py',
        'tests/context_rot/test_adaptive_thresholds.py',
        'tests/context_rot/test_widget.py'
    ]
    
    success = True
    for test_file in test_files:
        component_name = Path(test_file).stem.replace('test_', '')
        cmd = ['python', '-m', 'pytest', test_file, '-v', '--tb=short']
        if not run_command(cmd, f"Unit tests for {component_name}"):
            success = False
    
    return success

def run_integration_tests():
    """Run integration tests."""
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_integration.py', '-v', '--tb=short']
    return run_command(cmd, "Integration tests")

def run_performance_tests():
    """Run performance tests."""
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_performance.py', '-v', '-m', 'performance', '--tb=short']
    return run_command(cmd, "Performance tests")

def run_stress_tests():
    """Run stress tests."""
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_performance.py', '-v', '-m', 'stress', '--tb=short']
    return run_command(cmd, "Stress tests")

def run_production_readiness_tests():
    """Run production readiness validation."""
    print(f"\n{'='*60}")
    print("PRODUCTION READINESS VALIDATION")
    print('='*60)
    
    # Run comprehensive test suite
    success = True
    
    # 1. Security tests
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_security.py', '-v']
    if not run_command(cmd, "Security validation"):
        success = False
    
    # 2. Performance benchmarks
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_performance.py', '-v', '-m', 'performance']
    if not run_command(cmd, "Performance benchmarks"):
        success = False
    
    # 3. Integration validation
    cmd = ['python', '-m', 'pytest', 'tests/context_rot/test_integration.py::TestContextRotProductionReadiness', '-v']
    if not run_command(cmd, "Production integration validation"):
        success = False
    
    return success

def run_all_tests():
    """Run all tests in sequence."""
    print(f"\n{'='*60}")
    print("COMPREHENSIVE CONTEXT ROT METER TEST SUITE")
    print('='*60)
    
    results = {
        'Unit Tests': run_unit_tests(),
        'Integration Tests': run_integration_tests(), 
        'Performance Tests': run_performance_tests()
    }
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print('='*60)
    
    total_passed = 0
    for test_type, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED" 
        print(f"{test_type}: {status}")
        if passed:
            total_passed += 1
    
    print(f"\nOverall: {total_passed}/{len(results)} test categories passed")
    
    if total_passed == len(results):
        print("🎊 ALL TESTS PASSED - Context Rot Meter is ready for production!")
        return True
    else:
        print("💥 Some tests failed. Please review and fix issues before deployment.")
        return False

def run_quick_validation():
    """Run quick validation tests."""
    print("Running quick validation tests...")
    
    cmd = [
        'python', '-m', 'pytest', 
        'tests/context_rot/',
        '-v',
        '--tb=short',
        '-x',  # Stop on first failure
        '--maxfail=5'  # Stop after 5 failures
    ]
    
    return run_command(cmd, "Quick validation")

def check_dependencies():
    """Check that required dependencies are available."""
    print("Checking dependencies...")
    
    required_packages = [
        'pytest',
        'asyncio',
        'psutil'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - missing")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Please install missing packages before running tests.")
        return False
    
    print("All dependencies available.")
    return True

def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description='Context Rot Meter Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Modes:
  unit          Run unit tests only
  integration   Run integration tests only
  performance   Run performance tests only
  stress        Run stress tests only
  production    Run production readiness validation
  quick         Run quick validation (fast)
  all           Run all test categories (default)

Examples:
  python test_runner.py                    # Run all tests
  python test_runner.py unit               # Run unit tests only
  python test_runner.py performance        # Run performance tests only
  python test_runner.py production         # Validate production readiness
        """
    )
    
    parser.add_argument(
        'mode',
        nargs='?',
        default='all',
        choices=['unit', 'integration', 'performance', 'stress', 'production', 'quick', 'all'],
        help='Test mode to run (default: all)'
    )
    
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Check dependencies before running tests'
    )
    
    args = parser.parse_args()
    
    # Check dependencies if requested
    if args.check_deps and not check_dependencies():
        return 1
    
    # Run tests based on mode
    success = False
    
    if args.mode == 'unit':
        success = run_unit_tests()
    elif args.mode == 'integration':
        success = run_integration_tests()
    elif args.mode == 'performance':
        success = run_performance_tests()
    elif args.mode == 'stress':
        success = run_stress_tests()
    elif args.mode == 'production':
        success = run_production_readiness_tests()
    elif args.mode == 'quick':
        success = run_quick_validation()
    elif args.mode == 'all':
        success = run_all_tests()
    else:
        print(f"Unknown mode: {args.mode}")
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)