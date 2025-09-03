"""Tests for advanced search automation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from pathlib import Path

from src.context_cleaner.telemetry.automation.search_engine import (
    AdvancedSearchEngine,
    SearchResults,
    SearchResult,
    SearchStrategy,
    WorkflowPattern,
)


class TestAdvancedSearchEngine:
    """Test suite for AdvancedSearchEngine."""
    
    @pytest.fixture
    def search_engine(self, mock_telemetry_client):
        """Create search engine with mocked dependencies."""
        engine = AdvancedSearchEngine(mock_telemetry_client, Path.cwd())
        return engine
    
    @pytest.fixture
    def sample_workflow_pattern(self):
        """Create sample workflow pattern."""
        return WorkflowPattern(
            name="Read-Edit Pattern",
            sequence=["Read", "Edit", "Bash"],
            frequency=25,
            success_rate=0.85,
            context_types=["py", "js"],
            typical_queries=["function", "bug", "implement"]
        )
    
    @pytest.mark.asyncio
    async def test_initialize_patterns(self, search_engine, mock_telemetry_client):
        """Test workflow pattern initialization from telemetry."""
        # Mock telemetry query results
        mock_telemetry_client.execute_query = AsyncMock(return_value=[
            {
                "tool_sequence": ["Read", "Grep", "Edit"],
                "frequency": 15,
                "success_rate": 0.8
            },
            {
                "tool_sequence": ["Glob", "Read", "TodoWrite"],
                "frequency": 10,
                "success_rate": 0.7
            }
        ])
        
        await search_engine.initialize_patterns()
        
        assert len(search_engine.workflow_patterns) >= 2
        
        # Check if patterns were created correctly
        pattern_names = [p.name for p in search_engine.workflow_patterns]
        assert any("Read-Edit Pattern" in name for name in pattern_names)
    
    @pytest.mark.asyncio
    async def test_deep_search(self, search_engine, mock_telemetry_client):
        """Test deep search functionality."""
        # Initialize with default patterns
        search_engine._initialize_default_patterns()
        
        # Mock file relationships
        await search_engine._build_file_relationships()
        
        results = await search_engine.deep_search("authentication error", progressive=True)
        
        assert isinstance(results, SearchResults)
        assert results.query == "authentication error"
        assert len(results.strategies_used) > 0
        assert results.confidence >= 0.0
        assert len(results.suggested_actions) > 0
    
    @pytest.mark.asyncio
    async def test_keyword_search(self, search_engine):
        """Test keyword search strategy."""
        results = await search_engine._keyword_search("function", context_files=None)
        
        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, SearchResult)
            assert result.search_strategy == SearchStrategy.KEYWORD_SEARCH
            assert result.relevance_score > 0
    
    def test_extract_search_terms(self, search_engine):
        """Test search term extraction."""
        query = "find the authentication function in config"
        terms = search_engine._extract_search_terms(query)
        
        assert "authentication" in terms
        assert "function" in terms
        assert "config" in terms
        assert "the" not in terms  # Stop word should be filtered
        assert query.strip() in terms  # Original query should be included
    
    @pytest.mark.asyncio
    async def test_find_related_files(self, search_engine):
        """Test related file discovery."""
        # Build relationships first
        await search_engine._build_file_relationships()
        
        initial_files = ["src/main.py", "src/config.py"]
        related_files = await search_engine._find_related_files(initial_files)
        
        assert isinstance(related_files, list)
        assert len(related_files) <= search_engine.context_expansion_limit
        
        # Should not include the original files
        for file in related_files:
            assert file not in initial_files
    
    @pytest.mark.asyncio
    async def test_contextual_search(self, search_engine):
        """Test contextual search in related files."""
        related_files = ["tests/test_auth.py", "docs/auth_guide.md"]
        results = await search_engine._contextual_search("authentication", related_files)
        
        assert len(results) == len(related_files)
        for result in results:
            assert result.search_strategy == SearchStrategy.CONTEXTUAL_SEARCH
            assert result.file_path in related_files
    
    @pytest.mark.asyncio
    async def test_pattern_search(self, search_engine):
        """Test pattern-based search."""
        target_files = ["src/auth.py", "src/utils.py"]
        results = await search_engine._pattern_search("function", target_files)
        
        assert len(results) > 0
        for result in results:
            assert result.search_strategy == SearchStrategy.PATTERN_MATCHING
            assert result.file_path in target_files
    
    def test_generate_search_patterns(self, search_engine):
        """Test regex pattern generation."""
        # Test function query
        function_patterns = search_engine._generate_search_patterns("function authenticate")
        assert len(function_patterns) > 0
        assert any("def" in pattern for pattern in function_patterns)
        
        # Test class query
        class_patterns = search_engine._generate_search_patterns("class AuthManager")
        assert len(class_patterns) > 0
        assert any("class" in pattern for pattern in class_patterns)
    
    @pytest.mark.asyncio
    async def test_generate_action_suggestions(self, search_engine, sample_workflow_pattern):
        """Test action suggestion generation."""
        search_engine.workflow_patterns = [sample_workflow_pattern]
        
        # Create mock search results
        results = SearchResults(
            query="implement function",
            results=[
                SearchResult("src/main.py", "Function implementation", 0.9),
                SearchResult("tests/test_main.py", "Test for function", 0.7)
            ],
            total_matches=2,
            search_time=1.5,
            strategies_used=[SearchStrategy.KEYWORD_SEARCH],
            confidence=0.8
        )
        
        suggestions = await search_engine._generate_action_suggestions("implement function", results)
        
        assert len(suggestions) > 0
        assert any("Read" in suggestion for suggestion in suggestions)
    
    def test_find_best_workflow_pattern(self, search_engine, sample_workflow_pattern):
        """Test workflow pattern matching."""
        search_engine.workflow_patterns = [sample_workflow_pattern]
        
        # Create results with Python files
        results = SearchResults(
            query="fix bug in function",
            results=[SearchResult("src/main.py", "Bug fix", 0.9)],
            total_matches=1,
            search_time=1.0,
            strategies_used=[SearchStrategy.KEYWORD_SEARCH],
            confidence=0.8
        )
        
        best_pattern = search_engine._find_best_workflow_pattern("fix bug", results)
        
        assert best_pattern is not None
        assert best_pattern.name == "Read-Edit Pattern"
    
    def test_get_next_tools_in_pattern(self, search_engine, sample_workflow_pattern):
        """Test next tool suggestion from workflow patterns."""
        # Test when we've used "Read"
        next_tools = search_engine._get_next_tools_in_pattern(sample_workflow_pattern, ["Read"])
        
        assert "Edit" in next_tools or "Bash" in next_tools
        assert len(next_tools) <= 2
    
    def test_calculate_search_confidence(self, search_engine):
        """Test search confidence calculation."""
        # High confidence scenario
        high_confidence_results = SearchResults(
            query="test query",
            results=[
                SearchResult("file1.py", "content", 0.9),
                SearchResult("file2.py", "content", 0.8),
                SearchResult("file3.py", "content", 0.7)
            ],
            total_matches=3,
            search_time=1.0,
            strategies_used=[SearchStrategy.KEYWORD_SEARCH, SearchStrategy.CONTEXTUAL_SEARCH],
            confidence=0.0  # Will be calculated
        )
        
        confidence = search_engine._calculate_search_confidence(high_confidence_results)
        assert 0.0 <= confidence <= 1.0
        
        # Low confidence scenario (no results)
        low_confidence_results = SearchResults(
            query="test query",
            results=[],
            total_matches=0,
            search_time=0.1,
            strategies_used=[SearchStrategy.KEYWORD_SEARCH],
            confidence=0.0
        )
        
        low_confidence = search_engine._calculate_search_confidence(low_confidence_results)
        assert low_confidence == 0.0
        assert confidence > low_confidence
    
    @pytest.mark.asyncio
    async def test_search_analytics(self, search_engine):
        """Test search analytics functionality."""
        # Add some search history
        search_engine._search_history = [
            {
                'query': 'test query 1',
                'timestamp': datetime.now(),
                'result_count': 5,
                'confidence': 0.8,
                'strategies': ['keyword_search'],
                'search_time': 1.2
            },
            {
                'query': 'test query 2',
                'timestamp': datetime.now(),
                'result_count': 3,
                'confidence': 0.6,
                'strategies': ['keyword_search', 'contextual_search'],
                'search_time': 2.1
            }
        ]
        
        analytics = await search_engine.get_search_analytics()
        
        assert analytics['total_searches'] == 2
        assert 'average_confidence' in analytics
        assert 'average_results' in analytics
        assert 'average_search_time' in analytics
        assert 'strategy_usage' in analytics
    
    def test_search_results_operations(self):
        """Test SearchResults utility methods."""
        results = SearchResults(
            query="test",
            results=[],
            total_matches=0,
            search_time=1.0,
            strategies_used=[],
            confidence=0.0
        )
        
        # Test adding results
        result1 = SearchResult("file1.py", "content", 0.9)
        result2 = SearchResult("file2.js", "content", 0.7)
        
        results.add_result(result1)
        results.add_result(result2)
        
        assert results.total_matches == 2
        assert len(results.results) == 2
        
        # Test get_top_files
        top_files = results.get_top_files(1)
        assert len(top_files) == 1
        assert top_files[0] == "file1.py"  # Higher relevance score
        
        # Test get_files_by_extension
        py_files = results.get_files_by_extension("py")
        js_files = results.get_files_by_extension("js")
        
        assert "file1.py" in py_files
        assert "file2.js" in js_files
    
    def test_workflow_pattern_structure(self, sample_workflow_pattern):
        """Test WorkflowPattern dataclass structure."""
        pattern = sample_workflow_pattern
        
        assert pattern.name == "Read-Edit Pattern"
        assert "Read" in pattern.sequence
        assert pattern.frequency == 25
        assert 0.0 <= pattern.success_rate <= 1.0
        assert "py" in pattern.context_types
        assert len(pattern.typical_queries) > 0
    
    @pytest.mark.asyncio
    async def test_file_relationship_caching(self, search_engine):
        """Test file relationship caching mechanism."""
        # First call should build relationships
        await search_engine._build_file_relationships()
        initial_cache_time = search_engine._relationship_cache_time
        
        # Second call should use cache
        await search_engine._build_file_relationships()
        second_cache_time = search_engine._relationship_cache_time
        
        # Cache time should not change if TTL hasn't expired
        assert initial_cache_time == second_cache_time
        
        # Force cache refresh
        search_engine._relationship_cache_time = datetime.now() - timedelta(hours=2)
        await search_engine._build_file_relationships()
        refreshed_cache_time = search_engine._relationship_cache_time
        
        # Cache should have been refreshed
        assert refreshed_cache_time > initial_cache_time