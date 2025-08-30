#!/usr/bin/env python3
"""
Redundancy Detection Engine

Identifies and categorizes redundant content in context including:
- Duplicate content detection (exact and similar matches)
- Obsolete todos and completed tasks
- Redundant file reads (same file read multiple times)
- Stale error messages and resolved issues
- Similar system reminders and repeated explanations

Performance: Optimized for large contexts with efficient similarity detection
"""

import re
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Set, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


@dataclass
class RedundancyReport:
    """Comprehensive redundancy analysis report."""
    
    # Overall metrics
    duplicate_content_percentage: float      # Percentage of duplicate content
    stale_content_percentage: float         # Percentage of stale/obsolete content
    redundant_files_count: int              # Number of redundantly read files
    obsolete_todos_count: int               # Number of completed/obsolete todos
    
    # Detailed findings
    duplicate_items: List[Dict[str, Any]]    # Specific duplicate content items
    obsolete_items: List[Dict[str, Any]]     # Specific obsolete content items
    redundant_file_groups: List[List[str]]   # Groups of redundant file reads
    stale_error_messages: List[str]          # Stale error messages
    
    # Analysis metadata
    total_items_analyzed: int                # Total content items analyzed
    total_estimated_tokens: int             # Total tokens in analyzed content
    redundancy_analysis_duration: float     # Time taken for analysis
    
    # Optimization recommendations
    safe_to_remove: List[Dict[str, Any]]     # Items safe for immediate removal
    consolidation_candidates: List[Dict[str, Any]]  # Items that could be consolidated
    
    def get_redundancy_summary(self) -> str:
        """Get human-readable redundancy summary."""
        summary_parts = [
            f"Duplicate Content: {self.duplicate_content_percentage:.1f}%",
            f"Stale Content: {self.stale_content_percentage:.1f}%",
            f"Redundant Files: {self.redundant_files_count}",
            f"Obsolete Todos: {self.obsolete_todos_count}"
        ]
        return " | ".join(summary_parts)


