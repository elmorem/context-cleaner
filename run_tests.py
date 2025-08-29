#!/usr/bin/env python3
"""
Comprehensive Test Runner for Context Cleaner
Runs test suites with different configurations and generates reports.
"""

import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any


class TestRunner:
    """Comprehensive test runner with multiple test categories."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.test_results = {}
        
    def run_unit_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run unit tests only."""
        print("🧪 Running Unit Tests...")
        cmd = ["python", "-m", "pytest", "-m", "unit"]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, "unit_tests")
        return result
    
    def run_integration_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run integration tests."""
        print("🔗 Running Integration Tests...")
        cmd = ["python", "-m", "pytest", "-m", "integration"]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, "integration_tests")
        return result
    
    def run_performance_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run performance and monitoring tests."""
        print("⚡ Running Performance Tests...")
        cmd = ["python", "-m", "pytest", "-m", "performance"]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, "performance_tests")
        return result
    
    def run_slow_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run slow tests (stress testing, etc)."""
        print("🐌 Running Slow Tests...")
        cmd = ["python", "-m", "pytest", "-m", "slow", "--timeout=300"]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, "slow_tests")
        return result
    
    def run_all_tests(self, verbose: bool = True, include_slow: bool = False) -> Dict[str, Any]:
        """Run all tests with comprehensive coverage."""
        print("🚀 Running All Tests...")
        cmd = ["python", "-m", "pytest"]
        
        if not include_slow:
            cmd.extend(["-m", "not slow"])
        
        if verbose:
            cmd.append("-v")
        
        # Add coverage options
        cmd.extend([
            "--cov=src/context_cleaner",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=json"
        ])
        
        result = self._run_pytest_command(cmd, "all_tests")
        return result
    
    def run_specific_test_file(self, test_file: str, verbose: bool = True) -> Dict[str, Any]:
        """Run a specific test file."""
        print(f"🎯 Running Test File: {test_file}")
        cmd = ["python", "-m", "pytest", f"tests/{test_file}"]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, f"file_{test_file}")
        return result
    
    def run_test_category(self, category: str, verbose: bool = True) -> Dict[str, Any]:
        """Run tests by category marker."""
        print(f"📂 Running {category.title()} Tests...")
        cmd = ["python", "-m", "pytest", "-m", category]
        if verbose:
            cmd.append("-v")
        
        result = self._run_pytest_command(cmd, f"category_{category}")
        return result
    
    def _run_pytest_command(self, cmd: List[str], test_name: str) -> Dict[str, Any]:
        """Execute pytest command and capture results."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            test_result = {
                "command": " ".join(cmd),
                "return_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
            # Parse test results from output
            test_result.update(self._parse_pytest_output(result.stdout))
            
            self.test_results[test_name] = test_result
            
            # Print summary
            if test_result["success"]:
                print(f"✅ {test_name}: {test_result.get('passed', 0)} passed, "
                      f"{test_result.get('failed', 0)} failed in {duration:.2f}s")
            else:
                print(f"❌ {test_name}: Failed with return code {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}...")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_name}: Timeout after 10 minutes")
            return {
                "command": " ".join(cmd),
                "return_code": -1,
                "duration": 600,
                "success": False,
                "error": "Timeout"
            }
        except Exception as e:
            print(f"💥 {test_name}: Exception occurred: {e}")
            return {
                "command": " ".join(cmd),
                "return_code": -1,
                "duration": 0,
                "success": False,
                "error": str(e)
            }
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output to extract test statistics."""
        stats = {}
        
        # Look for summary line like "5 passed, 2 failed in 10.23s"
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line and ('failed' in line or 'error' in line or 'in' in line):
                # Parse test counts
                import re
                
                passed_match = re.search(r'(\d+)\s+passed', line)
                if passed_match:
                    stats['passed'] = int(passed_match.group(1))
                
                failed_match = re.search(r'(\d+)\s+failed', line)
                if failed_match:
                    stats['failed'] = int(failed_match.group(1))
                else:
                    stats['failed'] = 0
                
                error_match = re.search(r'(\d+)\s+error', line)
                if error_match:
                    stats['errors'] = int(error_match.group(1))
                else:
                    stats['errors'] = 0
                
                skipped_match = re.search(r'(\d+)\s+skipped', line)
                if skipped_match:
                    stats['skipped'] = int(skipped_match.group(1))
                else:
                    stats['skipped'] = 0
                
                break
        
        # Look for coverage percentage
        for line in lines:
            if 'TOTAL' in line and '%' in line:
                import re
                coverage_match = re.search(r'(\d+)%', line)
                if coverage_match:
                    stats['coverage_percent'] = int(coverage_match.group(1))
                break
        
        return stats
    
    def generate_test_report(self, output_file: str = "test_report.html"):
        """Generate HTML test report."""
        print(f"📊 Generating Test Report: {output_file}")
        
        html_content = self._create_html_report()
        
        report_path = self.project_root / output_file
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        print(f"✅ Report saved to: {report_path}")
        return report_path
    
    def _create_html_report(self) -> str:
        """Create HTML report content."""
        total_passed = sum(r.get('passed', 0) for r in self.test_results.values())
        total_failed = sum(r.get('failed', 0) for r in self.test_results.values())
        total_errors = sum(r.get('errors', 0) for r in self.test_results.values())
        total_duration = sum(r.get('duration', 0) for r in self.test_results.values())
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Context Cleaner Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        .success {{ color: #28a745; }}
        .failure {{ color: #dc3545; }}
        .test-category {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
        .coverage {{ background: #e7f3ff; padding: 10px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>Context Cleaner Test Report</h1>
    <div class="summary">
        <h2>Overall Summary</h2>
        <p><strong>Total Tests:</strong> {total_passed + total_failed + total_errors}</p>
        <p><strong class="success">Passed:</strong> {total_passed}</p>
        <p><strong class="failure">Failed:</strong> {total_failed}</p>
        <p><strong class="failure">Errors:</strong> {total_errors}</p>
        <p><strong>Total Duration:</strong> {total_duration:.2f} seconds</p>
    </div>
    
    <h2>Test Categories</h2>
    <table>
        <tr>
            <th>Category</th>
            <th>Status</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Duration</th>
            <th>Coverage</th>
        </tr>
"""
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            passed = result.get('passed', 0)
            failed = result.get('failed', 0)
            duration = result.get('duration', 0)
            coverage = result.get('coverage_percent', 'N/A')
            
            html += f"""
        <tr>
            <td>{test_name}</td>
            <td>{status}</td>
            <td>{passed}</td>
            <td>{failed}</td>
            <td>{duration:.2f}s</td>
            <td>{coverage}%</td>
        </tr>
"""
        
        html += """
    </table>
    
    <div class="coverage">
        <h3>Coverage Information</h3>
        <p>Detailed coverage report available in <code>htmlcov/index.html</code></p>
        <p>JSON coverage data available in <code>coverage.json</code></p>
    </div>
    
    <h3>Quick Commands</h3>
    <pre>
# Run all tests
python run_tests.py --all

# Run only unit tests
python run_tests.py --unit

# Run with coverage
python run_tests.py --coverage

# Run specific category
python run_tests.py --category performance
    </pre>
    
</body>
</html>
"""
        return html
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "="*60)
        print("🎯 CONTEXT CLEANER TEST SUMMARY")
        print("="*60)
        
        if not self.test_results:
            print("❌ No tests were run")
            return
        
        total_passed = sum(r.get('passed', 0) for r in self.test_results.values())
        total_failed = sum(r.get('failed', 0) for r in self.test_results.values())
        total_errors = sum(r.get('errors', 0) for r in self.test_results.values())
        total_duration = sum(r.get('duration', 0) for r in self.test_results.values())
        
        successful_categories = sum(1 for r in self.test_results.values() if r['success'])
        total_categories = len(self.test_results)
        
        print(f"📊 Test Categories: {successful_categories}/{total_categories} passed")
        print(f"🧪 Individual Tests: {total_passed} passed, {total_failed} failed, {total_errors} errors")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        
        # Show category breakdown
        print("\n📂 Category Results:")
        for test_name, result in self.test_results.items():
            status = "✅" if result['success'] else "❌"
            duration = result.get('duration', 0)
            passed = result.get('passed', 0)
            failed = result.get('failed', 0)
            print(f"   {status} {test_name}: {passed} passed, {failed} failed ({duration:.2f}s)")
        
        # Overall status
        if total_failed == 0 and total_errors == 0 and successful_categories == total_categories:
            print("\n🎉 ALL TESTS PASSED! Ready for distribution.")
        else:
            print(f"\n⚠️  {total_failed + total_errors} test failures detected. Review before distribution.")


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(description="Context Cleaner Test Runner")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--slow", action="store_true", help="Run slow tests")
    parser.add_argument("--coverage", action="store_true", help="Run all tests with coverage")
    parser.add_argument("--category", type=str, help="Run specific test category")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--report", action="store_true", help="Generate HTML report")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent
    runner = TestRunner(project_root)
    
    verbose = not args.quiet
    
    # Determine which tests to run
    if args.all or args.coverage:
        runner.run_all_tests(verbose=verbose, include_slow=args.slow)
    elif args.unit:
        runner.run_unit_tests(verbose=verbose)
    elif args.integration:
        runner.run_integration_tests(verbose=verbose)
    elif args.performance:
        runner.run_performance_tests(verbose=verbose)
    elif args.slow:
        runner.run_slow_tests(verbose=verbose)
    elif args.category:
        runner.run_test_category(args.category, verbose=verbose)
    elif args.file:
        runner.run_specific_test_file(args.file, verbose=verbose)
    else:
        # Default: run all tests except slow ones
        print("Running default test suite (all tests except slow ones)")
        runner.run_all_tests(verbose=verbose, include_slow=False)
    
    # Generate report if requested
    if args.report:
        runner.generate_test_report()
    
    # Always print summary
    runner.print_summary()
    
    # Exit with appropriate code
    failed_categories = sum(1 for r in runner.test_results.values() if not r['success'])
    sys.exit(0 if failed_categories == 0 else 1)


if __name__ == "__main__":
    main()