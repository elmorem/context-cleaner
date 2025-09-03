"""
Task Orchestration System for Phase 3 Advanced Automation

Implements intelligent multi-agent workflow coordination based on telemetry patterns
and learned optimization strategies. Leverages the Task tool for complex workflow execution.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from ..clients.clickhouse_client import ClickHouseClient
from ..analytics.session_analysis import SessionAnalyticsEngine
from ..automation.search_engine import AdvancedSearchEngine, WorkflowPattern

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for orchestration planning"""
    SIMPLE = "simple"           # Single agent, 1-2 steps
    MODERATE = "moderate"       # 2-3 agents, 3-5 steps
    COMPLEX = "complex"         # 3-5 agents, 5-10 steps
    ENTERPRISE = "enterprise"   # 5+ agents, 10+ steps


class AgentType(Enum):
    """Available agent types for orchestration"""
    GENERAL_PURPOSE = "general-purpose"
    CODEBASE_ARCHITECT = "codebase-architect"
    FRONTEND_EXPERT = "frontend-typescript-react-expert"
    BACKEND_ENGINEER = "python-backend-engineer"
    SENIOR_REVIEWER = "senior-code-reviewer"
    TEST_ENGINEER = "test-engineer"
    CI_LOG_ANALYZER = "ci-log-analyzer"
    DJANGO_EXPERT = "django-migration-expert"
    DOCKER_EXPERT = "docker-operations-expert"
    DATABASE_EXPERT = "postgresql-database-expert"
    IOS_EXPERT = "ios-swift-expert"
    GIS_EXPERT = "gis-mapping-expert"
    UI_ENGINEER = "ui-engineer"


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class Subtask:
    """Individual subtask within a workflow"""
    id: str
    description: str
    agent_type: AgentType
    estimated_duration: timedelta
    dependencies: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    context_requirements: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)
    priority: int = 5  # 1-10 scale, 10 = highest priority


@dataclass
class WorkflowStep:
    """Executable workflow step"""
    subtask: Subtask
    agent_prompt: str
    expected_output: str
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class Workflow:
    """Complete workflow definition"""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    complexity: TaskComplexity
    estimated_total_duration: timedelta
    created_at: datetime = field(default_factory=datetime.now)
    dependencies_resolved: bool = False
    success_rate_prediction: float = 0.8


@dataclass
class WorkflowExecution:
    """Workflow execution tracking"""
    workflow_id: str
    session_id: str
    status: TaskStatus
    progress_percentage: float
    completed_steps: int
    total_steps: int
    start_time: datetime
    end_time: Optional[datetime] = None
    total_cost: float = 0.0
    agent_utilization: Dict[str, int] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)


