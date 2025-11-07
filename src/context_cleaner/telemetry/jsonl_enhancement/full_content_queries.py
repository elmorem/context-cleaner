"""Advanced queries for complete content analysis."""

from typing import List, Dict, Any, Optional
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient


class FullContentQueries:
    """Advanced queries for complete content analysis."""

    def __init__(self, clickhouse_client: ClickHouseClient):
        self.clickhouse = clickhouse_client

    async def get_complete_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """Get COMPLETE conversation content for a session."""
        query = """
        SELECT 
            message_uuid,
            timestamp,
            role,
            message_content,        -- FULL MESSAGE CONTENT
            message_length,
            input_tokens,
            output_tokens,
            cost_usd,
            model_name,
            contains_code_blocks,
            programming_languages
        FROM otel.claude_message_content
        WHERE session_id = {session_id:String}
        ORDER BY timestamp ASC
        """

        return await self.clickhouse.execute_query(query, {"session_id": session_id})

    async def search_conversation_content(
        self, search_term: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search through ACTUAL message content across all conversations."""
        query = """
        SELECT 
            session_id,
            message_uuid, 
            timestamp,
            role,
            message_preview,
            message_length,
            model_name,
            -- Extract context around the search term
            substr(
                message_content, 
                greatest(1, position(lower(message_content), lower({search_term:String})) - 100), 
                300
            ) as context_snippet
        FROM otel.claude_message_content
        WHERE lower(message_content) LIKE '%' || lower({search_term:String}) || '%'
        ORDER BY timestamp DESC
        LIMIT {limit:UInt32}
        """

        return await self.clickhouse.execute_query(
            query, {"search_term": search_term, "limit": limit}
        )

    async def get_complete_file_history(self, file_path: str) -> List[Dict[str, Any]]:
        """Get COMPLETE file content history with full contents."""
        query = """
        SELECT 
            session_id,
            message_uuid,
            timestamp,
            file_content,           -- COMPLETE FILE CONTENT
            file_size,
            operation_type,
            programming_language,
            file_type,
            contains_secrets,
            contains_imports,
            line_count
        FROM otel.claude_file_content  
        WHERE file_path = {file_path:String}
        ORDER BY timestamp DESC
        """

        return await self.clickhouse.execute_query(query, {"file_path": file_path})

    async def search_file_content(
        self, search_term: str, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search through ACTUAL file contents."""
        query = """
        SELECT 
            session_id,
            file_path,
            timestamp,
            file_size,
            programming_language,
            file_type,
            -- Extract code context around search term
            substr(
                file_content,
                greatest(1, position(lower(file_content), lower({search_term:String})) - 200),
                500
            ) as code_snippet
        FROM otel.claude_file_content
        WHERE lower(file_content) LIKE '%' || lower({search_term:String}) || '%'
        {language_filter}
        ORDER BY timestamp DESC
        LIMIT 100
        """

        language_filter = ""
        params = {"search_term": search_term}

        if language:
            language_filter = "AND programming_language = {language:String}"
            params["language"] = language

        formatted_query = query.format(language_filter=language_filter)

        return await self.clickhouse.execute_query(formatted_query, params)

    async def analyze_code_patterns(self, language: str) -> Dict[str, Any]:
        """Analyze patterns in ACTUAL code content."""
        query = """
        WITH 
            function_matches AS (
                SELECT 
                    session_id,
                    file_path,
                    extractAll(file_content, 'def\\\\s+(\\\\w+)\\\\(') as python_functions,
                    extractAll(file_content, 'function\\\\s+(\\\\w+)\\\\(') as js_functions,
                    extractAll(file_content, 'class\\\\s+(\\\\w+)') as class_names
                FROM otel.claude_file_content
                WHERE programming_language = {language:String}
            )
        SELECT 
            count() as total_files,
            avg(file_size) as avg_file_size,
            avg(line_count) as avg_line_count,
            uniq(session_id) as unique_sessions,
            
            -- Most common function names
            arrayStringConcat(
                arraySlice(
                    topK(10)(arrayJoin(
                        arrayConcat(python_functions, js_functions)
                    )), 1, 10
                ), ', '
            ) as common_functions,
            
            -- Most common class names  
            arrayStringConcat(
                arraySlice(
                    topK(5)(arrayJoin(class_names)), 1, 5
                ), ', '
            ) as common_classes,
            
            -- Files with potential issues
            countIf(contains_secrets) as files_with_secrets,
            countIf(file_size > 10000) as large_files
            
        FROM function_matches
        """

        results = await self.clickhouse.execute_query(query, {"language": language})
        return results[0] if results else {}

    async def get_tool_execution_analysis(
        self, tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze COMPLETE tool execution results."""
        query = """
        SELECT 
            tool_name,
            count() as execution_count,
            countIf(success) as successful_executions,
            round(countIf(success) * 100.0 / count(), 2) as success_rate,
            avg(output_size) as avg_output_size,
            countIf(contains_error) as error_count,
            
            -- Sample of recent tool inputs and outputs
            groupArray(
                tuple(tool_input, left(tool_output, 200))
            )[1:5] as sample_executions
            
        FROM otel.claude_tool_results
        {tool_filter}
        GROUP BY tool_name
        ORDER BY execution_count DESC
        """

        tool_filter = ""
        params = {}

        if tool_name:
            tool_filter = "WHERE tool_name = {tool_name:String}"
            params["tool_name"] = tool_name

        formatted_query = query.format(tool_filter=tool_filter)

        return await self.clickhouse.execute_query(formatted_query, params)

    async def get_content_statistics(self) -> Dict[str, Any]:
        """Get comprehensive content statistics."""
        stats = {}

        # Message content statistics
        message_stats_query = """
        SELECT 
            count() as total_messages,
            uniq(session_id) as unique_sessions,
            sum(message_length) as total_characters,
            avg(message_length) as avg_message_length,
            sum(input_tokens) as total_input_tokens,
            sum(output_tokens) as total_output_tokens,
            sum(cost_usd) as total_cost,
            countIf(contains_code_blocks) as messages_with_code,
            arrayStringConcat(
                arraySlice(topK(5)(arrayJoin(programming_languages)), 1, 5), 
                ', '
            ) as top_languages
        FROM otel.claude_message_content
        WHERE timestamp >= now() - INTERVAL 30 DAY
        """

        message_stats = await self.clickhouse.execute_query(message_stats_query)
        stats["messages"] = message_stats[0] if message_stats else {}

        # File content statistics
        file_stats_query = """
        SELECT 
            count() as total_file_accesses,
            uniq(file_path) as unique_files,
            sum(file_size) as total_file_bytes,
            avg(file_size) as avg_file_size,
            avg(line_count) as avg_line_count,
            countIf(contains_secrets) as files_with_secrets,
            countIf(contains_imports) as files_with_imports,
            arrayStringConcat(
                arraySlice(topK(5)(programming_language), 1, 5),
                ', '
            ) as top_file_languages
        FROM otel.claude_file_content
        WHERE timestamp >= now() - INTERVAL 30 DAY
        """

        file_stats = await self.clickhouse.execute_query(file_stats_query)
        stats["files"] = file_stats[0] if file_stats else {}

        # Tool execution statistics
        tool_stats_query = """
        SELECT 
            count() as total_tool_executions,
            uniq(tool_name) as unique_tools,
            countIf(success) as successful_executions,
            round(countIf(success) * 100.0 / count(), 2) as overall_success_rate,
            sum(output_size) as total_output_bytes,
            arrayStringConcat(
                arraySlice(topK(5)(tool_name), 1, 5),
                ', '
            ) as most_used_tools
        FROM otel.claude_tool_results
        WHERE timestamp >= now() - INTERVAL 30 DAY
        """

        tool_stats = await self.clickhouse.execute_query(tool_stats_query)
        stats["tools"] = tool_stats[0] if tool_stats else {}

        return stats

    async def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation sessions with basic metadata."""
        query = f"""
        SELECT 
            session_id,
            min(timestamp) as session_start,
            max(timestamp) as session_end,
            count() as message_count,
            sum(message_length) as total_characters,
            countIf(role = 'user') as user_messages,
            countIf(role = 'assistant') as assistant_messages,
            countIf(contains_code_blocks) as code_messages,
            sum(input_tokens) as total_input_tokens,
            sum(output_tokens) as total_output_tokens,
            sum(cost_usd) as session_cost
        FROM otel.claude_message_content
        WHERE timestamp >= now() - INTERVAL 30 DAY
        GROUP BY session_id
        ORDER BY session_start DESC
        LIMIT {limit}
        """

        return await self.clickhouse.execute_query(query)
