"""
Data Extraction Engine

Parses JSONL files efficiently with streaming for large files, converts enhanced
token analysis results to SessionTokenMetrics format, handles different JSONL
schema versions, validates data integrity, and supports parallel processing.

Designed to handle the 2.768B token dataset with memory-efficient streaming
and robust error handling.
"""

import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import aiofiles

from ..models.token_bridge_models import SessionTokenMetrics
from ..analysis.enhanced_token_counter import (
    SessionTokenMetrics as AnalysisSessionMetrics,
)
from .jsonl_discovery import JSONLFileInfo

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of data extraction from JSONL files."""

    # Operation metadata
    extraction_id: str
    start_time: datetime
    end_time: datetime
    file_path: str

    # Extraction statistics
    total_lines_processed: int = 0
    total_lines_skipped: int = 0
    total_sessions_found: int = 0
    sessions_extracted: Dict[str, SessionTokenMetrics] = field(default_factory=dict)

    # Data integrity
    parsing_errors: int = 0
    validation_errors: int = 0
    schema_version_detected: Optional[str] = None

    # Performance metrics
    processing_rate_lines_per_second: float = 0.0
    memory_peak_mb: Optional[float] = None

    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def extraction_duration_seconds(self) -> float:
        """Duration of extraction operation."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Percentage of lines successfully processed."""
        total = self.total_lines_processed + self.total_lines_skipped
        if total == 0:
            return 0.0
        return (self.total_lines_processed / total) * 100

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        logger.error(f"Extraction error: {error}")

    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
        logger.warning(f"Extraction warning: {warning}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "extraction_id": self.extraction_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "extraction_duration_seconds": self.extraction_duration_seconds,
            "file_path": self.file_path,
            "total_lines_processed": self.total_lines_processed,
            "total_lines_skipped": self.total_lines_skipped,
            "total_sessions_found": self.total_sessions_found,
            "parsing_errors": self.parsing_errors,
            "validation_errors": self.validation_errors,
            "success_rate": self.success_rate,
            "processing_rate_lines_per_second": self.processing_rate_lines_per_second,
            "memory_peak_mb": self.memory_peak_mb,
            "schema_version_detected": self.schema_version_detected,
            "errors": self.errors,
            "warnings": self.warnings,
            "sessions_summary": {
                session_id: {
                    "calculated_total_tokens": metrics.calculated_total_tokens,
                    "total_reported_tokens": metrics.total_reported_tokens,
                    "accuracy_ratio": metrics.accuracy_ratio,
                    "undercount_percentage": metrics.undercount_percentage,
                }
                for session_id, metrics in self.sessions_extracted.items()
            },
        }


