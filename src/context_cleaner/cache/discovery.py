"""
Cache Discovery Service

Discovers and manages access to Claude Code cache files across different
platforms and configurations. Handles permissions, missing files, and
provides a unified interface for cache access.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

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
        'darwin': [
            '.claude/projects',
        ],
        'linux': [
            '.claude/projects',
            '.config/claude/projects',
        ],
        'win32': [
            'AppData/Roaming/claude/projects',
            'AppData/Local/claude/projects',
        ]
    }
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize discovery service with optional configuration."""
        self.config = config or CacheConfig()
        self.discovered_locations: List[CacheLocation] = []
        self._cache_stats = {
            'locations_found': 0,
            'session_files_found': 0,
            'total_size_bytes': 0,
            'inaccessible_locations': 0,
            'last_discovery_time': None
        }
    
    def discover_cache_locations(self, custom_paths: Optional[List[Path]] = None) -> List[CacheLocation]:
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
        self._cache_stats['last_discovery_time'] = start_time
        
        discovery_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Discovery completed in {discovery_time:.2f}s: "
                   f"found {len(self.discovered_locations)} cache locations")
        
        return self.discovered_locations
    
    def _get_search_paths(self, custom_paths: Optional[List[Path]] = None) -> List[Path]:
        """Get list of paths to search for cache files."""
        search_paths = []
        
        # Add custom paths if provided
        if custom_paths:
            search_paths.extend(custom_paths)
        
        # Add platform-specific default paths
        import sys
        platform_patterns = self.CACHE_LOCATION_PATTERNS.get(sys.platform, [])
        for pattern in platform_patterns:
            platform_path = Path.home() / pattern
            search_paths.append(platform_path)
        
        # Add current working directory cache (if exists)
        cwd_cache = Path.cwd() / '.claude' / 'projects'
        if cwd_cache.exists():
            search_paths.append(cwd_cache)
        
        # Remove duplicates while preserving order
        unique_paths = []
        for path in search_paths:
            if path not in unique_paths:
                unique_paths.append(path)
        
        logger.debug(f"Searching {len(unique_paths)} potential cache locations")
        return unique_paths
    
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
            session_files = list(project_dir.glob('*.jsonl'))
            
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
                    error_message="No accessible session files"
                )
            
            return CacheLocation(
                path=project_dir,
                project_name=self._extract_project_name(project_dir.name),
                session_files=accessible_files,
                last_modified=last_modified,
                total_size_bytes=total_size,
                is_accessible=True
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
                error_message=str(e)
            )
    
    def _extract_project_name(self, dir_name: str) -> str:
        """Extract readable project name from directory name."""
        # Handle encoded project paths like "-Users-username-code-projectname"
        if dir_name.startswith('-'):
            parts = dir_name[1:].split('-')
            if len(parts) >= 2:
                # Try to find the project name (usually the last meaningful part)
                for part in reversed(parts):
                    if part and part not in ['Users', 'code', 'Documents', 'Desktop']:
                        return part.replace('_', '-')
        
        return dir_name.replace('_', '-')
    
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
                    logger.debug(f"Skipping old cache location: {location.path} ({age_days} days old)")
                    continue
            
            # Skip empty locations
            if location.session_count == 0:
                continue
            
            filtered.append(location)
        
        return filtered
    
    def _update_stats(self) -> None:
        """Update discovery statistics."""
        self._cache_stats['locations_found'] = len(self.discovered_locations)
        self._cache_stats['session_files_found'] = sum(
            loc.session_count for loc in self.discovered_locations
        )
        self._cache_stats['total_size_bytes'] = sum(
            loc.total_size_bytes for loc in self.discovered_locations
        )
        self._cache_stats['inaccessible_locations'] = sum(
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
            if cwd_name in location.project_name.lower() or location.project_name.lower() in cwd_name:
                return location
        
        logger.info(f"Current project cache not found for: {cwd_name}")
        return None
    
    def get_recent_session_files(self, max_files: int = 10) -> List[Tuple[Path, CacheLocation]]:
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
        
        if stats['total_size_bytes'] > 0:
            stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
        
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
                    with open(session_file, 'r') as f:
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
            'locations_found': 0,
            'session_files_found': 0,
            'total_size_bytes': 0,
            'inaccessible_locations': 0,
            'last_discovery_time': None
        }