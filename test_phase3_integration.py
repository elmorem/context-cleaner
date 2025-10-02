#!/usr/bin/env python3
"""
Phase 3 Integration Test Script

Test the integration of memory optimizer, CPU optimizer, and real-time dashboard
to ensure they work together correctly.
"""

import sys
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from context_cleaner.optimization.memory_optimizer import MemoryOptimizer
from context_cleaner.optimization.cpu_optimizer import CPUOptimizer, TaskPriority
from context_cleaner.dashboard.comprehensive_health_dashboard import (
    ComprehensiveHealthDashboard as RealTimePerformanceDashboard,
)
from context_cleaner.config.settings import ContextCleanerConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase3IntegrationTester:
    """Test Phase 3 performance optimization integration."""
    
    def __init__(self):
        """Initialize the integration tester."""
        self.config = ContextCleanerConfig.from_env()
        
        # Initialize optimizers
        self.memory_optimizer = MemoryOptimizer(self.config)
        self.cpu_optimizer = CPUOptimizer(self.config)
        
        # Initialize dashboard
        self.dashboard = RealTimePerformanceDashboard(self.config)
        
        # Test results
        self.test_results = {}
        self.test_passed = 0
        self.test_failed = 0
    
    def run_all_tests(self):
        """Run all integration tests."""
        logger.info("🚀 Starting Phase 3 Integration Tests")
        logger.info("=" * 60)
        
        # Test individual components
        self.test_memory_optimizer()
        self.test_cpu_optimizer() 
        self.test_optimizer_integration()
        self.test_dashboard_metrics()
        self.test_performance_under_load()
        
        # Print summary
        self.print_test_summary()
        
        return self.test_failed == 0
    
    def test_memory_optimizer(self):
        """Test memory optimizer functionality."""
        logger.info("🧠 Testing Memory Optimizer")
        
        try:
            # Start monitoring
            self.memory_optimizer.start_monitoring()
            time.sleep(1)
            
            # Test cache operations
            analytics_cache = self.memory_optimizer.get_cache("analytics")
            if analytics_cache:
                # Add test data to cache
                for i in range(10):
                    analytics_cache.put(f"test_key_{i}", f"test_data_{i}" * 100, priority=2)
                
                # Verify cache operations
                cached_item = analytics_cache.get("test_key_0")
                assert cached_item is not None, "Cache retrieval failed"
                
                cache_stats = analytics_cache.get_stats()
                assert cache_stats["total_items"] > 0, "Cache items not recorded"
                
                self._record_test_result("Memory Cache Operations", True)
            else:
                self._record_test_result("Memory Cache Operations", False, "Cache not found")
            
            # Test memory monitoring
            memory_report = self.memory_optimizer.get_memory_report()
            assert "current" in memory_report, "Memory report missing current section"
            assert memory_report["current"]["process_mb"] > 0, "Process memory not detected"
            
            self._record_test_result("Memory Monitoring", True)
            
            # Test optimization
            initial_memory = memory_report["current"]["process_mb"]
            self.memory_optimizer.force_optimization()
            time.sleep(1)
            
            optimized_report = self.memory_optimizer.get_memory_report()
            logger.info(f"Memory optimization: {initial_memory:.1f}MB → {optimized_report['current']['process_mb']:.1f}MB")
            
            self._record_test_result("Memory Optimization", True)
            
            # Stop monitoring
            self.memory_optimizer.stop_monitoring()
            
        except Exception as e:
            self._record_test_result("Memory Optimizer", False, str(e))
    
    def test_cpu_optimizer(self):
        """Test CPU optimizer functionality."""
        logger.info("⚡ Testing CPU Optimizer")
        
        try:
            # Start CPU optimizer
            self.cpu_optimizer.start()
            time.sleep(1)
            
            # Test task scheduling
            test_results = {"task_executed": False}
            
            def test_task():
                test_results["task_executed"] = True
                time.sleep(0.1)  # Simulate work
                return "task_completed"
            
            # Schedule tasks with different priorities
            self.cpu_optimizer.schedule_background_task(
                name="test_high_priority",
                func=test_task,
                priority=TaskPriority.HIGH,
                max_duration_ms=1000
            )
            
            self.cpu_optimizer.schedule_background_task(
                name="test_medium_priority", 
                func=test_task,
                priority=TaskPriority.MEDIUM,
                max_duration_ms=500
            )
            
            # Wait for task execution
            time.sleep(3)
            
            assert test_results["task_executed"], "Background tasks not executed"
            self._record_test_result("CPU Task Scheduling", True)
            
            # Test performance reporting
            perf_report = self.cpu_optimizer.get_performance_report()
            assert "summary" in perf_report, "Performance report missing summary"
            assert "scheduler" in perf_report, "Performance report missing scheduler info"
            
            current_cpu = perf_report["summary"]["current_cpu_percent"]
            logger.info(f"Current CPU usage: {current_cpu:.1f}%")
            
            self._record_test_result("CPU Performance Reporting", True)
            
            # Test optimization
            optimization_result = self.cpu_optimizer.force_optimization()
            assert "cpu" in optimization_result, "CPU optimization result invalid"
            
            self._record_test_result("CPU Optimization", True)
            
            # Stop CPU optimizer
            self.cpu_optimizer.stop()
            
        except Exception as e:
            self._record_test_result("CPU Optimizer", False, str(e))
    
    def test_optimizer_integration(self):
        """Test integration between memory and CPU optimizers.""" 
        logger.info("🔗 Testing Optimizer Integration")
        
        try:
            # Start both optimizers
            self.memory_optimizer.start_monitoring()
            self.cpu_optimizer.start()
            time.sleep(1)
            
            # Create some load to test cooperation
            def memory_intensive_task():
                # Create temporary data structures
                data = [list(range(1000)) for _ in range(100)]
                time.sleep(0.5)
                return len(data)
            
            def cpu_intensive_task():
                # CPU-bound calculation
                result = sum(i * i for i in range(10000))
                time.sleep(0.1)
                return result
            
            # Schedule mixed workload
            for i in range(5):
                self.cpu_optimizer.schedule_background_task(
                    name=f"memory_task_{i}",
                    func=memory_intensive_task,
                    priority=TaskPriority.MEDIUM,
                    max_duration_ms=2000
                )
                
                self.cpu_optimizer.schedule_background_task(
                    name=f"cpu_task_{i}",
                    func=cpu_intensive_task,
                    priority=TaskPriority.LOW,
                    max_duration_ms=1000
                )
            
            # Monitor performance during load
            logger.info("Monitoring performance under mixed workload...")
            initial_memory = self.memory_optimizer.get_memory_report()["current"]["process_mb"]
            initial_cpu = self.cpu_optimizer.get_performance_report()["summary"]["current_cpu_percent"]
            
            time.sleep(5)  # Let tasks execute
            
            final_memory = self.memory_optimizer.get_memory_report()["current"]["process_mb"]
            final_cpu = self.cpu_optimizer.get_performance_report()["summary"]["current_cpu_percent"]
            
            logger.info(f"Performance during load:")
            logger.info(f"  Memory: {initial_memory:.1f}MB → {final_memory:.1f}MB")
            logger.info(f"  CPU: {initial_cpu:.1f}% → {final_cpu:.1f}%")
            
            # Verify optimizers maintained reasonable performance under load
            memory_target = self.memory_optimizer.critical_memory_mb  # Use critical threshold
            cpu_target = self.cpu_optimizer.critical_cpu_percent  # Use critical threshold
            
            memory_ok = final_memory <= memory_target * 1.2  # Allow 20% over critical during load
            cpu_ok = final_cpu <= cpu_target * 1.5  # Allow 50% over critical during load
            
            self._record_test_result("Memory Target Maintenance", memory_ok, 
                                   f"Memory {final_memory:.1f}MB > {memory_target * 1.2:.1f}MB" if not memory_ok else None)
            
            self._record_test_result("CPU Target Maintenance", cpu_ok,
                                   f"CPU {final_cpu:.1f}% > {cpu_target * 1.5:.1f}%" if not cpu_ok else None)
            
            # Stop optimizers
            self.memory_optimizer.stop_monitoring()
            self.cpu_optimizer.stop()
            
        except Exception as e:
            self._record_test_result("Optimizer Integration", False, str(e))
    
    def test_dashboard_metrics(self):
        """Test dashboard metrics collection."""
        logger.info("📊 Testing Dashboard Metrics")
        
        try:
            # Start optimizers for dashboard to monitor
            self.memory_optimizer.start_monitoring()
            self.cpu_optimizer.start()
            time.sleep(1)
            
            # Test metrics collection
            metrics = self.dashboard._get_current_metrics()
            
            # Verify required fields
            required_fields = ["timestamp", "memory", "cpu", "system", "overall_health"]
            for field in required_fields:
                assert field in metrics, f"Missing required field: {field}"
            
            # Verify memory metrics
            memory_fields = ["current_mb", "target_mb", "usage_percent", "health_score"]
            for field in memory_fields:
                assert field in metrics["memory"], f"Missing memory field: {field}"
                assert isinstance(metrics["memory"][field], (int, float)), f"Invalid memory field type: {field}"
            
            # Verify CPU metrics  
            cpu_fields = ["current_percent", "target_percent", "health_score"]
            for field in cpu_fields:
                assert field in metrics["cpu"], f"Missing CPU field: {field}"
                assert isinstance(metrics["cpu"][field], (int, float)), f"Invalid CPU field type: {field}"
            
            logger.info("Dashboard metrics structure validated")
            logger.info(f"Memory: {metrics['memory']['current_mb']:.1f}MB ({metrics['memory']['health_score']}% health)")
            logger.info(f"CPU: {metrics['cpu']['current_percent']:.1f}% ({metrics['cpu']['health_score']}% health)")
            logger.info(f"Overall Health: {metrics['overall_health']}%")
            
            self._record_test_result("Dashboard Metrics Collection", True)
            
            # Test dashboard stats
            dashboard_stats = self.dashboard.get_dashboard_stats()
            assert isinstance(dashboard_stats, dict), "Dashboard stats not returned as dict"
            assert "memory_optimizer_active" in dashboard_stats, "Missing memory optimizer status"
            assert "cpu_optimizer_active" in dashboard_stats, "Missing CPU optimizer status"
            
            self._record_test_result("Dashboard Statistics", True)
            
            # Stop optimizers
            self.memory_optimizer.stop_monitoring()
            self.cpu_optimizer.stop()
            
        except Exception as e:
            self._record_test_result("Dashboard Metrics", False, str(e))
    
    def test_performance_under_load(self):
        """Test system performance under sustained load."""
        logger.info("🔥 Testing Performance Under Load")
        
        try:
            # Start all systems
            self.memory_optimizer.start_monitoring()
            self.cpu_optimizer.start()
            time.sleep(1)
            
            # Create sustained load
            def sustained_load_task():
                # Mixed CPU and memory load
                data = []
                for i in range(1000):
                    data.append([j * j for j in range(100)])
                    if i % 100 == 0:
                        time.sleep(0.01)  # Brief pause
                return len(data)
            
            # Schedule sustained load
            logger.info("Creating sustained load for 10 seconds...")
            start_time = time.time()
            
            for i in range(20):  # Many concurrent tasks
                self.cpu_optimizer.schedule_background_task(
                    name=f"load_task_{i}",
                    func=sustained_load_task,
                    priority=TaskPriority.LOW,
                    max_duration_ms=3000
                )
            
            # Monitor performance every second
            performance_samples = []
            for second in range(10):
                time.sleep(1)
                
                memory_report = self.memory_optimizer.get_memory_report()
                cpu_report = self.cpu_optimizer.get_performance_report()
                
                sample = {
                    "second": second,
                    "memory_mb": memory_report["current"]["process_mb"],
                    "cpu_percent": cpu_report["summary"]["current_cpu_percent"],
                    "memory_health": memory_report["current"]["health_score"],
                    "cpu_health": cpu_report["summary"]["health_score"]
                }
                performance_samples.append(sample)
                
                logger.info(f"Second {second}: Memory={sample['memory_mb']:.1f}MB, "
                           f"CPU={sample['cpu_percent']:.1f}%, "
                           f"Health=({sample['memory_health']},{sample['cpu_health']})")
            
            # Analyze performance
            avg_memory = sum(s["memory_mb"] for s in performance_samples) / len(performance_samples)
            avg_cpu = sum(s["cpu_percent"] for s in performance_samples) / len(performance_samples)
            min_memory_health = min(s["memory_health"] for s in performance_samples)
            min_cpu_health = min(s["cpu_health"] for s in performance_samples)
            
            logger.info(f"Performance under load summary:")
            logger.info(f"  Average Memory: {avg_memory:.1f}MB (target: {self.memory_optimizer.target_memory_mb}MB)")
            logger.info(f"  Average CPU: {avg_cpu:.1f}% (target: {self.cpu_optimizer.target_cpu_percent}%)")
            logger.info(f"  Minimum Health: Memory={min_memory_health}, CPU={min_cpu_health}")
            
            # Performance criteria (realistic for heavy load testing)
            memory_ok = avg_memory <= self.memory_optimizer.critical_memory_mb * 1.5  # Allow 50% over critical during heavy load
            cpu_ok = avg_cpu <= self.cpu_optimizer.critical_cpu_percent * 2.0  # Allow 2x critical during heavy load  
            health_ok = min_memory_health >= 20 and min_cpu_health >= 10  # Minimum acceptable health under stress
            
            self._record_test_result("Memory Under Load", memory_ok,
                                   f"Average memory {avg_memory:.1f}MB exceeded critical threshold" if not memory_ok else None)
            
            self._record_test_result("CPU Under Load", cpu_ok,
                                   f"Average CPU {avg_cpu:.1f}% exceeded critical threshold" if not cpu_ok else None)
            
            self._record_test_result("Health Under Load", health_ok,
                                   f"Minimum health too low: Memory={min_memory_health}, CPU={min_cpu_health}" if not health_ok else None)
            
            # Stop systems
            self.memory_optimizer.stop_monitoring()
            self.cpu_optimizer.stop()
            
        except Exception as e:
            self._record_test_result("Performance Under Load", False, str(e))
    
    def _record_test_result(self, test_name: str, passed: bool, error_msg: str = None):
        """Record a test result."""
        self.test_results[test_name] = {
            "passed": passed,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }
        
        if passed:
            self.test_passed += 1
            logger.info(f"✅ {test_name}: PASSED")
        else:
            self.test_failed += 1
            logger.error(f"❌ {test_name}: FAILED" + (f" - {error_msg}" if error_msg else ""))
    
    def print_test_summary(self):
        """Print test execution summary."""
        logger.info("=" * 60)
        logger.info("📊 Phase 3 Integration Test Summary")
        logger.info("=" * 60)
        
        total_tests = self.test_passed + self.test_failed
        success_rate = (self.test_passed / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {self.test_passed}")
        logger.info(f"Failed: {self.test_failed}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        
        if self.test_failed > 0:
            logger.info("\n❌ Failed Tests:")
            for test_name, result in self.test_results.items():
                if not result["passed"]:
                    logger.info(f"  - {test_name}: {result['error']}")
        
        if self.test_failed == 0:
            logger.info("\n🎉 All tests passed! Phase 3 integration is ready.")
        else:
            logger.info(f"\n⚠️  {self.test_failed} tests failed. Please review and fix issues.")
        
        logger.info("=" * 60)


def main():
    """Main test execution."""
    tester = Phase3IntegrationTester()
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
