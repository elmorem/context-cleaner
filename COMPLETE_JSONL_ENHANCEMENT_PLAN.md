# COMPLETE JSONL Enhancement Plan - Full Content Storage Implementation

## Executive Summary

**Mission**: Store and analyze complete JSONL conversation data including full message content, file contents, and tool results in ClickHouse for comprehensive Context Cleaner enhancement.

**Key Principle**: *Complete Content Storage* - This system captures the full 144.79 MB of actual conversation data currently stored only in local JSONL files.

**Architecture Philosophy**: Privacy-first full content database with searchable conversation history, file content analysis, and tool usage intelligence.

---

## Critical Implementation Update: FULL CONTENT STORAGE

### Database Schema - Complete Content Storage

The system stores **actual content**, not just metadata:

#### 1. Complete Message Content Storage
```sql
CREATE TABLE otel.claude_message_content (
    message_uuid String,
    session_id String, 
    timestamp DateTime64(3),
    role LowCardinality(String), -- 'user', 'assistant'
    
    -- FULL MESSAGE CONTENT STORAGE
    message_content String,      -- COMPLETE conversation message (full user prompts, assistant responses)
    message_preview String,      -- First 200 chars for quick access
    message_hash String,         -- SHA-256 for deduplication
    message_length UInt32,       -- Character count
    
    -- Message metadata
    model_name String,
    input_tokens UInt32,
    output_tokens UInt32,
    cost_usd Float64,
    
    -- Content analysis (computed from full content)
    contains_code_blocks Bool MATERIALIZED position(message_content, '```') > 0,
    contains_file_references Bool MATERIALIZED position(message_content, '/') > 0 OR position(message_content, '\\') > 0,
    programming_languages Array(String), -- Detected from content
    
    PRIMARY KEY (message_uuid),
    INDEX idx_session (session_id) TYPE set(100) GRANULARITY 8192,
    INDEX idx_content_hash (message_hash) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_search (message_content) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = MergeTree()
