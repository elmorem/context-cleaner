"""Context Window Analyzer for real-time directory-based context usage."""

import os
import json
import glob
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging
from datetime import datetime

from .session_parser import SessionCacheParser
from .models import CacheConfig, FileType

logger = logging.getLogger(__name__)


class ContextWindowAnalyzer:
    """Analyzes actual context window usage from local JSONL session files."""

    def __init__(self, claude_projects_dir: str = None):
        self.claude_projects_dir = claude_projects_dir or os.path.expanduser(
            "~/.claude/projects"
        )
        # Initialize SessionCacheParser for accurate token counting (ccusage approach)
        self.session_parser = SessionCacheParser(CacheConfig())

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
        if encoded_name.startswith("-"):
            # Remove leading dash and replace -- with /
            decoded = encoded_name[1:].replace("--", "/")
            # Replace remaining single dashes with /
            decoded = decoded.replace("-", "/")
            return f"/{decoded}"
        return encoded_name

    def _get_latest_session_file(self, project_path: str) -> Optional[str]:
        """Get the most recent session file for a project."""
        try:
            jsonl_files = sorted(
                glob.glob(f"{project_path}/*.jsonl"),
                key=os.path.getmtime,
                reverse=True,
            )

            if not jsonl_files:
                return None

            for candidate in jsonl_files:
                if not self._is_summary_file(candidate):
                    return candidate

            # Fall back to most recent file even if it's a summary
            return jsonl_files[0]

        except Exception as e:
            logger.error(f"Error finding latest session: {e}")
            return None

    def _is_summary_file(self, file_path: str) -> bool:
        """Determine if a session file is a summary metadata file."""
        summary_parser = getattr(self.session_parser, "summary_parser", None)
        if summary_parser:
            try:
                metadata = summary_parser.detect_file_type(Path(file_path))
                if metadata.file_type == FileType.SUMMARY:
                    return True
                return False
            except Exception as detection_error:  # pragma: no cover - defensive
                logger.debug(
                    "Failed to detect session file type for %s: %s",
                    file_path,
                    detection_error,
                )

        # Fallback: inspect first few lines for summary markers
        try:
            with open(file_path, "r") as handle:
                for _ in range(5):
                    line = handle.readline()
                    if not line:
                        break
                    if '"type":"summary"' in line:
                        return True
        except Exception as read_error:  # pragma: no cover - defensive
            logger.debug(
                "Failed to read session file for summary detection %s: %s",
                file_path,
                read_error,
            )

        return False

    def _find_previous_conversation_file(self, current_file: str) -> Optional[str]:
        """Locate the next most recent conversation file for a project."""
        project_path = os.path.dirname(current_file)
        try:
            jsonl_files = sorted(
                glob.glob(f"{project_path}/*.jsonl"),
                key=os.path.getmtime,
                reverse=True,
            )
        except Exception as glob_error:  # pragma: no cover - defensive
            logger.debug(
                "Failed to enumerate session files for %s: %s",
                project_path,
                glob_error,
            )
            return None

        encountered_current = False
        for candidate in jsonl_files:
            if not encountered_current:
                if os.path.samefile(candidate, current_file):
                    encountered_current = True
                continue

            if self._is_summary_file(candidate):
                continue

            return candidate

        return None

    def _analyze_session_context(self, session_file: str) -> Dict[str, any]:
        """Analyze context usage from a session file."""
        try:
            file_size = os.path.getsize(session_file)
            file_size_mb = file_size / (1024 * 1024)

            # Get basic file stats
            stat = os.stat(session_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)

            # Get actual token usage from JSONL using SessionCacheParser (ccusage approach)
            estimated_tokens = 0
            try:
                session_path = Path(session_file)
                session_analysis = self.session_parser.parse_session_file(session_path)
                if session_analysis:
                    estimated_tokens = session_analysis.total_tokens
                    logger.debug(
                        "Parsed %s actual tokens from %s",
                        estimated_tokens,
                        session_file,
                    )
                else:
                    logger.debug(
                        "Latest session file %s did not contain conversation data; searching for fallback",
                        session_file,
                    )
                    fallback_file = self._find_previous_conversation_file(session_file)
                    if fallback_file:
                        logger.debug(
                            "Using fallback session file for context stats: %s",
                            fallback_file,
                        )
                        session_path = Path(fallback_file)
                        session_analysis = self.session_parser.parse_session_file(
                            session_path
                        )
                        if session_analysis:
                            # Update file metadata to reflect the fallback file
                            session_file = fallback_file
                            file_size = os.path.getsize(session_file)
                            file_size_mb = file_size / (1024 * 1024)
                            stat = os.stat(session_file)
                            last_modified = datetime.fromtimestamp(stat.st_mtime)
                            estimated_tokens = session_analysis.total_tokens
                        else:
                            logger.warning(
                                "Fallback session file also lacked conversation data: %s",
                                fallback_file,
                            )
                    else:
                        logger.debug(
                            "No fallback conversation file found for directory %s",
                            os.path.dirname(session_file),
                        )
            except Exception as e:
                logger.error(f"Error parsing tokens from {session_file}: {e}")
                # No fallback estimation - maintain accuracy by returning 0

            # Count entries and tool usage
            entry_count, tool_calls, file_reads = self._count_session_activity(
                session_file
            )

            return {
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size_mb, 2),
                "estimated_tokens": estimated_tokens,
                "last_activity": last_modified,
                "entry_count": entry_count,
                "tool_calls": tool_calls,
                "file_reads": file_reads,
                "session_file": os.path.basename(session_file),
            }

        except Exception as e:
            logger.error(f"Error analyzing session {session_file}: {e}")
            return {
                "file_size_bytes": 0,
                "file_size_mb": 0,
                "estimated_tokens": 0,
                "last_activity": None,
                "entry_count": 0,
                "tool_calls": 0,
                "file_reads": 0,
                "session_file": "unknown",
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

            with open(session_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_count += 1

                        # Check for tool usage
                        message = entry.get("message", {})
                        content = message.get("content", [])

                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "tool_use":
                                        tool_calls += 1
                                        if item.get("name") == "Read":
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

            with open(session_file, "r") as f:
                data = f.read(sample_size)
                lines = data.split("\n")

                for line in lines:
                    if line.strip():
                        try:
                            entry = json.loads(line.strip())
                            sample_entries += 1

                            message = entry.get("message", {})
                            content = message.get("content", [])

                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        if item.get("type") == "tool_use":
                                            sample_tools += 1
                                            if item.get("name") == "Read":
                                                sample_reads += 1

                        except json.JSONDecodeError:
                            continue

            # Extrapolate to full file
            ratio = file_size / sample_size if sample_size > 0 else 1

            return (
                int(sample_entries * ratio),
                int(sample_tools * ratio),
                int(sample_reads * ratio),
            )

        except Exception as e:
            logger.error(f"Error sampling session: {e}")
            return 0, 0, 0

    def get_all_sessions_stats(self) -> Dict[str, any]:
        """Get comprehensive statistics across ALL session files (not just latest)."""
        all_stats = {}
        total_tokens = 0
        total_sessions = 0
        total_size_bytes = 0

        try:
            for project_path in glob.glob(f"{self.claude_projects_dir}/*"):
                if not os.path.isdir(project_path):
                    continue

                project_name = os.path.basename(project_path)
                directory = self._decode_project_path(project_name)

                # Get ALL session files for this project
                all_session_files = self._get_all_session_files(project_path)

                project_tokens = 0
                project_sessions = 0
                project_size = 0

                for session_file in all_session_files:
                    try:
                        session_path = Path(session_file)
                        session_analysis = self.session_parser.parse_session_file(
                            session_path
                        )

                        if session_analysis:
                            project_tokens += session_analysis.total_tokens
                            project_sessions += 1
                            project_size += os.path.getsize(session_file)

                    except Exception as e:
                        logger.debug(f"Error parsing session {session_file}: {e}")
                        continue

                if project_sessions > 0:
                    all_stats[directory] = {
                        "total_tokens": project_tokens,
                        "session_count": project_sessions,
                        "total_size_bytes": project_size,
                        "total_size_mb": round(project_size / (1024 * 1024), 2),
                    }

                    total_tokens += project_tokens
                    total_sessions += project_sessions
                    total_size_bytes += project_size

        except Exception as e:
            logger.error(f"Error analyzing all sessions: {e}")

        return {
            "total_tokens": total_tokens,
            "total_sessions": total_sessions,
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "project_count": len(all_stats),
            "projects": all_stats,
        }

    def _get_all_session_files(self, project_path: str) -> List[str]:
        """Get all session files for a project (not just the latest)."""
        try:
            jsonl_files = sorted(
                glob.glob(f"{project_path}/*.jsonl"),
                key=os.path.getmtime,
                reverse=True,
            )

            # Filter out summary files
            conversation_files = []
            for candidate in jsonl_files:
                if not self._is_summary_file(candidate):
                    conversation_files.append(candidate)

            return conversation_files

        except Exception as e:
            logger.error(f"Error finding all session files: {e}")
            return []

    def get_total_context_usage(self) -> Dict[str, any]:
        """Get total context usage across all projects (active sessions only)."""
        stats = self.get_directory_context_stats()

        total_size_bytes = sum(d["file_size_bytes"] for d in stats.values())
        total_size_mb = sum(d["file_size_mb"] for d in stats.values())
        total_tokens = sum(d["estimated_tokens"] for d in stats.values())
        total_entries = sum(d["entry_count"] for d in stats.values())
        total_tools = sum(d["tool_calls"] for d in stats.values())
        total_reads = sum(d["file_reads"] for d in stats.values())

        active_directories = len([d for d in stats.values() if d["last_activity"]])

        return {
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_mb, 2),
            "estimated_total_tokens": total_tokens,
            "total_entries": total_entries,
            "total_tool_calls": total_tools,
            "total_file_reads": total_reads,
            "active_directories": active_directories,
            "directory_breakdown": stats,
        }
