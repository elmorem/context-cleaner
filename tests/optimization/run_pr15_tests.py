"""
Test Runner for PR15.3 Intelligent Cache-Based Optimization

This script provides a comprehensive test runner specifically for PR15.3 components,
with different test categories and execution modes to support development and CI/CD.

Usage:
    python tests/optimization/run_pr15_tests.py [options]

Options:
    --category {unit,integration,performance,all}  Test category to run
    --component {dashboard,recommender,analytics,reports,strategies,all}  Component to test
    --verbose                                      Verbose output
    --coverage                                     Run with coverage report
    --no-sklearn                                   Test without sklearn dependencies
    --no-numpy                                     Test without numpy dependencies
    --fast                                         Skip slow tests
    --ci                                          CI mode (strict, no interactive)
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd, verbose=False, capture_output=False):
    """Run a command and handle output."""
    if verbose:
        print(f"Running: {' '.join(cmd)}")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, check=False)
            return result.returncode, "", ""
    except Exception as e:
        print(f"Error running command: {e}")
        return 1, "", str(e)


def get_test_files(category, component):
    """Get list of test files based on category and component."""
    base_dir = Path(__file__).parent
    test_files = []
    
    if component == "all":
        if category == "unit":
            test_files = [
                "test_cache_dashboard.py",
                "test_intelligent_recommender.py", 
                "test_cross_session_analytics.py"
            ]
        elif category == "integration":
            test_files = ["test_integration.py"]
        elif category == "performance":
            test_files = [
                "test_cache_dashboard.py::TestCacheDashboardPerformance",
                "test_intelligent_recommender.py::TestIntelligentRecommenderPerformance",
                "test_cross_session_analytics.py::TestPerformanceAndMemory",
                "test_integration.py::TestIntegratedPerformance"
            ]
        else:  # all
            test_files = [
                "test_cache_dashboard.py",
                "test_intelligent_recommender.py",
                "test_cross_session_analytics.py", 
                "test_integration.py"
            ]
    else:
        # Specific component
        component_map = {
            "dashboard": "test_cache_dashboard.py",
            "recommender": "test_intelligent_recommender.py",
            "analytics": "test_cross_session_analytics.py",
            "reports": "test_advanced_reports.py",  # Not implemented yet
            "strategies": "test_personalized_strategies.py"  # Not implemented yet
        }
        
        if component in component_map:
            test_file = component_map[component]
            if category == "performance":
                if component == "dashboard":
                    test_files = [f"{test_file}::TestCacheDashboardPerformance"]
                elif component == "recommender":
                    test_files = [f"{test_file}::TestIntelligentRecommenderPerformance"]
                elif component == "analytics":
                    test_files = [f"{test_file}::TestPerformanceAndMemory"]
                else:
                    test_files = [test_file]
            else:
                test_files = [test_file]
    
    # Convert to full paths and filter existing files
    full_paths = []
    for test_file in test_files:
        full_path = base_dir / test_file.split("::")[0]
        if full_path.exists():
            full_paths.append(str(base_dir / test_file))
    
    return full_paths


def build_pytest_command(test_files, args):
    """Build pytest command with appropriate options."""
    cmd = ["python", "-m", "pytest"]
    
    # Add test files
    cmd.extend(test_files)
    
    # Add pytest options
    cmd.extend(["-v", "--tb=short"])
    
    # Handle coverage
    if args.coverage:
        cmd.extend([
            "--cov=src/context_cleaner/optimization",
            "--cov-report=html:htmlcov/pr15_coverage",
            "--cov-report=term-missing"
        ])
    
    # Handle verbose
    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-q")
    
    # Handle fast mode (skip slow tests)
    if args.fast:
        cmd.extend(["-m", "not slow"])
    
    # Handle CI mode
    if args.ci:
        cmd.extend(["--strict-markers", "--tb=short"])
        # Set environment variables for CI
        os.environ["CI"] = "true"
        os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")
    
    # Handle dependency testing
    if args.no_sklearn:
        os.environ["SKLEARN_DISABLED"] = "true"
    if args.no_numpy:
        os.environ["NUMPY_DISABLED"] = "true"
    
    return cmd


def print_test_summary():
    """Print test summary and information."""
    print("=" * 80)
    print("PR15.3 Intelligent Cache-Based Optimization Test Suite")
    print("=" * 80)
    print("\nThis test suite validates:")
    print("• Critical import violations and sklearn dependency handling")
    print("• Data type safety and edge case handling")
    print("• Complex async operations and concurrent execution")
    print("• Error handling and graceful fallback mechanisms")
    print("• Integration between optimization modules")
    print("• Performance under realistic workloads")
    print("• Memory efficiency and resource management")
    print()


def print_test_categories():
    """Print available test categories."""
    print("Available Test Categories:")
    print("• unit: Unit tests for individual components")
    print("• integration: Integration tests between modules")
    print("• performance: Performance and scalability tests")
    print("• all: All test categories")
    print()
    
    print("Available Components:")
    print("• dashboard: CacheEnhancedDashboard tests")
    print("• recommender: IntelligentRecommendationEngine tests") 
    print("• analytics: CrossSessionAnalyticsEngine tests")
    print("• reports: AdvancedReportingSystem tests (planned)")
    print("• strategies: PersonalizedOptimizationEngine tests (planned)")
    print("• all: All components")
    print()


def check_dependencies():
    """Check if required dependencies are available."""
    missing_deps = []
    
    try:
        import pytest
    except ImportError:
        missing_deps.append("pytest")
    
    try:
        import pytest_asyncio
    except ImportError:
        missing_deps.append("pytest-asyncio")
    
    if missing_deps:
        print(f"Missing required dependencies: {', '.join(missing_deps)}")
        print("Install with: pip install pytest pytest-asyncio pytest-cov")
        return False
    
    return True


def run_dependency_test_scenarios(test_files, args):
    """Run tests with different dependency scenarios."""
    print("\n" + "=" * 60)
    print("Running Dependency Test Scenarios")
    print("=" * 60)
    
    scenarios = [
        ("Standard (all dependencies)", {}),
        ("No sklearn", {"SKLEARN_DISABLED": "true"}),
        ("No numpy", {"NUMPY_DISABLED": "true"}),
        ("No ML dependencies", {"SKLEARN_DISABLED": "true", "NUMPY_DISABLED": "true"})
    ]
    
    results = []
    
    for scenario_name, env_vars in scenarios:
        print(f"\nRunning scenario: {scenario_name}")
        print("-" * 40)
        
        # Set environment variables
        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            # Build and run command
            cmd = build_pytest_command(test_files, args)
            cmd.extend(["-x"])  # Stop on first failure
            
            returncode, stdout, stderr = run_command(cmd, capture_output=True)
            
            if returncode == 0:
                print(f"✓ {scenario_name}: PASSED")
                results.append((scenario_name, "PASSED"))
            else:
                print(f"✗ {scenario_name}: FAILED")
                results.append((scenario_name, "FAILED"))
                if args.verbose:
                    print("STDERR:", stderr[-500:])  # Last 500 chars
        
        finally:
            # Restore environment
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
    
    print("\n" + "=" * 60)
    print("Dependency Test Results:")
    for scenario, result in results:
        status_symbol = "✓" if result == "PASSED" else "✗"
        print(f"  {status_symbol} {scenario}: {result}")
    
    return all(result == "PASSED" for _, result in results)


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for PR15.3 Intelligent Cache-Based Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--category",
        choices=["unit", "integration", "performance", "all"],
        default="unit",
        help="Test category to run"
    )
    
    parser.add_argument(
        "--component", 
        choices=["dashboard", "recommender", "analytics", "reports", "strategies", "all"],
        default="all",
        help="Component to test"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true", 
        help="Run with coverage report"
    )
    
    parser.add_argument(
        "--no-sklearn",
        action="store_true",
        help="Test without sklearn dependencies"
    )
    
    parser.add_argument(
        "--no-numpy",
        action="store_true",
        help="Test without numpy dependencies"
    )
    
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip slow tests"
    )
    
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode (strict, no interactive)"
    )
    
    parser.add_argument(
        "--test-dependencies",
        action="store_true",
        help="Test all dependency scenarios"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show test information and exit"
    )
    
    args = parser.parse_args()
    
    if args.info:
        print_test_summary()
        print_test_categories()
        return 0
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Print summary
    print_test_summary()
    
    # Get test files
    test_files = get_test_files(args.category, args.component)
    
    if not test_files:
        print(f"No test files found for category '{args.category}' and component '{args.component}'")
        print("Available test files:")
        base_dir = Path(__file__).parent
        for test_file in base_dir.glob("test_*.py"):
            print(f"  {test_file.name}")
        return 1
    
    print(f"Running {args.category} tests for {args.component}")
    print(f"Test files: {len(test_files)}")
    for test_file in test_files:
        print(f"  • {Path(test_file).name}")
    print()
    
    # Run dependency test scenarios if requested
    if args.test_dependencies:
        success = run_dependency_test_scenarios(test_files, args)
        return 0 if success else 1
    
    # Build and run pytest command
    cmd = build_pytest_command(test_files, args)
    
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    
    # Run tests
    returncode, stdout, stderr = run_command(cmd, verbose=args.verbose)
    
    # Print results
    print("\n" + "=" * 60)
    if returncode == 0:
        print("✓ All tests PASSED!")
    else:
        print(f"✗ Tests FAILED (exit code: {returncode})")
        if not args.verbose and stderr:
            print("Error output:")
            print(stderr[-1000:])  # Last 1000 chars
    
    # Coverage report info
    if args.coverage and returncode == 0:
        print("\nCoverage report generated:")
        print("  • Terminal: shown above")
        print("  • HTML: htmlcov/pr15_coverage/index.html")
    
    return returncode


if __name__ == "__main__":
    sys.exit(main())