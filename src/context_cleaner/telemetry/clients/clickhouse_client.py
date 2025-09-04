"""ClickHouse client for telemetry data access."""

import os
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import subprocess
import json
import logging

from .base import TelemetryClient, SessionMetrics, ErrorEvent, TelemetryEvent

logger = logging.getLogger(__name__)


class ClickHouseClient(TelemetryClient):
    """ClickHouse client for accessing Claude Code telemetry data."""
    
    def __init__(self, host: str = "localhost", port: int = 9000, database: str = "otel"):
        self.host = host
        self.port = port
        self.database = database
        self.connection_string = f"tcp://{host}:{port}"
        
    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query against ClickHouse and return results."""
        try:
            # Use docker exec to run clickhouse-client
            cmd = [
                "docker", "exec", "clickhouse-otel", 
                "clickhouse-client", 
                "--query", query,
                "--format", "JSONEachRow"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"ClickHouse query failed: {result.stderr}")
                return []
            
            # Parse JSON lines
            results = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON line: {line}, error: {e}")
            
            return results
            
        except subprocess.TimeoutExpired:
            logger.error("ClickHouse query timed out")
            return []
        except Exception as e:
            logger.error(f"ClickHouse query error: {e}")
            return []
    
    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """Get comprehensive metrics for a specific session."""
        query = f"""
        SELECT 
            LogAttributes['session.id'] as session_id,
            MIN(Timestamp) as start_time,
            MAX(Timestamp) as end_time,
            COUNT(*) as api_calls,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
            SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
            SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens,
            SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as error_count
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body IN ('claude_code.api_request', 'claude_code.api_error')
        GROUP BY LogAttributes['session.id']
        """
        
        results = await self.execute_query(query)
        if not results:
            return None
            
        data = results[0]
        
        # Get tools used in this session
        tools_query = f"""
        SELECT DISTINCT LogAttributes['tool_name'] as tool
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body = 'claude_code.tool_decision'
            AND LogAttributes['tool_name'] != ''
        """
        
        tools_results = await self.execute_query(tools_query)
        tools_used = [t['tool'] for t in tools_results]
        
        return SessionMetrics(
            session_id=data['session_id'],
            start_time=datetime.fromisoformat(data['start_time'].replace('Z', '+00:00')),
            end_time=datetime.fromisoformat(data['end_time'].replace('Z', '+00:00')) if data['end_time'] else None,
            api_calls=int(data['api_calls']),
            total_cost=float(data['total_cost'] or 0),
            total_input_tokens=int(data['total_input_tokens'] or 0),
            total_output_tokens=int(data['total_output_tokens'] or 0),
            error_count=int(data['error_count']),
            tools_used=tools_used
        )
    
    async def get_recent_errors(self, hours: int = 24) -> List[ErrorEvent]:
        """Get recent error events within specified time window."""
        query = f"""
        SELECT 
            Timestamp,
            LogAttributes['session.id'] as session_id,
            LogAttributes['error'] as error_type,
            toFloat64OrNull(LogAttributes['duration_ms']) as duration_ms,
            LogAttributes['model'] as model,
            toInt32OrNull(LogAttributes['input_tokens']) as input_tokens,
            LogAttributes['terminal.type'] as terminal_type
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_error'
            AND Timestamp >= now() - INTERVAL {hours} HOUR
        ORDER BY Timestamp DESC
        """
        
        results = await self.execute_query(query)
        
        errors = []
        for row in results:
            errors.append(ErrorEvent(
                timestamp=datetime.fromisoformat(row['Timestamp'].replace('Z', '+00:00')),
                session_id=row['session_id'],
                error_type=row['error_type'],
                duration_ms=float(row['duration_ms']),
                model=row['model'],
                input_tokens=row['input_tokens'],
                terminal_type=row['terminal_type']
            ))
        
        return errors
    
    async def get_cost_trends(self, days: int = 7) -> Dict[str, float]:
        """Get cost trends over specified number of days."""
        query = f"""
        SELECT 
            toDate(Timestamp) as date,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as daily_cost
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
            AND Timestamp >= now() - INTERVAL {days} DAY
            AND LogAttributes['cost_usd'] != ''
        GROUP BY date
        ORDER BY date DESC
        """
        
        results = await self.execute_query(query)
        return {row['date']: float(row['daily_cost']) for row in results}
    
    async def get_current_session_cost(self, session_id: str) -> float:
        """Get the current cost for an active session."""
        query = f"""
        SELECT SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as session_cost
        FROM otel.otel_logs
        WHERE LogAttributes['session.id'] = '{session_id}'
            AND Body = 'claude_code.api_request'
            AND LogAttributes['cost_usd'] != ''
        """
        
        results = await self.execute_query(query)
        if results and results[0]['session_cost']:
            return float(results[0]['session_cost'])
        return 0.0
    
    async def get_model_usage_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get model usage statistics over specified period."""
        query = f"""
        SELECT 
            LogAttributes['model'] as model,
            COUNT(*) as request_count,
            SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
            AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration_ms,
            SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
            SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens
        FROM otel.otel_logs
        WHERE Body = 'claude_code.api_request'
            AND Timestamp >= now() - INTERVAL {days} DAY
            AND LogAttributes['model'] != ''
        GROUP BY LogAttributes['model']
        ORDER BY request_count DESC
        """
        
        results = await self.execute_query(query)
        
        stats = {}
        for row in results:
            model = row['model']
            stats[model] = {
                'request_count': int(row['request_count']),
                'total_cost': float(row['total_cost'] or 0),
                'avg_duration_ms': float(row['avg_duration_ms'] or 0),
                'total_input_tokens': int(row['total_input_tokens'] or 0),
                'total_output_tokens': int(row['total_output_tokens'] or 0),
                'cost_per_token': float(row['total_cost'] or 0) / max(int(row['total_input_tokens'] or 0), 1)
            }
        
        return stats
    
    async def get_total_aggregated_stats(self) -> Dict[str, Any]:
        """Get total aggregated statistics across all sessions."""
        try:
            # Get total tokens, sessions, costs across all data
            query = """
            SELECT 
                COUNT(DISTINCT LogAttributes['session.id']) as total_sessions,
                SUM(toFloat64OrNull(LogAttributes['input_tokens'])) as total_input_tokens,
                SUM(toFloat64OrNull(LogAttributes['output_tokens'])) as total_output_tokens,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                COUNT(*) as total_api_calls,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as total_errors,
                MIN(Timestamp) as earliest_session,
                MAX(Timestamp) as latest_session
            FROM otel.otel_logs
            WHERE Body IN ('claude_code.api_request', 'claude_code.api_error')
                AND LogAttributes['input_tokens'] != ''
                AND LogAttributes['output_tokens'] != ''
            """
            
            results = await self.execute_query(query)
            if not results:
                return self._get_fallback_stats()
            
            data = results[0]
            
            # Get active agents/tools count
            tools_query = """
            SELECT COUNT(DISTINCT LogAttributes['tool_name']) as unique_tools
            FROM otel.otel_logs
            WHERE Body = 'claude_code.tool_decision'
                AND LogAttributes['tool_name'] != ''
                AND Timestamp >= now() - INTERVAL 30 DAY
            """
            
            tools_results = await self.execute_query(tools_query)
            unique_tools = tools_results[0]['unique_tools'] if tools_results else 0
            
            # Calculate success rate
            total_requests = int(data['total_api_calls'])
            total_errors = int(data['total_errors'])
            success_rate = ((total_requests - total_errors) / max(total_requests, 1)) * 100 if total_requests > 0 else 0
            
            total_tokens = int(data['total_input_tokens'] or 0) + int(data['total_output_tokens'] or 0)
            
            return {
                'total_tokens': f"{total_tokens:,}",
                'total_sessions': f"{int(data['total_sessions'] or 0):,}",
                'success_rate': f"{success_rate:.1f}%",
                'active_agents': str(unique_tools),
                'total_cost': f"${float(data['total_cost'] or 0):.2f}",
                'total_errors': int(data['total_errors'] or 0),
                'earliest_session': data['earliest_session'],
                'latest_session': data['latest_session'],
                'raw_total_tokens': total_tokens,
                'raw_total_sessions': int(data['total_sessions'] or 0),
                'raw_success_rate': success_rate
            }
            
        except Exception as e:
            print(f"Error getting aggregated stats: {e}")
            return self._get_fallback_stats()
    
    def _get_fallback_stats(self) -> Dict[str, Any]:
        """Fallback stats when ClickHouse query fails."""
        return {
            'total_tokens': '0',
            'total_sessions': '0',
            'success_rate': '0.0%',
            'active_agents': '0',
            'total_cost': '$0.00',
            'total_errors': 0,
            'earliest_session': None,
            'latest_session': None,
            'raw_total_tokens': 0,
            'raw_total_sessions': 0,
            'raw_success_rate': 0.0
        }

    async def health_check(self) -> bool:
        """Check if ClickHouse connection is healthy."""
        try:
            results = await self.execute_query("SELECT 1 as health")
            return len(results) > 0 and results[0].get('health') == 1
        except Exception:
            return False