class RedundancyDetector:
    """
    Advanced Redundancy Detection Engine
    
    Uses multiple detection strategies to identify redundant content:
    - Exact string matching for obvious duplicates
    - Fuzzy matching for similar content
    - Pattern recognition for common redundancy types
    - Temporal analysis for stale content
    """
    
    # Detection thresholds
    EXACT_MATCH_THRESHOLD = 1.0           # Exact duplicates
    SIMILARITY_THRESHOLD = 0.85           # Similar content threshold
    FUZZY_MATCH_MIN_LENGTH = 15          # Minimum length for fuzzy matching
    MAX_COMPARISON_ITEMS = 1000          # Limit comparisons for performance
    
    # Content patterns for obsolete detection
    OBSOLETE_PATTERNS = [
        r'(?i)(completed|done|fixed|resolved|closed)',
        r'(?i)(✅|✓|☑)',
        r'(?i)(no longer|not needed|obsolete|archived)',
        r'(?i)(already\s+(done|fixed|implemented))'
    ]
    
    # File path patterns for common duplicates
    FILE_PATTERNS = [
        r'\.py$', r'\.js$', r'\.ts$', r'\.md$', r'\.json$', r'\.yaml$', r'\.yml$'
    ]
    
    def __init__(self):
        """Initialize redundancy detection engine."""
        self.obsolete_regex = [re.compile(pattern) for pattern in self.OBSOLETE_PATTERNS]
        logger.debug("RedundancyDetector initialized")
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two text strings."""
        if not text1 or not text2:
            return 0.0
        
        # Quick check for exact matches
        if text1 == text2:
            return 1.0
        
        # Skip fuzzy matching for very short strings
        if len(text1) < self.FUZZY_MATCH_MIN_LENGTH or len(text2) < self.FUZZY_MATCH_MIN_LENGTH:
            return 1.0 if text1 == text2 else 0.0
        
        # Use SequenceMatcher for similarity calculation
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _extract_text_content(self, item: Any) -> str:
        """Extract text content from various item types."""
        if isinstance(item, str):
            return item
        elif isinstance(item, dict):
            # Extract meaningful text from dictionary
            text_parts = []
            for key, value in item.items():
                if isinstance(value, (str, int, float)):
                    text_parts.append(f"{key}: {value}")
            return " ".join(text_parts)
        elif isinstance(item, (list, tuple)):
            return " ".join(str(sub_item) for sub_item in item)
        else:
            return str(item)
    
    def _detect_exact_duplicates(self, items: List[Any]) -> List[Tuple[int, int]]:
        """Detect exact duplicate content items."""
        duplicates = []
        content_map = defaultdict(list)
        
        # Group items by content hash
        for i, item in enumerate(items):
            content = self._extract_text_content(item)
            if len(content.strip()) > 0:  # Skip empty content
                content_hash = hashlib.md5(content.encode()).hexdigest()
                content_map[content_hash].append(i)
        
        # Find groups with multiple items (duplicates)
        for indices in content_map.values():
            if len(indices) > 1:
                # Add all pairwise combinations as duplicates
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        duplicates.append((indices[i], indices[j]))
        
        return duplicates
    
    def _detect_similar_content(self, items: List[Any]) -> List[Tuple[int, int, float]]:
        """Detect similar (but not identical) content items."""
        similar_pairs = []
        
        # Limit comparisons for performance
        comparison_limit = min(len(items), self.MAX_COMPARISON_ITEMS)
        items_to_compare = items[:comparison_limit]
        
        for i in range(len(items_to_compare)):
            for j in range(i + 1, len(items_to_compare)):
                text1 = self._extract_text_content(items_to_compare[i])
                text2 = self._extract_text_content(items_to_compare[j])
                
                similarity = self._calculate_similarity(text1, text2)
                
                if self.SIMILARITY_THRESHOLD <= similarity < self.EXACT_MATCH_THRESHOLD:
                    similar_pairs.append((i, j, similarity))
        
        return similar_pairs
    
    def _detect_obsolete_todos(self, todos: List[Any]) -> List[int]:
        """Detect completed or obsolete todo items."""
        obsolete_indices = []
        
        for i, todo in enumerate(todos):
            todo_text = self._extract_text_content(todo).lower()
            
            # Check against obsolete patterns
            for pattern in self.obsolete_regex:
                if pattern.search(todo_text):
                    obsolete_indices.append(i)
                    break
        
        return obsolete_indices
    
    def _detect_redundant_files(self, file_items: List[Any]) -> List[List[str]]:
        """Detect files that have been read multiple times."""
        file_groups = defaultdict(list)
        
        for i, item in enumerate(file_items):
            # Extract file path from various formats
            file_path = None
            if isinstance(item, str):
                file_path = item
            elif isinstance(item, dict):
                # Look for common file path keys
                for key in ['path', 'file', 'filename', 'filepath', 'file_path']:
                    if key in item:
                        file_path = str(item[key])
                        break
            
            if file_path:
                # Normalize file path for comparison
                normalized_path = file_path.strip().lower()
                file_groups[normalized_path].append(i)
        
        # Return groups with multiple occurrences
        redundant_groups = []
        for path, indices in file_groups.items():
            if len(indices) > 1:
                redundant_groups.append([path] + [str(i) for i in indices])
        
        return redundant_groups
    
    def _detect_stale_errors(self, error_items: List[Any]) -> List[str]:
        """Detect error messages that are likely stale or resolved."""
        stale_errors = []
        
        stale_patterns = [
            r'(?i)(fixed|resolved|solved|corrected)',
            r'(?i)(no longer occurs|not happening)',
            r'(?i)(this error.*(was|has been).*fixed)'
        ]
        
        stale_regex = [re.compile(pattern) for pattern in stale_patterns]
        
        for error_item in error_items:
            error_text = self._extract_text_content(error_item)
            
            for pattern in stale_regex:
                if pattern.search(error_text):
                    stale_errors.append(error_text[:200] + "..." if len(error_text) > 200 else error_text)
                    break
        
        return stale_errors
    
    def _categorize_content(self, context_data: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Categorize context content into types for targeted analysis."""
        categories = {
            'conversations': [],
            'messages': [],
            'files': [],
            'todos': [],
            'tasks': [],
            'errors': [],
            'exceptions': [],
            'system_messages': [],
            'reminders': [],
            'other': []
        }
        
        def add_to_category(key: str, value: Any):
            """Add item to appropriate category based on key."""
            key_lower = key.lower()
            
            if any(word in key_lower for word in ['conversation', 'chat', 'message']):
                categories['messages'].append(value)
            elif any(word in key_lower for word in ['file', 'path', 'document']):
                categories['files'].append(value)
            elif any(word in key_lower for word in ['todo', 'task', 'action']):
                categories['todos'].append(value)
            elif any(word in key_lower for word in ['error', 'exception', 'failure']):
                categories['errors'].append(value)
            elif any(word in key_lower for word in ['system', 'reminder', 'note']):
                categories['system_messages'].append(value)
            else:
                categories['other'].append(value)
        
        # Recursively categorize content
        def categorize_recursive(data: Any, parent_key: str = ""):
            if isinstance(data, dict):
                for key, value in data.items():
                    full_key = f"{parent_key}.{key}" if parent_key else key
                    if isinstance(value, (dict, list)):
                        categorize_recursive(value, full_key)
                    else:
                        add_to_category(full_key, value)
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    categorize_recursive(item, f"{parent_key}[{i}]")
            else:
                add_to_category(parent_key, data)
        
        categorize_recursive(context_data)
        return categories
    
    async def analyze_redundancy(self, context_data: Dict[str, Any]) -> RedundancyReport:
        """
        Perform comprehensive redundancy analysis on context data.
        
        Args:
            context_data: Context data to analyze for redundancy
            
        Returns:
            RedundancyReport with detailed findings and recommendations
        """
        analysis_start = datetime.now()
        
        try:
            # Categorize content for targeted analysis
            categories = self._categorize_content(context_data)
            
            # Track all findings
            duplicate_items = []
            obsolete_items = []
            safe_to_remove = []
            consolidation_candidates = []
            
            total_items = sum(len(items) for items in categories.values())
            total_content = json.dumps(context_data, default=str)
            total_tokens = len(total_content) // 4
            
            # Analyze messages and conversations for duplicates
            messages = categories['messages']
            if messages:
                exact_duplicates = self._detect_exact_duplicates(messages)
                similar_content = self._detect_similar_content(messages)
                
                for i, j in exact_duplicates:
                    duplicate_items.append({
                        'type': 'exact_duplicate',
                        'category': 'messages',
                        'indices': [i, j],
                        'content_preview': str(messages[i])[:100] + "..."
                    })
                    safe_to_remove.append({
                        'type': 'duplicate_message',
                        'index': j,  # Remove the later occurrence
                        'reason': 'Exact duplicate of earlier message'
                    })
                
                for i, j, similarity in similar_content:
                    duplicate_items.append({
                        'type': 'similar_content',
                        'category': 'messages',
                        'indices': [i, j],
                        'similarity': similarity,
                        'content_preview': str(messages[i])[:100] + "..."
                    })
                    consolidation_candidates.append({
                        'type': 'similar_messages',
                        'indices': [i, j],
                        'similarity': similarity,
                        'reason': f'Similar content ({similarity:.2%} match)'
                    })
            
            # Analyze todos for obsolete items
            todos = categories['todos']
            obsolete_todo_indices = self._detect_obsolete_todos(todos)
            for index in obsolete_todo_indices:
                obsolete_items.append({
                    'type': 'obsolete_todo',
                    'index': index,
                    'content': str(todos[index])[:100] + "..."
                })
                safe_to_remove.append({
                    'type': 'completed_todo',
                    'index': index,
                    'reason': 'Task appears to be completed or obsolete'
                })
            
            # Analyze files for redundancy
            files = categories['files']
            redundant_file_groups = self._detect_redundant_files(files)
            
            # Analyze errors for stale messages
            errors = categories['errors']
            stale_error_messages = self._detect_stale_errors(errors)
            
            # Calculate percentages
            duplicate_content_count = len(duplicate_items) + len(obsolete_items)
            duplicate_content_percentage = (duplicate_content_count / max(1, total_items)) * 100
            
            stale_content_count = len(obsolete_items) + len(stale_error_messages)
            stale_content_percentage = (stale_content_count / max(1, total_items)) * 100
            
            analysis_duration = (datetime.now() - analysis_start).total_seconds()
            
            report = RedundancyReport(
                duplicate_content_percentage=duplicate_content_percentage,
                stale_content_percentage=stale_content_percentage,
                redundant_files_count=len(redundant_file_groups),
                obsolete_todos_count=len(obsolete_todo_indices),
                duplicate_items=duplicate_items,
                obsolete_items=obsolete_items,
                redundant_file_groups=redundant_file_groups,
                stale_error_messages=stale_error_messages,
                total_items_analyzed=total_items,
                total_estimated_tokens=total_tokens,
                redundancy_analysis_duration=analysis_duration,
                safe_to_remove=safe_to_remove,
                consolidation_candidates=consolidation_candidates
            )
            
            logger.info(f"Redundancy analysis completed: {duplicate_content_percentage:.1f}% duplicate content found")
            return report
            
        except Exception as e:
            logger.error(f"Redundancy analysis failed: {e}")
            # Return empty report on failure
            return RedundancyReport(
                duplicate_content_percentage=0.0,
                stale_content_percentage=0.0,
                redundant_files_count=0,
                obsolete_todos_count=0,
                duplicate_items=[],
                obsolete_items=[],
                redundant_file_groups=[],
                stale_error_messages=[],
                total_items_analyzed=0,
                total_estimated_tokens=0,
                redundancy_analysis_duration=0.0,
                safe_to_remove=[],
                consolidation_candidates=[]
            )