class AgentRegistry:
    """Registry of available agents and their capabilities"""
    
    def __init__(self):
        self.agents = {
            AgentType.GENERAL_PURPOSE: {
                "capabilities": ["research", "analysis", "file_operations", "coordination"],
                "cost_per_hour": 2.0,
                "avg_response_time": 5000,  # milliseconds
                "success_rate": 0.85,
                "specialties": ["general_tasks", "coordination", "research"]
            },
            AgentType.CODEBASE_ARCHITECT: {
                "capabilities": ["architecture_analysis", "performance_optimization", "security_review"],
                "cost_per_hour": 3.5,
                "avg_response_time": 8000,
                "success_rate": 0.92,
                "specialties": ["architecture", "scalability", "performance"]
            },
            AgentType.FRONTEND_EXPERT: {
                "capabilities": ["react_development", "typescript", "ui_components", "performance"],
                "cost_per_hour": 3.0,
                "avg_response_time": 6000,
                "success_rate": 0.88,
                "specialties": ["react", "typescript", "frontend", "ui"]
            },
            AgentType.BACKEND_ENGINEER: {
                "capabilities": ["api_development", "database_design", "python", "microservices"],
                "cost_per_hour": 3.2,
                "avg_response_time": 6500,
                "success_rate": 0.90,
                "specialties": ["python", "api", "backend", "database"]
            },
            AgentType.SENIOR_REVIEWER: {
                "capabilities": ["code_review", "best_practices", "security", "architecture"],
                "cost_per_hour": 4.0,
                "avg_response_time": 7000,
                "success_rate": 0.94,
                "specialties": ["review", "quality", "security", "best_practices"]
            },
            AgentType.TEST_ENGINEER: {
                "capabilities": ["test_development", "automation", "quality_assurance"],
                "cost_per_hour": 2.8,
                "avg_response_time": 5500,
                "success_rate": 0.87,
                "specialties": ["testing", "automation", "quality"]
            },
            AgentType.DOCKER_EXPERT: {
                "capabilities": ["containerization", "orchestration", "deployment"],
                "cost_per_hour": 3.5,
                "avg_response_time": 6000,
                "success_rate": 0.89,
                "specialties": ["docker", "containerization", "deployment"]
            }
        }
    
    def get_agent_info(self, agent_type: AgentType) -> Dict[str, Any]:
        """Get information about a specific agent type"""
        return self.agents.get(agent_type, {})
    
    def find_agents_by_capability(self, capability: str) -> List[AgentType]:
        """Find agents that have a specific capability"""
        matching_agents = []
        for agent_type, info in self.agents.items():
            if capability in info.get("capabilities", []):
                matching_agents.append(agent_type)
        return matching_agents
    
    def find_agents_by_specialty(self, specialty: str) -> List[AgentType]:
        """Find agents that specialize in a specific area"""
        matching_agents = []
        for agent_type, info in self.agents.items():
            specialties = info.get("specialties", [])
            if any(specialty.lower() in spec.lower() for spec in specialties):
                matching_agents.append(agent_type)
        return matching_agents


