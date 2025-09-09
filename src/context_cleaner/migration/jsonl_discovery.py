"""
JSONL Discovery Service

Scans filesystem for enhanced token analysis JSONL files, inventories and categorizes
files by session, date ranges, and size. Validates file integrity and generates
migration manifest with metadata and processing order.

Supports configurable search paths, filtering criteria, and handles large-scale
discovery operations for the 2.768B token migration.
"""

import os
import json
import logging
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class JSONLFileInfo:
    """Information about a discovered JSONL file."""

    # File identification
    path: str
    filename: str
    size_bytes: int

    # Timestamps
    created_at: datetime
    modified_at: datetime

    # Content metadata
    estimated_lines: int = 0
    estimated_sessions: int = 0
    estimated_tokens: int = 0

    # File integrity
    file_hash: Optional[str] = None
    is_corrupt: bool = False
    corruption_reason: Optional[str] = None

    # Processing metadata
    processing_priority: int = 0  # 0 = highest priority
    processing_group: str = "default"

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def age_days(self) -> int:
        """File age in days."""
        return (datetime.now() - self.modified_at).days

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "age_days": self.age_days,
            "estimated_lines": self.estimated_lines,
            "estimated_sessions": self.estimated_sessions,
            "estimated_tokens": self.estimated_tokens,
            "file_hash": self.file_hash,
            "is_corrupt": self.is_corrupt,
            "corruption_reason": self.corruption_reason,
            "processing_priority": self.processing_priority,
            "processing_group": self.processing_group,
        }


