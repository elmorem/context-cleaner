"""Tests for FullContentJsonlParser."""
import pytest
from datetime import datetime
from src.context_cleaner.telemetry.jsonl_enhancement.full_content_parser import FullContentJsonlParser

class TestFullContentJsonlParser:
    
    def test_extract_message_content_simple_text(self):
        """Test extracting simple text message content."""
        jsonl_entry = {
            'uuid': 'msg-123',
            'sessionId': 'session-456',
            'timestamp': '2025-01-01T12:00:00Z',
            'message': {
                'role': 'user',
                'content': 'Hello, how are you?',
                'model': 'claude-3-5-sonnet',
                'usage': {
                    'input_tokens': 10,
                    'output_tokens': 0,
                    'cost_usd': 0.05
                }
            }
        }
        
        result = FullContentJsonlParser.extract_message_content(jsonl_entry)
        
        assert result is not None
        assert result['message_uuid'] == 'msg-123'
        assert result['session_id'] == 'session-456'
        assert result['role'] == 'user'
        assert result['message_content'] == 'Hello, how are you?'
        assert result['message_length'] == 19
        assert result['model_name'] == 'claude-3-5-sonnet'
        assert result['input_tokens'] == 10
        assert result['programming_languages'] == []
    
    def test_extract_message_content_with_tools(self):
        """Test extracting message content with tool usage."""
        jsonl_entry = {
            'uuid': 'msg-123',
            'sessionId': 'session-456',
            'timestamp': '2025-01-01T12:00:00Z',
            'message': {
                'role': 'assistant',
                'content': [
                    {
                        'type': 'text',
                        'text': 'I will read the file for you.'
                    },
                    {
                        'type': 'tool_use',
                        'name': 'Read',
                        'id': 'tool-789',
                        'input': {
                            'file_path': '/path/to/file.py'
                        }
                    }
                ],
                'model': 'claude-3-5-sonnet'
            }
        }
        
        result = FullContentJsonlParser.extract_message_content(jsonl_entry)
        
        assert result is not None
        assert 'I will read the file for you.' in result['message_content']
        assert '[TOOL_USE: Read]' in result['message_content']
        assert '/path/to/file.py' in result['message_content']
    
    def test_detect_languages_in_text(self):
        """Test programming language detection in text."""
        text_with_python = """
        Here's a Python function:
        ```python
        def hello_world():
            print("Hello, World!")
        ```
        """
        
        languages = FullContentJsonlParser._detect_languages_in_text(text_with_python)
        assert 'python' in languages
    
    def test_detect_language_from_file(self):
        """Test language detection from file extension and content."""
        # Test extension-based detection
        assert FullContentJsonlParser._detect_language_from_file('', 'test.py') == 'python'
        assert FullContentJsonlParser._detect_language_from_file('', 'test.js') == 'javascript'
        
        # Test content-based detection
        python_content = "def main():\n    import os\n    pass"
        assert FullContentJsonlParser._detect_language_from_file(python_content, 'unknown') == 'python'
        
        js_content = "function test() {\n    const x = 1;\n}"
        assert FullContentJsonlParser._detect_language_from_file(js_content, 'unknown') == 'javascript'
    
    def test_classify_file_type(self):
        """Test file type classification."""
        assert FullContentJsonlParser._classify_file_type('', 'config.json') == 'config'
        assert FullContentJsonlParser._classify_file_type('', 'README.md') == 'documentation'
        assert FullContentJsonlParser._classify_file_type('', 'main.py') == 'code'
        assert FullContentJsonlParser._classify_file_type('', 'data.json') == 'data'
    
    def test_classify_tool_output(self):
        """Test tool output classification."""
        assert FullContentJsonlParser._classify_tool_output('file content', 'Read') == 'file_content'
        assert FullContentJsonlParser._classify_tool_output('', 'Bash') == 'command_output'
        assert FullContentJsonlParser._classify_tool_output('{"key": "value"}', 'Unknown') == 'json'
        assert FullContentJsonlParser._classify_tool_output('Error: something failed', 'Unknown') == 'error'
    
    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        # Test ISO format with Z
        result = FullContentJsonlParser._parse_timestamp('2025-01-01T12:00:00Z')
        assert isinstance(result, datetime)
        
        # Test ISO format with timezone
        result = FullContentJsonlParser._parse_timestamp('2025-01-01T12:00:00+00:00')
        assert isinstance(result, datetime)
        
        # Test invalid format (should return current time)
        result = FullContentJsonlParser._parse_timestamp('invalid')
        assert isinstance(result, datetime)
    
    def test_extract_file_content(self):
        """Test extracting file content from tool results."""
        jsonl_entry = {
            'sessionId': 'session-456',
            'parentUuid': 'msg-123',
            'timestamp': '2025-01-01T12:00:00Z',
            'toolUseResult': {
                'file': {
                    'filePath': '/path/to/test.py',
                    'content': 'def hello():\n    print("Hello, World!")\n'
                }
            }
        }
        
        result = FullContentJsonlParser.extract_file_content(jsonl_entry)
        
        assert result is not None
        assert result['session_id'] == 'session-456'
        assert result['message_uuid'] == 'msg-123'
        assert result['file_path'] == '/path/to/test.py'
        assert result['file_content'] == 'def hello():\n    print("Hello, World!")\n'
        assert result['file_extension'] == '.py'
        assert result['programming_language'] == 'python'
        assert result['file_type'] == 'code'
    
    def test_extract_tool_results(self):
        """Test extracting tool execution results."""
        jsonl_entry = {
            'uuid': 'msg-123',
            'sessionId': 'session-456',
            'timestamp': '2025-01-01T12:00:00Z',
            'message': {
                'content': [
                    {
                        'type': 'tool_use',
                        'name': 'Bash',
                        'id': 'tool-789',
                        'input': {
                            'command': 'ls -la'
                        }
                    }
                ]
            },
            'toolUseResult': {
                'stdout': 'total 8\ndrwxr-xr-x 2 user user 4096 Jan  1 12:00 .',
                'stderr': '',
                'exit_code': 0
            }
        }
        
        result = FullContentJsonlParser.extract_tool_results(jsonl_entry)
        
        assert result is not None
        assert result['tool_result_uuid'] == 'tool-789'
        assert result['session_id'] == 'session-456'
        assert result['tool_name'] == 'Bash'
        assert 'ls -la' in result['tool_input']
        assert 'total 8' in result['tool_output']
        assert result['success'] is True
        assert result['output_type'] == 'command_output'