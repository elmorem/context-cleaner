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
        
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a query against ClickHouse and return results."""
        try:
            # Handle parameterized queries by substituting parameters
            final_query = query
            if params:
                for key, value in params.items():
                    if isinstance(value, str):
                        # Escape and quote string values
                        escaped_value = value.replace("'", "\\'").replace("\\", "\\\\")
                        final_query = final_query.replace(f"{{{key}:String}}", f"'{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        final_query = final_query.replace(f"{{{key}:UInt32}}", str(value))
                        final_query = final_query.replace(f"{{{key}:Float64}}", str(value))
                        final_query = final_query.replace(f"{{{key}:Int32}}", str(value))
            
            # Use docker exec to run clickhouse-client
            cmd = [
                "docker", "exec", "clickhouse-otel", 
                "clickhouse-client", 
                "--query", final_query,
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
            # Get total tokens from official Claude Code token usage metrics
            # This includes input, output, cacheRead, and cacheCreation tokens
            token_query = """
            SELECT 
                Attributes['type'] as token_type,
                SUM(Value) as total_tokens
            FROM otel.otel_metrics_sum
            WHERE MetricName = 'claude_code.token.usage'
            GROUP BY token_type
            """
            
            token_results = await self.execute_query(token_query)
            
            # Calculate total tokens from all types (input + output + cacheRead + cacheCreation)
            total_tokens = 0
            token_breakdown = {}
            for row in token_results:
                token_type = row['token_type']
                tokens = int(row['total_tokens'])
                token_breakdown[token_type] = tokens
                total_tokens += tokens
            
            # Get sessions, costs, and API calls from OTEL logs
            stats_query = """
            SELECT 
                COUNT(DISTINCT LogAttributes['session.id']) as total_sessions,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                COUNT(*) as total_api_calls,
                SUM(CASE WHEN Body = 'claude_code.api_error' THEN 1 ELSE 0 END) as total_errors,
                MIN(Timestamp) as earliest_session,
                MAX(Timestamp) as latest_session
            FROM otel.otel_logs
            WHERE Body IN ('claude_code.api_request', 'claude_code.api_error')
            """
            
            stats_results = await self.execute_query(stats_query)
            if not stats_results:
                return self._get_fallback_stats()
            
            data = stats_results[0]
            
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
                'raw_success_rate': success_rate,
                'token_breakdown': token_breakdown  # Include breakdown for debugging
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

    # ===== JSONL CONTENT METHODS =====
    
    async def bulk_insert(self, table_name: str, records: List[Dict[str, Any]]) -> bool:
        """Bulk insert records into specified table."""
        if not records:
            return True
            
        try:
            # Convert records to JSON lines format with datetime handling
            def default_serializer(obj):
                if isinstance(obj, datetime):
                    # Format timestamp in ClickHouse-compatible format
                    return obj.strftime('%Y-%m-%d %H:%M:%S')
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            json_lines = '\n'.join([json.dumps(record, default=default_serializer) for record in records])
            
            # Use clickhouse-client with JSONEachRow format for bulk insert
            cmd = [
                "docker", "exec", "-i", "clickhouse-otel", 
                "clickhouse-client", 
                "--query", f"INSERT INTO otel.{table_name} FORMAT JSONEachRow",
            ]
            
            result = subprocess.run(
                cmd, 
                input=json_lines, 
                text=True, 
                capture_output=True, 
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Bulk insert failed for {table_name}: {result.stderr}")
                return False
            
            logger.info(f"Successfully inserted {len(records)} records into {table_name}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Bulk insert timed out for {table_name}")
            return False
        except Exception as e:
            logger.error(f"Bulk insert error for {table_name}: {e}")
            return False
    
    async def get_jsonl_content_stats(self) -> Dict[str, Any]:
        """Get statistics about JSONL content storage."""
        try:
            stats = {}
            
            # Message content stats
            message_query = """
            SELECT 
                count() as total_messages,
                uniq(session_id) as unique_sessions,
                sum(message_length) as total_characters,
                avg(message_length) as avg_message_length,
                sum(input_tokens) as total_input_tokens,
                sum(output_tokens) as total_output_tokens,
                sum(cost_usd) as total_cost,
                countIf(contains_code_blocks) as messages_with_code,
                min(timestamp) as earliest_message,
                max(timestamp) as latest_message
            FROM otel.claude_message_content
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            message_results = await self.execute_query(message_query)
            stats['messages'] = message_results[0] if message_results else {}
            
            # File content stats
            file_query = """
            SELECT 
                count() as total_file_accesses,
                uniq(file_path) as unique_files,
                sum(file_size) as total_file_bytes,
                avg(file_size) as avg_file_size,
                avg(line_count) as avg_line_count,
                countIf(contains_secrets) as files_with_secrets,
                countIf(contains_imports) as files_with_imports
            FROM otel.claude_file_content
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            file_results = await self.execute_query(file_query)
            stats['files'] = file_results[0] if file_results else {}
            
            # Tool results stats
            tool_query = """
            SELECT 
                count() as total_tool_executions,
                uniq(tool_name) as unique_tools,
                countIf(success) as successful_executions,
                round(countIf(success) * 100.0 / count(), 2) as success_rate,
                sum(output_size) as total_output_bytes
            FROM otel.claude_tool_results
            WHERE timestamp >= now() - INTERVAL 30 DAY
            """
            
            tool_results = await self.execute_query(tool_query)
            stats['tools'] = tool_results[0] if tool_results else {}
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting JSONL content stats: {e}")
            return {}

    async def get_model_token_stats(self, time_range_days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get model-specific token statistics from official Claude Code metrics."""
        try:
            # Get token data by model and type from official metrics
            token_query = f"""
            SELECT 
                Attributes['model'] as model,
                Attributes['type'] as token_type,
                SUM(Value) as total_tokens
            FROM otel.otel_metrics_sum
            WHERE MetricName = 'claude_code.token.usage'
                AND TimeUnix >= now() - INTERVAL {time_range_days} DAY
                AND Attributes['model'] IS NOT NULL
                AND Attributes['type'] IS NOT NULL
            GROUP BY Attributes['model'], Attributes['type']
            ORDER BY Attributes['model'], total_tokens DESC
            """
            
            token_results = await self.execute_query(token_query)
            
            # Get cost and request count from OTEL logs (still needed for these metrics)
            cost_query = f"""
            SELECT 
                LogAttributes['model'] as model,
                COUNT(*) as request_count,
                AVG(toFloat64OrNull(LogAttributes['cost_usd'])) as avg_cost,
                SUM(toFloat64OrNull(LogAttributes['cost_usd'])) as total_cost,
                AVG(toFloat64OrNull(LogAttributes['duration_ms'])) as avg_duration
            FROM otel.otel_logs 
            WHERE Body = 'claude_code.api_request'
                AND Timestamp >= now() - INTERVAL {time_range_days} DAY
                AND LogAttributes['model'] IS NOT NULL
                AND LogAttributes['cost_usd'] IS NOT NULL
            GROUP BY LogAttributes['model']
            ORDER BY request_count DESC
            """
            
            cost_results = await self.execute_query(cost_query)
            
            # Combine token and cost data by model
            model_stats = {}
            
            # Process token data first
            for row in token_results:
                model = row['model']
                token_type = row['token_type']
                tokens = int(row['total_tokens'])
                
                if model not in model_stats:
                    model_stats[model] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'cache_read_tokens': 0,
                        'cache_creation_tokens': 0,
                        'total_tokens': 0,
                        'request_count': 0,
                        'avg_cost': 0.0,
                        'total_cost': 0.0,
                        'avg_duration': 0.0
                    }
                
                # Map token types to our structure
                if token_type == 'input':
                    model_stats[model]['input_tokens'] = tokens
                elif token_type == 'output':
                    model_stats[model]['output_tokens'] = tokens
                elif token_type == 'cacheRead':
                    model_stats[model]['cache_read_tokens'] = tokens
                elif token_type == 'cacheCreation':
                    model_stats[model]['cache_creation_tokens'] = tokens
                
                model_stats[model]['total_tokens'] += tokens
            
            # Add cost and request data
            for row in cost_results:
                model = row['model']
                if model in model_stats:
                    model_stats[model].update({
                        'request_count': int(row['request_count']),
                        'avg_cost': float(row['avg_cost'] or 0),
                        'total_cost': float(row['total_cost'] or 0),
                        'avg_duration': float(row['avg_duration'] or 0)
                    })
            
            # Calculate efficiency metrics
            for model, stats in model_stats.items():
                total_tokens = stats['total_tokens']
                total_cost = stats['total_cost']
                
                if total_tokens > 0 and total_cost > 0:
                    stats['cost_per_token'] = total_cost / total_tokens
                    stats['tokens_per_dollar'] = total_tokens / total_cost
                else:
                    stats['cost_per_token'] = 0
                    stats['tokens_per_dollar'] = 0
            
            return model_stats
            
        except Exception as e:
            logger.error(f"Error getting model token stats: {e}")
            return {}