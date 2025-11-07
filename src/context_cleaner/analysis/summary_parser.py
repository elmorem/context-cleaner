"""
Project Summary Parser

Parses Claude Code project summary files to extract project metadata,
completion status, categorization, and analytics data.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator

from .models import (
    ProjectSummary,
    SummaryType,
    FileMetadata,
    FileType,
)

logger = logging.getLogger(__name__)


class ProjectSummaryParser:
    """Parser for Claude Code project summary files (.jsonl format)."""

    def __init__(self):
        """Initialize parser."""
        self.stats = {
            "files_parsed": 0,
            "summaries_parsed": 0,
            "errors_encountered": 0,
            "parse_time_seconds": 0.0,
        }

    def detect_file_type(self, file_path: Path) -> FileMetadata:
        """
        Detect if a JSONL file contains conversation data or summary metadata.

        Args:
            file_path: Path to the .jsonl file

        Returns:
            FileMetadata with file type detection results
        """
        try:
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return FileMetadata(
                    file_path=str(file_path),
                    file_type=FileType.UNKNOWN,
                    first_line_content={},
                    line_count=0,
                    file_size_bytes=0,
                    last_modified=datetime.now(),
                )

            # Get file stats
            file_stat = file_path.stat()
            file_size_bytes = file_stat.st_size
            last_modified = datetime.fromtimestamp(file_stat.st_mtime)

            # Read first line to determine file type
            first_line_content = {}
            line_count = 0

            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    line_count = line_num

                    # Parse first non-empty line
                    if line_num == 1 or not first_line_content:
                        try:
                            first_line_content = json.loads(line)
                        except json.JSONDecodeError:
                            continue

            # Determine file type based on first line content
            file_type = self._classify_file_type(first_line_content)

            return FileMetadata(
                file_path=str(file_path),
                file_type=file_type,
                first_line_content=first_line_content,
                line_count=line_count,
                file_size_bytes=file_size_bytes,
                last_modified=last_modified,
            )

        except Exception as e:
            logger.error(f"Error detecting file type for {file_path}: {e}")
            return FileMetadata(
                file_path=str(file_path),
                file_type=FileType.UNKNOWN,
                first_line_content={},
                line_count=0,
                file_size_bytes=0,
                last_modified=datetime.now(),
            )

    def _classify_file_type(self, first_line: Dict[str, Any]) -> FileType:
        """
        Classify file type based on first line content structure.

        Args:
            first_line: Parsed JSON content of first line

        Returns:
            FileType enum value
        """
        if not first_line:
            return FileType.UNKNOWN

        # Check for summary file indicators
        if first_line.get("type") == "summary":
            return FileType.SUMMARY

        # Check for conversation file indicators
        if (
            first_line.get("uuid")
            and first_line.get("timestamp")
            and ("message" in first_line or "type" in first_line)
        ):
            return FileType.CONVERSATION

        return FileType.UNKNOWN

    def parse_summary_file(self, file_path: Path) -> List[ProjectSummary]:
        """
        Parse a project summary file.

        Args:
            file_path: Path to the .jsonl summary file

        Returns:
            List of ProjectSummary objects
        """
        start_time = datetime.now()
        summaries = []

        try:
            if not file_path.exists():
                logger.warning(f"Summary file not found: {file_path}")
                return []

            logger.info(f"Parsing summary file: {file_path}")

            for summary_data in self._parse_summary_lines(file_path):
                summary = self._parse_summary_data(summary_data, file_path)
                if summary:
                    summaries.append(summary)

            # Update stats
            self.stats["files_parsed"] += 1
            self.stats["summaries_parsed"] += len(summaries)
            self.stats["parse_time_seconds"] += (
                datetime.now() - start_time
            ).total_seconds()

            logger.info(f"Parsed {len(summaries)} summaries from {file_path}")
            return summaries

        except Exception as e:
            logger.error(f"Error parsing summary file {file_path}: {e}")
            self.stats["errors_encountered"] += 1
            return []

    def _parse_summary_lines(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """
        Parse summary data from .jsonl file.

        Args:
            file_path: Path to .jsonl file

        Yields:
            Dict objects with summary data
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        if data.get("type") == "summary":
                            yield data
                        else:
                            logger.debug(
                                f"Skipping non-summary line {line_num} in {file_path}"
                            )

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Invalid JSON on line {line_num} in {file_path}: {e}"
                        )
                        continue
                    except Exception as e:
                        logger.warning(
                            f"Error parsing line {line_num} in {file_path}: {e}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Error reading summary file {file_path}: {e}")
            return

    def _parse_summary_data(
        self, data: Dict[str, Any], file_path: Path
    ) -> Optional[ProjectSummary]:
        """
        Parse a single summary from JSON data.

        Args:
            data: JSON data for a single summary
            file_path: Path to the source file

        Returns:
            ProjectSummary object or None if parsing fails
        """
        try:
            # Extract required fields
            uuid = data.get("uuid", f"summary_{file_path.stem}")
            leaf_uuid = data.get("leafUuid", "")
            summary_text = data.get("summary", "")

            if not summary_text:
                logger.warning(f"Summary missing text content in {file_path}")
                return None

            # Determine summary type
            summary_type = SummaryType.SUMMARY  # Default type

            # Extract project path if available
            project_path = str(file_path.parent) if file_path else None

            # Generate timestamp (use file modification time if not available)
            timestamp = datetime.now()
            if file_path and file_path.exists():
                timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)

            # Extract tags from summary text (simple keyword extraction)
            tags = self._extract_tags(summary_text)

            # Determine completion status
            completion_status = (
                "completed" if self._is_completed(summary_text) else "in_progress"
            )

            return ProjectSummary(
                uuid=uuid,
                leaf_uuid=leaf_uuid,
                summary_type=summary_type,
                title=self._generate_title(summary_text),
                description=summary_text,
                timestamp=timestamp,
                project_path=project_path,
                tags=tags,
                completion_status=completion_status,
            )

        except Exception as e:
            logger.warning(f"Error parsing summary data from {file_path}: {e}")
            return None

    def _extract_tags(self, summary_text: str) -> List[str]:
        """Extract relevant tags from summary text."""
        tags = []
        text_lower = summary_text.lower()

        # Technology tags
        tech_keywords = {
            "python": "python",
            "javascript": "javascript",
            "typescript": "typescript",
            "react": "react",
            "django": "django",
            "flask": "flask",
            "fastapi": "fastapi",
            "node": "nodejs",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "postgres": "postgresql",
            "mysql": "mysql",
            "redis": "redis",
            "aws": "aws",
            "azure": "azure",
            "gcp": "gcp",
        }

        for keyword, tag in tech_keywords.items():
            if keyword in text_lower:
                tags.append(tag)

        # Feature type tags
        if any(word in text_lower for word in ["auth", "login", "security"]):
            tags.append("authentication")
        if any(word in text_lower for word in ["api", "endpoint", "rest"]):
            tags.append("api")
        if any(word in text_lower for word in ["ui", "frontend", "component"]):
            tags.append("frontend")
        if any(word in text_lower for word in ["database", "db", "migration"]):
            tags.append("database")
        if any(word in text_lower for word in ["test", "testing", "spec"]):
            tags.append("testing")

        return list(set(tags))  # Remove duplicates

    def _is_completed(self, summary_text: str) -> bool:
        """Check if project appears to be completed based on summary text."""
        completed_indicators = [
            "completed",
            "finished",
            "done",
            "fixed",
            "implemented",
            "deployed",
            "released",
            "resolved",
            "solved",
        ]
        text_lower = summary_text.lower()
        return any(indicator in text_lower for indicator in completed_indicators)

    def _generate_title(self, summary_text: str) -> str:
        """Generate a concise title from summary text."""
        # Take first sentence or first 60 characters
        sentences = summary_text.split(". ")
        if sentences:
            title = sentences[0]
            if len(title) > 60:
                title = title[:57] + "..."
            return title
        return summary_text[:60] + ("..." if len(summary_text) > 60 else "")

    def get_stats(self) -> Dict[str, Any]:
        """Get parsing statistics."""
        return self.stats.copy()
