"""
Enhanced Token Counter using Anthropic's Count-Tokens API

This service addresses the 90% undercount issue in the current token analysis by:
1. Processing all JSONL files, not just 10 recent ones
2. Analyzing all conversation lines, not just first 1000
3. Using Anthropic's count-tokens API to validate and supplement usage statistics  
4. Implementing session-based token tracking for better context analytics
"""

import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
# Optional imports for enhanced functionality
try:
    import aiofiles
except ImportError:
    aiofiles = None

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)


@dataclass
class SessionTokenMetrics:
    """Token metrics for a specific session."""
    session_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # From existing usage statistics
    reported_input_tokens: int = 0
    reported_output_tokens: int = 0
    reported_cache_creation_tokens: int = 0
    reported_cache_read_tokens: int = 0
    
    # From count-tokens API validation
    calculated_input_tokens: int = 0
    calculated_total_tokens: int = 0
    
    # Conversation content for analysis
    user_messages: List[str] = field(default_factory=list)
    assistant_messages: List[str] = field(default_factory=list)
    system_prompts: List[str] = field(default_factory=list)
    tool_calls: List[Dict] = field(default_factory=list)
    
    # Categorization
    content_categories: Dict[str, int] = field(default_factory=lambda: {
        "claude_md": 0, "custom_agents": 0, "mcp_tools": 0,
        "system_prompts": 0, "system_tools": 0, "user_messages": 0
    })
    
    @property
    def total_reported_tokens(self) -> int:
        """Total tokens from existing usage statistics."""
        return (self.reported_input_tokens + self.reported_output_tokens + 
                self.reported_cache_creation_tokens + self.reported_cache_read_tokens)
    
    @property  
    def accuracy_ratio(self) -> float:
        """Ratio of calculated to reported tokens (detects undercounting)."""
        if self.total_reported_tokens == 0:
            return 0.0
        return self.calculated_total_tokens / self.total_reported_tokens
    
    @property
    def undercount_percentage(self) -> float:
        """Percentage of tokens that were undercounted."""
        if self.calculated_total_tokens == 0:
            return 0.0
        missed_tokens = max(0, self.calculated_total_tokens - self.total_reported_tokens)
        return (missed_tokens / self.calculated_total_tokens) * 100


@dataclass
class EnhancedTokenAnalysis:
    """Comprehensive token analysis results."""
    total_sessions_analyzed: int
    total_files_processed: int
    total_lines_processed: int
    
    # Aggregate metrics
    total_reported_tokens: int
    total_calculated_tokens: int
    global_accuracy_ratio: float
    global_undercount_percentage: float
    
    # Session-based metrics
    sessions: Dict[str, SessionTokenMetrics] = field(default_factory=dict)
    
    # Category breakdowns (enhanced)
    category_reported: Dict[str, int] = field(default_factory=dict)
    category_calculated: Dict[str, int] = field(default_factory=dict)
    
    # Processing statistics
    api_calls_made: int = 0
    processing_time_seconds: float = 0.0
    errors_encountered: List[str] = field(default_factory=list)
    
    @property
    def improvement_summary(self) -> Dict[str, Any]:
        """Summary of improvements over current implementation."""
        return {
            "previous_limitations": {
                "files_processed": "10 most recent",
                "lines_per_file": "first 1000 only", 
                "content_types": "assistant messages only"
            },
            "enhanced_coverage": {
                "files_processed": self.total_files_processed,
                "lines_processed": self.total_lines_processed,
                "sessions_tracked": len(self.sessions),
                "api_validations": self.api_calls_made
            },
            "accuracy_improvement": {
                "undercount_detected": f"{self.global_undercount_percentage:.1f}%",
                "missed_tokens": self.total_calculated_tokens - self.total_reported_tokens,
                "accuracy_ratio": f"{self.global_accuracy_ratio:.2f}x"
            }
        }


