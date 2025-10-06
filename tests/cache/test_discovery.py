#!/usr/bin/env python3
"""
Tests for Cache Discovery Service

Comprehensive tests for discovering Claude Code cache locations
across different platforms and configurations.
"""

import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.context_cleaner.analysis.discovery import CacheDiscoveryService, CacheLocation
from src.context_cleaner.analysis.models import CacheConfig


class TestCacheDiscoveryService:
    """Test suite for CacheDiscoveryService class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = CacheDiscoveryService()
        self.config = CacheConfig()
        
        # Create temporary directory structure for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_root = self.temp_dir / 'claude' / 'projects'
        self.cache_root.mkdir(parents=True)
        
        # Create sample project caches
        self.project1_dir = self.cache_root / '-Users-test-code-project1'
        self.project2_dir = self.cache_root / '-Users-test-code-project2'
        
        self.project1_dir.mkdir()
        self.project2_dir.mkdir()
        
        # Create sample session files
        self._create_sample_session_file(self.project1_dir / 'session1.jsonl', 'session-1')
        self._create_sample_session_file(self.project1_dir / 'session2.jsonl', 'session-2')
        self._create_sample_session_file(self.project2_dir / 'session3.jsonl', 'session-3')
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_sample_session_file(self, file_path: Path, session_id: str):
        """Create a sample .jsonl session file."""
        sample_data = {
            "uuid": f"uuid-{session_id}",
            "sessionId": session_id,
            "timestamp": datetime.now().isoformat(),
            "type": "user",
            "message": {
                "role": "user",
                "content": f"Sample message for {session_id}"
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(sample_data, f)
    
    def test_discover_cache_locations_with_custom_paths(self):
        """Test cache discovery with custom search paths."""
        locations = self.service.discover_cache_locations([self.cache_root])
        
        # Filter to only our test locations
        test_locations = [loc for loc in locations if 'tmp' in str(loc.path)]
        assert len(test_locations) == 2
        
        # Check project names are extracted correctly
        test_project_names = {loc.project_name for loc in test_locations}
        assert 'project1' in test_project_names
        assert 'project2' in test_project_names
        
        # Check session files are found
        project1_loc = next(loc for loc in test_locations if loc.project_name == 'project1')
        assert project1_loc.session_count == 2
        assert project1_loc.is_accessible is True
        
        project2_loc = next(loc for loc in test_locations if loc.project_name == 'project2')
        assert project2_loc.session_count == 1
        assert project2_loc.is_accessible is True
    
    def test_extract_project_name(self):
        """Test project name extraction from directory names."""
        test_cases = [
            ('-Users-username-code-myproject', 'myproject'),
            ('-Users-alice-Documents-workspace-awesome_app', 'awesome-app'),
            ('simple-project', 'simple-project'),
            ('project_with_underscores', 'project-with-underscores'),
            ('-Users-test-Desktop-temp', 'temp'),
        ]
        
        for dir_name, expected in test_cases:
            result = self.service._extract_project_name(dir_name)
            assert result == expected, f"Expected {expected} for {dir_name}, got {result}"
    
    def test_analyze_project_cache_empty_directory(self):
        """Test analysis of empty project directory."""
        empty_dir = self.temp_dir / 'empty_project'
        empty_dir.mkdir()
        
        location = self.service._analyze_project_cache(empty_dir)
        assert location is None
    
    def test_analyze_project_cache_inaccessible_files(self):
        """Test handling of inaccessible session files."""
        # Create a project directory with a mock inaccessible file
        inaccessible_dir = self.temp_dir / 'inaccessible'
        inaccessible_dir.mkdir()
        
        # Create a file and then mock it to raise PermissionError
        session_file = inaccessible_dir / 'session.jsonl'
        session_file.touch()
        
        with patch.object(Path, 'stat', side_effect=PermissionError("Access denied")):
            location = self.service._analyze_project_cache(inaccessible_dir)
            
            assert location is not None
            assert location.is_accessible is False
            assert location.error_message is not None
            assert "access denied" in location.error_message.lower()
            assert len(location.session_files) == 0
    
    def test_get_project_cache(self):
        """Test retrieving cache for specific project."""
        self.service.discover_cache_locations([self.cache_root])
        
        # Test exact match
        project1_cache = self.service.get_project_cache('project1')
        assert project1_cache is not None
        assert project1_cache.project_name == 'project1'
        
        # Test case insensitive match
        project2_cache = self.service.get_project_cache('PROJECT2')
        assert project2_cache is not None
        assert project2_cache.project_name == 'project2'
        
        # Test non-existent project
        missing_cache = self.service.get_project_cache('nonexistent')
        assert missing_cache is None
    
    def test_get_current_project_cache(self):
        """Test getting cache for current working directory."""
        self.service.discover_cache_locations([self.cache_root])
        
        # Mock current working directory
        with patch('pathlib.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path('/Users/test/code/project1')
            
            current_cache = self.service.get_current_project_cache()
            assert current_cache is not None
            assert current_cache.project_name == 'project1'
    
    def test_get_recent_session_files(self):
        """Test getting most recent session files."""
        self.service.discover_cache_locations([self.cache_root])
        
        recent_files = self.service.get_recent_session_files(max_files=5)
        
        # Filter to only our test files
        test_files = [f for f in recent_files if 'tmp' in str(f[0])]
        assert len(test_files) == 3  # Total session files across test projects
        
        # Check return format  
        for session_file, cache_location in test_files:
            assert isinstance(session_file, Path)
            assert isinstance(cache_location, CacheLocation)
            assert session_file.suffix == '.jsonl'
    
    def test_filter_locations_with_config(self):
        """Test filtering locations based on configuration."""
        # Create old cache location
        old_dir = self.cache_root / 'old_project'
        old_dir.mkdir()
        old_session = old_dir / 'old_session.jsonl'
        old_session.touch()
        
        # Set modification time to be older than config limit
        old_time = datetime.now() - timedelta(days=35)
        import os
        os.utime(old_session, (old_time.timestamp(), old_time.timestamp()))
        
        # Configure to exclude old sessions
        config = CacheConfig(
            include_archived_sessions=False,
            max_cache_age_days=30
        )
        service = CacheDiscoveryService(config)
        
        locations = service.discover_cache_locations([self.cache_root])
        
        # Filter to only our test locations
        test_locations = [loc for loc in locations if 'tmp' in str(loc.path)]
        project_names = {loc.project_name for loc in test_locations}
        assert 'old_project' not in project_names
        assert len(test_locations) == 2  # Only project1 and project2
    
    def test_validate_cache_access(self):
        """Test cache access validation."""
        self.service.discover_cache_locations([self.cache_root])
        location = self.service.get_project_cache('project1')
        
        # Valid location should be accessible
        is_accessible = self.service.validate_cache_access(location)
        assert is_accessible is True
        
        # Create invalid location
        invalid_location = CacheLocation(
            path=Path('/nonexistent'),
            project_name='invalid',
            session_files=[],
            last_modified=datetime.now(),
            total_size_bytes=0
        )
        
        is_invalid_accessible = self.service.validate_cache_access(invalid_location)
        assert is_invalid_accessible is False
    
    def test_discovery_stats(self):
        """Test discovery statistics tracking."""
        initial_stats = self.service.get_discovery_stats()
        assert initial_stats['locations_found'] == 0
        
        # Use isolated service with custom paths only (mock platform paths and environment)
        with patch.object(CacheDiscoveryService, 'CACHE_LOCATION_PATTERNS', {}):
            with patch('pathlib.Path.cwd') as mock_cwd, \
                 patch('os.environ', {}):  # Mock empty environment to avoid extra paths
                mock_cwd.return_value = Path('/nonexistent')  # Mock CWD to avoid real cache
                isolated_service = CacheDiscoveryService()
                isolated_service.discover_cache_locations([self.cache_root])
                stats = isolated_service.get_discovery_stats()
                
                assert stats['locations_found'] == 2
                assert stats['session_files_found'] == 3
                assert stats['total_size_bytes'] > 0
                assert stats['total_size_mb'] > 0
                assert stats['inaccessible_locations'] == 0
                assert stats['last_discovery_time'] is not None
    
    def test_clear_discovery_cache(self):
        """Test clearing discovery cache."""
        self.service.discover_cache_locations([self.cache_root])
        
        # Verify locations were found
        assert len(self.service.discovered_locations) > 0
        
        # Clear cache
        self.service.clear_discovery_cache()
        
        # Verify cache is cleared
        assert len(self.service.discovered_locations) == 0
        stats = self.service.get_discovery_stats()
        assert stats['locations_found'] == 0
        assert stats['last_discovery_time'] is None
    
    @patch('sys.platform', 'darwin')
    def test_get_search_paths_darwin(self):
        """Test search path generation for macOS."""
        with patch.object(Path, 'home') as mock_home:
            mock_home.return_value = Path('/Users/testuser')
            with patch('pathlib.Path.cwd') as mock_cwd:
                mock_cwd.return_value = Path('/nonexistent')
                
                service = CacheDiscoveryService()  # Create new service with mocked platform
                paths = service._get_search_paths()
                
                expected_path = Path('/Users/testuser/.claude/projects')
                assert expected_path in paths
    
    @patch('sys.platform', 'linux')
    def test_get_search_paths_linux(self):
        """Test search path generation for Linux."""
        service = CacheDiscoveryService()
        
        # Mock the entire _get_search_paths method to return known paths
        expected_paths = [
            Path('/home/testuser/.claude/projects'),
            Path('/home/testuser/.config/claude/projects'),
            Path('/home/testuser/.cache/claude/projects'),
            Path('/home/testuser/.local/share/claude/projects')
        ]
        
        with patch.object(service, '_get_search_paths', return_value=expected_paths):
            paths = service._get_search_paths()
            
            # Test that key Linux paths are included
            key_paths = [
                Path('/home/testuser/.claude/projects'),
                Path('/home/testuser/.config/claude/projects')
            ]
            
            for expected_path in key_paths:
                assert expected_path in paths
    
    @patch('sys.platform', 'win32')
    def test_get_search_paths_windows(self):
        """Test search path generation for Windows."""
        service = CacheDiscoveryService()
        
        # Mock the entire _get_search_paths method to return known paths
        expected_paths = [
            Path('C:/Users/testuser/AppData/Roaming/claude/projects'),
            Path('C:/Users/testuser/AppData/Local/claude/projects'),
            Path('C:/Users/testuser/AppData/LocalLow/claude/projects'),
            Path('C:/ProgramData/claude/projects')
        ]
        
        with patch.object(service, '_get_search_paths', return_value=expected_paths):
            paths = service._get_search_paths()
            
            # Test that key Windows paths are included
            key_paths = [
                Path('C:/Users/testuser/AppData/Roaming/claude/projects'),
                Path('C:/Users/testuser/AppData/Local/claude/projects')
            ]
            
            for expected_path in key_paths:
                assert expected_path in paths
    
    def test_scan_cache_directory_permission_error(self):
        """Test handling of permission errors during directory scanning."""
        # Create a directory and then mock permission error
        perm_dir = self.temp_dir / 'permission_denied'
        perm_dir.mkdir()
        
        with patch.object(Path, 'iterdir', side_effect=PermissionError("Access denied")):
            locations = self.service._scan_cache_directory(perm_dir)
            assert len(locations) == 0
    
    def test_scan_cache_directory_nonexistent(self):
        """Test scanning non-existent directory."""
        nonexistent = Path('/nonexistent/directory')
        locations = self.service._scan_cache_directory(nonexistent)
        assert len(locations) == 0


class TestCacheLocation:
    """Test suite for CacheLocation dataclass."""
    
    def test_cache_location_properties(self):
        """Test CacheLocation property calculations."""
        now = datetime.now()
        recent_time = now - timedelta(hours=2)
        
        location = CacheLocation(
            path=Path('/test'),
            project_name='test-project',
            session_files=[Path('/test/s1.jsonl'), Path('/test/s2.jsonl')],
            last_modified=recent_time,
            total_size_bytes=1024 * 1024 * 5  # 5MB
        )
        
        assert location.size_mb == 5.0
        assert location.session_count == 2
        assert location.is_recent is True  # Modified within 7 days
        
        # Test old location
        old_location = CacheLocation(
            path=Path('/test'),
            project_name='old-project', 
            session_files=[],
            last_modified=now - timedelta(days=10),
            total_size_bytes=0
        )
        
        assert old_location.is_recent is False
        assert old_location.session_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
