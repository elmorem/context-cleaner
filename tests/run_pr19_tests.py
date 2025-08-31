#!/usr/bin/env python3
"""
PR19 Test Runner - Optimization Modes & Interactive Workflow

Runs all tests related to PR19 implementation including:
- Unit tests for InteractiveWorkflowManager
- Unit tests for ChangeApprovalSystem  
- Unit tests for CLI optimization commands
- Integration tests for complete workflow
- Performance and compatibility tests

Usage:
    python tests/run_pr19_tests.py
    python tests/run_pr19_tests.py --verbose
    python tests/run_pr19_tests.py --coverage
    python tests/run_pr19_tests.py --quick  # Skip integration tests
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional
import time


class PR19TestRunner:
    """Test runner for PR19 Optimization Modes & Interactive Workflow."""
    
    def __init__(self, verbose: bool = False, coverage: bool = False, quick: bool = False):
        """Initialize test runner."""
        self.verbose = verbose
        self.coverage = coverage
        self.quick = quick
        self.test_root = Path(__file__).parent
        self.project_root = self.test_root.parent
        
        # PR19 test modules
        self.unit_tests = [
            "tests/optimization/test_interactive_workflow.py",
            "tests/optimization/test_change_approval.py", 
            "tests/cli/test_optimization_commands.py"
        ]
        
        self.integration_tests = [
            "tests/integration/test_pr19_optimization_workflow.py"
        ]
        
        # Test markers for different test categories
        self.markers = {
            "unit": "not integration and not performance",
            "integration": "integration",
            "performance": "performance", 
            "all": ""
        }
    
    def run_tests(self, test_category: str = "all") -> bool:
        """Run tests for specified category."""
        print(f"🚀 Running PR19 {test_category} tests...")
        print(f"📍 Project root: {self.project_root}")
        print("=" * 60)
        
        # Determine which tests to run
        if test_category == "unit":
            test_files = self.unit_tests
        elif test_category == "integration":
            test_files = self.integration_tests
        elif test_category == "all":
            test_files = self.unit_tests + ([] if self.quick else self.integration_tests)
        else:
            print(f"❌ Unknown test category: {test_category}")
            return False
        
        # Build pytest command
        cmd = self._build_pytest_command(test_files, test_category)
        
        # Run tests
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=not self.verbose,
                text=True,
                check=False
            )
            
            execution_time = time.time() - start_time
            
            # Report results
            if result.returncode == 0:
                print(f"✅ All PR19 {test_category} tests passed!")
                print(f"⏱️ Execution time: {execution_time:.2f} seconds")
                
                if not self.verbose and result.stdout:
                    self._print_test_summary(result.stdout)
                    
                if self.coverage and result.stdout:
                    self._print_coverage_summary(result.stdout)
                    
                return True
            else:
                print(f"❌ Some PR19 {test_category} tests failed")
                print(f"⏱️ Execution time: {execution_time:.2f} seconds")
                
                if not self.verbose:
                    print("\n📋 Test Output:")
                    if result.stdout:
                        print(result.stdout)
                    if result.stderr:
                        print("STDERR:", result.stderr)
                
                return False
                
        except KeyboardInterrupt:
            print("\n⏹️ Tests interrupted by user")
            return False
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return False
    
    def _build_pytest_command(self, test_files: List[str], category: str) -> List[str]:
        """Build pytest command with appropriate options."""
        cmd = ["python", "-m", "pytest"]
        
        # Add test files
        for test_file in test_files:
            if (self.project_root / test_file).exists():
                cmd.append(test_file)
            else:
                print(f"⚠️ Test file not found: {test_file}")
        
        # Add pytest options
        if self.verbose:
            cmd.extend(["-v", "-s"])
        else:
            cmd.append("-q")
        
        # Add coverage if requested
        if self.coverage:
            cmd.extend([
                "--cov=context_cleaner.optimization.interactive_workflow",
                "--cov=context_cleaner.optimization.change_approval", 
                "--cov=context_cleaner.cli.optimization_commands",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov/pr19"
            ])
        
        # Add markers
        if category in self.markers and self.markers[category]:
            cmd.extend(["-m", self.markers[category]])
        
        # Add additional pytest options
        cmd.extend([
            "--tb=short",
            "--strict-markers",
            "--disable-warnings"  # Reduce noise in output
        ])
        
        return cmd
    
    def _print_test_summary(self, output: str) -> None:
        """Print concise test summary."""
        lines = output.split('\n')
        
        # Find summary line
        for line in lines:
            if 'passed' in line or 'failed' in line or 'error' in line:
                if any(keyword in line for keyword in ['===', 'FAILED', 'PASSED', 'ERROR']):
                    print(f"📊 {line.strip()}")
    
    def _print_coverage_summary(self, output: str) -> None:
        """Print coverage summary if available."""
        lines = output.split('\n')
        in_coverage = False
        
        for line in lines:
            if 'Name' in line and 'Stmts' in line and 'Cover' in line:
                in_coverage = True
                print(f"\n📈 Coverage Report:")
                print(f"   {line}")
                continue
            elif in_coverage and line.strip() and not line.startswith('TOTAL'):
                if 'context_cleaner' in line:
                    print(f"   {line}")
            elif in_coverage and line.startswith('TOTAL'):
                print(f"   {line}")
                break
    
    def validate_installation(self) -> bool:
        """Validate that PR19 components can be imported."""
        print("🔍 Validating PR19 installation...")
        
        try:
            # Test core imports
            from context_cleaner.optimization.interactive_workflow import (
                InteractiveWorkflowManager, start_interactive_optimization
            )
            from context_cleaner.optimization.change_approval import (
                ChangeApprovalSystem, create_quick_approval
            )
            from context_cleaner.cli.optimization_commands import (
                OptimizationCommandHandler
            )
            
            print("✅ All PR19 components imported successfully")
            
            # Test basic functionality
            manager = InteractiveWorkflowManager()
            approval_system = ChangeApprovalSystem()
            handler = OptimizationCommandHandler()
            
            print("✅ All PR19 components instantiated successfully")
            return True
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("💡 Make sure the project is properly installed")
            return False
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False
    
    def run_smoke_tests(self) -> bool:
        """Run quick smoke tests to verify basic functionality."""
        print("💨 Running PR19 smoke tests...")
        
        try:
            # Test InteractiveWorkflowManager
            from context_cleaner.optimization.interactive_workflow import InteractiveWorkflowManager
            from context_cleaner.optimization.personalized_strategies import StrategyType
            
            manager = InteractiveWorkflowManager()
            session = manager.start_interactive_optimization(
                {"test": "data"}, 
                StrategyType.BALANCED
            )
            
            assert session is not None
            assert session.session_id in manager.active_sessions
            manager.cancel_session(session.session_id)
            print("✅ InteractiveWorkflowManager smoke test passed")
            
            # Test ChangeApprovalSystem
            from context_cleaner.optimization.change_approval import ChangeApprovalSystem
            from unittest.mock import Mock
            
            approval_system = ChangeApprovalSystem()
            mock_plan = Mock()
            mock_plan.operations = [Mock(), Mock()]
            mock_plan.total_operations = 2
            
            approval_id = approval_system.create_approval_session(mock_plan)
            assert approval_id is not None
            assert len(approval_system.approval_history) == 1
            print("✅ ChangeApprovalSystem smoke test passed")
            
            # Test CLI OptimizationCommandHandler
            from context_cleaner.cli.optimization_commands import OptimizationCommandHandler
            
            handler = OptimizationCommandHandler()
            assert handler is not None
            print("✅ OptimizationCommandHandler smoke test passed")
            
            return True
            
        except Exception as e:
            print(f"❌ Smoke test failed: {e}")
            return False
    
    def generate_test_report(self) -> None:
        """Generate comprehensive test report."""
        print("\n📋 PR19 Test Suite Report")
        print("=" * 50)
        
        # Count test files
        unit_test_count = len([f for f in self.unit_tests if (self.project_root / f).exists()])
        integration_test_count = len([f for f in self.integration_tests if (self.project_root / f).exists()])
        
        print(f"📁 Unit test files: {unit_test_count}")
        print(f"📁 Integration test files: {integration_test_count}")
        print(f"📁 Total test files: {unit_test_count + integration_test_count}")
        
        # List test modules
        print(f"\n🧪 Unit Test Modules:")
        for test_file in self.unit_tests:
            status = "✅" if (self.project_root / test_file).exists() else "❌"
            print(f"   {status} {test_file}")
        
        if not self.quick:
            print(f"\n🔗 Integration Test Modules:")
            for test_file in self.integration_tests:
                status = "✅" if (self.project_root / test_file).exists() else "❌"
                print(f"   {status} {test_file}")
        
        print(f"\n🎯 Test Coverage Areas:")
        print(f"   • InteractiveWorkflowManager - Session management & strategy execution")
        print(f"   • ChangeApprovalSystem - Selective approval & user preferences")
        print(f"   • CLI Integration - All optimization commands & error handling")
        print(f"   • End-to-End Workflow - Complete optimization pipeline")
        print(f"   • Performance & Scalability - Large datasets & concurrent sessions")
        print(f"   • Backward Compatibility - Integration with existing components")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run PR19 Optimization Modes & Interactive Workflow tests",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--category", 
        choices=["unit", "integration", "all"],
        default="all",
        help="Test category to run (default: all)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true", 
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Skip integration tests for faster execution"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate installation without running tests"
    )
    
    parser.add_argument(
        "--smoke-only",
        action="store_true", 
        help="Only run smoke tests"
    )
    
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate test report without running tests"
    )
    
    args = parser.parse_args()
    
    # Create test runner
    runner = PR19TestRunner(
        verbose=args.verbose,
        coverage=args.coverage,
        quick=args.quick
    )
    
    # Handle special modes
    if args.report_only:
        runner.generate_test_report()
        return
    
    if args.validate_only:
        success = runner.validate_installation()
        sys.exit(0 if success else 1)
    
    if args.smoke_only:
        success = runner.run_smoke_tests()
        sys.exit(0 if success else 1)
    
    # Validate installation first
    if not runner.validate_installation():
        print("❌ Installation validation failed")
        sys.exit(1)
    
    # Run smoke tests
    if not runner.run_smoke_tests():
        print("❌ Smoke tests failed")
        sys.exit(1)
    
    # Run main test suite
    success = runner.run_tests(args.category)
    
    # Generate report
    if success:
        runner.generate_test_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()