ORDER BY (session_id, timestamp)
PARTITION BY toDate(timestamp)
TTL timestamp + INTERVAL 30 DAY;
```

#### 2. Complete File Content Storage
```sql
CREATE TABLE otel.claude_file_content (
    file_access_uuid String,
    session_id String,
    message_uuid String, -- Links to the message that accessed this file
    timestamp DateTime64(3),
    
    -- COMPLETE FILE CONTENT STORAGE
    file_path String,
    file_content String,         -- ENTIRE file contents when read by tools
    file_content_hash String,    -- SHA-256 for deduplication 
    file_size UInt32,           -- Size in bytes
    file_extension LowCardinality(String),
    operation_type LowCardinality(String), -- 'read', 'write', 'edit'
    
    -- File analysis (computed from full content)
    file_type LowCardinality(String), -- 'code', 'config', 'data', 'documentation'
    programming_language LowCardinality(String),
    contains_secrets Bool MATERIALIZED position(lower(file_content), 'password') > 0 OR position(lower(file_content), 'api_key') > 0,
    contains_imports Bool MATERIALIZED position(file_content, 'import ') > 0 OR position(file_content, '#include') > 0,
    line_count UInt32 MATERIALIZED length(file_content) - length(replaceAll(file_content, '\n', '')) + 1,
    
    PRIMARY KEY (file_access_uuid),
    INDEX idx_file_path (file_path) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_hash (file_content_hash) TYPE set(1000) GRANULARITY 8192,
    INDEX idx_content_search (file_content) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = ReplacingMergeTree() -- Use ReplacingMergeTree for file deduplication
ORDER BY (file_path, file_content_hash)
PARTITION BY toDate(timestamp)
TTL timestamp + INTERVAL 30 DAY;
```

#### 3. Complete Tool Results Storage
```sql
CREATE TABLE otel.claude_tool_results (
    tool_result_uuid String,
    session_id String,
    message_uuid String,
    timestamp DateTime64(3),
    
    -- COMPLETE TOOL EXECUTION CONTENT
    tool_name LowCardinality(String),
    tool_input String,          -- COMPLETE tool parameters/commands
    tool_output String,         -- COMPLETE tool output/results/stdout
    tool_error String,          -- Complete error messages/stderr
    
    -- Tool metadata
    execution_time_ms UInt32,
    success Bool,
    exit_code Int32,
    
    -- Content analysis (computed from full output)
    output_size UInt32 MATERIALIZED length(tool_output),
    contains_error Bool MATERIALIZED length(tool_error) > 0,
    output_type LowCardinality(String), -- 'text', 'json', 'binary', 'image'
    is_file_operation Bool MATERIALIZED tool_name IN ('Read', 'Write', 'Edit'),
    is_system_command Bool MATERIALIZED tool_name = 'Bash',
    
    PRIMARY KEY (tool_result_uuid),
    INDEX idx_tool_name (tool_name) TYPE set(50) GRANULARITY 8192,
    INDEX idx_output_search (tool_output) TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 1
    
) ENGINE = MergeTree()
ORDER BY (session_id, timestamp, tool_name)
PARTITION BY toDate(timestamp)  
TTL timestamp + INTERVAL 30 DAY;
```

---

## Full Content JSONL Parser Implementation

### Complete Content Extraction

```python
# /src/context_cleaner/jsonl_enhancement/full_content_parser.py
import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class FullContentJsonlParser:
    """Extract COMPLETE content from JSONL entries for database storage."""
    
    @staticmethod
    def extract_message_content(jsonl_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract FULL message content from JSONL entry."""
        try:
            message = jsonl_entry.get('message', {})
            content = message.get('content', '')
            
            # Handle different content formats
            full_content = ""
            if isinstance(content, list):
                # Assistant messages with tools - reconstruct full content
                for item in content:
                    if item.get('type') == 'text':
                        full_content += item.get('text', '')
                    elif item.get('type') == 'tool_use':
                        tool_name = item.get('name', 'unknown')
                        tool_input = json.dumps(item.get('input', {}), indent=2)
                        full_content += f"\n[TOOL_USE: {tool_name}]\nInput: {tool_input}\n"
            elif isinstance(content, str):
                # Simple text content (user messages)
                full_content = content
            else:
                full_content = str(content)
            
            # Detect programming languages in content
            detected_languages = FullContentJsonlParser._detect_languages_in_text(full_content)
            
            return {
                'message_uuid': jsonl_entry.get('uuid'),
                'session_id': jsonl_entry.get('sessionId'),
                'timestamp': FullContentJsonlParser._parse_timestamp(jsonl_entry.get('timestamp')),
                'role': message.get('role', 'unknown'),
                'message_content': full_content,  # COMPLETE MESSAGE CONTENT
                'message_preview': full_content[:200] if full_content else '',
                'message_hash': hashlib.sha256(full_content.encode()).hexdigest(),
                'message_length': len(full_content),
                'model_name': message.get('model', ''),
                'input_tokens': message.get('usage', {}).get('input_tokens', 0),
                'output_tokens': message.get('usage', {}).get('output_tokens', 0),
                'cost_usd': message.get('usage', {}).get('cost_usd', 0.0),
                'programming_languages': detected_languages
            }
            
        except Exception as e:
            logger.error(f"Error extracting message content: {e}")
            return None
    
    @staticmethod  
    def extract_file_content(jsonl_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract COMPLETE file content from tool results."""
        try:
            # Look for tool results that contain file content
            tool_result = jsonl_entry.get('toolUseResult', {})
            file_info = tool_result.get('file', {})
            
            if not file_info:
                return None
            
            file_content = file_info.get('content', '')  # COMPLETE FILE CONTENT
            file_path = file_info.get('filePath', '')
            
            if not file_content or not file_path:
                return None
            
            # Analyze file content
            programming_language = FullContentJsonlParser._detect_language_from_file(file_content, file_path)
            file_type = FullContentJsonlParser._classify_file_type(file_content, file_path)
            
            return {
                'file_access_uuid': str(uuid.uuid4()),
                'session_id': jsonl_entry.get('sessionId'), 
                'message_uuid': jsonl_entry.get('parentUuid'),
                'timestamp': FullContentJsonlParser._parse_timestamp(jsonl_entry.get('timestamp')),
                'file_path': file_path,
                'file_content': file_content,  # COMPLETE FILE CONTENTS
                'file_content_hash': hashlib.sha256(file_content.encode()).hexdigest(),
                'file_size': len(file_content.encode()),
                'file_extension': Path(file_path).suffix.lower() if file_path else '',
                'operation_type': 'read',  # Inferred from JSONL context
                'file_type': file_type,
                'programming_language': programming_language
            }
            
        except Exception as e:
            logger.error(f"Error extracting file content: {e}")
            return None
    
    @staticmethod
    def extract_tool_results(jsonl_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract COMPLETE tool execution results."""
        try:
            # Extract tool use information from message
            message = jsonl_entry.get('message', {})
            content = message.get('content', [])
            
            tool_data = None
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'tool_use':
                        tool_data = item
                        break
            
            if not tool_data:
                return None
            
            # Get complete tool result
            tool_result = jsonl_entry.get('toolUseResult', {})
            
            # Reconstruct complete tool input
            tool_input_full = json.dumps(tool_data.get('input', {}), indent=2)
            
            # Get complete tool output
            stdout = tool_result.get('stdout', '')
            stderr = tool_result.get('stderr', '')
            tool_output_full = stdout
            tool_error_full = stderr if stderr else None
            
            # Determine output type
            output_type = FullContentJsonlParser._classify_tool_output(tool_output_full, tool_data.get('name'))
            
            return {
                'tool_result_uuid': tool_data.get('id', str(uuid.uuid4())),
                'session_id': jsonl_entry.get('sessionId'),
                'message_uuid': jsonl_entry.get('uuid'),
                'timestamp': FullContentJsonlParser._parse_timestamp(jsonl_entry.get('timestamp')),
                'tool_name': tool_data.get('name'),
                'tool_input': tool_input_full,        # COMPLETE TOOL INPUT
                'tool_output': tool_output_full,      # COMPLETE TOOL OUTPUT
                'tool_error': tool_error_full,        # COMPLETE ERROR OUTPUT
                'execution_time_ms': 0,  # Could be calculated if timestamps available
                'success': not bool(stderr),
                'exit_code': tool_result.get('exit_code', 0),
                'output_type': output_type
            }
            
        except Exception as e:
            logger.error(f"Error extracting tool results: {e}")
            return None
    
    @staticmethod
    def _detect_languages_in_text(text: str) -> List[str]:
        """Detect programming languages mentioned in text content."""
        languages = []
        
        # Code block detection
        import re
        code_blocks = re.findall(r'```(\w+)', text)
        languages.extend(code_blocks)
        
        # Keyword detection
        language_patterns = {
            'python': ['def ', 'import ', 'from ', '__init__', 'self.'],
            'javascript': ['function ', 'const ', 'let ', 'var ', '=>'],
            'typescript': ['interface ', 'type ', ': string', ': number'],
            'java': ['public class', 'private ', 'public static void'],
            'sql': ['SELECT ', 'FROM ', 'WHERE ', 'INSERT ', 'UPDATE'],
            'bash': ['#!/bin/bash', 'echo ', 'grep ', 'awk ', 'sed '],
            'go': ['func ', 'package ', 'import (', 'type '],
            'rust': ['fn ', 'let mut', 'impl ', 'struct ']
        }
        
        text_upper = text.upper()
        for lang, patterns in language_patterns.items():
            if any(pattern.upper() in text_upper for pattern in patterns):
                languages.append(lang)
        
        return list(set(languages))  # Remove duplicates
    
    @staticmethod
    def _detect_language_from_file(content: str, file_path: str) -> str:
        """Detect programming language from file content and extension."""
        extension_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.cs': 'csharp',
            '.rb': 'ruby', '.php': 'php', '.go': 'go', '.rs': 'rust',
            '.sql': 'sql', '.md': 'markdown', '.html': 'html', '.css': 'css',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml',
            '.sh': 'bash', '.bat': 'batch', '.ps1': 'powershell'
        }
        
        ext = Path(file_path).suffix.lower()
        if ext in extension_map:
            return extension_map[ext]
        
        # Content-based detection for files without clear extensions
        if 'def ' in content and ('import ' in content or 'from ' in content):
            return 'python'
        elif ('function ' in content or 'const ' in content) and ('{' in content and '}' in content):
            return 'javascript'
        elif 'SELECT ' in content.upper() and 'FROM ' in content.upper():
            return 'sql'
        elif content.strip().startswith('#!/bin/bash') or content.strip().startswith('#!/bin/sh'):
            return 'bash'
        elif content.strip().startswith('{') and content.strip().endswith('}'):
            return 'json'
        
        return 'text'
    
    @staticmethod
    def _classify_file_type(content: str, file_path: str) -> str:
        """Classify the type of file based on content and path."""
        path_lower = file_path.lower()
        
        # Configuration files
        if any(pattern in path_lower for pattern in ['config', '.env', 'settings', '.ini', '.conf']):
            return 'config'
        
        # Documentation
        if any(ext in path_lower for ext in ['.md', '.rst', '.txt', 'readme', 'doc']):
            return 'documentation'
        
        # Code files
        code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
        if any(ext in path_lower for ext in code_extensions):
            return 'code'
        
        # Data files
        data_extensions = ['.json', '.xml', '.csv', '.yaml', '.yml', '.sql']
        if any(ext in path_lower for ext in data_extensions):
            return 'data'
        
        return 'text'
    
    @staticmethod
    def _classify_tool_output(output: str, tool_name: str) -> str:
        """Classify the type of tool output."""
        if not output:
            return 'empty'
        
        if tool_name == 'Read':
            return 'file_content'
        elif tool_name == 'Bash':
            return 'command_output'
        elif tool_name in ['Write', 'Edit']:
            return 'file_operation'
        
        # Content-based classification
        output_stripped = output.strip()
        if output_stripped.startswith('{') and output_stripped.endswith('}'):
            return 'json'
        elif output_stripped.startswith('<') and output_stripped.endswith('>'):
            return 'xml'
        elif 'Error:' in output or 'Exception:' in output or 'Traceback' in output:
            return 'error'
        
        return 'text'
    
    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object."""
        try:
            # Handle ISO format with Z suffix
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except:
            return datetime.now()
```

---

## Enhanced Dashboard Queries - Full Content Access

### Rich Content Analysis and Search

```python
# /src/context_cleaner/dashboard/full_content_queries.py
from typing import List, Dict, Any, Optional
from ..telemetry.clients.clickhouse_client import ClickHouseClient

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
        
        return await self.clickhouse.execute_query(query, {'session_id': session_id})
    
    async def search_conversation_content(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
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
        
        return await self.clickhouse.execute_query(query, {
            'search_term': search_term,
            'limit': limit
        })
    
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
        
        return await self.clickhouse.execute_query(query, {'file_path': file_path})
    
    async def search_file_content(self, search_term: str, language: Optional[str] = None) -> List[Dict[str, Any]]:
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
        params = {'search_term': search_term}
        
        if language:
            language_filter = "AND programming_language = {language:String}"
            params['language'] = language
        
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
                    extractAll(file_content, 'def\\s+(\\w+)\\(') as python_functions,
                    extractAll(file_content, 'function\\s+(\\w+)\\(') as js_functions,
                    extractAll(file_content, 'class\\s+(\\w+)') as class_names
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
        
        results = await self.clickhouse.execute_query(query, {'language': language})
        return results[0] if results else {}
    
    async def get_tool_execution_analysis(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
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
            params['tool_name'] = tool_name
        
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
        stats['messages'] = message_stats[0] if message_stats else {}
        
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
        stats['files'] = file_stats[0] if file_stats else {}
        
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
        stats['tools'] = tool_stats[0] if tool_stats else {}
        
        return stats
```

---

## Privacy and Security for Full Content

### Content Sanitization Before Storage

```python
# /src/context_cleaner/jsonl_enhancement/content_security.py
import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ContentSecurityManager:
    """Manage security and privacy for full content storage."""
    
    # Comprehensive PII patterns
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        'api_key': r'\b[A-Za-z0-9]{20,}\b',
        'password_field': r'(password|passwd|pwd)[\s=:\'\"]+[^\s\'"]+',
        'token_field': r'(token|key|secret)[\s=:\'\"]+[^\s\'"]+',
        'private_key': r'-----BEGIN (RSA |EC |)PRIVATE KEY-----',
        'aws_key': r'AKIA[0-9A-Z]{16}',
        'github_token': r'ghp_[A-Za-z0-9]{36}',
        'slack_token': r'xox[baprs]-[A-Za-z0-9-]+'
    }
    
    @classmethod
    def sanitize_content(cls, content: str, privacy_level: str = 'standard') -> str:
        """Sanitize content based on privacy level."""
        if not content:
            return content
        
        if privacy_level == 'strict':
            return cls._strict_sanitization(content)
        elif privacy_level == 'standard':
            return cls._standard_sanitization(content)
        elif privacy_level == 'minimal':
            return cls._minimal_sanitization(content)
        
        return content
    
    @classmethod
    def _strict_sanitization(cls, content: str) -> str:
        """Strict sanitization - redact most potentially sensitive content."""
        sanitized = content
        
        # Redact all PII patterns
        for pattern_name, pattern in cls.PII_PATTERNS.items():
            sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=re.IGNORECASE)
        
        # Redact file paths that might contain usernames
        sanitized = re.sub(r'/home/[^/\s]+', '/home/[REDACTED]', sanitized)
        sanitized = re.sub(r'C:\\Users\\[^\\]+', 'C:\\Users\\[REDACTED]', sanitized)
        
        # Redact URLs with sensitive info
        sanitized = re.sub(r'https?://[^\s]+', '[REDACTED_URL]', sanitized)
        
        return sanitized
    
    @classmethod  
    def _standard_sanitization(cls, content: str) -> str:
        """Standard sanitization - redact obvious secrets and PII."""
        sanitized = content
        
        # Redact critical patterns
        critical_patterns = ['api_key', 'password_field', 'token_field', 'private_key', 'aws_key', 'github_token', 'slack_token']
        for pattern_name in critical_patterns:
            if pattern_name in cls.PII_PATTERNS:
                pattern = cls.PII_PATTERNS[pattern_name]
                sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=re.IGNORECASE)
        
        # Redact email addresses
        sanitized = re.sub(cls.PII_PATTERNS['email'], '[REDACTED_EMAIL]', sanitized)
        
        return sanitized
    
    @classmethod
    def _minimal_sanitization(cls, content: str) -> str:
        """Minimal sanitization - only redact obvious API keys and tokens."""
        sanitized = content
        
        # Only redact the most critical patterns
        critical_patterns = ['private_key', 'aws_key', 'github_token', 'slack_token']
        for pattern_name in critical_patterns:
            if pattern_name in cls.PII_PATTERNS:
                pattern = cls.PII_PATTERNS[pattern_name]
                sanitized = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    @classmethod
    def analyze_content_risks(cls, content: str) -> Dict[str, Any]:
        """Analyze content for potential security risks."""
        risks = {
            'contains_pii': False,
            'contains_secrets': False,
            'contains_credentials': False,
            'risk_level': 'low',
            'detected_patterns': []
        }
        
        for pattern_name, pattern in cls.PII_PATTERNS.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                risks['detected_patterns'].append({
                    'type': pattern_name,
                    'count': len(matches)
                })
                
                if pattern_name in ['email', 'phone', 'ssn', 'credit_card']:
                    risks['contains_pii'] = True
                elif pattern_name in ['api_key', 'token_field', 'private_key', 'aws_key', 'github_token']:
                    risks['contains_secrets'] = True
                elif pattern_name in ['password_field']:
                    risks['contains_credentials'] = True
        
        # Determine overall risk level
        if risks['contains_secrets'] or risks['contains_credentials']:
            risks['risk_level'] = 'high'
        elif risks['contains_pii']:
            risks['risk_level'] = 'medium'
        
        return risks
```

---

## Complete Implementation Integration

### Enhanced Batch Processor for Full Content

```python
# /src/context_cleaner/jsonl_enhancement/full_content_processor.py
import asyncio
from typing import List, Dict, Any
from .full_content_parser import FullContentJsonlParser
from .content_security import ContentSecurityManager
from ..telemetry.clients.clickhouse_client import ClickHouseClient

class FullContentBatchProcessor:
    """Process complete JSONL content for database storage."""
    
    def __init__(self, clickhouse_client: ClickHouseClient, privacy_level: str = 'standard'):
        self.clickhouse = clickhouse_client
        self.privacy_level = privacy_level
        self.parser = FullContentJsonlParser()
        self.security_manager = ContentSecurityManager()
    
    async def process_jsonl_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process JSONL entries and store complete content."""
        stats = {
            'messages_processed': 0,
            'files_processed': 0,
            'tools_processed': 0,
            'errors': 0
        }
        
        message_batch = []
        file_batch = []
        tool_batch = []
        
        for entry in entries:
            try:
                # Extract message content
                message_data = self.parser.extract_message_content(entry)
                if message_data:
                    # Sanitize content before storage
                    message_data['message_content'] = self.security_manager.sanitize_content(
                        message_data['message_content'], 
                        self.privacy_level
                    )
                    message_batch.append(message_data)
                
                # Extract file content
                file_data = self.parser.extract_file_content(entry)
                if file_data:
                    # Sanitize file content
                    file_data['file_content'] = self.security_manager.sanitize_content(
                        file_data['file_content'],
                        self.privacy_level
                    )
                    file_batch.append(file_data)
                
                # Extract tool results
                tool_data = self.parser.extract_tool_results(entry)
                if tool_data:
                    # Sanitize tool outputs
                    tool_data['tool_output'] = self.security_manager.sanitize_content(
                        tool_data['tool_output'],
                        self.privacy_level
                    )
                    if tool_data['tool_error']:
                        tool_data['tool_error'] = self.security_manager.sanitize_content(
                            tool_data['tool_error'],
                            self.privacy_level
                        )
                    tool_batch.append(tool_data)
                
            except Exception as e:
                logger.error(f"Error processing JSONL entry: {e}")
                stats['errors'] += 1
        
        # Batch insert into respective tables
        if message_batch:
            await self.clickhouse.bulk_insert('claude_message_content', message_batch)
            stats['messages_processed'] = len(message_batch)
        
        if file_batch:
            await self.clickhouse.bulk_insert('claude_file_content', file_batch)
            stats['files_processed'] = len(file_batch)
        
        if tool_batch:
            await self.clickhouse.bulk_insert('claude_tool_results', tool_batch)
            stats['tools_processed'] = len(tool_batch)
        
        return stats
```

---

## Summary: Complete Content Storage

**YES - The database now stores ACTUAL CONTENT:**

✅ **Complete Conversation Messages**: Full user prompts and assistant responses  
✅ **Complete File Contents**: Entire file contents when accessed by tools  
✅ **Complete Tool Results**: Full command outputs, error messages, execution results  
✅ **Searchable Content**: Full-text search across all stored content  
✅ **Content Analysis**: Programming language detection, pattern analysis, security scanning  
✅ **Privacy Protection**: Configurable sanitization with PII/credential redaction  

**Content Storage Capabilities:**
- **Message Search**: Search through actual conversation content  
- **Code Analysis**: Analyze patterns in real file contents
- **Tool Intelligence**: Complete tool execution history with full outputs
- **Content Statistics**: Comprehensive analytics on actual content
- **Security Analysis**: PII and credential detection in real content

This implementation provides the **complete conversation and file content database** that enables comprehensive analysis of actual usage patterns, far beyond just metadata and file paths.

The plan is now saved in `/Users/markelmore/_code/context-cleaner/COMPLETE_JSONL_ENHANCEMENT_PLAN.md` with full content storage specifications.