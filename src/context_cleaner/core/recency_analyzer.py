#!/usr/bin/env python3
"""
Recency Analysis Engine

Categorizes context content by recency and relevance to current work session:
- Fresh Context: Modified within last hour (highest priority)  
- Recent Context: Modified within current session (high priority)
- Aging Context: Older than current session but potentially relevant
- Stale Context: From previous unrelated work (low priority)

Uses temporal analysis, content patterns, and session correlation to determine recency.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from dateutil import parser
import pytz

logger = logging.getLogger(__name__)


@dataclass
class RecencyReport:
    """Comprehensive recency analysis report."""
    
    # Recency percentages (should sum to ~100%)
    fresh_context_percentage: float      # Content from last hour
    recent_context_percentage: float     # Content from current session  
    aging_context_percentage: float      # Content older than session
    stale_context_percentage: float      # Content from unrelated work
    
    # Detailed categorization
    fresh_items: List[Dict[str, Any]]     # Fresh content items with timestamps
    recent_items: List[Dict[str, Any]]    # Recent content items  
    aging_items: List[Dict[str, Any]]     # Aging content items
    stale_items: List[Dict[str, Any]]     # Stale content items
    
    # Session analysis
    estimated_session_start: Optional[str]  # Estimated current session start time
    session_duration_minutes: float         # Estimated session duration
    session_activity_score: float           # How active the session has been (0-1)
    
    # Analysis metadata
    total_items_categorized: int            # Total items analyzed for recency
    items_with_timestamps: int              # Items that had extractable timestamps
    analysis_timestamp: str                 # When this analysis was performed
    recency_analysis_duration: float       # Time taken for analysis
    
    def get_recency_summary(self) -> str:
        """Get human-readable recency summary."""
        return (f"Fresh: {self.fresh_context_percentage:.0f}% | "
               f"Recent: {self.recent_context_percentage:.0f}% | "
               f"Aging: {self.aging_context_percentage:.0f}% | "
               f"Stale: {self.stale_context_percentage:.0f}%")


class RecencyAnalyzer:
    """
    Advanced Recency Analysis Engine
    
    Analyzes temporal patterns in context to categorize content by recency
    and relevance to current work session.
    """
    
    # Time thresholds for recency categorization
    FRESH_THRESHOLD = timedelta(hours=1)      # Content from last hour
    RECENT_THRESHOLD = timedelta(hours=6)     # Content from current session
    AGING_THRESHOLD = timedelta(days=1)       # Content from last day
    # Anything older is considered stale
    
    # Patterns for extracting timestamps from various formats
    TIMESTAMP_PATTERNS = [
        # ISO format patterns
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',
        # Human readable patterns  
        r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?',
        r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
        # Relative time patterns
        r'(?i)(\d+)\s*(minute|hour|day|week)s?\s*ago',
        r'(?i)(just\s*now|moments?\s*ago|recently|earlier\s*today)',
    ]
    
    # Keywords that suggest current/active work
    CURRENT_WORK_KEYWORDS = [
        'current', 'active', 'working', 'debugging', 'implementing',
        'now', 'today', 'this', 'in progress', 'currently'
    ]
    
    # Keywords that suggest stale/old work  
    STALE_WORK_KEYWORDS = [
        'previous', 'old', 'legacy', 'deprecated', 'archived',
        'yesterday', 'last week', 'before', 'completed', 'finished'
    ]
    
    def __init__(self):
        """Initialize recency analysis engine."""
        self.timestamp_regex = [re.compile(pattern) for pattern in self.TIMESTAMP_PATTERNS]
        self.current_work_regex = re.compile('|'.join(self.CURRENT_WORK_KEYWORDS), re.IGNORECASE)
        self.stale_work_regex = re.compile('|'.join(self.STALE_WORK_KEYWORDS), re.IGNORECASE)
        logger.debug("RecencyAnalyzer initialized")
    
    def _extract_timestamp(self, content: Any) -> Optional[datetime]:
        """Extract timestamp from content using various strategies."""
        content_str = str(content)
        
        # Try direct timestamp extraction from common keys
        if isinstance(content, dict):
            timestamp_keys = ['timestamp', 'created_at', 'updated_at', 'modified_at', 
                            'time', 'date', 'last_modified', 'created', 'modified']
            
            for key in timestamp_keys:
                if key in content:
                    try:
                        return self._parse_timestamp(str(content[key]))
                    except Exception:
                        continue
        
        # Try pattern matching in content string
        for pattern in self.timestamp_regex:
            match = pattern.search(content_str)
            if match:
                try:
                    return self._parse_timestamp(match.group(0))
                except Exception:
                    continue
        
        return None
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string into datetime object."""
        try:
            # Handle relative time expressions
            relative_match = re.match(r'(?i)(\d+)\s*(minute|hour|day|week)s?\s*ago', timestamp_str)
            if relative_match:
                amount = int(relative_match.group(1))
                unit = relative_match.group(2).lower()
                
                if unit.startswith('minute'):
                    delta = timedelta(minutes=amount)
                elif unit.startswith('hour'):
                    delta = timedelta(hours=amount)
                elif unit.startswith('day'):
                    delta = timedelta(days=amount)
                elif unit.startswith('week'):
                    delta = timedelta(weeks=amount)
                else:
                    return None
                
                return datetime.now(pytz.UTC) - delta
            
            # Handle "just now" type expressions
            if re.match(r'(?i)(just\s*now|moments?\s*ago)', timestamp_str):
                return datetime.now(pytz.UTC) - timedelta(minutes=1)
            
            # Use dateutil parser for standard formats
            parsed_dt = parser.parse(timestamp_str)
            
            # Add timezone if not present (assume UTC)
            if parsed_dt.tzinfo is None:
                parsed_dt = pytz.UTC.localize(parsed_dt)
            
            return parsed_dt
            
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None
    
    def _estimate_session_start(self, timestamps: List[datetime]) -> Optional[datetime]:
        """Estimate when the current work session started based on timestamp patterns."""
        if not timestamps:
            return None
        
        # Sort timestamps
        sorted_timestamps = sorted(timestamps)
        
        # Look for the largest gap between consecutive timestamps
        # This likely indicates the session start
        max_gap = timedelta(0)
        session_start_candidate = sorted_timestamps[0]
        
        for i in range(1, len(sorted_timestamps)):
            gap = sorted_timestamps[i] - sorted_timestamps[i-1]
            if gap > max_gap and gap > timedelta(hours=1):  # Significant gap
                max_gap = gap
                session_start_candidate = sorted_timestamps[i]
        
        # If no significant gap found, use the earliest timestamp within last 6 hours
        now = datetime.now(pytz.UTC)
        cutoff = now - timedelta(hours=6)
        
        for timestamp in sorted_timestamps:
            if timestamp >= cutoff:
                return timestamp
        
        return session_start_candidate
    
    def _calculate_session_activity(self, timestamps: List[datetime], 
                                   session_start: datetime) -> float:
        """Calculate how active the session has been (0-1 score)."""
        if not timestamps or not session_start:
            return 0.0
        
        now = datetime.now(pytz.UTC)
        session_duration = (now - session_start).total_seconds()
        
        if session_duration <= 0:
            return 0.0
        
        # Count activity in time windows
        window_size = timedelta(minutes=15)
        num_windows = max(1, int(session_duration / window_size.total_seconds()))
        
        active_windows = set()
        for timestamp in timestamps:
            if timestamp >= session_start:
                window_index = int((timestamp - session_start).total_seconds() / window_size.total_seconds())
                active_windows.add(window_index)
        
        # Activity score is percentage of windows with activity
        return len(active_windows) / num_windows
    
    def _categorize_by_timestamp(self, timestamp: datetime, session_start: Optional[datetime]) -> str:
        """Categorize content by timestamp relative to current session."""
        now = datetime.now(pytz.UTC)
        
        # Fresh: within last hour
        if now - timestamp <= self.FRESH_THRESHOLD:
            return 'fresh'
        
        # Recent: within current session or last 6 hours if no session detected
        recent_threshold = self.RECENT_THRESHOLD
        if session_start and timestamp >= session_start:
            return 'recent'
        elif now - timestamp <= recent_threshold:
            return 'recent'
        
        # Aging: within last day but older than session
        if now - timestamp <= self.AGING_THRESHOLD:
            return 'aging'
        
        # Stale: older than a day
        return 'stale'
    
    def _categorize_by_content(self, content: Any) -> Optional[str]:
        """Categorize content based on textual clues about recency."""
        content_str = str(content).lower()
        
        # Check for current work indicators
        if self.current_work_regex.search(content_str):
            return 'recent'  # Bias toward recent for current work
        
        # Check for stale work indicators
        if self.stale_work_regex.search(content_str):
            return 'stale'   # Bias toward stale for old work
        
        return None  # No clear indication from content
    
    def _extract_content_items(self, context_data: Dict[str, Any]) -> List[Tuple[str, Any]]:
        """Extract individual content items from context data for analysis."""
        items = []
        
        def extract_recursive(data: Any, path: str = ""):
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, (dict, list)):
                        extract_recursive(value, current_path)
                    else:
                        items.append((current_path, value))
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    current_path = f"{path}[{i}]"
                    if isinstance(item, (dict, list)):
                        extract_recursive(item, current_path)
                    else:
                        items.append((current_path, item))
        
        extract_recursive(context_data)
        return items
    
    async def analyze_recency(self, context_data: Dict[str, Any]) -> RecencyReport:
        """
        Perform comprehensive recency analysis on context data.
        
        Args:
            context_data: Context data to analyze for recency patterns
            
        Returns:
            RecencyReport with detailed recency categorization and insights
        """
        analysis_start = datetime.now()
        
        try:
            # Extract individual content items
            content_items = self._extract_content_items(context_data)
            
            # Extract timestamps from all content
            timestamps = []
            timestamped_items = []
            
            for path, item in content_items:
                timestamp = self._extract_timestamp(item)
                if timestamp:
                    timestamps.append(timestamp)
                    timestamped_items.append((path, item, timestamp))
            
            # Estimate session start time
            session_start = self._estimate_session_start(timestamps)
            session_duration = 0.0
            session_activity = 0.0
            
            if session_start:
                now = datetime.now(pytz.UTC)
                session_duration = (now - session_start).total_seconds() / 60  # Minutes
                session_activity = self._calculate_session_activity(timestamps, session_start)
            
            # Categorize items by recency
            fresh_items = []
            recent_items = []
            aging_items = []
            stale_items = []
            
            # Process items with timestamps
            for path, item, timestamp in timestamped_items:
                category = self._categorize_by_timestamp(timestamp, session_start)
                
                item_data = {
                    'path': path,
                    'content_preview': str(item)[:100] + ("..." if len(str(item)) > 100 else ""),
                    'timestamp': timestamp.isoformat(),
                    'categorization_method': 'timestamp'
                }
                
                if category == 'fresh':
                    fresh_items.append(item_data)
                elif category == 'recent':
                    recent_items.append(item_data)
                elif category == 'aging':
                    aging_items.append(item_data)
                else:  # stale
                    stale_items.append(item_data)
            
            # Process items without timestamps using content analysis
            for path, item in content_items:
                if not any(path == ti[0] for ti in timestamped_items):  # Not already categorized
                    content_category = self._categorize_by_content(item)
                    
                    item_data = {
                        'path': path,
                        'content_preview': str(item)[:100] + ("..." if len(str(item)) > 100 else ""),
                        'timestamp': None,
                        'categorization_method': 'content_analysis'
                    }
                    
                    if content_category == 'recent':
                        recent_items.append(item_data)
                    elif content_category == 'stale':
                        stale_items.append(item_data)
                    else:
                        # Default to aging for items without clear indicators
                        aging_items.append(item_data)
            
            # Calculate percentages
            total_items = len(content_items)
            if total_items > 0:
                fresh_percentage = (len(fresh_items) / total_items) * 100
                recent_percentage = (len(recent_items) / total_items) * 100
                aging_percentage = (len(aging_items) / total_items) * 100
                stale_percentage = (len(stale_items) / total_items) * 100
            else:
                fresh_percentage = recent_percentage = aging_percentage = stale_percentage = 0
            
            analysis_duration = (datetime.now() - analysis_start).total_seconds()
            
            report = RecencyReport(
                fresh_context_percentage=fresh_percentage,
                recent_context_percentage=recent_percentage,
                aging_context_percentage=aging_percentage,
                stale_context_percentage=stale_percentage,
                fresh_items=fresh_items,
                recent_items=recent_items,
                aging_items=aging_items,
                stale_items=stale_items,
                estimated_session_start=session_start.isoformat() if session_start else None,
                session_duration_minutes=session_duration,
                session_activity_score=session_activity,
                total_items_categorized=total_items,
                items_with_timestamps=len(timestamped_items),
                analysis_timestamp=analysis_start.isoformat(),
                recency_analysis_duration=analysis_duration
            )
            
            logger.info(f"Recency analysis completed: {fresh_percentage:.0f}% fresh, "
                       f"{recent_percentage:.0f}% recent, {stale_percentage:.0f}% stale")
            
            return report
            
        except Exception as e:
            logger.error(f"Recency analysis failed: {e}")
            # Return empty report on failure
            return RecencyReport(
                fresh_context_percentage=0.0,
                recent_context_percentage=0.0,
                aging_context_percentage=0.0,
                stale_context_percentage=0.0,
                fresh_items=[],
                recent_items=[],
                aging_items=[],
                stale_items=[],
                estimated_session_start=None,
                session_duration_minutes=0.0,
                session_activity_score=0.0,
                total_items_categorized=0,
                items_with_timestamps=0,
                analysis_timestamp=datetime.now().isoformat(),
                recency_analysis_duration=0.0
            )


