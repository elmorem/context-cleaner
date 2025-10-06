"""Integration tests for JSONL enhancement system."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.jsonl_enhancement.jsonl_processor_service import JsonlProcessorService

class TestJsonlIntegration:
    """Integration tests for the complete JSONL enhancement system."""
    
    @pytest.fixture
    def sample_jsonl_data(self):
        """Sample JSONL data for testing."""
        return [
            {
                "uuid": "msg-001",
                "sessionId": "session-123",
                "timestamp": "2025-01-01T12:00:00Z",
                "message": {
                    "role": "user",
                    "content": "Hello, can you help me write a Python function?",
                    "model": "claude-3-5-sonnet",
                    "usage": {
                        "input_tokens": 15,
                        "output_tokens": 0,
                        "cost_usd": 0.001
                    }
                }
            },
            {
                "uuid": "msg-002", 
                "sessionId": "session-123",
                "timestamp": "2025-01-01T12:01:00Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "I'll help you create a Python function."
                        },
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "id": "tool-001",
                            "input": {
                                "file_path": "/tmp/example.py",
                                "content": "def hello_world():\n    print('Hello, World!')\n"
                            }
                        }
                    ],
                    "model": "claude-3-5-sonnet",
                    "usage": {
                        "input_tokens": 15,
                        "output_tokens": 45,
                        "cost_usd": 0.002
                    }
                },
                "toolUseResult": {
                    "stdout": "File written successfully",
                    "stderr": "",
                    "exit_code": 0,
                    "file": {
                        "filePath": "/tmp/example.py",
                        "content": "def hello_world():\n    print('Hello, World!')\n"
                    }
                }
            }
        ]
    
    @pytest.fixture
    def temp_jsonl_file(self, sample_jsonl_data):
        """Create a temporary JSONL file with sample data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for entry in sample_jsonl_data:
                f.write(json.dumps(entry) + '\n')
            temp_file = Path(f.name)
        
        yield temp_file
        
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
    
    @pytest.fixture
    def mock_clickhouse_client(self):
        """Mock ClickHouse client for testing."""
        client = MagicMock(spec=ClickHouseClient)
        client.health_check = AsyncMock(return_value=True)
        client.bulk_insert = AsyncMock(return_value=True)
        client.execute_query = AsyncMock(return_value=[])
        client.get_jsonl_content_stats = AsyncMock(return_value={
            'messages': {'total_messages': 2, 'unique_sessions': 1},
            'files': {'total_file_accesses': 1, 'unique_files': 1},
            'tools': {'total_tool_executions': 1, 'unique_tools': 1}
        })
        return client
    
    @pytest.mark.asyncio
    async def test_jsonl_service_initialization(self, mock_clickhouse_client):
        """Test JSONL service initialization."""
        service = JsonlProcessorService(mock_clickhouse_client, 'standard')
        
        assert service.clickhouse == mock_clickhouse_client
        assert service.privacy_level == 'standard'
        assert service.processor is not None
        assert service.queries is not None
    
    @pytest.mark.asyncio
    async def test_process_jsonl_file_success(self, mock_clickhouse_client, temp_jsonl_file):
        """Test successful JSONL file processing."""
        service = JsonlProcessorService(mock_clickhouse_client, 'standard')
        
        # Mock the processor methods
        with patch.object(service.processor, 'process_jsonl_entries') as mock_process:
            mock_process.return_value = {
                'messages_processed': 2,
                'files_processed': 1,
                'tools_processed': 1,
                'errors': 0
            }
            
            stats = await service.process_jsonl_file(temp_jsonl_file, batch_size=10)
            
            # Verify results
            assert stats['total_entries'] == 2
            assert stats['messages_processed'] == 2
            assert stats['files_processed'] == 1
            assert stats['tools_processed'] == 1
            assert stats['errors'] == 0
            assert stats['batches_processed'] == 1
            assert stats['processing_time_seconds'] > 0
            
            # Verify processor was called
            mock_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_processing_status(self, mock_clickhouse_client):
        """Test getting processing status."""
        service = JsonlProcessorService(mock_clickhouse_client, 'minimal')
        
        # Mock table check query
        mock_clickhouse_client.execute_query.return_value = [
            {'name': 'claude_message_content'},
            {'name': 'claude_file_content'},
            {'name': 'claude_tool_results'}
        ]
        
        status = await service.get_processing_status()
        
        assert status['status'] == 'healthy'
        assert status['database_connection'] is True
        assert status['content_tables_available'] is True
        assert status['privacy_level'] == 'minimal'
        assert len(status['existing_tables']) == 3
        assert 'content_stats' in status
    
    @pytest.mark.asyncio
    async def test_search_conversation_content(self, mock_clickhouse_client):
        """Test conversation content search."""
        service = JsonlProcessorService(mock_clickhouse_client)
        
        # Mock search results
        mock_search_results = [
            {
                'session_id': 'session-123',
                'message_uuid': 'msg-001',
                'timestamp': '2025-01-01 12:00:00',
                'role': 'user',
                'message_preview': 'Hello, can you help me...',
                'context_snippet': '...help me write a Python function...'
            }
        ]
        
        with patch.object(service.queries, 'search_conversation_content') as mock_search:
            mock_search.return_value = mock_search_results
            
            results = await service.search_conversation_content("Python function", limit=10)
            
            assert len(results) == 1
            assert results[0]['session_id'] == 'session-123'
            assert 'Python function' in results[0]['context_snippet']
            
            mock_search.assert_called_once_with("Python function", 10)
    
    @pytest.mark.asyncio
    async def test_content_sanitization_integration(self, mock_clickhouse_client):
        """Test that content sanitization works in the integration."""
        service = JsonlProcessorService(mock_clickhouse_client, 'strict')
        
        # Create JSONL data with sensitive content
        sensitive_data = [{
            "uuid": "msg-sensitive",
            "sessionId": "session-456", 
            "timestamp": "2025-01-01T12:00:00Z",
            "message": {
                "role": "user",
                "content": "My password is secret123 and my email is user@example.com",
                "model": "claude-3-5-sonnet"
            }
        }]
        
        # Create temporary file with sensitive data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for entry in sensitive_data:
                f.write(json.dumps(entry) + '\n')
            temp_file = Path(f.name)
        
        try:
            # Mock the actual processing to capture what gets passed to ClickHouse
            captured_data = {'messages': [], 'files': [], 'tools': []}
            
            async def mock_bulk_insert(table_name, records):
                normalized_table = table_name.split('.')[-1]
                key = {
                    'claude_message_content': 'messages',
                    'claude_file_content': 'files',
                    'claude_tool_results': 'tools'
                }.get(normalized_table)
                if key:
                    captured_data[key] = records
                return True
            
            mock_clickhouse_client.bulk_insert.side_effect = mock_bulk_insert
            
            await service.process_jsonl_file(temp_file, batch_size=10)
            
            # Verify content was sanitized in the messages
            assert len(captured_data['messages']) == 1
            message_content = captured_data['messages'][0]['message_content']
            assert '[REDACTED_PASSWORD_FIELD]' in message_content
            assert '[REDACTED_EMAIL]' in message_content
        
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_clickhouse_client_bulk_insert_integration(self):
        """Test ClickHouse client bulk insert functionality."""
        # Test with a real ClickHouse client (mocked execute)
        client = ClickHouseClient()
        
        sample_records = [
            {
                'message_uuid': 'test-001',
                'session_id': 'session-test',
                'timestamp': datetime.now(),
                'role': 'user',
                'message_content': 'Test message',
                'message_length': 12,
                'input_tokens': 5,
                'output_tokens': 0
            }
        ]
        
        # Mock the subprocess.run call
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr='')
            
            result = await client.bulk_insert('claude_message_content', sample_records)
            
            assert result is True
            mock_run.assert_called_once()

            # Verify the command was constructed correctly
            call_args = mock_run.call_args
            cmd_parts = call_args[0][0]
            assert 'clickhouse-client' in cmd_parts
            assert any('INSERT INTO otel.claude_message_content FORMAT JSONEachRow' in part for part in cmd_parts)
    
    @pytest.mark.asyncio 
    async def test_parameterized_query_execution(self):
        """Test parameterized query execution."""
        client = ClickHouseClient()
        
        # Mock subprocess.run for query execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, 
                stdout='{"session_id":"test-session","message_count":5}\n'
            )
            
            query = "SELECT session_id, count() as message_count FROM otel.claude_message_content WHERE session_id = {session_id:String}"
            params = {'session_id': 'test-session'}
            
            results = await client.execute_query(query, params)
            
            assert len(results) == 1
            assert results[0]['session_id'] == 'test-session'
            assert results[0]['message_count'] == 5
            
            # Verify parameter substitution occurred
            call_args = mock_run.call_args
            # Query should be in the --query parameter
            cmd_args = call_args[0][0]
            query_index = cmd_args.index('--query') + 1
            executed_query = cmd_args[query_index]
            assert "'test-session'" in executed_query
            assert "{session_id:String}" not in executed_query
    
    def test_telemetry_module_exports(self):
        """Test that telemetry module properly exports JSONL components."""
        from src.context_cleaner.telemetry import JsonlProcessorService, FullContentQueries
        
        # Verify classes are properly exported
        assert JsonlProcessorService is not None
        assert FullContentQueries is not None
        
        # Verify they can be instantiated (with mock client)
        mock_client = MagicMock()
        service = JsonlProcessorService(mock_client)
        queries = FullContentQueries(mock_client)
        
        assert service.clickhouse == mock_client
        assert queries.clickhouse == mock_client
