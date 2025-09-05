"""Extract COMPLETE content from JSONL entries for database storage."""
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
            if not isinstance(tool_result, dict):
                return None
                
            file_info = tool_result.get('file', {})
            if not isinstance(file_info, dict):
                return None
            
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
        
        # Data files (check before code to prioritize data classification)
        data_extensions = ['.json', '.xml', '.csv', '.yaml', '.yml', '.sql']
        if any(ext in path_lower for ext in data_extensions):
            return 'data'
        
        # Code files
        code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php']
        if any(ext in path_lower for ext in code_extensions):
            return 'code'
        
        return 'text'
    
    @staticmethod
    def _classify_tool_output(output: str, tool_name: str) -> str:
        """Classify the type of tool output."""
        # Tool-specific classification first
        if tool_name == 'Read':
            return 'file_content'
        elif tool_name == 'Bash':
            return 'command_output'
        elif tool_name in ['Write', 'Edit']:
            return 'file_operation'
        
        # Then check for empty output
        if not output:
            return 'empty'
        
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