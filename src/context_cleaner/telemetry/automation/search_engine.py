"""
Advanced Search Automation Using Telemetry Patterns

Implements intelligent progressive search based on discovered telemetry patterns:
- Read → Grep → Read → Glob sequences
- Context-aware file discovery
- Pattern-based search optimization
- Automated workflow suggestions
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """Different search strategies based on telemetry patterns"""
    KEYWORD_SEARCH = "keyword_search"           # Simple keyword matching
    SEMANTIC_SEARCH = "semantic_search"         # Context-aware search
    PATTERN_MATCHING = "pattern_matching"       # Regex and pattern search
    CONTEXTUAL_SEARCH = "contextual_search"     # Based on file relationships
    PROGRESSIVE_SEARCH = "progressive_search"   # Multi-stage search refinement


@dataclass
class SearchResult:
    """Individual search result"""
    file_path: str
    content_snippet: str
    relevance_score: float
    line_number: Optional[int] = None
    context_lines: List[str] = field(default_factory=list)
    search_strategy: SearchStrategy = SearchStrategy.KEYWORD_SEARCH


@dataclass
class SearchResults:
    """Collection of search results with metadata"""
    query: str
    results: List[SearchResult]
    total_matches: int
    search_time: float
    strategies_used: List[SearchStrategy]
    confidence: float
    suggested_actions: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    
    def add_result(self, result: SearchResult):
        """Add a result to the collection"""
        self.results.append(result)
        self.total_matches += 1
    
    def get_top_files(self, limit: int = 5) -> List[str]:
        """Get top files by relevance score"""
        sorted_results = sorted(self.results, key=lambda r: r.relevance_score, reverse=True)
        return [r.file_path for r in sorted_results[:limit]]
    
    def get_files_by_extension(self, extension: str) -> List[str]:
        """Get files with specific extension"""
        return [r.file_path for r in self.results 
                if r.file_path.endswith(f'.{extension}')]


@dataclass
class WorkflowPattern:
    """Discovered workflow pattern from telemetry"""
    name: str
    sequence: List[str]  # Tool sequence like ["Read", "Grep", "Edit"]
    frequency: int
    success_rate: float
    context_types: List[str]  # File types where this pattern is successful
    typical_queries: List[str]


class AdvancedSearchEngine:
    """Intelligent search engine based on telemetry patterns"""
    
    def __init__(self, telemetry_client: ClickHouseClient, workspace_root: Optional[Path] = None):
        self.telemetry = telemetry_client
        self.workspace_root = workspace_root or Path.cwd()
        
        # Search optimization parameters
        self.max_results_per_strategy = 50
        self.confidence_threshold = 0.7
        self.context_expansion_limit = 10
        
        # Workflow patterns discovered from telemetry
        self.workflow_patterns: List[WorkflowPattern] = []
        
        # File relationship cache
        self._file_relationships: Dict[str, Set[str]] = {}
        self._relationship_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)
        
        # Search history for learning
        self._search_history: List[Dict[str, Any]] = []
    
    async def initialize_patterns(self):
        """Initialize workflow patterns from telemetry data"""
        try:
            # Query telemetry for common tool sequences
            sequence_query = """
            SELECT 
                tool_sequence,
                COUNT(*) as frequency,
                AVG(success_score) as success_rate
            FROM (
                SELECT 
                    session_id,
                    groupArray(tool_name) as tool_sequence,
                    1.0 as success_score  -- Simplified success scoring
                FROM claude_code_logs 
                WHERE Timestamp >= now() - INTERVAL 30 DAY
                AND tool_name IS NOT NULL
                GROUP BY session_id
            )
            GROUP BY tool_sequence
            HAVING frequency >= 5
            ORDER BY frequency DESC
            LIMIT 20
            """
            
            results = await self.telemetry.execute_query(sequence_query)
            
            for result in results:
                sequence = result.get('tool_sequence', [])
                if len(sequence) >= 2:  # Only patterns with 2+ tools
                    pattern = WorkflowPattern(
                        name=f"{sequence[0]}-{sequence[-1]} Pattern",
                        sequence=sequence,
                        frequency=result.get('frequency', 0),
                        success_rate=result.get('success_rate', 0.0),
                        context_types=['py', 'js', 'ts', 'md'],  # Common file types
                        typical_queries=[]  # Will be populated as we learn
                    )
                    self.workflow_patterns.append(pattern)
            
            logger.info(f"Initialized {len(self.workflow_patterns)} workflow patterns")
            
        except Exception as e:
            logger.warning(f"Could not initialize patterns from telemetry: {e}")
            # Fall back to default patterns
            self._initialize_default_patterns()
    
    def _initialize_default_patterns(self):
        """Initialize with default patterns if telemetry is unavailable"""
        default_patterns = [
            WorkflowPattern(
                name="Read-Grep-Edit Pattern",
                sequence=["Read", "Grep", "Edit"],
                frequency=50,
                success_rate=0.85,
                context_types=['py', 'js', 'ts'],
                typical_queries=["function", "class", "error", "config"]
            ),
            WorkflowPattern(
                name="Glob-Read-Analyze Pattern", 
                sequence=["Glob", "Read", "TodoWrite"],
                frequency=30,
                success_rate=0.78,
                context_types=['py', 'md', 'json'],
                typical_queries=["files", "documentation", "structure"]
            ),
            WorkflowPattern(
                name="Search-Understand-Modify Pattern",
                sequence=["Grep", "Read", "Edit", "Bash"],
                frequency=25,
                success_rate=0.92,
                context_types=['py', 'js', 'sh'],
                typical_queries=["bug", "fix", "implement", "test"]
            )
        ]
        
        self.workflow_patterns.extend(default_patterns)
        logger.info(f"Initialized {len(default_patterns)} default workflow patterns")
    
    async def deep_search(self, query: str, context_files: Optional[List[str]] = None,
                         progressive: bool = True) -> SearchResults:
        """
        Perform intelligent progressive search based on telemetry patterns
        
        This implements the discovered "Read → Grep → Read → Glob" pattern
        """
        start_time = datetime.now()
        
        # Initialize search results
        results = SearchResults(
            query=query,
            results=[],
            total_matches=0,
            search_time=0.0,
            strategies_used=[],
            confidence=0.0
        )
        
        try:
            # Stage 1: Initial keyword search (fast)
            logger.info(f"Stage 1: Keyword search for '{query}'")
            keyword_results = await self._keyword_search(query, context_files)
            results.strategies_used.append(SearchStrategy.KEYWORD_SEARCH)
            
            for result in keyword_results:
                results.add_result(result)
            
            # Stage 2: Context expansion based on initial results
            if progressive and keyword_results:
                logger.info("Stage 2: Context expansion")
                related_files = await self._find_related_files([r.file_path for r in keyword_results])
                contextual_results = await self._contextual_search(query, related_files)
                results.strategies_used.append(SearchStrategy.CONTEXTUAL_SEARCH)
                
                for result in contextual_results:
                    if result.file_path not in [r.file_path for r in results.results]:
                        results.add_result(result)
                
                results.related_files.extend(related_files[:10])  # Limit related files
            
            # Stage 3: Pattern-based search refinement
            if progressive:
                logger.info("Stage 3: Pattern analysis")
                pattern_results = await self._pattern_search(query, results.get_top_files(10))
                results.strategies_used.append(SearchStrategy.PATTERN_MATCHING)
                
                for result in pattern_results:
                    # Check if we already have this file, update with better score if needed
                    existing = next((r for r in results.results 
                                   if r.file_path == result.file_path), None)
                    if existing:
                        if result.relevance_score > existing.relevance_score:
                            existing.relevance_score = result.relevance_score
                            existing.content_snippet = result.content_snippet
                    else:
                        results.add_result(result)
            
            # Stage 4: Generate suggestions based on workflow patterns
            results.suggested_actions = await self._generate_action_suggestions(query, results)
            
            # Calculate final metrics
            search_duration = (datetime.now() - start_time).total_seconds()
            results.search_time = search_duration
            results.confidence = self._calculate_search_confidence(results)
            
            # Store search in history for learning
            self._add_to_search_history(query, results)
            
            logger.info(f"Deep search completed: {results.total_matches} results in {search_duration:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Error in deep search for '{query}': {e}")
            results.search_time = (datetime.now() - start_time).total_seconds()
            return results
    
    async def _keyword_search(self, query: str, context_files: Optional[List[str]] = None) -> List[SearchResult]:
        """Perform initial keyword search"""
        results = []
        
        try:
            # Use Grep-like search patterns
            search_terms = self._extract_search_terms(query)
            
            # Simulate file search (in real implementation, would use actual grep/ripgrep)
            for term in search_terms:
                # This would be replaced with actual file system search
                mock_results = self._simulate_file_search(term, context_files)
                results.extend(mock_results)
            
            # Remove duplicates and sort by relevance
            unique_results = {}
            for result in results:
                key = f"{result.file_path}:{result.line_number}"
                if key not in unique_results or result.relevance_score > unique_results[key].relevance_score:
                    unique_results[key] = result
            
            return list(unique_results.values())
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query"""
        # Remove common words and extract keywords
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        
        # Split on whitespace and punctuation
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out stop words and short words
        terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Add original query as well
        if len(query.strip()) > 0:
            terms.append(query.strip())
        
        return terms
    
    def _simulate_file_search(self, term: str, context_files: Optional[List[str]] = None) -> List[SearchResult]:
        """Simulate file search (replace with actual search in real implementation)"""
        # This is a mock implementation - in reality would use grep/ripgrep
        common_files = [
            "src/main.py",
            "src/utils/helpers.py", 
            "src/config.py",
            "README.md",
            "tests/test_main.py"
        ]
        
        if context_files:
            search_files = context_files
        else:
            search_files = common_files
        
        results = []
        for file_path in search_files[:5]:  # Limit for demo
            # Simulate finding matches
            relevance = min(1.0, len(term) / 10.0 + 0.3)  # Simple relevance scoring
            
            result = SearchResult(
                file_path=file_path,
                content_snippet=f"Found '{term}' in context...",
                relevance_score=relevance,
                line_number=42,  # Mock line number
                context_lines=[f"  def function_with_{term}():", f"      return {term}_value"],
                search_strategy=SearchStrategy.KEYWORD_SEARCH
            )
            results.append(result)
        
        return results
    
    async def _find_related_files(self, initial_files: List[str]) -> List[str]:
        """Find files related to the initial search results"""
        if not initial_files:
            return []
        
        # Check cache first
        if self._should_refresh_relationships():
            await self._build_file_relationships()
        
        related = set()
        for file_path in initial_files:
            if file_path in self._file_relationships:
                related.update(self._file_relationships[file_path])
        
        return list(related)[:self.context_expansion_limit]
    
    def _should_refresh_relationships(self) -> bool:
        """Check if file relationships need to be refreshed"""
        return (not self._relationship_cache_time or 
                datetime.now() - self._relationship_cache_time > self._cache_ttl)
    
    async def _build_file_relationships(self):
        """Build file relationships from import patterns and directory structure"""
        try:
            # This would analyze actual file imports, directory structure, etc.
            # For now, simulate with common relationships
            
            relationships = {
                "src/main.py": {"src/config.py", "src/utils/helpers.py", "tests/test_main.py"},
                "src/config.py": {"src/main.py", "src/settings.py"},
                "src/utils/helpers.py": {"src/main.py", "tests/test_utils.py"},
                "README.md": {"src/main.py", "setup.py", "requirements.txt"},
                "tests/test_main.py": {"src/main.py", "tests/conftest.py"}
            }
            
            self._file_relationships = relationships
            self._relationship_cache_time = datetime.now()
            
            logger.debug(f"Built relationships for {len(relationships)} files")
            
        except Exception as e:
            logger.error(f"Error building file relationships: {e}")
    
    async def _contextual_search(self, query: str, related_files: List[str]) -> List[SearchResult]:
        """Perform contextual search in related files"""
        results = []
        
        for file_path in related_files:
            # Weight relevance based on file relationship strength
            base_relevance = 0.6  # Lower than direct matches but still relevant
            
            result = SearchResult(
                file_path=file_path,
                content_snippet=f"Related context for '{query}' found in {file_path}",
                relevance_score=base_relevance,
                search_strategy=SearchStrategy.CONTEXTUAL_SEARCH
            )
            results.append(result)
        
        return results
    
    async def _pattern_search(self, query: str, target_files: List[str]) -> List[SearchResult]:
        """Perform pattern-based search using regex and advanced patterns"""
        results = []
        
        # Generate search patterns based on query
        patterns = self._generate_search_patterns(query)
        
        for file_path in target_files:
            for pattern in patterns:
                # Simulate pattern matching
                result = SearchResult(
                    file_path=file_path,
                    content_snippet=f"Pattern '{pattern}' matched in {file_path}",
                    relevance_score=0.8,  # Pattern matches are usually high relevance
                    search_strategy=SearchStrategy.PATTERN_MATCHING
                )
                results.append(result)
        
        return results
    
    def _generate_search_patterns(self, query: str) -> List[str]:
        """Generate regex patterns based on query"""
        patterns = []
        
        # Function/method patterns
        if any(word in query.lower() for word in ['function', 'method', 'def']):
            patterns.append(r'def\s+\w*' + re.escape(query.lower()) + r'\w*\s*\(')
        
        # Class patterns
        if any(word in query.lower() for word in ['class', 'object']):
            patterns.append(r'class\s+\w*' + re.escape(query.lower()) + r'\w*\s*[\(:]')
        
        # Variable/constant patterns
        patterns.append(r'\b\w*' + re.escape(query.lower()) + r'\w*\b')
        
        return patterns[:5]  # Limit patterns to avoid performance issues
    
    async def _generate_action_suggestions(self, query: str, results: SearchResults) -> List[str]:
        """Generate next action suggestions based on workflow patterns and results"""
        suggestions = []
        
        # Suggest based on workflow patterns
        best_pattern = self._find_best_workflow_pattern(query, results)
        if best_pattern:
            next_tools = self._get_next_tools_in_pattern(best_pattern, ["Grep"])  # Assume we just did search
            for tool in next_tools[:3]:
                if tool == "Read":
                    suggestions.append(f"Read top result: {results.get_top_files(1)[0] if results.results else 'file'}")
                elif tool == "Edit":
                    suggestions.append("Edit the most relevant file found")
                elif tool == "TodoWrite":
                    suggestions.append("Track findings with TodoWrite")
                elif tool == "Bash":
                    suggestions.append("Test or execute changes")
        
        # Suggest based on file types found
        py_files = results.get_files_by_extension('py')
        if py_files:
            suggestions.append(f"Analyze Python files: {', '.join(py_files[:3])}")
        
        js_files = results.get_files_by_extension('js')
        if js_files:
            suggestions.append(f"Review JavaScript files: {', '.join(js_files[:3])}")
        
        # Generic suggestions
        if len(results.results) > 5:
            suggestions.append("Narrow search scope with more specific terms")
        elif len(results.results) < 3:
            suggestions.append("Broaden search or check related directories")
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    def _find_best_workflow_pattern(self, query: str, results: SearchResults) -> Optional[WorkflowPattern]:
        """Find the best workflow pattern for the current context"""
        if not self.workflow_patterns:
            return None
        
        # Score patterns based on query and results
        pattern_scores = []
        for pattern in self.workflow_patterns:
            score = 0
            
            # Check if query matches typical queries
            for typical_query in pattern.typical_queries:
                if typical_query.lower() in query.lower():
                    score += 2
            
            # Check file types in results
            for result in results.results:
                file_ext = result.file_path.split('.')[-1] if '.' in result.file_path else ''
                if file_ext in pattern.context_types:
                    score += 1
            
            # Weight by pattern success rate and frequency
            score *= (pattern.success_rate * (pattern.frequency / 100))
            
            pattern_scores.append((pattern, score))
        
        # Return pattern with highest score
        if pattern_scores:
            best_pattern, best_score = max(pattern_scores, key=lambda x: x[1])
            if best_score > 0:
                return best_pattern
        
        return None
    
    def _get_next_tools_in_pattern(self, pattern: WorkflowPattern, current_tools: List[str]) -> List[str]:
        """Get next tools in a workflow pattern"""
        sequence = pattern.sequence
        if not current_tools:
            return sequence[:2]  # Return first 2 tools
        
        # Find where we are in the pattern
        for i, tool in enumerate(sequence):
            if tool in current_tools:
                # Return remaining tools in pattern
                return sequence[i+1:i+3]  # Next 2 tools
        
        # If current tools don't match pattern, return beginning of pattern
        return sequence[:2]
    
    def _calculate_search_confidence(self, results: SearchResults) -> float:
        """Calculate confidence in search results"""
        if not results.results:
            return 0.0
        
        # Factors that increase confidence
        confidence = 0.0
        
        # Number of results (but with diminishing returns)
        result_score = min(len(results.results) / 10.0, 0.3)
        confidence += result_score
        
        # Average relevance score
        avg_relevance = sum(r.relevance_score for r in results.results) / len(results.results)
        confidence += avg_relevance * 0.4
        
        # Strategy diversity
        strategy_bonus = len(set(results.strategies_used)) * 0.1
        confidence += strategy_bonus
        
        # Time bonus (faster searches might be less thorough)
        if results.search_time < 2.0:
            confidence -= 0.1
        
        return min(confidence, 1.0)
    
    def _add_to_search_history(self, query: str, results: SearchResults):
        """Add search to history for learning purposes"""
        history_entry = {
            'query': query,
            'timestamp': datetime.now(),
            'result_count': results.total_matches,
            'confidence': results.confidence,
            'strategies': [s.value for s in results.strategies_used],
            'search_time': results.search_time
        }
        
        self._search_history.append(history_entry)
        
        # Limit history size
        if len(self._search_history) > 100:
            self._search_history.pop(0)
    
    async def get_search_analytics(self) -> Dict[str, Any]:
        """Get analytics about search patterns and performance"""
        if not self._search_history:
            return {"message": "No search history available"}
        
        total_searches = len(self._search_history)
        avg_confidence = sum(s['confidence'] for s in self._search_history) / total_searches
        avg_results = sum(s['result_count'] for s in self._search_history) / total_searches
        avg_time = sum(s['search_time'] for s in self._search_history) / total_searches
        
        # Most common strategies
        all_strategies = []
        for search in self._search_history:
            all_strategies.extend(search['strategies'])
        
        strategy_counts = {}
        for strategy in all_strategies:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        return {
            'total_searches': total_searches,
            'average_confidence': avg_confidence,
            'average_results': avg_results,
            'average_search_time': avg_time,
            'strategy_usage': strategy_counts,
            'workflow_patterns': len(self.workflow_patterns)
        }