@dataclass
class FileDiscoveryResult:
    """Result of JSONL file discovery operation."""

    # Discovery metadata
    discovery_id: str
    start_time: datetime
    end_time: datetime
    search_paths: List[str]

    # Discovery results
    total_files_found: int = 0
    total_size_bytes: int = 0
    files_by_priority: Dict[int, List[JSONLFileInfo]] = field(default_factory=lambda: defaultdict(list))
    files_by_group: Dict[str, List[JSONLFileInfo]] = field(default_factory=lambda: defaultdict(list))

    # File categorization
    recent_files: List[JSONLFileInfo] = field(default_factory=list)  # Modified within 7 days
    large_files: List[JSONLFileInfo] = field(default_factory=list)  # > 100MB
    corrupt_files: List[JSONLFileInfo] = field(default_factory=list)  # Failed integrity check

    # Estimates
    estimated_total_lines: int = 0
    estimated_total_sessions: int = 0
    estimated_total_tokens: int = 0

    # Processing order
    processing_manifest: List[JSONLFileInfo] = field(default_factory=list)

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def total_size_mb(self) -> float:
        """Total size in megabytes."""
        return self.total_size_bytes / (1024 * 1024)

    @property
    def discovery_duration_seconds(self) -> float:
        """Discovery operation duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def healthy_files(self) -> List[JSONLFileInfo]:
        """List of non-corrupt files ready for processing."""
        return [f for f in self.processing_manifest if not f.is_corrupt]

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        logger.error(f"Discovery error: {error}")

    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
        logger.warning(f"Discovery warning: {warning}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "discovery_id": self.discovery_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "discovery_duration_seconds": self.discovery_duration_seconds,
            "search_paths": self.search_paths,
            "total_files_found": self.total_files_found,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": self.total_size_mb,
            "estimated_total_lines": self.estimated_total_lines,
            "estimated_total_sessions": self.estimated_total_sessions,
            "estimated_total_tokens": self.estimated_total_tokens,
            "recent_files_count": len(self.recent_files),
            "large_files_count": len(self.large_files),
            "corrupt_files_count": len(self.corrupt_files),
            "healthy_files_count": len(self.healthy_files),
            "errors": self.errors,
            "warnings": self.warnings,
            "processing_manifest": [f.to_dict() for f in self.processing_manifest],
        }


class JSONLDiscoveryService:
    """
    Service for discovering and cataloging JSONL files for migration.

    Provides comprehensive filesystem scanning, file integrity validation,
    and generates processing manifests with optimal ordering for large-scale
    migration operations.
    """

    def __init__(
        self,
        default_search_paths: Optional[List[str]] = None,
        file_patterns: Optional[List[str]] = None,
        max_file_age_days: Optional[int] = None,
        enable_integrity_check: bool = True,
        enable_content_analysis: bool = True,
    ):
        self.default_search_paths = default_search_paths or [str(Path.home() / ".claude" / "projects")]
        self.file_patterns = file_patterns or ["*.jsonl"]
        self.max_file_age_days = max_file_age_days
        self.enable_integrity_check = enable_integrity_check
        self.enable_content_analysis = enable_content_analysis

        # Content analysis patterns for categorization
        self.priority_patterns = {
            0: ["recent", "priority", "important"],  # Highest priority
            1: ["session", "conversation"],  # Session files
            2: ["cache", "temp", "backup"],  # Lower priority
        }

        self.group_patterns = {
            "sessions": ["session", "conversation", "chat"],
            "analysis": ["analysis", "token", "summary"],
            "cache": ["cache", "temp", "backup"],
            "system": ["system", "config", "log"],
        }

    async def discover_files(
        self,
        search_paths: Optional[List[str]] = None,
        filter_criteria: Optional[Dict[str, Any]] = None,
        max_files: Optional[int] = None,
        sort_by: str = "modified_desc",  # modified_desc, size_desc, priority_asc
    ) -> FileDiscoveryResult:
        """
        Discover and catalog JSONL files for migration.

        Args:
            search_paths: Directories to search (defaults to configured paths)
            filter_criteria: Optional filtering criteria
            max_files: Maximum number of files to discover
            sort_by: Sorting method for processing order

        Returns:
            FileDiscoveryResult with comprehensive file inventory
        """
        start_time = datetime.now()
        discovery_id = f"discovery_{start_time.strftime('%Y%m%d_%H%M%S')}"

        search_paths = search_paths or self.default_search_paths

        result = FileDiscoveryResult(
            discovery_id=discovery_id,
            start_time=start_time,
            end_time=start_time,  # Will be updated
            search_paths=search_paths,
        )

        logger.info(f"Starting JSONL discovery in paths: {search_paths}")

        try:
            # Discover files in all search paths
            all_files: List[JSONLFileInfo] = []

            for search_path in search_paths:
                path_files = await self._scan_directory(search_path, result)
                all_files.extend(path_files)

            # Apply filtering if specified
            if filter_criteria:
                all_files = await self._apply_filters(all_files, filter_criteria)

            # Limit number of files if specified
            if max_files and len(all_files) > max_files:
                all_files = all_files[:max_files]
                result.add_warning(f"Limited discovery to {max_files} files")

            # Analyze file content if enabled
            if self.enable_content_analysis:
                await self._analyze_file_content(all_files, result)

            # Check file integrity if enabled
            if self.enable_integrity_check:
                await self._check_file_integrity(all_files, result)

            # Categorize and prioritize files
            await self._categorize_files(all_files, result)

            # Generate processing manifest with optimal ordering
            result.processing_manifest = await self._generate_processing_order(all_files, sort_by)

            # Calculate final statistics
            result.total_files_found = len(all_files)
            result.total_size_bytes = sum(f.size_bytes for f in all_files)
            result.estimated_total_lines = sum(f.estimated_lines for f in all_files)
            result.estimated_total_sessions = sum(f.estimated_sessions for f in all_files)
            result.estimated_total_tokens = sum(f.estimated_tokens for f in all_files)

            result.end_time = datetime.now()

            logger.info(
                f"Discovery complete: {result.total_files_found} files, "
                f"{result.total_size_mb:.1f}MB, "
                f"~{result.estimated_total_tokens:,} estimated tokens"
            )

            return result

        except Exception as e:
            result.add_error(f"Discovery failed: {str(e)}")
            result.end_time = datetime.now()
            logger.error(f"JSONL discovery failed: {e}")
            return result

    async def _scan_directory(self, directory_path: str, result: FileDiscoveryResult) -> List[JSONLFileInfo]:
        """Scan a single directory for JSONL files."""
        files = []

        try:
            path = Path(directory_path).expanduser().resolve()

            if not path.exists():
                result.add_warning(f"Search path does not exist: {directory_path}")
                return files

            if not path.is_dir():
                result.add_warning(f"Search path is not a directory: {directory_path}")
                return files

            # Recursively find JSONL files
            for pattern in self.file_patterns:
                for file_path in path.rglob(pattern):
                    if file_path.is_file():
                        try:
                            file_info = await self._create_file_info(file_path)

                            # Apply age filter if specified
                            if self.max_file_age_days is not None:
                                if file_info.age_days > self.max_file_age_days:
                                    continue

                            files.append(file_info)

                        except Exception as e:
                            result.add_error(f"Error processing file {file_path}: {str(e)}")

        except Exception as e:
            result.add_error(f"Error scanning directory {directory_path}: {str(e)}")

        return files

    async def _create_file_info(self, file_path: Path) -> JSONLFileInfo:
        """Create JSONLFileInfo from a file path."""
        stat = file_path.stat()

        return JSONLFileInfo(
            path=str(file_path),
            filename=file_path.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
        )

    async def _apply_filters(self, files: List[JSONLFileInfo], filter_criteria: Dict[str, Any]) -> List[JSONLFileInfo]:
        """Apply filtering criteria to file list."""
        filtered_files = files

        # Filter by minimum size
        if "min_size_mb" in filter_criteria:
            min_bytes = filter_criteria["min_size_mb"] * 1024 * 1024
            filtered_files = [f for f in filtered_files if f.size_bytes >= min_bytes]

        # Filter by maximum size
        if "max_size_mb" in filter_criteria:
            max_bytes = filter_criteria["max_size_mb"] * 1024 * 1024
            filtered_files = [f for f in filtered_files if f.size_bytes <= max_bytes]

        # Filter by age
        if "max_age_days" in filter_criteria:
            max_age = filter_criteria["max_age_days"]
            filtered_files = [f for f in filtered_files if f.age_days <= max_age]

        # Filter by filename patterns
        if "filename_patterns" in filter_criteria:
            patterns = filter_criteria["filename_patterns"]
            if isinstance(patterns, str):
                patterns = [patterns]
            filtered_files = [f for f in filtered_files if any(pattern in f.filename.lower() for pattern in patterns)]

        return filtered_files

    async def _analyze_file_content(self, files: List[JSONLFileInfo], result: FileDiscoveryResult):
        """Analyze file content to estimate lines, sessions, and tokens."""
        logger.info(f"Analyzing content for {len(files)} files...")

        for file_info in files:
            try:
                # Sample file content for estimation
                lines_sampled = 0
                sessions_found: Set[str] = set()
                total_content_length = 0

                async with aiofiles.open(file_info.path, "r", encoding="utf-8") as file:
                    # Sample first 100 lines for estimation
                    async for line_num, line in enumerate(file):
                        if line_num >= 100:  # Sample limit
                            break

                        lines_sampled += 1

                        try:
                            entry = json.loads(line.strip())

                            # Extract session ID
                            session_id = self._extract_session_id(entry)
                            if session_id:
                                sessions_found.add(session_id)

                            # Estimate content length for token calculation
                            content = self._extract_content(entry)
                            total_content_length += len(content)

                        except json.JSONDecodeError:
                            continue
                        except Exception:
                            continue

                # Estimate totals based on sample
                if lines_sampled > 0:
                    # Estimate total lines based on file size and sample
                    avg_line_size = (
                        file_info.size_bytes / max(lines_sampled, 1)
                        if lines_sampled < 100
                        else file_info.size_bytes / (file_info.size_bytes / (total_content_length / lines_sampled))
                    )
                    file_info.estimated_lines = max(1, int(file_info.size_bytes / max(avg_line_size, 1)))

                    # Estimate sessions (with extrapolation)
                    session_density = len(sessions_found) / lines_sampled
                    file_info.estimated_sessions = max(1, int(file_info.estimated_lines * session_density))

                    # Estimate tokens (rough approximation: 1.3 tokens per word, avg 10 words per line)
                    avg_content_per_line = total_content_length / lines_sampled if lines_sampled > 0 else 100
                    estimated_words = (avg_content_per_line / 5) * file_info.estimated_lines  # Rough word estimate
                    file_info.estimated_tokens = max(1, int(estimated_words * 1.3))

            except Exception as e:
                result.add_warning(f"Content analysis failed for {file_info.filename}: {str(e)}")
                # Set default estimates
                file_info.estimated_lines = max(1, file_info.size_bytes // 500)  # Rough estimate
                file_info.estimated_sessions = max(1, file_info.estimated_lines // 100)
                file_info.estimated_tokens = max(1, file_info.estimated_lines * 50)  # Very rough estimate

    async def _check_file_integrity(self, files: List[JSONLFileInfo], result: FileDiscoveryResult):
        """Check file integrity and detect corruption."""
        logger.info(f"Checking integrity for {len(files)} files...")

        for file_info in files:
            try:
                # Calculate file hash
                file_info.file_hash = await self._calculate_file_hash(file_info.path)

                # Basic corruption detection
                try:
                    async with aiofiles.open(file_info.path, "r", encoding="utf-8") as file:
                        lines_checked = 0

                        async for line in file:
                            if lines_checked >= 10:  # Check first 10 lines
                                break

                            line = line.strip()
                            if line:  # Skip empty lines
                                try:
                                    json.loads(line)
                                    lines_checked += 1
                                except json.JSONDecodeError:
                                    file_info.is_corrupt = True
                                    file_info.corruption_reason = f"Invalid JSON at line {lines_checked + 1}"
                                    break

                        if lines_checked == 0:
                            file_info.is_corrupt = True
                            file_info.corruption_reason = "File appears empty or unreadable"

                except UnicodeDecodeError:
                    file_info.is_corrupt = True
                    file_info.corruption_reason = "File encoding error"

            except Exception as e:
                file_info.is_corrupt = True
                file_info.corruption_reason = f"Integrity check failed: {str(e)}"
                result.add_warning(f"Integrity check failed for {file_info.filename}: {str(e)}")

    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hasher = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as file:
            # Read in chunks to handle large files
            while chunk := await file.read(8192):
                hasher.update(chunk)

        return hasher.hexdigest()

    async def _categorize_files(self, files: List[JSONLFileInfo], result: FileDiscoveryResult):
        """Categorize files by priority and processing groups."""
        for file_info in files:
            # Assign priority based on patterns
            file_info.processing_priority = self._determine_priority(file_info)

            # Assign processing group
            file_info.processing_group = self._determine_group(file_info)

            # Categorize for result summary
            if file_info.age_days <= 7:
                result.recent_files.append(file_info)

            if file_info.size_mb > 100:
                result.large_files.append(file_info)

            if file_info.is_corrupt:
                result.corrupt_files.append(file_info)

            # Group by priority and processing group
            result.files_by_priority[file_info.processing_priority].append(file_info)
            result.files_by_group[file_info.processing_group].append(file_info)

    def _determine_priority(self, file_info: JSONLFileInfo) -> int:
        """Determine processing priority for a file."""
        filename_lower = file_info.filename.lower()

        # Check priority patterns
        for priority, patterns in self.priority_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return priority

        # Priority based on file characteristics
        if file_info.age_days <= 1:  # Very recent files
            return 0
        elif file_info.age_days <= 7:  # Recent files
            return 1
        elif file_info.size_mb > 100:  # Large files (process later)
            return 3
        else:
            return 2  # Default priority

    def _determine_group(self, file_info: JSONLFileInfo) -> str:
        """Determine processing group for a file."""
        filename_lower = file_info.filename.lower()

        for group, patterns in self.group_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return group

        return "default"

    async def _generate_processing_order(self, files: List[JSONLFileInfo], sort_by: str) -> List[JSONLFileInfo]:
        """Generate optimal processing order for files."""
        if sort_by == "priority_asc":
            # Sort by priority first, then by modified date (newest first)
            return sorted(files, key=lambda f: (f.processing_priority, -f.modified_at.timestamp()))

        elif sort_by == "size_desc":
            # Sort by size (largest first) - good for parallel processing
            return sorted(files, key=lambda f: -f.size_bytes)

        elif sort_by == "size_asc":
            # Sort by size (smallest first) - good for quick wins
            return sorted(files, key=lambda f: f.size_bytes)

        else:  # modified_desc (default)
            # Sort by modified date (newest first)
            return sorted(files, key=lambda f: -f.modified_at.timestamp())

    def _extract_session_id(self, entry: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from JSONL entry."""
        candidates = [
            entry.get("session_id"),
            entry.get("sessionId"),
            entry.get("id"),
            entry.get("conversation_id"),
        ]

        for candidate in candidates:
            if candidate and isinstance(candidate, str):
                return candidate

        return None

    def _extract_content(self, entry: Dict[str, Any]) -> str:
        """Extract content text from JSONL entry for analysis."""
        content_sources = [
            entry.get("message", {}).get("content", ""),
            entry.get("content", ""),
            entry.get("text", ""),
            str(entry.get("data", "")),
        ]

        # Combine all content sources
        combined_content = " ".join(str(source) for source in content_sources if source)
        return combined_content

    async def save_manifest(self, result: FileDiscoveryResult, output_path: str) -> bool:
        """Save discovery result as JSON manifest file."""
        try:
            async with aiofiles.open(output_path, "w", encoding="utf-8") as file:
                await file.write(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

            logger.info(f"Discovery manifest saved to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save manifest: {e}")
            return False

    async def load_manifest(self, manifest_path: str) -> Optional[FileDiscoveryResult]:
        """Load discovery result from JSON manifest file."""
        try:
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as file:
                data = json.loads(await file.read())

            # Reconstruct FileDiscoveryResult from dictionary
            # This is a simplified reconstruction - in production you'd want more robust deserialization
            result = FileDiscoveryResult(
                discovery_id=data["discovery_id"],
                start_time=datetime.fromisoformat(data["start_time"]),
                end_time=datetime.fromisoformat(data["end_time"]),
                search_paths=data["search_paths"],
                total_files_found=data["total_files_found"],
                total_size_bytes=data["total_size_bytes"],
                estimated_total_lines=data["estimated_total_lines"],
                estimated_total_sessions=data["estimated_total_sessions"],
                estimated_total_tokens=data["estimated_total_tokens"],
                errors=data.get("errors", []),
                warnings=data.get("warnings", []),
            )

            # Reconstruct processing manifest
            for file_data in data.get("processing_manifest", []):
                file_info = JSONLFileInfo(
                    path=file_data["path"],
                    filename=file_data["filename"],
                    size_bytes=file_data["size_bytes"],
                    created_at=datetime.fromisoformat(file_data["created_at"]),
                    modified_at=datetime.fromisoformat(file_data["modified_at"]),
                    estimated_lines=file_data.get("estimated_lines", 0),
                    estimated_sessions=file_data.get("estimated_sessions", 0),
                    estimated_tokens=file_data.get("estimated_tokens", 0),
                    file_hash=file_data.get("file_hash"),
                    is_corrupt=file_data.get("is_corrupt", False),
                    corruption_reason=file_data.get("corruption_reason"),
                    processing_priority=file_data.get("processing_priority", 2),
                    processing_group=file_data.get("processing_group", "default"),
                )
                result.processing_manifest.append(file_info)

            logger.info(f"Discovery manifest loaded from: {manifest_path}")
            return result

        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return None
