#!/usr/bin/env python3
"""
Test Runner for Enhanced Token Counting System

Comprehensive test suite for validating the 90% token undercount fix.
Run this script to validate that the Enhanced Token Counting System
properly addresses the token undercount issue.
"""

import sys
import subprocess
import time
from pathlib import Path


def run_test_suite():
    """Run the complete enhanced token counting test suite."""
    print("🧪 Enhanced Token Counting System - Comprehensive Test Suite")
    print("=" * 80)
    print("Validating the 90% token undercount fix implementation")
    print()
    
    # Define test modules in order of complexity
    test_modules = [
        {
            "name": "Test Fixtures",
            "module": "tests.analysis.fixtures",
            "description": "Mock data and test utilities for undercount scenarios"
        },
        {
            "name": "Core Functionality",
            "module": "tests.analysis.test_enhanced_token_counter",
            "description": "Unit tests for EnhancedTokenCounterService and core components"
        },
        {
            "name": "Dashboard Integration", 
            "module": "tests.analysis.test_dashboard_integration",
            "description": "Integration tests for dashboard compatibility and fallback handling"
        },
        {
            "name": "Undercount Validation",
            "module": "tests.analysis.test_undercount_validation", 
            "description": "Critical tests validating 90% undercount detection and comparison"
        },
        {
            "name": "Performance Testing",
            "module": "tests.analysis.test_performance",
            "description": "Performance tests for large file processing and scalability"
        },
        {
            "name": "CLI Commands",
            "module": "tests.analysis.test_cli_commands",
            "description": "CLI interface tests for enhanced token analysis commands"
        },
        {
            "name": "Complete Integration",
            "module": "tests.analysis.test_integration_complete",
            "description": "End-to-end integration tests simulating real-world scenarios"
        }
    ]
    
    results = []
    total_start_time = time.time()
    
    for i, test_module in enumerate(test_modules, 1):
        print(f"📋 [{i}/{len(test_modules)}] {test_module['name']}")
        print(f"    {test_module['description']}")
        print(f"    Module: {test_module['module']}")
        
        # Run the test module
        start_time = time.time()
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                test_module['module'].replace('.', '/') + '.py',
                "-v",
                "--tb=short",
                "--durations=5"
            ], capture_output=True, text=True)
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"    ✅ PASSED ({duration:.2f}s)")
                results.append(("PASSED", test_module['name'], duration))
            else:
                print(f"    ❌ FAILED ({duration:.2f}s)")
                print(f"    Error output: {result.stderr[:200]}...")
                results.append(("FAILED", test_module['name'], duration))
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"    💥 ERROR ({duration:.2f}s): {str(e)}")
            results.append(("ERROR", test_module['name'], duration))
        
        print()
    
    # Summary
    total_duration = time.time() - total_start_time
    passed = len([r for r in results if r[0] == "PASSED"])
    failed = len([r for r in results if r[0] == "FAILED"])
    errors = len([r for r in results if r[0] == "ERROR"])
    
    print("📊 Test Suite Summary")
    print("=" * 50)
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"💥 Errors: {errors}")
    print()
    
    if failed == 0 and errors == 0:
        print("🎉 All tests passed! Enhanced Token Counting System is working correctly.")
        print("✅ 90% token undercount issue has been successfully addressed.")
        print()
        print("Key validations completed:")
        print("  • File discovery: ALL files processed (vs current 10 file limit)")
        print("  • Line processing: Complete files processed (vs current 1000 line limit)")
        print("  • Content types: All message types processed (vs assistant only)")
        print("  • Session tracking: Comprehensive session-based analytics")
        print("  • API integration: Anthropic count-tokens API validation")
        print("  • Dashboard compatibility: Drop-in replacement functionality")
        print("  • Performance: Scales to large files and many files")
        print("  • Undercount detection: Accurately detects and quantifies undercount")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the failures above.")
        print("The Enhanced Token Counting System may need adjustments.")
        return 1


def run_specific_undercount_tests():
    """Run only the critical undercount detection tests."""
    print("🎯 Running Critical Undercount Detection Tests")
    print("=" * 60)
    
    critical_tests = [
        "tests/analysis/test_undercount_validation.py::TestUndercountDetection::test_severe_undercount_detection",
        "tests/analysis/test_undercount_validation.py::TestUndercountComparison::test_current_vs_enhanced_system_comparison", 
        "tests/analysis/test_enhanced_token_counter.py::TestEnhancedTokenCounterService::test_file_discovery_vs_current_limitation",
        "tests/analysis/test_enhanced_token_counter.py::TestEnhancedTokenCounterService::test_complete_file_processing_vs_line_limit",
        "tests/analysis/test_integration_complete.py::TestCompleteSystemIntegration::test_complete_undercount_detection_workflow"
    ]
    
    for test in critical_tests:
        print(f"Running: {test}")
        result = subprocess.run([
            sys.executable, "-m", "pytest", test, "-v"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ PASSED")
        else:
            print("  ❌ FAILED")
            print(f"  Error: {result.stderr[:100]}...")
        print()


def run_performance_benchmarks():
    """Run performance benchmarks to validate scalability."""
    print("⚡ Performance Benchmarks")
    print("=" * 40)
    
    perf_tests = [
        "tests/analysis/test_performance.py::TestLargeFileProcessing::test_large_single_file_processing",
        "tests/analysis/test_performance.py::TestLargeFileProcessing::test_multiple_large_files_processing",
        "tests/analysis/test_performance.py::TestLargeFileProcessing::test_memory_usage_with_large_files"
    ]
    
    for test in perf_tests:
        print(f"Benchmark: {test.split('::')[-1]}")
        result = subprocess.run([
            sys.executable, "-m", "pytest", test, "-v", "--tb=line"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ Performance criteria met")
        else:
            print("  ⚠️  Performance issues detected")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Token Counting System Test Runner")
    parser.add_argument("--mode", choices=["all", "critical", "performance"], default="all",
                       help="Test mode: all tests, critical undercount tests only, or performance benchmarks")
    
    args = parser.parse_args()
    
    if args.mode == "critical":
        run_specific_undercount_tests()
    elif args.mode == "performance":
        run_performance_benchmarks()
    else:
        sys.exit(run_test_suite())