if __name__ == "__main__":
    # Test redundancy detection
    test_data = {
        'messages': [
            'Help me debug this function',
            'I can help you debug that function',
            'Help me debug this function',  # Exact duplicate
            'Help me debug this method',   # Similar content
            'The function is working now - fixed it!'  # Resolution
        ],
        'todos': [
            'Fix authentication bug',
            'Write unit tests', 
            'Update documentation',
            'Deploy to staging - COMPLETED ✅',  # Obsolete
            'Fix login issue - already done',    # Obsolete
        ],
        'files': [
            '/project/src/main.py',
            '/project/src/utils.py',
            '/project/src/main.py',  # Duplicate
            '/project/tests/test_main.py'
        ],
        'errors': [
            'TypeError: invalid argument',
            'This error was fixed in the last commit',  # Stale
            'Connection timeout error'
        ]
    }
    
    import asyncio
    
    async def test_redundancy_detector():
        detector = RedundancyDetector()
        report = await detector.analyze_redundancy(test_data)
        
        print("=== Redundancy Analysis Results ===")
        print(f"Duplicate Content: {report.duplicate_content_percentage:.1f}%")
        print(f"Stale Content: {report.stale_content_percentage:.1f}%") 
        print(f"Redundant Files: {report.redundant_files_count}")
        print(f"Obsolete Todos: {report.obsolete_todos_count}")
        print(f"Analysis Duration: {report.redundancy_analysis_duration:.3f}s")
        print(f"Items Safe to Remove: {len(report.safe_to_remove)}")
        print(f"Consolidation Candidates: {len(report.consolidation_candidates)}")
    
    asyncio.run(test_redundancy_detector())