class DataExtractionEngine:
    """
    Engine for extracting and transforming JSONL data to SessionTokenMetrics.

    Handles multiple JSONL schema versions, provides memory-efficient streaming
    for large files, and converts enhanced token analysis results to the
    standardized SessionTokenMetrics format required by the bridge service.
    """

    def __init__(
        self,
        max_memory_mb: int = 500,  # Memory limit for single file processing
        enable_validation: bool = True,
        chunk_size: int = 1000,  # Lines to process in memory at once
        supported_schemas: Optional[List[str]] = None,
    ):
        self.max_memory_mb = max_memory_mb
        self.enable_validation = enable_validation
        self.chunk_size = chunk_size
        self.supported_schemas = supported_schemas or ["v1", "v2", "enhanced"]

        # Schema version detection patterns
        self.schema_patterns = {
            "v1": ["timestamp", "type", "message"],
            "v2": ["sessionId", "usage", "content"],
            "enhanced": ["analysis_id", "enhanced_metrics", "session_token_metrics"],
        }

        # Content categorization patterns (consistent with enhanced token counter)
        self.categorization_patterns = {
            "claude_md": ["claude.md", "claude code", "claudemd"],
            "custom_agents": ["agent:", "custom agent", "specialized agent"],
            "mcp_tools": ["mcp__", "mcp_", "model context protocol"],
            "system_prompts": [
                "system-reminder",
                "instructions",
                "guidelines",
                "you are",
            ],
            "system_tools": [
                "bash",
                "read",
                "write",
                "edit",
                "grep",
                "glob",
                "task",
                "tool",
            ],
        }

    async def extract_from_file(
        self,
        file_info: JSONLFileInfo,
        max_lines: Optional[int] = None,
        skip_corrupted: bool = True,
    ) -> ExtractionResult:
        """
        Extract SessionTokenMetrics from a single JSONL file.

        Args:
            file_info: Information about the file to process
            max_lines: Maximum lines to process (None for all)
            skip_corrupted: Skip corrupted entries instead of failing

        Returns:
            ExtractionResult with extracted sessions and metadata
        """
        start_time = datetime.now()
        extraction_id = f"extract_{start_time.strftime('%Y%m%d_%H%M%S')}_{Path(file_info.path).stem}"

        result = ExtractionResult(
            extraction_id=extraction_id,
            start_time=start_time,
            end_time=start_time,  # Will be updated
            file_path=file_info.path,
        )

        if file_info.is_corrupt and not skip_corrupted:
            result.add_error(
                f"File is marked as corrupt: {file_info.corruption_reason}"
            )
            result.end_time = datetime.now()
            return result

        logger.info(f"Extracting data from: {file_info.filename}")

        try:
            sessions: Dict[str, SessionTokenMetrics] = {}
            lines_processed = 0

            # Stream file processing to handle large files
            async for chunk in self._stream_file_chunks(
                file_info.path, self.chunk_size
            ):
                chunk_sessions = await self._process_chunk(chunk, result)

                # Merge chunk sessions with main sessions
                for session_id, session_metrics in chunk_sessions.items():
                    if session_id in sessions:
                        sessions[session_id] = await self._merge_sessions(
                            sessions[session_id], session_metrics
                        )
                    else:
                        sessions[session_id] = session_metrics

                lines_processed += len(chunk)

                # Check memory usage and process in smaller chunks if needed
                if self._estimate_memory_usage(sessions) > self.max_memory_mb:
                    logger.warning(
                        f"Memory limit approached, processed {lines_processed} lines"
                    )
                    break

                # Check line limit
                if max_lines and lines_processed >= max_lines:
                    break

            result.total_lines_processed = lines_processed
            result.total_sessions_found = len(sessions)
            result.sessions_extracted = sessions

            # Validate extracted sessions if enabled
            if self.enable_validation:
                await self._validate_extracted_sessions(sessions, result)

            # Calculate performance metrics
            result.end_time = datetime.now()
            duration = result.extraction_duration_seconds
            if duration > 0:
                result.processing_rate_lines_per_second = lines_processed / duration

            logger.info(
                f"Extraction complete: {len(sessions)} sessions from {lines_processed} lines"
            )

            return result

        except Exception as e:
            result.add_error(f"Extraction failed: {str(e)}")
            result.end_time = datetime.now()
            logger.error(f"Data extraction failed for {file_info.filename}: {e}")
            return result

    async def extract_from_multiple_files(
        self,
        files: List[JSONLFileInfo],
        max_concurrent: int = 3,
        progress_callback: Optional[callable] = None,
    ) -> List[ExtractionResult]:
        """
        Extract data from multiple files concurrently.

        Args:
            files: List of files to process
            max_concurrent: Maximum concurrent extractions
            progress_callback: Optional progress callback

        Returns:
            List of ExtractionResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def extract_with_semaphore(file_info: JSONLFileInfo) -> ExtractionResult:
            async with semaphore:
                return await self.extract_from_file(file_info)

        # Process files concurrently
        tasks = [extract_with_semaphore(file_info) for file_info in files]

        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(files))

        return results

    async def _stream_file_chunks(
        self, file_path: str, chunk_size: int
    ) -> AsyncGenerator[List[str], None]:
        """Stream file in chunks to manage memory usage."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
                chunk = []

                async for line in file:
                    chunk.append(line.strip())

                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []

                # Yield remaining lines
                if chunk:
                    yield chunk

        except Exception as e:
            logger.error(f"Error streaming file {file_path}: {e}")
            raise

    async def _process_chunk(
        self, lines: List[str], result: ExtractionResult
    ) -> Dict[str, SessionTokenMetrics]:
        """Process a chunk of lines and extract session metrics."""
        sessions: Dict[str, SessionTokenMetrics] = {}

        for line_num, line in enumerate(lines, 1):
            if not line:  # Skip empty lines
                result.total_lines_skipped += 1
                continue

            try:
                entry = json.loads(line)

                # Detect schema version if not already detected
                if not result.schema_version_detected:
                    result.schema_version_detected = self._detect_schema_version(entry)

                # Extract session information
                session_id = self._extract_session_id(entry)
                if not session_id:
                    result.total_lines_skipped += 1
                    continue

                # Create or update session metrics
                if session_id not in sessions:
                    sessions[session_id] = SessionTokenMetrics(session_id=session_id)

                await self._process_entry(entry, sessions[session_id], result)

            except json.JSONDecodeError:
                result.parsing_errors += 1
                result.total_lines_skipped += 1
                continue
            except Exception as e:
                result.add_warning(f"Error processing line {line_num}: {str(e)}")
                result.total_lines_skipped += 1
                continue

        return sessions

    def _detect_schema_version(self, entry: Dict[str, Any]) -> str:
        """Detect JSONL schema version from entry structure."""
        for version, patterns in self.schema_patterns.items():
            if all(self._has_nested_key(entry, pattern) for pattern in patterns):
                return version

        return "unknown"

    def _has_nested_key(self, data: Dict[str, Any], key_path: str) -> bool:
        """Check if nested key exists in dictionary."""
        keys = key_path.split(".")
        current = data

        try:
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return False
            return True
        except (KeyError, TypeError):
            return False

    def _extract_session_id(self, entry: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from JSONL entry (multiple schema support)."""
        # Try various session ID field patterns
        candidates = [
            entry.get("session_id"),
            entry.get("sessionId"),
            entry.get("id"),
            entry.get("conversation_id"),
            entry.get("chat_id"),
            # Nested patterns
            entry.get("metadata", {}).get("session_id"),
            entry.get("context", {}).get("session_id"),
        ]

        for candidate in candidates:
            if candidate and isinstance(candidate, str):
                return candidate

        return None

    async def _process_entry(
        self,
        entry: Dict[str, Any],
        session_metrics: SessionTokenMetrics,
        result: ExtractionResult,
    ):
        """Process a single JSONL entry and update session metrics."""
        try:
            # Extract usage statistics (compatible with multiple schemas)
            usage = self._extract_usage_stats(entry)
            if usage:
                session_metrics.reported_input_tokens += usage.get("input_tokens", 0)
                session_metrics.reported_output_tokens += usage.get("output_tokens", 0)
                session_metrics.reported_cache_creation_tokens += usage.get(
                    "cache_creation_input_tokens", 0
                )
                session_metrics.reported_cache_read_tokens += usage.get(
                    "cache_read_input_tokens", 0
                )

            # Extract content for analysis
            content = self._extract_content(entry)
            if content:
                # Categorize content
                category = self._categorize_content(content)
                if category not in session_metrics.content_categories:
                    session_metrics.content_categories[category] = 0
                session_metrics.content_categories[category] += len(content.split())

                # Use actual token data from usage stats (ccusage approach)
                if usage:
                    # Use actual reported tokens when available (following ccusage accuracy)
                    actual_tokens = (
                        usage.get("input_tokens", 0)
                        + usage.get("output_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )
                    if actual_tokens > 0:
                        session_metrics.calculated_total_tokens += actual_tokens
                        logger.debug(
                            f"Used {actual_tokens} actual tokens from JSONL usage data"
                        )
                    # Skip content without actual usage data to maintain accuracy (ccusage method)

            # Extract timestamps
            timestamp = self._extract_timestamp(entry)
            if timestamp:
                if (
                    not session_metrics.start_time
                    or timestamp < session_metrics.start_time
                ):
                    session_metrics.start_time = timestamp
                if not session_metrics.end_time or timestamp > session_metrics.end_time:
                    session_metrics.end_time = timestamp

            # Calculate derived metrics
            session_metrics.calculate_accuracy_ratio()
            session_metrics.calculate_undercount_percentage()

        except Exception as e:
            result.add_warning(
                f"Error processing entry for session {session_metrics.session_id}: {str(e)}"
            )

    def _extract_usage_stats(self, entry: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """Extract usage statistics from entry (multiple schema support)."""
        # Try various usage field patterns
        usage_locations = [
            entry.get("usage"),
            entry.get("message", {}).get("usage"),
            entry.get("metadata", {}).get("usage"),
            entry.get("stats"),
            entry.get("token_usage"),
        ]

        for usage in usage_locations:
            if isinstance(usage, dict):
                return usage

        return None

    def _extract_content(self, entry: Dict[str, Any]) -> str:
        """Extract content text from JSONL entry."""
        content_sources = [
            entry.get("content", ""),
            entry.get("message", {}).get("content", ""),
            entry.get("text", ""),
            entry.get("data", ""),
            # Handle list-based content
            self._extract_list_content(entry.get("messages", [])),
        ]

        # Combine all content sources
        combined_content = " ".join(str(source) for source in content_sources if source)
        return combined_content.strip()

    def _extract_list_content(self, messages: List[Any]) -> str:
        """Extract content from list of messages."""
        if not isinstance(messages, list):
            return ""

        content_parts = []
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if content:
                    content_parts.append(str(content))

        return " ".join(content_parts)

    def _extract_timestamp(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from entry."""
        timestamp_fields = [
            "timestamp",
            "created_at",
            "time",
            "datetime",
            "message.timestamp",
        ]

        for field in timestamp_fields:
            value = entry
            for key in field.split("."):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    value = None
                    break

            if value:
                try:
                    if isinstance(value, str):
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    elif isinstance(value, (int, float)):
                        return datetime.fromtimestamp(value)
                except (ValueError, TypeError):
                    continue

        return None

    def _categorize_content(self, content: str) -> str:
        """Categorize content using pattern matching."""
        content_lower = content.lower()

        for category, patterns in self.categorization_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                return category

        return "user_messages"  # Default category

    async def _merge_sessions(
        self, existing: SessionTokenMetrics, new: SessionTokenMetrics
    ) -> SessionTokenMetrics:
        """Merge two SessionTokenMetrics for the same session."""
        # Aggregate token counts
        existing.reported_input_tokens += new.reported_input_tokens
        existing.reported_output_tokens += new.reported_output_tokens
        existing.reported_cache_creation_tokens += new.reported_cache_creation_tokens
        existing.reported_cache_read_tokens += new.reported_cache_read_tokens
        existing.calculated_total_tokens += new.calculated_total_tokens

        # Merge content categories
        for category, count in new.content_categories.items():
            if category not in existing.content_categories:
                existing.content_categories[category] = 0
            existing.content_categories[category] += count

        # Update timestamps
        if new.start_time:
            if not existing.start_time or new.start_time < existing.start_time:
                existing.start_time = new.start_time

        if new.end_time:
            if not existing.end_time or new.end_time > existing.end_time:
                existing.end_time = new.end_time

        # Recalculate derived metrics
        existing.calculate_accuracy_ratio()
        existing.calculate_undercount_percentage()

        return existing

    def _estimate_memory_usage(self, sessions: Dict[str, SessionTokenMetrics]) -> float:
        """Estimate memory usage of sessions in MB."""
        # Rough estimation: each session ~ 2KB + content
        base_memory = len(sessions) * 2  # KB

        # Add content size estimate
        for session in sessions.values():
            content_size = (
                sum(sessions[session.session_id].content_categories.values()) * 0.1
            )  # KB
            base_memory += content_size

        return base_memory / 1024  # Convert to MB

    async def _validate_extracted_sessions(
        self, sessions: Dict[str, SessionTokenMetrics], result: ExtractionResult
    ):
        """Validate extracted session metrics."""
        for session_id, metrics in sessions.items():
            validation_errors = metrics.validate()

            if validation_errors:
                result.validation_errors += len(validation_errors)
                for error in validation_errors:
                    result.add_warning(f"Session {session_id} validation: {error}")

    async def convert_to_bridge_format(
        self, extraction_result: ExtractionResult
    ) -> List[SessionTokenMetrics]:
        """
        Convert extraction result to bridge-compatible SessionTokenMetrics.

        Args:
            extraction_result: Result from extraction operation

        Returns:
            List of SessionTokenMetrics ready for bridge storage
        """
        bridge_sessions = []

        for session_id, session_metrics in extraction_result.sessions_extracted.items():
            # Session metrics is already in the correct format
            # Just ensure metadata is set appropriately for bridge storage
            session_metrics.data_source = "historical_migration"
            session_metrics.files_processed = 1  # This extraction was from one file

            bridge_sessions.append(session_metrics)

        return bridge_sessions