class AnthropicTokenCounter:
    """Interface to Anthropic's count-tokens API."""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages/count_tokens"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def count_tokens_for_messages(self, messages: List[Dict], system: str = None) -> int:
        """Count tokens for a list of messages using Anthropic's API."""
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01", 
                "content-type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages
            }
            
            if system:
                payload["system"] = system
                
            async with self.session.post(self.base_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("input_tokens", 0)
                else:
                    error_text = await response.text()
                    logger.warning(f"Count-tokens API error {response.status}: {error_text}")
                    return 0
                    
        except Exception as e:
            logger.error(f"Error calling count-tokens API: {e}")
            return 0


class EnhancedTokenCounterService:
    """Enhanced token counting service addressing the 90% undercount issue."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.anthropic_api_key = anthropic_api_key
        self.cache_dir = Path.home() / ".claude" / "projects"
        
        # Content categorization patterns
        self.categorization_patterns = {
            "claude_md": ["claude.md", "claude code", "claudemd"],
            "custom_agents": ["agent:", "custom agent", "specialized agent"],
            "mcp_tools": ["mcp__", "mcp_", "model context protocol"],
            "system_prompts": ["system-reminder", "instructions", "guidelines", "you are", "assistant:"],
            "system_tools": ["bash", "read", "write", "edit", "grep", "glob", "task", "tool"],
        }
        
    async def analyze_comprehensive_token_usage(
        self, 
        max_files: Optional[int] = None,
        max_lines_per_file: Optional[int] = None,
        use_count_tokens_api: bool = True
    ) -> EnhancedTokenAnalysis:
        """
        Perform comprehensive token analysis addressing current limitations.
        
        Args:
            max_files: Max files to process (None = all files, current = 10)
            max_lines_per_file: Max lines per file (None = all lines, current = 1000)  
            use_count_tokens_api: Whether to use Anthropic's count-tokens API
        """
        start_time = datetime.now()
        
        if not self.cache_dir.exists():
            logger.error("Claude Code cache directory not found")
            return self._create_empty_analysis()
            
        # Find all JSONL files (removing current 10-file limitation)
        jsonl_files = list(self.cache_dir.glob("**/*.jsonl"))
        if max_files:
            jsonl_files = sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[:max_files]
            
        logger.info(f"Processing {len(jsonl_files)} JSONL files (vs current limit of 10)")
        
        sessions: Dict[str, SessionTokenMetrics] = {}
        total_lines_processed = 0
        api_calls_made = 0
        errors = []
        
        # Process all files comprehensively
        token_counter = None
        if use_count_tokens_api and self.anthropic_api_key:
            token_counter = AnthropicTokenCounter(self.anthropic_api_key)
            
        try:
            if token_counter:
                async with token_counter:
                    for file_path in jsonl_files:
                        try:
                            session_data = await self._process_jsonl_file(
                                file_path, token_counter, max_lines_per_file
                            )
                            if session_data:
                                sessions.update(session_data)
                                total_lines_processed += sum(len(s.user_messages) + len(s.assistant_messages) 
                                                           for s in session_data.values())
                        except Exception as e:
                            errors.append(f"Error processing {file_path}: {str(e)}")
                            logger.error(f"Error processing {file_path}: {e}")
            else:
                # Fallback to enhanced analysis without API
                for file_path in jsonl_files:
                    try:
                        session_data = await self._process_jsonl_file_fallback(file_path, max_lines_per_file)
                        if session_data:
                            sessions.update(session_data)
                    except Exception as e:
                        errors.append(f"Error processing {file_path}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            errors.append(f"Analysis error: {str(e)}")
            
        # Calculate aggregate metrics
        total_reported = sum(s.total_reported_tokens for s in sessions.values())
        total_calculated = sum(s.calculated_total_tokens for s in sessions.values())
        
        global_accuracy_ratio = total_calculated / total_reported if total_reported > 0 else 0.0
        global_undercount = ((total_calculated - total_reported) / total_calculated * 100) if total_calculated > 0 else 0.0
        
        # Generate category breakdowns
        category_reported = defaultdict(int)
        category_calculated = defaultdict(int)
        
        for session in sessions.values():
            for category, tokens in session.content_categories.items():
                category_reported[category] += tokens
                
        processing_time = (datetime.now() - start_time).total_seconds()
        
        analysis = EnhancedTokenAnalysis(
            total_sessions_analyzed=len(sessions),
            total_files_processed=len(jsonl_files),
            total_lines_processed=total_lines_processed,
            total_reported_tokens=total_reported,
            total_calculated_tokens=total_calculated,
            global_accuracy_ratio=global_accuracy_ratio,
            global_undercount_percentage=max(0, global_undercount),
            sessions=sessions,
            category_reported=dict(category_reported),
            category_calculated=dict(category_calculated),
            api_calls_made=api_calls_made,
            processing_time_seconds=processing_time,
            errors_encountered=errors
        )
        
        logger.info(f"Enhanced token analysis complete:")
        logger.info(f"  Files processed: {len(jsonl_files)} (vs previous 10)")
        logger.info(f"  Lines processed: {total_lines_processed} (vs previous ~10,000)")
        logger.info(f"  Sessions analyzed: {len(sessions)}")
        logger.info(f"  Undercount detected: {global_undercount:.1f}%")
        logger.info(f"  Processing time: {processing_time:.2f}s")
        
        return analysis
        
    async def _process_jsonl_file(
        self, 
        file_path: Path, 
        token_counter: AnthropicTokenCounter,
        max_lines: Optional[int] = None
    ) -> Dict[str, SessionTokenMetrics]:
        """Process a single JSONL file with count-tokens API validation."""
        sessions = {}
        line_count = 0
        
        try:
            if aiofiles:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                    async for line in file:
                        if max_lines and line_count >= max_lines:
                            break
                            
                        line_count += 1
                        
                        try:
                            entry = json.loads(line.strip())
                            session_id = self._extract_session_id(entry)
                            
                            if session_id not in sessions:
                                sessions[session_id] = SessionTokenMetrics(session_id=session_id)
                                
                            await self._process_entry(entry, sessions[session_id], token_counter)
                            
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing line in {file_path}: {e}")
                            continue
            else:
                # Fallback to synchronous file reading
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        if max_lines and line_count >= max_lines:
                            break
                            
                        line_count += 1
                        
                        try:
                            entry = json.loads(line.strip())
                            session_id = self._extract_session_id(entry)
                            
                            if session_id not in sessions:
                                sessions[session_id] = SessionTokenMetrics(session_id=session_id)
                                
                            await self._process_entry(entry, sessions[session_id], token_counter)
                            
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing line in {file_path}: {e}")
                            continue
                        
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            
        return sessions
    
    async def _process_jsonl_file_fallback(
        self,
        file_path: Path, 
        max_lines: Optional[int] = None
    ) -> Dict[str, SessionTokenMetrics]:
        """Process JSONL file without API validation (enhanced version of current method)."""
        sessions = {}
        line_count = 0
        
        try:
            if aiofiles:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                    async for line in file:
                        if max_lines and line_count >= max_lines:
                            break
                            
                        line_count += 1
                        
                        try:
                            entry = json.loads(line.strip())
                            session_id = self._extract_session_id(entry)
                            
                            if session_id not in sessions:
                                sessions[session_id] = SessionTokenMetrics(session_id=session_id)
                                
                            await self._process_entry_fallback(entry, sessions[session_id])
                            
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing line in {file_path}: {e}")
                            continue
            else:
                # Fallback to synchronous file reading
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        if max_lines and line_count >= max_lines:
                            break
                            
                        line_count += 1
                        
                        try:
                            entry = json.loads(line.strip())
                            session_id = self._extract_session_id(entry)
                            
                            if session_id not in sessions:
                                sessions[session_id] = SessionTokenMetrics(session_id=session_id)
                                
                            await self._process_entry_fallback(entry, sessions[session_id])
                            
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing line in {file_path}: {e}")
                            continue
                        
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            
        return sessions
    
    async def _process_entry(
        self, 
        entry: Dict, 
        session_metrics: SessionTokenMetrics,
        token_counter: AnthropicTokenCounter
    ):
        """Process a single JSONL entry with API validation."""
        # Extract existing usage statistics (current method)
        if entry.get("type") == "assistant":
            usage = entry.get("message", {}).get("usage", {})
            session_metrics.reported_input_tokens += usage.get("input_tokens", 0)
            session_metrics.reported_output_tokens += usage.get("output_tokens", 0)
            session_metrics.reported_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
            session_metrics.reported_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        
        # Extract content for API validation (new enhancement)
        content = ""
        if entry.get("type") == "user":
            content = str(entry.get("message", {}).get("content", ""))
            session_metrics.user_messages.append(content)
        elif entry.get("type") == "assistant":
            content = str(entry.get("message", {}).get("content", ""))
            session_metrics.assistant_messages.append(content)
        
        # Categorize content (enhanced)
        if content:
            category = self._categorize_content(content)
            session_metrics.content_categories[category] += len(content.split())
            
        # Use count-tokens API to validate (if we have sufficient messages)
        if len(session_metrics.user_messages) + len(session_metrics.assistant_messages) >= 5:
            messages = []
            
            # Build message array for API
            for user_msg in session_metrics.user_messages[-3:]:  # Recent context
                messages.append({"role": "user", "content": user_msg})
            for asst_msg in session_metrics.assistant_messages[-3:]:
                messages.append({"role": "assistant", "content": asst_msg})
                
            if messages:
                api_tokens = await token_counter.count_tokens_for_messages(messages)
                session_metrics.calculated_total_tokens = max(
                    session_metrics.calculated_total_tokens, api_tokens
                )
    
    async def _process_entry_fallback(self, entry: Dict, session_metrics: SessionTokenMetrics):
        """Process entry without API validation (enhanced version of current method)."""
        # Extract ALL usage statistics (not just assistant type)
        usage = entry.get("message", {}).get("usage", {})
        if usage:
            session_metrics.reported_input_tokens += usage.get("input_tokens", 0)
            session_metrics.reported_output_tokens += usage.get("output_tokens", 0) 
            session_metrics.reported_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
            session_metrics.reported_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        
        # Extract content for analysis
        content = ""
        if entry.get("type") == "user":
            content = str(entry.get("message", {}).get("content", ""))
            session_metrics.user_messages.append(content)
        elif entry.get("type") == "assistant":
            content = str(entry.get("message", {}).get("content", ""))
            session_metrics.assistant_messages.append(content)
            
        # Categorize content
        if content:
            category = self._categorize_content(content)
            session_metrics.content_categories[category] += len(content.split())
            
        # Use actual token metrics when available (ccusage approach - no estimation fallbacks)
        if usage:
            # Only use actual reported tokens - no estimation fallbacks that cause inaccuracy
            actual_tokens = (
                usage.get("input_tokens", 0) +
                usage.get("output_tokens", 0) + 
                usage.get("cache_creation_input_tokens", 0) +
                usage.get("cache_read_input_tokens", 0)
            )
            if actual_tokens > 0:
                session_metrics.calculated_total_tokens += actual_tokens
        # Skip content without actual token metrics to maintain ccusage-level accuracy
    
    def _extract_session_id(self, entry: Dict) -> str:
        """Extract session ID from JSONL entry."""
        # Try multiple common patterns
        candidates = [
            entry.get("session_id"),
            entry.get("sessionId"),
            entry.get("id"),
            entry.get("conversation_id"),
        ]
        
        for candidate in candidates:
            if candidate and isinstance(candidate, str):
                return candidate
                
        # Fallback to file-based session grouping
        return "unknown_session"
    
    def _categorize_content(self, content: str) -> str:
        """Categorize content using enhanced pattern matching."""
        content_lower = content.lower()
        
        for category, patterns in self.categorization_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                return category
                
        return "user_messages"  # Default category
    
    def _create_empty_analysis(self) -> EnhancedTokenAnalysis:
        """Create empty analysis when no data is available."""
        return EnhancedTokenAnalysis(
            total_sessions_analyzed=0,
            total_files_processed=0,
            total_lines_processed=0,
            total_reported_tokens=0,
            total_calculated_tokens=0,
            global_accuracy_ratio=0.0,
            global_undercount_percentage=0.0,
            errors_encountered=["Claude Code cache directory not found"]
        )


class SessionTokenTracker:
    """Session-based token tracking for real-time analytics."""
    
    def __init__(self):
        self.session_counters: Dict[str, SessionTokenMetrics] = {}
        self.lock = asyncio.Lock()
    
    async def update_session_tokens(
        self, 
        session_id: str, 
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0
    ):
        """Update token counts for a specific session."""
        async with self.lock:
            if session_id not in self.session_counters:
                self.session_counters[session_id] = SessionTokenMetrics(session_id=session_id)
                
            metrics = self.session_counters[session_id]
            metrics.reported_input_tokens += input_tokens
            metrics.reported_output_tokens += output_tokens  
            metrics.reported_cache_creation_tokens += cache_creation_tokens
            metrics.reported_cache_read_tokens += cache_read_tokens
            
            if not metrics.start_time:
                metrics.start_time = datetime.now()
            metrics.end_time = datetime.now()
    
    async def get_session_metrics(self, session_id: str) -> Optional[SessionTokenMetrics]:
        """Get current metrics for a specific session."""
        async with self.lock:
            return self.session_counters.get(session_id)
    
    async def get_all_session_metrics(self) -> Dict[str, SessionTokenMetrics]:
        """Get metrics for all tracked sessions.""" 
        async with self.lock:
            return self.session_counters.copy()
    
    async def cleanup_old_sessions(self, hours: int = 24):
        """Remove session data older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        async with self.lock:
            to_remove = []
            for session_id, metrics in self.session_counters.items():
                if metrics.end_time and metrics.end_time < cutoff_time:
                    to_remove.append(session_id)
                    
            for session_id in to_remove:
                del self.session_counters[session_id]
                
            logger.info(f"Cleaned up {len(to_remove)} old session counters")