if __name__ == "__main__":
    # Test recency analysis
    now = datetime.now(pytz.UTC)
    
    test_data = {
        'current_task': {
            'description': 'Currently debugging authentication bug',
            'timestamp': now.isoformat(),  # Fresh
            'status': 'in_progress'
        },
        'recent_messages': [
            {
                'content': 'Working on the login function now',
                'timestamp': (now - timedelta(minutes=30)).isoformat()  # Fresh
            },
            {
                'content': 'This is from earlier today',
                'timestamp': (now - timedelta(hours=3)).isoformat()  # Recent
            }
        ],
        'old_todos': [
            {
                'task': 'Previous project setup - completed last week',
                'timestamp': (now - timedelta(days=7)).isoformat()  # Stale
            },
            {
                'task': 'Yesterday\'s debugging session',
                'timestamp': (now - timedelta(days=1, hours=2)).isoformat()  # Stale
            }
        ],
        'files_accessed': [
            {
                'path': '/project/auth.py',
                'last_modified': (now - timedelta(hours=2)).isoformat()  # Recent
            },
            {
                'path': '/project/legacy_code.py', 
                'last_modified': (now - timedelta(days=5)).isoformat()  # Stale
            }
        ],
        'session_notes': 'Currently working on implementing OAuth2 integration'  # Current work
    }
    
    import asyncio
    
    async def test_recency_analyzer():
        analyzer = RecencyAnalyzer()
        report = await analyzer.analyze_recency(test_data)
        
        print("=== Recency Analysis Results ===")
        print(f"Fresh Context: {report.fresh_context_percentage:.1f}%")
        print(f"Recent Context: {report.recent_context_percentage:.1f}%")
        print(f"Aging Context: {report.aging_context_percentage:.1f}%")
        print(f"Stale Context: {report.stale_context_percentage:.1f}%")
        print(f"Session Duration: {report.session_duration_minutes:.1f} minutes")
        print(f"Session Activity: {report.session_activity_score:.2f}")
        print(f"Items with Timestamps: {report.items_with_timestamps}")
        print(f"Analysis Duration: {report.recency_analysis_duration:.3f}s")
        
        print(f"\nFresh Items ({len(report.fresh_items)}):")
        for item in report.fresh_items[:3]:  # Show first 3
            print(f"  - {item['path']}: {item['content_preview']}")
        
        print(f"\nStale Items ({len(report.stale_items)}):")
        for item in report.stale_items[:3]:  # Show first 3
            print(f"  - {item['path']}: {item['content_preview']}")
    
    asyncio.run(test_recency_analyzer())