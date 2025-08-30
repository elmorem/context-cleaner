#!/usr/bin/env python3
"""
Basic Phase 3 Integration Test

Quick test to verify memory optimizer, CPU optimizer, and dashboard work.
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from context_cleaner.optimization.memory_optimizer import MemoryOptimizer
from context_cleaner.optimization.cpu_optimizer import CPUOptimizer, TaskPriority
from context_cleaner.dashboard.real_time_performance_dashboard import RealTimePerformanceDashboard

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Basic integration test."""
    logger.info("🚀 Starting Basic Phase 3 Integration Test")
    
    try:
        # Test 1: Memory Optimizer
        logger.info("1. Testing Memory Optimizer...")
        memory_optimizer = MemoryOptimizer()
        memory_optimizer.start_monitoring()
        time.sleep(2)
        
        memory_report = memory_optimizer.get_memory_report()
        logger.info(f"   Memory usage: {memory_report['current']['process_mb']:.1f}MB")
        logger.info(f"   Health score: {memory_report['current']['health_score']}")
        
        memory_optimizer.stop_monitoring()
        logger.info("   ✅ Memory optimizer works!")
        
        # Test 2: CPU Optimizer  
        logger.info("2. Testing CPU Optimizer...")
        cpu_optimizer = CPUOptimizer()
        cpu_optimizer.start()
        time.sleep(1)
        
        # Schedule a simple task
        def test_task():
            return sum(i for i in range(1000))
        
        cpu_optimizer.schedule_background_task(
            name="test_task",
            func=test_task,
            priority=TaskPriority.HIGH
        )
        
        time.sleep(2)
        
        cpu_report = cpu_optimizer.get_performance_report()
        logger.info(f"   CPU usage: {cpu_report['summary']['current_cpu_percent']:.1f}%")
        logger.info(f"   Health score: {cpu_report['summary']['health_score']}")
        
        cpu_optimizer.stop()
        logger.info("   ✅ CPU optimizer works!")
        
        # Test 3: Dashboard Metrics
        logger.info("3. Testing Dashboard Metrics...")
        memory_optimizer.start_monitoring()
        cpu_optimizer.start()
        time.sleep(1)
        
        dashboard = RealTimePerformanceDashboard()
        metrics = dashboard._get_current_metrics()
        
        logger.info(f"   Dashboard collected metrics successfully")
        logger.info(f"   Memory: {metrics['memory']['current_mb']:.1f}MB")
        logger.info(f"   CPU: {metrics['cpu']['current_percent']:.1f}%")
        logger.info(f"   Overall health: {metrics['overall_health']}")
        
        memory_optimizer.stop_monitoring()
        cpu_optimizer.stop()
        logger.info("   ✅ Dashboard metrics work!")
        
        logger.info("\n🎉 All basic integration tests passed!")
        logger.info("Phase 3 components are working correctly together.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)