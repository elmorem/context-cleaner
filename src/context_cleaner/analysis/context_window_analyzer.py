"""Context Window Analyzer for real-time directory-based context usage."""

import os
import json
import glob
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ContextWindowAnalyzer:
    """Analyzes actual context window usage from local JSONL session files."""
    
    def __init__(self, claude_projects_dir: str = None):
        self.claude_projects_dir = claude_projects_dir or os.path.expanduser("~/.claude/projects")
        
    def get_directory_context_stats(self) -> Dict[str, Dict[str, any]]:
        """Get context window statistics for each active directory."""
        stats = {}
        
        try:
            for project_path in glob.glob(f"{self.claude_projects_dir}/*"):
                if not os.path.isdir(project_path):
                    continue
                    
                project_name = os.path.basename(project_path)
                # Convert project path back to readable directory
                directory = self._decode_project_path(project_name)
                
                # Get latest session file and its stats
                latest_session = self._get_latest_session_file(project_path)
                if latest_session:
                    context_data = self._analyze_session_context(latest_session)
                    stats[directory] = context_data
                    
        except Exception as e:
            logger.error(f"Error analyzing context stats: {e}")
            
        return stats
    
    def _decode_project_path(self, encoded_name: str) -> str:
        """Convert encoded project name back to readable path."""
        # Claude encodes paths like: -Users-markelmore--code-context-cleaner
        if encoded_name.startswith('-'):
            # Remove leading dash and replace -- with /
            decoded = encoded_name[1:].replace('--', '/')
            # Replace remaining single dashes with /
            decoded = decoded.replace('-', '/')
            return f"/{decoded}"
        return encoded_name
    
    def _get_latest_session_file(self, project_path: str) -> Optional[str]:
        """Get the most recent session file for a project."""
        try:
            jsonl_files = glob.glob(f"{project_path}/*.jsonl")
            if not jsonl_files:
                return None
                
            # Get the largest file (likely current active session)
            latest_file = max(jsonl_files, key=os.path.getsize)
            return latest_file
            
        except Exception as e:
            logger.error(f"Error finding latest session: {e}")
            return None
    
    def _analyze_session_context(self, session_file: str) -> Dict[str, any]:
        """Analyze context usage from a session file."""
        try:
            file_size = os.path.getsize(session_file)
            file_size_mb = file_size / (1024 * 1024)
            
            # Get basic file stats
            stat = os.stat(session_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Estimate context window usage
            # Rough estimate: 1 token ≈ 4 characters for text
            estimated_tokens = file_size // 4
            
            # Count entries and tool usage
            entry_count, tool_calls, file_reads = self._count_session_activity(session_file)
            
            return {
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size_mb, 2),
                'estimated_tokens': estimated_tokens,
                'last_activity': last_modified,
                'entry_count': entry_count,
                'tool_calls': tool_calls,
                'file_reads': file_reads,
                'session_file': os.path.basename(session_file)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing session {session_file}: {e}")
            return {
                'file_size_bytes': 0,
                'file_size_mb': 0,
                'estimated_tokens': 0,
                'last_activity': None,
                'entry_count': 0,
                'tool_calls': 0,
                'file_reads': 0,
                'session_file': 'unknown'
            }
    
    def _count_session_activity(self, session_file: str) -> Tuple[int, int, int]:
        """Count entries, tool calls, and file reads in session."""
        entry_count = 0
        tool_calls = 0
        file_reads = 0
        
        try:
            # For very large files, sample rather than read entire file
            file_size = os.path.getsize(session_file)
            
            if file_size > 10 * 1024 * 1024:  # > 10MB
                # Sample the file instead of reading entirely
                return self._sample_session_activity(session_file)
            
            with open(session_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_count += 1
                        
                        # Check for tool usage
                        message = entry.get('message', {})
                        content = message.get('content', [])
                        
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'tool_use':
                                        tool_calls += 1
                                        if item.get('name') == 'Read':
                                            file_reads += 1
                                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error counting session activity: {e}")
            
        return entry_count, tool_calls, file_reads
    
    def _sample_session_activity(self, session_file: str) -> Tuple[int, int, int]:
        """Sample large files to estimate activity."""
        try:
            file_size = os.path.getsize(session_file)
            sample_size = min(1024 * 1024, file_size // 10)  # Sample 1MB or 10% of file
            
            sample_entries = 0
            sample_tools = 0
            sample_reads = 0
            
            with open(session_file, 'r') as f:
                data = f.read(sample_size)
                lines = data.split('\n')
                
                for line in lines:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            sample_entries += 1
                            
                            message = entry.get('message', {})
                            content = message.get('content', [])
                            
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        if item.get('type') == 'tool_use':
                                            sample_tools += 1
                                            if item.get('name') == 'Read':
                                                sample_reads += 1
                                                
                        except json.JSONDecodeError:
                            continue
            
            # Extrapolate to full file
            ratio = file_size / sample_size if sample_size > 0 else 1
            
            return (
                int(sample_entries * ratio),
                int(sample_tools * ratio), 
                int(sample_reads * ratio)
            )
            
        except Exception as e:
            logger.error(f"Error sampling session: {e}")
            return 0, 0, 0
    
    def get_total_context_usage(self) -> Dict[str, any]:
        """Get total context usage across all projects."""
        stats = self.get_directory_context_stats()
        
        total_size_bytes = sum(d['file_size_bytes'] for d in stats.values())
        total_size_mb = sum(d['file_size_mb'] for d in stats.values())
        total_tokens = sum(d['estimated_tokens'] for d in stats.values())
        total_entries = sum(d['entry_count'] for d in stats.values())
        total_tools = sum(d['tool_calls'] for d in stats.values())
        total_reads = sum(d['file_reads'] for d in stats.values())
        
        active_directories = len([d for d in stats.values() if d['last_activity']])
        
        return {
            'total_size_bytes': total_size_bytes,
            'total_size_mb': round(total_size_mb, 2),
            'estimated_total_tokens': total_tokens,
            'total_entries': total_entries,
            'total_tool_calls': total_tools,
            'total_file_reads': total_reads,
            'active_directories': active_directories,
            'directory_breakdown': stats
        }