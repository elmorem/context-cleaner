"""
Cache Discovery Service

Discovers and manages access to Claude Code cache files across different
platforms and configurations. Handles permissions, missing files, and
provides a unified interface for cache access.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .models import CacheConfig

logger = logging.getLogger(__name__)


@dataclass
class CacheLocation:
    """Information about a discovered cache location."""

    path: Path
    project_name: str
    session_files: List[Path]
    last_modified: datetime
    total_size_bytes: int
    is_accessible: bool = True
    error_message: Optional[str] = None

    @property
    def size_mb(self) -> float:
        """Get cache size in MB."""
        return self.total_size_bytes / (1024 * 1024)

    @property
    def is_recent(self) -> bool:
        """Check if cache was modified recently."""
        return (datetime.now() - self.last_modified).days < 7

    @property
    def session_count(self) -> int:
        """Get number of session files."""
        return len(self.session_files)


class CacheDiscoveryService:
    """Service for discovering Claude Code cache files."""

    # Common Claude Code cache location patterns by platform
    CACHE_LOCATION_PATTERNS = {
        "darwin": [
            ".claude/projects",
            "Library/Application Support/claude/projects",
            "Library/Caches/claude/projects",
        ],
        "linux": [
            ".claude/projects",
            ".config/claude/projects",
            ".cache/claude/projects",
            ".local/share/claude/projects",
        ],
        "win32": [
            "AppData/Roaming/claude/projects",
            "AppData/Local/claude/projects",
            "AppData/LocalLow/claude/projects",
        ],
    }

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize discovery service with optional configuration."""
        self.config = config or CacheConfig()
        self.discovered_locations: List[CacheLocation] = []
        self._cache_stats = {
            "locations_found": 0,
            "session_files_found": 0,
            "total_size_bytes": 0,
            "inaccessible_locations": 0,
            "last_discovery_time": None,
        }

    def discover_cache_locations(
        self, custom_paths: Optional[List[Path]] = None
    ) -> List[CacheLocation]:
        """
        Discover all available Claude Code cache locations.

        Args:
            custom_paths: Optional list of custom paths to search

        Returns:
            List of discovered cache locations
        """
        start_time = datetime.now()
        logger.info("Starting cache location discovery...")

        self.discovered_locations = []
        search_paths = self._get_search_paths(custom_paths)

        for base_path in search_paths:
            try:
                locations = self._scan_cache_directory(base_path)
                self.discovered_locations.extend(locations)
            except Exception as e:
                logger.warning(f"Error scanning cache directory {base_path}: {e}")
                continue

        # Filter based on config
        self.discovered_locations = self._filter_locations(self.discovered_locations)

        # Update stats
        self._update_stats()
        self._cache_stats["last_discovery_time"] = start_time

        discovery_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Discovery completed in {discovery_time:.2f}s: "
            f"found {len(self.discovered_locations)} cache locations"
        )

        return self.discovered_locations

    def _get_search_paths(
        self, custom_paths: Optional[List[Path]] = None
    ) -> List[Path]:
        """Get list of paths to search for cache files."""
        search_paths = []

        # Add custom paths if provided
        if custom_paths:
            search_paths.extend(custom_paths)

        # Method 1: Platform-specific default paths (user home directory)
        import sys

        platform_patterns = self.CACHE_LOCATION_PATTERNS.get(sys.platform, [])
        for pattern in platform_patterns:
            platform_path = Path.home() / pattern
            search_paths.append(platform_path)

        # Method 2: Environment variables (platform-specific)
        import os

        # Platform-specific environment variables
        if sys.platform == "win32":
            # Windows environment variables
            env_vars = [
                "CLAUDE_CACHE_DIR",
                "APPDATA",
                "LOCALAPPDATA",
                "USERPROFILE",
                "TEMP",
                "TMP",
            ]
            for env_var in env_vars:
                env_path = os.environ.get(env_var)
                if env_path:
                    if env_var in ["APPDATA", "LOCALAPPDATA"]:
                        search_paths.append(Path(env_path) / "claude" / "projects")
                    elif env_var == "USERPROFILE":
                        search_paths.extend(
                            [
                                Path(env_path)
                                / "AppData"
                                / "Roaming"
                                / "claude"
                                / "projects",
                                Path(env_path)
                                / "AppData"
                                / "Local"
                                / "claude"
                                / "projects",
                                Path(env_path) / ".claude" / "projects",
                            ]
                        )
                    elif env_var in ["TEMP", "TMP"]:
                        search_paths.append(Path(env_path) / "claude" / "projects")
                    else:  # CLAUDE_CACHE_DIR
                        search_paths.append(Path(env_path) / "claude" / "projects")

        elif sys.platform.startswith("linux"):
            # Ubuntu/Linux environment variables
            env_vars = [
                "CLAUDE_CACHE_DIR",
                "XDG_CACHE_HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "HOME",
            ]
            for env_var in env_vars:
                env_path = os.environ.get(env_var)
                if env_path:
                    if env_var == "XDG_CACHE_HOME":
                        search_paths.append(Path(env_path) / "claude" / "projects")
                    elif env_var == "XDG_CONFIG_HOME":
                        search_paths.append(Path(env_path) / "claude" / "projects")
                    elif env_var == "XDG_DATA_HOME":
                        search_paths.append(Path(env_path) / "claude" / "projects")
                    elif env_var == "HOME":
                        search_paths.extend(
                            [
                                Path(env_path) / ".claude" / "projects",
                                Path(env_path) / ".config" / "claude" / "projects",
                                Path(env_path) / ".cache" / "claude" / "projects",
                                Path(env_path)
                                / ".local"
                                / "share"
                                / "claude"
                                / "projects",
                            ]
                        )
                    else:  # CLAUDE_CACHE_DIR
                        search_paths.append(Path(env_path) / "claude" / "projects")

        else:  # macOS or other platforms
            env_vars = ["CLAUDE_CACHE_DIR", "HOME"]
            for env_var in env_vars:
                env_path = os.environ.get(env_var)
                if env_path:
                    if env_var == "HOME":
                        search_paths.extend(
                            [
                                Path(env_path) / ".claude" / "projects",
                                Path(env_path)
                                / "Library"
                                / "Application Support"
                                / "claude"
                                / "projects",
                                Path(env_path)
                                / "Library"
                                / "Caches"
                                / "claude"
                                / "projects",
                            ]
                        )
                    else:  # CLAUDE_CACHE_DIR
                        search_paths.append(Path(env_path) / "claude" / "projects")

        # Method 3: System-wide cache locations (for system installs)
        system_cache_locations = []
        if sys.platform == "darwin":  # macOS
            system_cache_locations.extend(
                [
                    Path("/Library/Caches/claude/projects"),
                    Path("/Library/Application Support/claude/projects"),
                    Path("/tmp/claude/projects"),
                    Path("/var/tmp/claude/projects"),
                    Path("/usr/local/share/claude/projects"),
                ]
            )
        elif sys.platform.startswith("linux"):  # Ubuntu/Linux
            system_cache_locations.extend(
                [
                    # Standard Linux locations
                    Path("/var/cache/claude/projects"),
                    Path("/var/lib/claude/projects"),
                    Path("/usr/local/share/claude/projects"),
                    Path("/usr/share/claude/projects"),
                    Path("/opt/claude/projects"),
                    # Temporary locations
                    Path("/tmp/claude/projects"),
                    Path("/var/tmp/claude/projects"),
                    # Snap package locations (Ubuntu)
                    Path("/var/snap/claude/common/projects"),
                    Path("/snap/claude/common/projects"),
                    # Flatpak locations (Ubuntu/Linux)
                    Path("/var/lib/flatpak/app/claude/projects"),
                ]
            )

            # Add user-specific snap/flatpak locations if running as user
            try:
                if hasattr(os, "getuid") and os.getuid() != 0:  # Not root
                    system_cache_locations.extend(
                        [
                            Path.home() / "snap" / "claude" / "common" / "projects",
                            Path.home() / ".var" / "app" / "claude" / "projects",
                        ]
                    )
            except (AttributeError, OSError):
                pass

        elif sys.platform == "win32":  # Windows
            system_cache_locations.extend(
                [
                    # Standard Windows system locations
                    Path("C:/ProgramData/claude/projects"),
                    Path("C:/Program Files/claude/projects"),
                    Path("C:/Program Files (x86)/claude/projects"),
                    # Temporary locations
                    Path("C:/Windows/Temp/claude/projects"),
                    Path("C:/Temp/claude/projects"),
                    # Microsoft Store app locations
                    Path("C:/Program Files/WindowsApps/claude/projects"),
                ]
            )

            # Add Windows user-specific locations
            try:
                username = os.environ.get("USERNAME", "User")
                system_cache_locations.extend(
                    [
                        Path(f"C:/Users/{username}/AppData/Roaming/claude/projects"),
                        Path(f"C:/Users/{username}/AppData/Local/claude/projects"),
                        Path(f"C:/Users/{username}/AppData/LocalLow/claude/projects"),
                    ]
                )
            except Exception:
                pass

        search_paths.extend(system_cache_locations)

        # Method 4: Current working directory and parent directories (development/pip installs)
        cwd = Path.cwd()
        for i in range(3):  # Check current dir and 2 parent levels
            cwd_cache = cwd / ".claude" / "projects"
            if cwd_cache.exists():
                search_paths.append(cwd_cache)
            # Also check without dot prefix (public cache)
            cwd_cache_public = cwd / "claude" / "projects"
            if cwd_cache_public.exists():
                search_paths.append(cwd_cache_public)
            # Move up one level
            cwd = cwd.parent
            if cwd == cwd.parent:  # Reached filesystem root
                break

        # Method 5: Package-relative paths (for pip-installed packages)
        try:
            import context_cleaner

            package_path = Path(context_cleaner.__file__).parent

            # Check relative to package installation
            package_cache_locations = [
                package_path.parent
                / "cache"
                / "claude"
                / "projects",  # site-packages level
                package_path.parent.parent
                / "cache"
                / "claude"
                / "projects",  # lib level
                package_path
                / ".."
                / ".."
                / ".."
                / ".claude"
                / "projects",  # user level from pip install
            ]

            for cache_path in package_cache_locations:
                try:
                    resolved_path = cache_path.resolve()
                    search_paths.append(resolved_path)
                except (OSError, RuntimeError):
                    # Handle cases where path resolution fails
                    pass

        except (ImportError, AttributeError):
            logger.debug("Could not determine package installation path")

        # Method 6: User-specific temporary directories (cross-platform)
        temp_locations = []

        # Standard temp directory from Python's tempfile module
        import tempfile

        system_temp = Path(tempfile.gettempdir())
        temp_locations.extend(
            [
                system_temp / "claude" / "projects",
                system_temp / f"claude_user" / "projects",
            ]
        )

        # Platform-specific temp locations
        if sys.platform == "win32":
            # Windows temp directories
            temp_locations.extend(
                [
                    Path.home() / "AppData" / "Local" / "Temp" / "claude" / "projects",
                    Path("C:/Windows/Temp/claude/projects"),
                    Path("C:/Temp/claude/projects"),
                ]
            )
        elif sys.platform.startswith("linux"):
            # Ubuntu/Linux temp directories
            temp_locations.extend(
                [
                    Path.home() / "tmp" / "claude" / "projects",
                    Path("/tmp") / "claude" / "projects",
                    Path("/var/tmp") / "claude" / "projects",
                ]
            )

            # User-specific temp with UID if available
            try:
                if hasattr(os, "getuid"):
                    uid = os.getuid()
                    temp_locations.extend(
                        [
                            Path("/tmp") / f"claude_{uid}" / "projects",
                            Path("/var/tmp") / f"claude_{uid}" / "projects",
                        ]
                    )
            except (AttributeError, OSError):
                pass
        else:
            # macOS and other platforms
            temp_locations.extend(
                [
                    Path.home() / "tmp" / "claude" / "projects",
                    Path("/tmp") / "claude" / "projects",
                    Path("/var/tmp") / "claude" / "projects",
                ]
            )

        search_paths.extend(temp_locations)

        # Remove duplicates while preserving order and add safety checks
        unique_paths = []
        accessible_paths = []

        for path in search_paths:
            try:
                # Resolve to handle symlinks and relative paths
                resolved_path = path.resolve()
                if resolved_path not in unique_paths:
                    unique_paths.append(resolved_path)

                    # Check if path is potentially accessible (exists or parent exists)
                    if resolved_path.exists():
                        accessible_paths.append(resolved_path)
                    elif resolved_path.parent.exists():
                        # Parent exists, so path could be created
                        accessible_paths.append(resolved_path)

            except (OSError, RuntimeError, PermissionError):
                # If path resolution fails, try the original path
                if path not in unique_paths:
                    unique_paths.append(path)
                    # For unresolved paths, add them but don't mark as accessible

        # Log discovery stats
        logger.debug(f"Searching {len(unique_paths)} potential cache locations")
        logger.debug(f"Found {len(accessible_paths)} potentially accessible paths")
        logger.debug(
            f"Sample cache search paths: {[str(p) for p in unique_paths[:3]]}{'...' if len(unique_paths) > 3 else ''}"
        )

        # Prioritize existing/accessible paths first
        prioritized_paths = accessible_paths + [
            p for p in unique_paths if p not in accessible_paths
        ]

        return prioritized_paths

    def _scan_cache_directory(self, base_path: Path) -> List[CacheLocation]:
        """
        Scan a directory for Claude Code cache files.

        Args:
            base_path: Base path to scan

        Returns:
            List of discovered cache locations
        """
        locations = []

        if not base_path.exists():
            logger.debug(f"Cache directory does not exist: {base_path}")
            return locations

        if not base_path.is_dir():
            logger.debug(f"Path is not a directory: {base_path}")
            return locations

        try:
            # Each subdirectory represents a project cache
            for project_dir in base_path.iterdir():
                if not project_dir.is_dir():
                    continue

                location = self._analyze_project_cache(project_dir)
                if location:
                    locations.append(location)

        except PermissionError:
            logger.warning(f"Permission denied accessing cache directory: {base_path}")
        except Exception as e:
            logger.error(f"Error scanning cache directory {base_path}: {e}")

        return locations

    def _analyze_project_cache(self, project_dir: Path) -> Optional[CacheLocation]:
        """
        Analyze a single project cache directory.

        Args:
            project_dir: Path to project cache directory

        Returns:
            CacheLocation object or None if invalid/inaccessible
        """
        try:
            # Find .jsonl session files
            session_files = list(project_dir.glob("*.jsonl"))

            if not session_files:
                logger.debug(f"No session files found in: {project_dir}")
                return None

            # Calculate total size and last modified time
            total_size = 0
            last_modified = datetime.min

            accessible_files = []
            for session_file in session_files:
                try:
                    stat = session_file.stat()
                    total_size += stat.st_size
                    file_modified = datetime.fromtimestamp(stat.st_mtime)
                    last_modified = max(last_modified, file_modified)
                    accessible_files.append(session_file)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Cannot access session file {session_file}: {e}")
                    continue

            if not accessible_files:
                return CacheLocation(
                    path=project_dir,
                    project_name=project_dir.name,
                    session_files=[],
                    last_modified=datetime.now(),
                    total_size_bytes=0,
                    is_accessible=False,
                    error_message="No accessible session files",
                )

            return CacheLocation(
                path=project_dir,
                project_name=self._extract_project_name(project_dir.name),
                session_files=accessible_files,
                last_modified=last_modified,
                total_size_bytes=total_size,
                is_accessible=True,
            )

        except Exception as e:
            logger.warning(f"Error analyzing project cache {project_dir}: {e}")
            return CacheLocation(
                path=project_dir,
                project_name=project_dir.name,
                session_files=[],
                last_modified=datetime.now(),
                total_size_bytes=0,
                is_accessible=False,
                error_message=str(e),
            )

    def _extract_project_name(self, dir_name: str) -> str:
        """Extract readable project name from directory name."""
        # Handle encoded project paths like "-Users-username-code-projectname"
        if dir_name.startswith("-"):
            parts = dir_name[1:].split("-")
            if len(parts) >= 2:
                # Try to find the project name (usually the last meaningful part)
                for part in reversed(parts):
                    if part and part not in ["Users", "code", "Documents", "Desktop"]:
                        return part.replace("_", "-")

        return dir_name.replace("_", "-")

    def _filter_locations(self, locations: List[CacheLocation]) -> List[CacheLocation]:
        """Filter locations based on configuration."""
        filtered = []

        for location in locations:
            # Skip inaccessible locations unless configured otherwise
            if not location.is_accessible:
                continue

            # Skip archived sessions if configured
            if not self.config.include_archived_sessions:
                age_days = (datetime.now() - location.last_modified).days
                if age_days > self.config.max_cache_age_days:
                    logger.debug(
                        f"Skipping old cache location: {location.path} ({age_days} days old)"
                    )
                    continue

            # Skip empty locations
            if location.session_count == 0:
                continue

            filtered.append(location)

        return filtered

    def _update_stats(self) -> None:
        """Update discovery statistics."""
        self._cache_stats["locations_found"] = len(self.discovered_locations)
        self._cache_stats["session_files_found"] = sum(
            loc.session_count for loc in self.discovered_locations
        )
        self._cache_stats["total_size_bytes"] = sum(
            loc.total_size_bytes for loc in self.discovered_locations
        )
        self._cache_stats["inaccessible_locations"] = sum(
            1 for loc in self.discovered_locations if not loc.is_accessible
        )

    def get_project_cache(self, project_name: str) -> Optional[CacheLocation]:
        """
        Get cache location for a specific project.

        Args:
            project_name: Name of the project to find

        Returns:
            CacheLocation for the project or None if not found
        """
        for location in self.discovered_locations:
            if location.project_name.lower() == project_name.lower():
                return location

        logger.info(f"Project cache not found: {project_name}")
        return None

    def get_current_project_cache(self) -> Optional[CacheLocation]:
        """
        Get cache location for the current working directory project.

        Returns:
            CacheLocation for current project or None if not found
        """
        cwd_name = Path.cwd().name.lower()

        # First try exact match
        for location in self.discovered_locations:
            if location.project_name.lower() == cwd_name:
                return location

        # Try partial match
        for location in self.discovered_locations:
            if (
                cwd_name in location.project_name.lower()
                or location.project_name.lower() in cwd_name
            ):
                return location

        logger.info(f"Current project cache not found for: {cwd_name}")
        return None

    def get_recent_session_files(
        self, max_files: int = 10
    ) -> List[Tuple[Path, CacheLocation]]:
        """
        Get most recently modified session files across all locations.

        Args:
            max_files: Maximum number of files to return

        Returns:
            List of (session_file_path, cache_location) tuples
        """
        all_files = []

        for location in self.discovered_locations:
            for session_file in location.session_files:
                try:
                    mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                    all_files.append((session_file, location, mtime))
                except (OSError, PermissionError):
                    continue

        # Sort by modification time (newest first)
        all_files.sort(key=lambda x: x[2], reverse=True)

        return [(path, location) for path, location, _ in all_files[:max_files]]

    def get_discovery_stats(self) -> Dict[str, any]:
        """Get cache discovery statistics."""
        stats = self._cache_stats.copy()

        if stats["total_size_bytes"] > 0:
            stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)

        return stats

    def validate_cache_access(self, location: CacheLocation) -> bool:
        """
        Validate that cache location is accessible and readable.

        Args:
            location: CacheLocation to validate

        Returns:
            True if accessible, False otherwise
        """
        try:
            if not location.path.exists():
                return False

            if not location.path.is_dir():
                return False

            # Try to access at least one session file
            for session_file in location.session_files[:1]:  # Check first file only
                try:
                    with open(session_file, "r") as f:
                        f.read(1)  # Try to read one character
                    return True
                except (PermissionError, OSError):
                    continue

            return len(location.session_files) == 0  # Empty location is valid

        except Exception as e:
            logger.warning(f"Error validating cache access for {location.path}: {e}")
            return False

    def clear_discovery_cache(self) -> None:
        """Clear cached discovery results."""
        self.discovered_locations = []
        self._cache_stats = {
            "locations_found": 0,
            "session_files_found": 0,
            "total_size_bytes": 0,
            "inaccessible_locations": 0,
            "last_discovery_time": None,
        }