class WorkflowTemplateManager:
    """Manages predefined workflow templates"""
    
    def __init__(self):
        self.templates = {
            "code_analysis": {
                "name": "Comprehensive Code Analysis",
                "description": "Full codebase analysis with recommendations",
                "complexity": TaskComplexity.COMPLEX,
                "steps": [
                    {
                        "description": "Analyze overall codebase architecture",
                        "agent_type": AgentType.CODEBASE_ARCHITECT,
                        "estimated_minutes": 15,
                        "dependencies": [],
                        "success_criteria": ["Architecture overview completed", "Key components identified"]
                    },
                    {
                        "description": "Read and analyze core files",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 10,
                        "dependencies": ["0"],
                        "success_criteria": ["Core files analyzed", "Code patterns identified"]
                    },
                    {
                        "description": "Review code quality and identify issues",
                        "agent_type": AgentType.SENIOR_REVIEWER,
                        "estimated_minutes": 20,
                        "dependencies": ["1"],
                        "success_criteria": ["Quality review completed", "Issues documented"]
                    },
                    {
                        "description": "Generate improvement recommendations",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 10,
                        "dependencies": ["2"],
                        "success_criteria": ["Recommendations provided", "Action plan created"]
                    }
                ]
            },
            
            "feature_implementation": {
                "name": "Full-Stack Feature Implementation",
                "description": "Complete feature development with frontend, backend, and testing",
                "complexity": TaskComplexity.ENTERPRISE,
                "steps": [
                    {
                        "description": "Research and analyze requirements",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 15,
                        "dependencies": [],
                        "success_criteria": ["Requirements documented", "Approach defined"]
                    },
                    {
                        "description": "Develop frontend components",
                        "agent_type": AgentType.FRONTEND_EXPERT,
                        "estimated_minutes": 30,
                        "dependencies": ["0"],
                        "success_criteria": ["UI components created", "Frontend logic implemented"]
                    },
                    {
                        "description": "Implement backend API endpoints",
                        "agent_type": AgentType.BACKEND_ENGINEER,
                        "estimated_minutes": 25,
                        "dependencies": ["0"],
                        "success_criteria": ["API endpoints implemented", "Database integration completed"]
                    },
                    {
                        "description": "Create comprehensive tests",
                        "agent_type": AgentType.TEST_ENGINEER,
                        "estimated_minutes": 20,
                        "dependencies": ["1", "2"],
                        "success_criteria": ["Test suite created", "Coverage requirements met"]
                    },
                    {
                        "description": "Perform integration testing and review",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 15,
                        "dependencies": ["3"],
                        "success_criteria": ["Integration tests passed", "Feature verified"]
                    }
                ]
            },
            
            "debugging_session": {
                "name": "Systematic Bug Investigation",
                "description": "Methodical debugging with root cause analysis",
                "complexity": TaskComplexity.MODERATE,
                "steps": [
                    {
                        "description": "Reproduce and document the error",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 10,
                        "dependencies": [],
                        "success_criteria": ["Error reproduced", "Symptoms documented"]
                    },
                    {
                        "description": "Analyze logs and error traces",
                        "agent_type": AgentType.CI_LOG_ANALYZER,
                        "estimated_minutes": 15,
                        "dependencies": ["0"],
                        "success_criteria": ["Logs analyzed", "Error patterns identified"]
                    },
                    {
                        "description": "Identify root cause",
                        "agent_type": AgentType.SENIOR_REVIEWER,
                        "estimated_minutes": 20,
                        "dependencies": ["1"],
                        "success_criteria": ["Root cause identified", "Fix strategy defined"]
                    },
                    {
                        "description": "Implement fix",
                        "agent_type": AgentType.GENERAL_PURPOSE,
                        "estimated_minutes": 15,
                        "dependencies": ["2"],
                        "success_criteria": ["Fix implemented", "Code changes validated"]
                    },
                    {
                        "description": "Verify fix with tests",
                        "agent_type": AgentType.TEST_ENGINEER,
                        "estimated_minutes": 10,
                        "dependencies": ["3"],
                        "success_criteria": ["Fix verified", "Regression tests added"]
                    }
                ]
            },

            "performance_optimization": {
                "name": "Performance Analysis and Optimization",
                "description": "Comprehensive performance improvement workflow",
                "complexity": TaskComplexity.COMPLEX,
                "steps": [
                    {
                        "description": "Analyze system architecture for bottlenecks",
                        "agent_type": AgentType.CODEBASE_ARCHITECT,
                        "estimated_minutes": 20,
                        "dependencies": [],
                        "success_criteria": ["Performance baseline established", "Bottlenecks identified"]
                    },
                    {
                        "description": "Optimize database queries and structure",
                        "agent_type": AgentType.DATABASE_EXPERT,
                        "estimated_minutes": 25,
                        "dependencies": ["0"],
                        "success_criteria": ["Query optimization completed", "Database tuning applied"]
                    },
                    {
                        "description": "Optimize frontend performance",
                        "agent_type": AgentType.FRONTEND_EXPERT,
                        "estimated_minutes": 20,
                        "dependencies": ["0"],
                        "success_criteria": ["Frontend optimizations applied", "Bundle size reduced"]
                    },
                    {
                        "description": "Review and validate optimizations",
                        "agent_type": AgentType.SENIOR_REVIEWER,
                        "estimated_minutes": 15,
                        "dependencies": ["1", "2"],
                        "success_criteria": ["Performance improvements validated", "No regressions introduced"]
                    }
                ]
            }
        }
    
    def get_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get a workflow template by name"""
        return self.templates.get(template_name)
    
    def list_templates(self) -> List[str]:
        """List all available template names"""
        return list(self.templates.keys())
    
    def find_templates_by_complexity(self, complexity: TaskComplexity) -> List[str]:
        """Find templates matching a specific complexity level"""
        matching = []
        for name, template in self.templates.items():
            if template["complexity"] == complexity:
                matching.append(name)
        return matching


class TaskOrchestrator:
    """Main orchestration engine for multi-agent workflows"""
    
    def __init__(self, telemetry_client: ClickHouseClient):
        self.telemetry = telemetry_client
        self.analytics = SessionAnalyticsEngine(telemetry_client)
        self.search_engine = AdvancedSearchEngine(telemetry_client)
        self.agent_registry = AgentRegistry()
        self.template_manager = WorkflowTemplateManager()
        
        # Workflow state management
        self.active_workflows: Dict[str, WorkflowExecution] = {}
        self.workflow_history: List[WorkflowExecution] = []
        
        # Learning and optimization
        self.success_patterns: Dict[str, float] = {}
        self.agent_performance_history: Dict[AgentType, List[float]] = {}
        
        # Configuration
        self.max_concurrent_workflows = 3
        self.default_timeout = timedelta(hours=2)
        
        # Callbacks for monitoring
        self.progress_callbacks: List[Callable[[WorkflowExecution], None]] = []
        self.completion_callbacks: List[Callable[[WorkflowExecution], None]] = []
    
    def register_progress_callback(self, callback: Callable[[WorkflowExecution], None]):
        """Register callback for workflow progress updates"""
        self.progress_callbacks.append(callback)
    
    def register_completion_callback(self, callback: Callable[[WorkflowExecution], None]):
        """Register callback for workflow completion"""
        self.completion_callbacks.append(callback)
    
    async def orchestrate_from_description(self, description: str, 
                                         session_id: Optional[str] = None) -> WorkflowExecution:
        """
        Create and execute a workflow from a task description
        
        This is the main entry point for task orchestration
        """
        try:
            session_id = session_id or str(uuid.uuid4())
            
            logger.info(f"Starting workflow orchestration for: {description}")
            
            # Step 1: Analyze task complexity
            complexity = await self._analyze_task_complexity(description)
            logger.info(f"Task complexity determined: {complexity.value}")
            
            # Step 2: Generate task breakdown
            subtasks = await self._generate_subtasks(description, complexity)
            logger.info(f"Generated {len(subtasks)} subtasks")
            
            # Step 3: Create optimized workflow
            workflow = await self._create_workflow(description, subtasks, complexity)
            logger.info(f"Created workflow with {len(workflow.steps)} steps")
            
            # Step 4: Execute with monitoring
            execution = await self._execute_workflow(workflow, session_id)
            
            return execution
            
        except Exception as e:
            logger.error(f"Error in workflow orchestration: {e}")
            raise
    
    async def orchestrate_from_template(self, template_name: str, 
                                      context: Dict[str, Any] = None,
                                      session_id: Optional[str] = None) -> WorkflowExecution:
        """Execute a workflow from a predefined template"""
        template = self.template_manager.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        session_id = session_id or str(uuid.uuid4())
        
        # Convert template to workflow
        workflow = await self._template_to_workflow(template, context or {})
        
        # Execute workflow
        execution = await self._execute_workflow(workflow, session_id)
        
        return execution
    
    async def _analyze_task_complexity(self, description: str) -> TaskComplexity:
        """Analyze task description to determine complexity level"""
        description_lower = description.lower()
        
        # Count complexity indicators
        complexity_indicators = {
            "simple_keywords": ["read", "show", "list", "check", "view"],
            "moderate_keywords": ["analyze", "create", "implement", "debug", "optimize", "refactor"],
            "complex_keywords": ["design", "architect", "migrate", "integrate", "performance"],
            "enterprise_keywords": ["system", "platform", "infrastructure", "scalable", "enterprise"]
        }
        
        scores = {}
        for level, keywords in complexity_indicators.items():
            scores[level] = sum(1 for keyword in keywords if keyword in description_lower)
        
        # Additional complexity factors
        if any(word in description_lower for word in ["and", "then", "also", "plus"]):
            scores["moderate_keywords"] += 1
            
        if len(description.split()) > 20:  # Long descriptions tend to be more complex
            scores["complex_keywords"] += 1
            
        if any(tech in description_lower for tech in ["react", "python", "database", "api", "docker"]):
            scores["moderate_keywords"] += 1
        
        # Determine complexity based on highest score
        if scores["enterprise_keywords"] >= 2 or scores["complex_keywords"] >= 3:
            return TaskComplexity.ENTERPRISE
        elif scores["complex_keywords"] >= 2 or scores["moderate_keywords"] >= 3:
            return TaskComplexity.COMPLEX
        elif scores["moderate_keywords"] >= 1 or scores["simple_keywords"] >= 3:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.SIMPLE
    
    async def _generate_subtasks(self, description: str, complexity: TaskComplexity) -> List[Subtask]:
        """Break down main task into subtasks based on complexity"""
        subtasks = []
        
        # Use search engine to find similar successful patterns
        similar_patterns = await self._find_similar_workflow_patterns(description)
        
        if complexity == TaskComplexity.SIMPLE:
            # Single task, usually one agent
            subtasks.append(Subtask(
                id="0",
                description=description,
                agent_type=await self._select_best_agent_for_task(description),
                estimated_duration=timedelta(minutes=10),
                success_criteria=[f"Task completed: {description}"]
            ))
            
        elif complexity == TaskComplexity.MODERATE:
            # 3-5 subtasks
            if "debug" in description.lower() or "error" in description.lower():
                # Use debugging template approach
                subtasks = await self._generate_debugging_subtasks(description)
            elif "analyze" in description.lower():
                # Use analysis template approach
                subtasks = await self._generate_analysis_subtasks(description)
            else:
                # Generic moderate complexity breakdown
                subtasks = await self._generate_generic_subtasks(description, 3)
                
        elif complexity == TaskComplexity.COMPLEX:
            # 5-8 subtasks
            if "implement" in description.lower() and "feature" in description.lower():
                subtasks = await self._generate_feature_implementation_subtasks(description)
            elif "optimize" in description.lower() or "performance" in description.lower():
                subtasks = await self._generate_optimization_subtasks(description)
            else:
                subtasks = await self._generate_generic_subtasks(description, 6)
                
        else:  # ENTERPRISE
            # 8+ subtasks for enterprise-level tasks
            subtasks = await self._generate_enterprise_subtasks(description)
        
        return subtasks
    
    async def _generate_debugging_subtasks(self, description: str) -> List[Subtask]:
        """Generate subtasks for debugging workflows"""
        return [
            Subtask("0", f"Reproduce and document the issue: {description}",
                   AgentType.GENERAL_PURPOSE, timedelta(minutes=10),
                   success_criteria=["Issue reproduced", "Error documented"]),
            Subtask("1", "Analyze error logs and traces",
                   AgentType.CI_LOG_ANALYZER, timedelta(minutes=15),
                   dependencies=["0"], success_criteria=["Logs analyzed", "Error patterns found"]),
            Subtask("2", "Identify root cause and solution approach",
                   AgentType.SENIOR_REVIEWER, timedelta(minutes=20),
                   dependencies=["1"], success_criteria=["Root cause identified", "Fix strategy defined"]),
            Subtask("3", "Implement fix based on analysis",
                   await self._select_best_agent_for_task(description), timedelta(minutes=15),
                   dependencies=["2"], success_criteria=["Fix implemented", "Code validated"]),
            Subtask("4", "Verify fix and add regression tests",
                   AgentType.TEST_ENGINEER, timedelta(minutes=10),
                   dependencies=["3"], success_criteria=["Fix verified", "Tests added"])
        ]
    
    async def _generate_analysis_subtasks(self, description: str) -> List[Subtask]:
        """Generate subtasks for analysis workflows"""
        return [
            Subtask("0", f"Initial research and context gathering: {description}",
                   AgentType.GENERAL_PURPOSE, timedelta(minutes=15),
                   success_criteria=["Context gathered", "Scope defined"]),
            Subtask("1", "Deep analysis using specialized expertise",
                   AgentType.CODEBASE_ARCHITECT, timedelta(minutes=20),
                   dependencies=["0"], success_criteria=["Analysis completed", "Insights generated"]),
            Subtask("2", "Review findings and validate conclusions",
                   AgentType.SENIOR_REVIEWER, timedelta(minutes=15),
                   dependencies=["1"], success_criteria=["Findings reviewed", "Conclusions validated"]),
            Subtask("3", "Generate recommendations and action plan",
                   AgentType.GENERAL_PURPOSE, timedelta(minutes=10),
                   dependencies=["2"], success_criteria=["Recommendations provided", "Plan created"])
        ]
    
    async def _generate_generic_subtasks(self, description: str, num_tasks: int) -> List[Subtask]:
        """Generate generic subtasks for unknown patterns"""
        subtasks = []
        
        # Always start with research/planning
        subtasks.append(Subtask(
            "0", f"Research and plan approach for: {description}",
            AgentType.GENERAL_PURPOSE, timedelta(minutes=10),
            success_criteria=["Approach planned", "Requirements understood"]
        ))
        
        # Add implementation tasks based on description
        best_agent = await self._select_best_agent_for_task(description)
        for i in range(1, num_tasks - 1):
            subtasks.append(Subtask(
                str(i), f"Implementation step {i} for: {description}",
                best_agent, timedelta(minutes=15),
                dependencies=["0"] if i == 1 else [str(i-1)],
                success_criteria=[f"Step {i} completed"]
            ))
        
        # Always end with review/validation
        subtasks.append(Subtask(
            str(num_tasks - 1), f"Review and validate completed work",
            AgentType.SENIOR_REVIEWER, timedelta(minutes=10),
            dependencies=[str(num_tasks - 2)],
            success_criteria=["Work reviewed", "Quality validated"]
        ))
        
        return subtasks
    
    async def _select_best_agent_for_task(self, task_description: str) -> AgentType:
        """Select the most appropriate agent for a given task"""
        task_lower = task_description.lower()
        
        # Rule-based agent selection with telemetry optimization
        if any(word in task_lower for word in ["react", "typescript", "frontend", "ui", "component"]):
            return AgentType.FRONTEND_EXPERT
        elif any(word in task_lower for word in ["python", "api", "backend", "server", "database"]):
            return AgentType.BACKEND_ENGINEER
        elif any(word in task_lower for word in ["docker", "container", "deployment", "orchestration"]):
            return AgentType.DOCKER_EXPERT
        elif any(word in task_lower for word in ["test", "testing", "quality", "coverage"]):
            return AgentType.TEST_ENGINEER
        elif any(word in task_lower for word in ["review", "audit", "security", "quality"]):
            return AgentType.SENIOR_REVIEWER
        elif any(word in task_lower for word in ["architecture", "design", "scalability", "performance"]):
            return AgentType.CODEBASE_ARCHITECT
        elif any(word in task_lower for word in ["log", "debug", "error", "failure"]):
            return AgentType.CI_LOG_ANALYZER
        else:
            return AgentType.GENERAL_PURPOSE
    
    async def _create_workflow(self, description: str, subtasks: List[Subtask], 
                             complexity: TaskComplexity) -> Workflow:
        """Create executable workflow from subtasks"""
        workflow_id = str(uuid.uuid4())
        
        # Convert subtasks to workflow steps
        steps = []
        for subtask in subtasks:
            agent_prompt = await self._generate_agent_prompt(subtask, description)
            
            step = WorkflowStep(
                subtask=subtask,
                agent_prompt=agent_prompt,
                expected_output=f"Completion of: {subtask.description}"
            )
            steps.append(step)
        
        # Calculate total estimated duration
        total_duration = sum((step.subtask.estimated_duration for step in steps), timedelta())
        
        # Predict success rate based on historical data
        success_rate = await self._predict_workflow_success_rate(description, subtasks)
        
        workflow = Workflow(
            id=workflow_id,
            name=f"Workflow: {description[:50]}{'...' if len(description) > 50 else ''}",
            description=description,
            steps=steps,
            complexity=complexity,
            estimated_total_duration=total_duration,
            success_rate_prediction=success_rate
        )
        
        return workflow
    
    async def _generate_agent_prompt(self, subtask: Subtask, main_description: str) -> str:
        """Generate detailed prompt for agent execution"""
        prompt_parts = [
            f"Task: {subtask.description}",
            f"Context: This is part of a larger workflow - '{main_description}'",
            f"Expected Duration: ~{subtask.estimated_duration.total_seconds() / 60:.0f} minutes"
        ]
        
        if subtask.dependencies:
            prompt_parts.append(f"Dependencies: This task depends on completion of step(s): {', '.join(subtask.dependencies)}")
        
        if subtask.success_criteria:
            prompt_parts.append("Success Criteria:")
            for criterion in subtask.success_criteria:
                prompt_parts.append(f"- {criterion}")
        
        if subtask.context_requirements:
            prompt_parts.append("Required Context:")
            for requirement in subtask.context_requirements:
                prompt_parts.append(f"- {requirement}")
        
        prompt_parts.extend([
            "",
            "Please complete this task efficiently and provide a clear summary of what was accomplished.",
            "If you encounter any blockers or need additional information, please specify what is needed."
        ])
        
        return "\n".join(prompt_parts)
    
    async def _predict_workflow_success_rate(self, description: str, subtasks: List[Subtask]) -> float:
        """Predict workflow success rate based on historical data"""
        # Base success rate
        base_rate = 0.8
        
        # Adjust based on complexity
        complexity_modifier = len(subtasks) * -0.02  # Slightly lower success with more steps
        
        # Adjust based on agent types (some agents are more reliable)
        agent_reliability = []
        for subtask in subtasks:
            agent_info = self.agent_registry.get_agent_info(subtask.agent_type)
            agent_reliability.append(agent_info.get("success_rate", 0.8))
        
        avg_agent_reliability = sum(agent_reliability) / len(agent_reliability) if agent_reliability else 0.8
        
        # Combine factors
        predicted_rate = base_rate + complexity_modifier + (avg_agent_reliability - 0.8)
        
        # Clamp to reasonable bounds
        return max(0.3, min(0.95, predicted_rate))
    
    async def _execute_workflow(self, workflow: Workflow, session_id: str) -> WorkflowExecution:
        """Execute workflow with monitoring and error handling"""
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            session_id=session_id,
            status=TaskStatus.RUNNING,
            progress_percentage=0.0,
            completed_steps=0,
            total_steps=len(workflow.steps),
            start_time=datetime.now()
        )
        
        # Add to active workflows
        self.active_workflows[workflow.id] = execution
        
        try:
            logger.info(f"Starting workflow execution: {workflow.name}")
            
            # Execute steps in dependency order
            completed_steps = set()
            
            for step_index, step in enumerate(workflow.steps):
                # Check if dependencies are satisfied
                if not all(dep_id in completed_steps for dep_id in step.subtask.dependencies):
                    step.status = TaskStatus.BLOCKED
                    execution.insights.append(f"Step {step_index} blocked by unmet dependencies")
                    continue
                
                # Execute step
                step.status = TaskStatus.RUNNING
                step.start_time = datetime.now()
                
                # Notify progress callbacks
                execution.progress_percentage = (execution.completed_steps / execution.total_steps) * 100
                for callback in self.progress_callbacks:
                    try:
                        callback(execution)
                    except Exception as e:
                        logger.error(f"Progress callback error: {e}")
                
                try:
                    # Simulate agent execution (in real implementation, would use Task tool)
                    step_result = await self._simulate_agent_execution(step, workflow)
                    
                    step.result = step_result
                    step.status = TaskStatus.COMPLETED
                    step.end_time = datetime.now()
                    
                    completed_steps.add(step.subtask.id)
                    execution.completed_steps += 1
                    
                    # Track agent utilization
                    agent_name = step.subtask.agent_type.value
                    execution.agent_utilization[agent_name] = execution.agent_utilization.get(agent_name, 0) + 1
                    
                    logger.info(f"Completed step {step_index}: {step.subtask.description}")
                    
                except Exception as step_error:
                    step.error_message = str(step_error)
                    step.status = TaskStatus.FAILED
                    step.end_time = datetime.now()
                    
                    # Handle step failure
                    if step.retry_count < step.max_retries:
                        step.retry_count += 1
                        step.status = TaskStatus.PENDING
                        logger.warning(f"Step {step_index} failed, retrying ({step.retry_count}/{step.max_retries})")
                    else:
                        logger.error(f"Step {step_index} failed permanently: {step_error}")
                        execution.insights.append(f"Step {step_index} failed: {step_error}")
            
            # Determine final execution status
            failed_steps = [s for s in workflow.steps if s.status == TaskStatus.FAILED]
            if failed_steps:
                execution.status = TaskStatus.FAILED
                execution.insights.append(f"{len(failed_steps)} steps failed")
            elif execution.completed_steps == execution.total_steps:
                execution.status = TaskStatus.COMPLETED
                execution.insights.append("All steps completed successfully")
            else:
                execution.status = TaskStatus.FAILED
                execution.insights.append("Workflow incomplete due to dependency issues")
            
            execution.end_time = datetime.now()
            execution.progress_percentage = 100.0 if execution.status == TaskStatus.COMPLETED else (execution.completed_steps / execution.total_steps) * 100
            
            # Calculate total cost (rough estimation)
            total_duration = (execution.end_time - execution.start_time).total_seconds() / 3600
            execution.total_cost = total_duration * 2.5  # Average cost per hour
            
            # Notify completion callbacks
            for callback in self.completion_callbacks:
                try:
                    callback(execution)
                except Exception as e:
                    logger.error(f"Completion callback error: {e}")
            
            logger.info(f"Workflow execution completed: {execution.status.value}")
            
        finally:
            # Move from active to history
            if workflow.id in self.active_workflows:
                del self.active_workflows[workflow.id]
            self.workflow_history.append(execution)
        
        return execution
    
    async def _simulate_agent_execution(self, step: WorkflowStep, workflow: Workflow) -> Dict[str, Any]:
        """
        Simulate agent execution for testing/demo
        
        In real implementation, this would use the Task tool to execute with actual agents
        """
        # Simulate processing time based on estimated duration
        processing_time = min(2.0, step.subtask.estimated_duration.total_seconds() / 60)  # Max 2 seconds simulation
        await asyncio.sleep(processing_time)
        
        # Return simulated successful result
        return {
            "status": "completed",
            "summary": f"Successfully completed: {step.subtask.description}",
            "agent_type": step.subtask.agent_type.value,
            "execution_time_seconds": processing_time,
            "artifacts_created": step.subtask.output_artifacts,
            "success_criteria_met": step.subtask.success_criteria
        }
    
    async def _find_similar_workflow_patterns(self, description: str) -> List[WorkflowPattern]:
        """Find similar successful workflow patterns from search engine"""
        try:
            await self.search_engine.initialize_patterns()
            return self.search_engine.workflow_patterns
        except Exception as e:
            logger.warning(f"Could not load workflow patterns: {e}")
            return []
    
    def get_active_workflows(self) -> List[WorkflowExecution]:
        """Get all currently active workflow executions"""
        return list(self.active_workflows.values())
    
    def get_workflow_history(self, limit: int = 50) -> List[WorkflowExecution]:
        """Get recent workflow execution history"""
        return self.workflow_history[-limit:]
    
    async def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get metrics about orchestration performance"""
        total_workflows = len(self.workflow_history)
        if total_workflows == 0:
            return {"total_workflows": 0, "success_rate": 0.0}
        
        successful = len([w for w in self.workflow_history if w.status == TaskStatus.COMPLETED])
        success_rate = successful / total_workflows
        
        avg_duration = sum(
            (w.end_time - w.start_time).total_seconds() / 60 
            for w in self.workflow_history if w.end_time
        ) / max(len([w for w in self.workflow_history if w.end_time]), 1)
        
        agent_usage = {}
        for workflow in self.workflow_history:
            for agent, count in workflow.agent_utilization.items():
                agent_usage[agent] = agent_usage.get(agent, 0) + count
        
        return {
            "total_workflows": total_workflows,
            "success_rate": success_rate,
            "average_duration_minutes": avg_duration,
            "agent_utilization": agent_usage,
            "active_workflows": len(self.active_workflows)
        }
    
    # Dashboard widget support methods
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status for dashboard widgets"""
        return {
            "active_workflows": len(self.active_workflows),
            "queued_workflows": len([w for w in self.active_workflows.values() if w.status == TaskStatus.PENDING]),
            "active_agents": list(self.agent_registry.list_available_agents()),
            "resource_usage": {
                "cpu": 15.2,  # Mock data - would integrate with system monitoring
                "memory": 34.7,
                "active_connections": len(self.active_workflows)
            }
        }
    
    async def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get workflow execution statistics for dashboard widgets"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_workflows = [w for w in self.workflow_history if w.start_time >= today]
        
        completed_today = len([w for w in today_workflows if w.status == TaskStatus.COMPLETED])
        failed_today = len([w for w in today_workflows if w.status == TaskStatus.FAILED])
        
        # Calculate average duration for completed workflows
        completed_with_end_time = [w for w in today_workflows 
                                 if w.status == TaskStatus.COMPLETED and w.end_time]
        
        if completed_with_end_time:
            total_duration = sum(
                (w.end_time - w.start_time).total_seconds() / 60
                for w in completed_with_end_time
            )
            avg_duration = total_duration / len(completed_with_end_time)
        else:
            avg_duration = 0.0
        
        return {
            "completed_today": completed_today,
            "failed_today": failed_today,
            "avg_duration_minutes": avg_duration
        }