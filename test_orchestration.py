#!/usr/bin/env python3
"""
Real-world testing script for Phase 3 Advanced Orchestration System

Tests the multi-agent workflow coordination, ML learning capabilities,
and dashboard integration with realistic development scenarios.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from context_cleaner.telemetry.orchestration.task_orchestrator import (
        TaskOrchestrator, TaskComplexity, AgentType
    )
    from context_cleaner.telemetry.orchestration.workflow_learner import WorkflowLearner
    from context_cleaner.telemetry.orchestration.agent_selector import AgentSelector, TaskContext
    from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
    from context_cleaner.telemetry.dashboard.widgets import TelemetryWidgetManager, TelemetryWidgetType
    
    ORCHESTRATION_AVAILABLE = True
    print("✅ All orchestration components successfully imported")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Some orchestration components are not available")
    ORCHESTRATION_AVAILABLE = False


class OrchestrationTester:
    """Comprehensive tester for Phase 3 orchestration capabilities"""
    
    def __init__(self):
        self.results: Dict[str, Any] = {
            "test_session_id": f"test_{int(time.time())}",
            "start_time": datetime.now(),
            "tests": {},
            "summary": {}
        }
        
        # Initialize components (with mock ClickHouse for testing)
        self.telemetry_client = None  # Will use mock
        self.task_orchestrator = None
        self.workflow_learner = None
        self.agent_selector = None
        
    async def setup_test_environment(self):
        """Set up the testing environment with orchestration components"""
        print("\n🔧 Setting up orchestration test environment...")
        
        try:
            # For testing, we'll use the orchestration components directly
            # without requiring actual ClickHouse connection
            print("  📊 Initializing orchestration components...")
            
            # Create mock telemetry client
            self.telemetry_client = type('MockTelemetryClient', (), {})()
            
            # Initialize orchestration components (respecting dependencies)
            self.task_orchestrator = TaskOrchestrator(self.telemetry_client)
            self.workflow_learner = WorkflowLearner(self.telemetry_client)  
            self.agent_selector = AgentSelector(self.telemetry_client, self.workflow_learner)
            
            print("  ✅ Task Orchestrator initialized")
            print("  ✅ Workflow Learner initialized")
            print("  ✅ Agent Selector initialized")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Setup failed: {e}")
            return False
    
    async def test_basic_workflow_orchestration(self) -> Dict[str, Any]:
        """Test basic workflow orchestration with a simple task"""
        print("\n🧪 Testing Basic Workflow Orchestration...")
        
        test_result = {
            "name": "basic_workflow_orchestration",
            "description": "Test simple task orchestration with single agent",
            "start_time": datetime.now(),
            "status": "running"
        }
        
        try:
            # Test simple task description
            simple_task = "Add error handling to the user authentication function"
            
            print(f"  📋 Task: {simple_task}")
            
            # Analyze task complexity
            complexity = await self.task_orchestrator._analyze_task_complexity(simple_task)
            print(f"  🔍 Detected complexity: {complexity}")
            
            # Generate subtasks
            subtasks = await self.task_orchestrator._generate_subtasks(simple_task, complexity)
            print(f"  📝 Generated {len(subtasks)} subtasks:")
            for i, subtask in enumerate(subtasks[:3]):  # Show first 3
                print(f"    {i+1}. {subtask.description[:60]}...")
            
            # Test agent registry
            available_agents = list(self.task_orchestrator.agent_registry.list_available_agents())
            print(f"  👥 Available agents: {len(available_agents)}")
            
            test_result.update({
                "complexity": complexity.value,
                "subtasks_generated": len(subtasks),
                "available_agents": len(available_agents),
                "status": "success",
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
            
            print("  ✅ Basic orchestration test passed")
            
        except Exception as e:
            print(f"  ❌ Basic orchestration test failed: {e}")
            test_result.update({
                "status": "failed",
                "error": str(e),
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
        
        return test_result
    
    async def test_agent_selection_system(self) -> Dict[str, Any]:
        """Test the advanced agent selection system"""
        print("\n🎯 Testing Agent Selection System...")
        
        test_result = {
            "name": "agent_selection_system",
            "description": "Test multi-criteria agent selection with various scenarios",
            "start_time": datetime.now(),
            "status": "running",
            "scenarios": []
        }
        
        try:
            # Test different task scenarios
            test_scenarios = [
                {
                    "description": "Optimize database queries in PostgreSQL",
                    "complexity": TaskComplexity.MODERATE,
                    "domain_keywords": ["database", "postgresql", "performance", "optimization"],
                    "expected_agent": "postgresql-database-expert"
                },
                {
                    "description": "Create responsive React components with TypeScript",
                    "complexity": TaskComplexity.MODERATE,
                    "domain_keywords": ["react", "typescript", "frontend", "components"],
                    "expected_agent": "frontend-typescript-react-expert"
                },
                {
                    "description": "Debug failing unit tests in Python backend",
                    "complexity": TaskComplexity.SIMPLE,
                    "domain_keywords": ["python", "testing", "debug", "backend"],
                    "expected_agent": "test-engineer"
                },
                {
                    "description": "Review code architecture and suggest improvements",
                    "complexity": TaskComplexity.COMPLEX,
                    "domain_keywords": ["architecture", "review", "refactoring"],
                    "expected_agent": "senior-code-reviewer"
                }
            ]
            
            for scenario in test_scenarios:
                print(f"  🔄 Testing scenario: {scenario['description'][:50]}...")
                
                # Create task context
                task_context = TaskContext(
                    description=scenario["description"],
                    complexity=scenario["complexity"],
                    domain_keywords=scenario["domain_keywords"],
                    session_id=self.results["test_session_id"]
                )
                
                # Test agent selection
                recommendation = await self.agent_selector.select_optimal_agent(task_context)
                
                scenario_result = {
                    "description": scenario["description"],
                    "selected_agent": recommendation.primary_agent.value,
                    "expected_agent": scenario["expected_agent"],
                    "confidence": recommendation.confidence,
                    "backup_agents": [agent.value for agent in recommendation.backup_agents],
                    "reasoning": recommendation.selection_reasoning,
                    "correct_selection": recommendation.primary_agent.value == scenario["expected_agent"]
                }
                
                test_result["scenarios"].append(scenario_result)
                
                print(f"    👤 Selected: {recommendation.primary_agent.value}")
                print(f"    🎯 Expected: {scenario['expected_agent']}")
                print(f"    ✅ Match: {'Yes' if scenario_result['correct_selection'] else 'No'}")
                print(f"    🔍 Confidence: {recommendation.confidence:.2f}")
            
            # Calculate overall success rate
            correct_selections = sum(1 for s in test_result["scenarios"] if s["correct_selection"])
            success_rate = correct_selections / len(test_scenarios)
            
            test_result.update({
                "total_scenarios": len(test_scenarios),
                "correct_selections": correct_selections,
                "success_rate": success_rate,
                "status": "success",
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
            
            print(f"  📊 Agent selection success rate: {success_rate:.1%}")
            print("  ✅ Agent selection test completed")
            
        except Exception as e:
            print(f"  ❌ Agent selection test failed: {e}")
            test_result.update({
                "status": "failed", 
                "error": str(e),
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
        
        return test_result
    
    async def test_workflow_learning_engine(self) -> Dict[str, Any]:
        """Test the ML-powered workflow learning capabilities"""
        print("\n🧠 Testing Workflow Learning Engine...")
        
        test_result = {
            "name": "workflow_learning_engine",
            "description": "Test ML learning from workflow patterns",
            "start_time": datetime.now(),
            "status": "running"
        }
        
        try:
            # Test learning status
            learning_status = await self.workflow_learner.get_learning_status()
            print(f"  📈 Learning engine status: {learning_status['status']}")
            print(f"  🧩 Learned patterns: {learning_status['learned_patterns']}")
            
            # Test performance insights
            performance_insights = await self.workflow_learner.get_performance_insights()
            workflow_templates = performance_insights["workflow_templates"]
            
            print(f"  📋 Workflow templates analyzed: {len(workflow_templates)}")
            for template_name, metrics in workflow_templates.items():
                success_rate = metrics["success_rate"]
                avg_duration = metrics["avg_duration"]
                print(f"    • {template_name}: {success_rate:.1f}% success, {avg_duration:.1f}min avg")
            
            # Test optimization opportunities
            optimizations = performance_insights["optimizations"]
            print(f"  🎯 Optimization opportunities: {len(optimizations)}")
            for opt in optimizations[:2]:  # Show first 2
                print(f"    • {opt['workflow']}: {opt['opportunity']}")
            
            # Test pattern insights
            pattern_insights = performance_insights["patterns"]
            print(f"  💡 Pattern insights: {len(pattern_insights)}")
            for insight in pattern_insights[:2]:  # Show first 2
                print(f"    • {insight}")
            
            test_result.update({
                "learning_status": learning_status["status"],
                "patterns_count": learning_status["learned_patterns"],
                "templates_analyzed": len(workflow_templates),
                "optimizations_found": len(optimizations),
                "insights_generated": len(pattern_insights),
                "status": "success",
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
            
            print("  ✅ Workflow learning test completed")
            
        except Exception as e:
            print(f"  ❌ Workflow learning test failed: {e}")
            test_result.update({
                "status": "failed",
                "error": str(e),
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
        
        return test_result
    
    async def test_complex_workflow_coordination(self) -> Dict[str, Any]:
        """Test complex multi-agent workflow coordination"""
        print("\n🏗️ Testing Complex Workflow Coordination...")
        
        test_result = {
            "name": "complex_workflow_coordination", 
            "description": "Test end-to-end complex workflow with multiple agents",
            "start_time": datetime.now(),
            "status": "running"
        }
        
        try:
            # Complex realistic task
            complex_task = """
            Implement a new user dashboard feature that displays real-time analytics:
            1. Design and implement PostgreSQL database schema for analytics data
            2. Create Python backend API endpoints with proper authentication
            3. Build responsive React frontend components with TypeScript
            4. Add comprehensive unit and integration tests
            5. Set up CI/CD pipeline with Docker containerization
            6. Conduct security review and performance optimization
            """
            
            print(f"  📋 Complex Task: Implementing user dashboard with analytics")
            
            # Analyze complexity 
            complexity = await self.task_orchestrator._analyze_task_complexity(complex_task)
            print(f"  🔍 Complexity level: {complexity.value}")
            
            # Generate detailed subtasks
            subtasks = await self.task_orchestrator._generate_subtasks(complex_task, complexity)
            print(f"  📝 Generated {len(subtasks)} subtasks")
            
            # Create workflow from subtasks
            workflow = await self.task_orchestrator._create_workflow(
                complex_task, subtasks, complexity
            )
            print(f"  🔧 Created workflow with {len(workflow.steps)} steps")
            
            # Show workflow steps and agents
            agent_assignments = {}
            for i, step in enumerate(workflow.steps[:6]):  # Show first 6 steps
                agent = step.assigned_agent.value if step.assigned_agent else "unassigned"
                agent_assignments[agent] = agent_assignments.get(agent, 0) + 1
                print(f"    Step {i+1}: {step.subtask.description[:50]}... → {agent}")
            
            print(f"  👥 Agent distribution:")
            for agent, count in sorted(agent_assignments.items()):
                print(f"    • {agent}: {count} tasks")
            
            # Test orchestration metrics
            metrics = await self.task_orchestrator.get_orchestration_metrics()
            
            test_result.update({
                "complexity": complexity.value,
                "subtasks_generated": len(subtasks),
                "workflow_steps": len(workflow.steps),
                "unique_agents": len(agent_assignments),
                "agent_distribution": agent_assignments,
                "orchestration_metrics": metrics,
                "status": "success",
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
            
            print("  ✅ Complex workflow coordination test completed")
            
        except Exception as e:
            print(f"  ❌ Complex workflow test failed: {e}")
            test_result.update({
                "status": "failed",
                "error": str(e),
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
        
        return test_result
    
    async def test_dashboard_widgets(self) -> Dict[str, Any]:
        """Test orchestration dashboard widgets"""
        print("\n📊 Testing Dashboard Widget Integration...")
        
        test_result = {
            "name": "dashboard_widgets",
            "description": "Test orchestration monitoring widgets",
            "start_time": datetime.now(),
            "status": "running"
        }
        
        try:
            # Test orchestration status
            orchestrator_status = await self.task_orchestrator.get_status()
            print(f"  📈 Active workflows: {orchestrator_status['active_workflows']}")
            print(f"  ⏳ Queued workflows: {orchestrator_status['queued_workflows']}")
            print(f"  👥 Active agents: {len(orchestrator_status['active_agents'])}")
            
            # Test agent utilization
            agent_utilization = await self.agent_selector.get_agent_utilization()
            utilization_data = agent_utilization['utilization']
            
            high_utilization = [(agent, util) for agent, util in utilization_data.items() if util > 50]
            print(f"  🔥 High utilization agents ({len(high_utilization)}):")
            for agent, util in sorted(high_utilization, key=lambda x: x[1], reverse=True)[:3]:
                print(f"    • {agent}: {util}%")
            
            # Test performance metrics
            performance_data = await self.agent_selector.get_performance_metrics()
            agent_performance = performance_data['performance']
            
            top_performers = [
                (agent, metrics['success_rate']) 
                for agent, metrics in agent_performance.items()
            ]
            top_performers.sort(key=lambda x: x[1], reverse=True)
            
            print(f"  🏆 Top performing agents:")
            for agent, success_rate in top_performers[:3]:
                print(f"    • {agent}: {success_rate}% success rate")
            
            test_result.update({
                "orchestrator_status": orchestrator_status,
                "total_agents": len(utilization_data),
                "high_utilization_count": len(high_utilization),
                "top_performer": top_performers[0][0] if top_performers else None,
                "avg_success_rate": sum(m['success_rate'] for m in agent_performance.values()) / len(agent_performance),
                "status": "success",
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
            
            print("  ✅ Dashboard widgets test completed")
            
        except Exception as e:
            print(f"  ❌ Dashboard widgets test failed: {e}")
            test_result.update({
                "status": "failed",
                "error": str(e),
                "duration": (datetime.now() - test_result["start_time"]).total_seconds()
            })
        
        return test_result
    
    async def run_all_tests(self):
        """Run all orchestration tests"""
        print("🚀 Starting Phase 3 Orchestration System Testing")
        print("=" * 60)
        
        # Setup test environment
        setup_success = await self.setup_test_environment()
        if not setup_success:
            print("❌ Test environment setup failed - aborting tests")
            return
        
        # Run test suite
        tests = [
            self.test_basic_workflow_orchestration,
            self.test_agent_selection_system,
            self.test_workflow_learning_engine,
            self.test_complex_workflow_coordination,
            self.test_dashboard_widgets
        ]
        
        for test_func in tests:
            try:
                result = await test_func()
                self.results["tests"][result["name"]] = result
                await asyncio.sleep(0.5)  # Brief pause between tests
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {e}")
        
        # Generate summary
        self.generate_test_summary()
        
    def generate_test_summary(self):
        """Generate comprehensive test summary"""
        print("\n" + "=" * 60)
        print("📋 PHASE 3 ORCHESTRATION TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results["tests"])
        passed_tests = len([t for t in self.results["tests"].values() if t["status"] == "success"])
        failed_tests = total_tests - passed_tests
        
        print(f"📊 Overall Results:")
        print(f"   • Total Tests: {total_tests}")
        print(f"   • Passed: {passed_tests} ✅")
        print(f"   • Failed: {failed_tests} ❌")
        print(f"   • Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        total_duration = (datetime.now() - self.results["start_time"]).total_seconds()
        print(f"   • Total Duration: {total_duration:.2f}s")
        
        print(f"\n🔍 Detailed Results:")
        for test_name, result in self.results["tests"].items():
            status_emoji = "✅" if result["status"] == "success" else "❌"
            duration = result.get("duration", 0)
            print(f"   {status_emoji} {test_name}: {result['status']} ({duration:.2f}s)")
            
            if result["status"] == "failed" and "error" in result:
                print(f"      Error: {result['error']}")
        
        # Key insights
        print(f"\n💡 Key Insights:")
        
        if "agent_selection_system" in self.results["tests"]:
            agent_test = self.results["tests"]["agent_selection_system"]
            if agent_test["status"] == "success":
                success_rate = agent_test.get("success_rate", 0)
                print(f"   • Agent selection accuracy: {success_rate:.1%}")
        
        if "complex_workflow_coordination" in self.results["tests"]:
            complex_test = self.results["tests"]["complex_workflow_coordination"]
            if complex_test["status"] == "success":
                agents_used = complex_test.get("unique_agents", 0)
                print(f"   • Complex workflows engage {agents_used} different agent types")
        
        if "dashboard_widgets" in self.results["tests"]:
            dashboard_test = self.results["tests"]["dashboard_widgets"]
            if dashboard_test["status"] == "success":
                avg_success = dashboard_test.get("avg_success_rate", 0)
                print(f"   • Average agent success rate: {avg_success:.1f}%")
        
        print(f"\n🎉 Phase 3 Orchestration Testing Complete!")
        
        # Save results to file
        results_file = f"orchestration_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"📄 Detailed results saved to: {results_file}")


async def main():
    """Main testing entry point"""
    if not ORCHESTRATION_AVAILABLE:
        print("❌ Orchestration components not available - cannot run tests")
        return
    
    tester = OrchestrationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())