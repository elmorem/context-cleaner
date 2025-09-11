"""
Claude Code Telemetry Data Collector

This module collects telemetry data from Claude Code sessions and feeds it into
the ClickHouse database for analysis by the Tool Usage Optimizer and Model 
Efficiency Tracker widgets.
"""

import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import random
import os

from .clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Represents a single tool execution result for telemetry collection."""
    
    tool_result_uuid: str
    session_id: str
    message_uuid: str
    timestamp: datetime
    tool_name: str
    tool_input: str
    tool_output: str
    tool_error: str
    execution_time_ms: int
    success: bool
    exit_code: int
    output_type: str


class ClaudeCodeTelemetryCollector:
    """Collects and stores Claude Code session telemetry data."""
    
    def __init__(self):
        """Initialize the telemetry collector."""
        self.clickhouse_client = ClickHouseClient()
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.is_enabled = os.getenv("CLAUDE_CODE_ENABLE_TELEMETRY", "0") == "1"
        
        # Service management state
        self.running = False
        self.background_task = None
        self.last_health_check = None
        self.metrics_collected = 0
        self.last_collection_time = None
        self.collection_errors = 0
        
        logger.info(f"Telemetry collector initialized - enabled: {self.is_enabled}")
        
    async def log_tool_usage(self, tool_result: ToolResult) -> bool:
        """
        Log a tool usage event to ClickHouse.
        
        Args:
            tool_result: The tool execution result to log
            
        Returns:
            True if successfully logged, False otherwise
        """
        if not self.is_enabled:
            logger.debug("Telemetry disabled, skipping tool usage log")
            return False
            
        try:
            # Convert to ClickHouse format
            data = {
                "tool_result_uuid": tool_result.tool_result_uuid,
                "session_id": tool_result.session_id,
                "message_uuid": tool_result.message_uuid,
                "timestamp": tool_result.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "tool_name": tool_result.tool_name,
                "tool_input": tool_result.tool_input,
                "tool_output": tool_result.tool_output,
                "tool_error": tool_result.tool_error,
                "execution_time_ms": tool_result.execution_time_ms,
                "success": tool_result.success,
                "exit_code": tool_result.exit_code,
                "output_type": tool_result.output_type
            }
            
            # Insert into ClickHouse
            success = await self._insert_tool_result(data)
            
            if success:
                logger.debug(f"Logged tool usage: {tool_result.tool_name} (session: {tool_result.session_id})")
            else:
                logger.warning(f"Failed to log tool usage: {tool_result.tool_name}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error logging tool usage: {e}")
            return False
    
    async def _insert_tool_result(self, data: Dict[str, Any]) -> bool:
        """Insert tool result data into ClickHouse."""
        try:
            # Convert to JSON format with datetime handling
            def default_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.strftime('%Y-%m-%d %H:%M:%S')
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            json_data = json.dumps(data, default=default_serializer)
            
            # Use docker exec with clickhouse-client (same as existing bulk_insert)
            cmd = [
                "docker", "exec", "-i", "clickhouse-otel", 
                "clickhouse-client", 
                "--query", "INSERT INTO otel.claude_tool_results FORMAT JSONEachRow",
            ]
            
            result = subprocess.run(
                cmd, 
                input=json_data, 
                text=True, 
                capture_output=True, 
                timeout=30
            )
            
            if result.returncode == 0:
                logger.debug(f"Successfully inserted tool result: {data['tool_name']}")
                return True
            else:
                logger.error(f"ClickHouse insert failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("ClickHouse insert timed out")
            return False
        except Exception as e:
            logger.error(f"Error inserting tool result: {e}")
            return False
    
    async def generate_sample_data(self, duration_minutes: int = 60) -> int:
        """
        Generate sample telemetry data for testing the widgets.
        
        Args:
            duration_minutes: How many minutes of data to generate
            
        Returns:
            Number of records generated
        """
        if not self.is_enabled:
            logger.warning("Telemetry disabled, cannot generate sample data")
            return 0
            
        logger.info(f"Generating {duration_minutes} minutes of sample telemetry data...")
        
        # Common Claude Code tools
        tools = [
            "Read", "Write", "Edit", "Bash", "Glob", "Grep", 
            "Task", "WebFetch", "WebSearch", "TodoWrite"
        ]
        
        # Generate realistic data distribution
        tool_weights = {
            "Read": 0.25,      # Most common - reading files
            "Edit": 0.20,      # Second most - editing files  
            "Bash": 0.15,      # Running commands
            "Write": 0.10,     # Writing new files
            "Grep": 0.08,      # Searching content
            "Glob": 0.05,      # Finding files
            "Task": 0.05,      # Agent tasks
            "WebFetch": 0.04,  # Web requests
            "WebSearch": 0.04, # Web searches
            "TodoWrite": 0.04  # Todo management
        }
        
        records_generated = 0
        start_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        # Generate data points (roughly 1-3 tool calls per minute)
        num_points = duration_minutes * random.randint(1, 3)
        
        for i in range(num_points):
            # Random timestamp within the duration
            minutes_offset = random.uniform(0, duration_minutes)
            timestamp = start_time + timedelta(minutes=minutes_offset)
            
            # Select tool based on realistic distribution
            tool_name = random.choices(tools, weights=list(tool_weights.values()))[0]
            
            # Generate realistic execution times based on tool type
            if tool_name in ["Read", "Write", "Edit"]:
                exec_time = random.randint(50, 500)  # File operations
            elif tool_name == "Bash":
                exec_time = random.randint(100, 2000)  # Commands vary widely
            elif tool_name in ["WebFetch", "WebSearch"]:
                exec_time = random.randint(500, 3000)  # Network operations
            elif tool_name == "Task":
                exec_time = random.randint(1000, 5000)  # Agent tasks take longer
            else:
                exec_time = random.randint(100, 800)  # Other tools
            
            # Most operations succeed
            success = random.random() > 0.05  # 95% success rate
            
            tool_result = ToolResult(
                tool_result_uuid=str(uuid.uuid4()),
                session_id=self.session_id,
                message_uuid=str(uuid.uuid4()),
                timestamp=timestamp,
                tool_name=tool_name,
                tool_input=self._generate_sample_input(tool_name),
                tool_output=self._generate_sample_output(tool_name, success),
                tool_error="" if success else self._generate_sample_error(tool_name),
                execution_time_ms=exec_time,
                success=success,
                exit_code=0 if success else random.choice([1, 2, 127]),
                output_type="text"
            )
            
            # Log the tool usage
            logged = await self.log_tool_usage(tool_result)
            if logged:
                records_generated += 1
                
            # Small delay to avoid overwhelming the system
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        logger.info(f"Generated {records_generated} telemetry records")
        return records_generated
    
    def _generate_sample_input(self, tool_name: str) -> str:
        """Generate realistic sample input for different tools."""
        samples = {
            "Read": '{"file_path": "/Users/user/project/src/main.py"}',
            "Write": '{"file_path": "/Users/user/project/output.txt", "content": "Sample content"}',
            "Edit": '{"file_path": "/Users/user/project/config.py", "old_string": "DEBUG = False", "new_string": "DEBUG = True"}',
            "Bash": '{"command": "python -m pytest tests/", "description": "Run tests"}',
            "Grep": '{"pattern": "function.*main", "path": "src/"}',
            "Glob": '{"pattern": "**/*.py"}',
            "Task": '{"description": "Analyze codebase", "prompt": "Review the code structure"}',
            "WebFetch": '{"url": "https://api.github.com/repos/user/repo", "prompt": "Get repo info"}',
            "WebSearch": '{"query": "Python best practices 2024"}',
            "TodoWrite": '{"todos": [{"content": "Fix bug in parser", "status": "pending"}]}'
        }
        return samples.get(tool_name, f'{{"tool": "{tool_name}", "params": "sample"}}')
    
    def _generate_sample_output(self, tool_name: str, success: bool) -> str:
        """Generate realistic sample output for different tools."""
        if not success:
            return ""
            
        samples = {
            "Read": "File contents: def main():\\n    print('Hello, World!')\\n",
            "Write": "File written successfully",
            "Edit": "File edited successfully",
            "Bash": "Collected 15 items\\n\\n=============== 15 passed in 2.34s ===============",
            "Grep": "src/main.py:5:def main():\\nsrc/utils.py:12:function main_helper():",
            "Glob": "src/main.py\\nsrc/utils.py\\ntests/test_main.py",
            "Task": "Analysis complete. The codebase follows standard Python structure.",
            "WebFetch": '{"name": "example-repo", "stars": 156, "language": "Python"}',
            "WebSearch": "Found 10 relevant results about Python best practices",
            "TodoWrite": "Todos updated successfully"
        }
        return samples.get(tool_name, f"Output from {tool_name}")
    
    def _generate_sample_error(self, tool_name: str) -> str:
        """Generate realistic sample errors for different tools."""
        errors = {
            "Read": "FileNotFoundError: [Errno 2] No such file or directory",
            "Write": "PermissionError: [Errno 13] Permission denied",
            "Edit": "ValueError: old_string not found in file",
            "Bash": "Command failed with exit code 1",
            "Grep": "No matches found",
            "Glob": "Invalid glob pattern",
            "Task": "Agent task timed out",
            "WebFetch": "HTTPError: 404 Not Found",
            "WebSearch": "Search request failed",
            "TodoWrite": "Invalid todo format"
        }
        return errors.get(tool_name, f"Error in {tool_name}")
    
    async def start_service(self) -> bool:
        """Start the telemetry collection service."""
        if not self.is_enabled:
            logger.info("Telemetry collection disabled via environment variable")
            return False
            
        if self.running:
            logger.warning("Telemetry collector already running")
            return True
            
        try:
            self.running = True
            self.last_health_check = datetime.now()
            
            # Start background collection task (if needed for continuous collection)
            # For now, we just mark as running since collection happens on-demand
            logger.info(f"Telemetry collector service started (session: {self.session_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start telemetry collector service: {e}")
            self.running = False
            return False
    
    async def stop_service(self) -> bool:
        """Stop the telemetry collection service."""
        if not self.running:
            return True
            
        try:
            self.running = False
            
            if self.background_task and not self.background_task.done():
                self.background_task.cancel()
                try:
                    await self.background_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Telemetry collector service stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping telemetry collector service: {e}")
            return False
    
    def is_healthy(self) -> bool:
        """Check if the telemetry collector service is healthy."""
        if not self.is_enabled or not self.running:
            return False
            
        try:
            # Check if we can connect to ClickHouse
            result = subprocess.run(
                ["docker", "exec", "clickhouse-otel", "clickhouse-client", "--query", "SELECT 1"],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False
            
            # Update health check timestamp
            self.last_health_check = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"Telemetry collector health check failed: {e}")
            self.collection_errors += 1
            return False
    
    def get_service_metrics(self) -> dict:
        """Get service metrics for monitoring."""
        return {
            "session_id": self.session_id,
            "running": self.running,
            "enabled": self.is_enabled,
            "metrics_collected": self.metrics_collected,
            "collection_errors": self.collection_errors,
            "last_collection_time": self.last_collection_time.isoformat() if self.last_collection_time else None,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
        }


# Global collector instance
_collector = None


def get_collector() -> ClaudeCodeTelemetryCollector:
    """Get the global telemetry collector instance."""
    global _collector
    if _collector is None:
        _collector = ClaudeCodeTelemetryCollector()
    return _collector


async def log_tool_usage(tool_name: str, tool_input: str, tool_output: str, 
                        execution_time_ms: int, success: bool = True, 
                        tool_error: str = "", exit_code: int = 0) -> bool:
    """
    Convenience function to log tool usage.
    
    Args:
        tool_name: Name of the tool used
        tool_input: Input parameters to the tool
        tool_output: Output from the tool
        execution_time_ms: How long the tool took to execute
        success: Whether the tool executed successfully
        tool_error: Error message if tool failed
        exit_code: Exit code from tool execution
        
    Returns:
        True if logged successfully, False otherwise
    """
    collector = get_collector()
    
    tool_result = ToolResult(
        tool_result_uuid=str(uuid.uuid4()),
        session_id=collector.session_id,
        message_uuid=str(uuid.uuid4()),
        timestamp=datetime.now(),
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        tool_error=tool_error,
        execution_time_ms=execution_time_ms,
        success=success,
        exit_code=exit_code,
        output_type="text"
    )
    
    return await collector.log_tool_usage(tool_result)