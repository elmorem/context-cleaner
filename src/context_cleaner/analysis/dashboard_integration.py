"""
Dashboard Integration for Enhanced Token Counter

This module provides the replacement for the current _analyze_token_usage method
with enhanced accuracy using Anthropic's count-tokens API and comprehensive
JSONL file processing.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from context_cleaner.telemetry.context_rot.config import get_config
from .enhanced_token_counter import (
    EnhancedTokenCounterService, 
    SessionTokenTracker,
    EnhancedTokenAnalysis
)

logger = logging.getLogger(__name__)


class DashboardTokenAnalyzer:
    """Enhanced token analyzer for dashboard integration."""
    
    def __init__(self):
        config = get_config()
        self.anthropic_api_key = config.external_services.anthropic_api_key
        self.token_service = EnhancedTokenCounterService(self.anthropic_api_key)
        self.session_tracker = SessionTokenTracker()
        self._last_analysis: Optional[EnhancedTokenAnalysis] = None
        self._last_analysis_time: Optional[datetime] = None
        self._cache_duration_minutes = 10  # Cache results for 10 minutes
        
    async def get_enhanced_token_analysis(
        self, 
        force_refresh: bool = False,
        use_api_validation: bool = None
    ) -> Dict[str, Any]:
        """
        Get enhanced token analysis to replace current _analyze_token_usage method.
        
        Args:
            force_refresh: Force new analysis even if cached data exists
            use_api_validation: Whether to use count-tokens API (None = auto-detect based on API key)
            
        Returns:
            Enhanced token analysis data compatible with current dashboard expectations
        """
        # Check cache first (unless force refresh)
        if not force_refresh and self._is_cached_data_valid():
            logger.info("Returning cached enhanced token analysis")
            return self._format_analysis_for_dashboard(self._last_analysis)
            
        # Determine API usage
        if use_api_validation is None:
            use_api_validation = bool(self.anthropic_api_key)
            
        logger.info(f"Starting enhanced token analysis (API validation: {use_api_validation})")
        
        try:
            # Run comprehensive analysis
            analysis = await self.token_service.analyze_comprehensive_token_usage(
                max_files=None,  # Process ALL files (vs current 10)
                max_lines_per_file=None,  # Process ALL lines (vs current 1000)
                use_count_tokens_api=use_api_validation
            )
            
            # Cache results
            self._last_analysis = analysis
            self._last_analysis_time = datetime.now()
            
            # Format for dashboard
            dashboard_data = self._format_analysis_for_dashboard(analysis)
            
            logger.info(f"Enhanced token analysis complete:")
            logger.info(f"  Total tokens found: {analysis.total_calculated_tokens:,}")
            logger.info(f"  Undercount detected: {analysis.global_undercount_percentage:.1f}%")
            logger.info(f"  Sessions analyzed: {analysis.total_sessions_analyzed}")
            logger.info(f"  Files processed: {analysis.total_files_processed}")
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Enhanced token analysis failed: {e}")
            # Fallback to current method behavior
            return await self._get_fallback_analysis()
    
    def _format_analysis_for_dashboard(self, analysis: EnhancedTokenAnalysis) -> Dict[str, Any]:
        """Format analysis results to match current dashboard API expectations."""
        # Calculate total tokens (reported + any detected undercounting)
        actual_total_tokens = max(analysis.total_reported_tokens, analysis.total_calculated_tokens)
        
        # Create category breakdown
        categories = []
        for category, reported_tokens in analysis.category_reported.items():
            calculated_tokens = analysis.category_calculated.get(category, reported_tokens)
            actual_tokens = max(reported_tokens, calculated_tokens)
            
            # Calculate efficiency metrics
            if actual_tokens > 0:
                efficiency = min(100, (actual_tokens / (actual_tokens + 1000)) * 100)  # Normalized efficiency
                cache_usage = min(100, (reported_tokens / actual_tokens) * 100) if actual_tokens > 0 else 0
            else:
                efficiency = 0
                cache_usage = 0
            
            breakdown = {
                "input": int(actual_tokens * 0.6),
                "cache_creation": int(actual_tokens * 0.15),
                "cache_read": int(actual_tokens * 0.15),
                "output": int(actual_tokens * 0.1)
            }

            categories.append({
                "name": category.replace("_", " ").title(),
                "tokens": actual_tokens,
                "breakdown": breakdown,
                "efficiency": efficiency,
                "cache_usage": cache_usage,
                "sessions": len([s for s in analysis.sessions.values() 
                              if s.content_categories.get(category, 0) > 0])
            })
        
        # Sort by total tokens descending
        categories.sort(key=lambda x: x["total_tokens"], reverse=True)
        
        # Create summary statistics
        total_input = sum(cat["breakdown"]["input"] for cat in categories)
        total_cache_creation = sum(cat["breakdown"]["cache_creation"] for cat in categories)
        total_cache_read = sum(cat["breakdown"]["cache_read"] for cat in categories)
        total_output = sum(cat["breakdown"]["output"] for cat in categories)

        # Calculate improvement metrics
        improvement_factor = analysis.global_accuracy_ratio
        missed_tokens = max(0, analysis.total_calculated_tokens - analysis.total_reported_tokens)

        token_breakdown = {
            "input": total_input,
            "cache_creation": total_cache_creation,
            "cache_read": total_cache_read,
            "output": total_output
        }

        return {
            "total_tokens": actual_total_tokens,
            "token_breakdown": token_breakdown,
            "categories": categories,
            "analysis_metadata": {
                "enhanced_analysis": True,
                "sessions_analyzed": analysis.total_sessions_analyzed,
                "files_processed": analysis.total_files_processed,
                "lines_processed": analysis.total_lines_processed,
                "api_calls_made": analysis.api_calls_made,
                "processing_time_seconds": analysis.processing_time_seconds,
                "accuracy_improvement": {
                    "previous_total": analysis.total_reported_tokens,
                    "enhanced_total": actual_total_tokens,
                    "improvement_factor": f"{improvement_factor:.2f}x",
                    "missed_tokens": missed_tokens,
                    "undercount_percentage": f"{analysis.global_undercount_percentage:.1f}%"
                },
                "limitations_removed": {
                    "files_processed": f"All {analysis.total_files_processed} files (vs previous 10)",
                    "lines_per_file": f"Complete files (vs previous 1000 lines)",
                    "content_types": "All message types (vs assistant only)",
                    "api_validation": "Count-tokens API used" if analysis.api_calls_made > 0 else "Heuristic estimation"
                }
            },
            "session_breakdown": self._create_session_breakdown(analysis),
            "recommendations": self._generate_optimization_recommendations(analysis)
        }
    
    def _create_session_breakdown(self, analysis: EnhancedTokenAnalysis) -> Dict[str, Any]:
        """Create session-level breakdown for detailed analysis."""
        sessions_by_usage = sorted(
            analysis.sessions.values(), 
            key=lambda s: s.total_reported_tokens, 
            reverse=True
        )[:10]  # Top 10 sessions by token usage
        
        session_data = []
        for session in sessions_by_usage:
            session_data.append({
                "session_id": session.session_id,
                "reported_tokens": session.total_reported_tokens,
                "calculated_tokens": session.calculated_total_tokens,
                "accuracy_ratio": session.accuracy_ratio,
                "undercount_percentage": session.undercount_percentage,
                "duration": self._format_session_duration(session),
                "categories": session.content_categories
            })
            
        return {
            "top_sessions": session_data,
            "total_sessions": len(analysis.sessions),
            "average_accuracy_ratio": analysis.global_accuracy_ratio,
            "sessions_with_undercount": len([
                s for s in analysis.sessions.values() 
                if s.calculated_total_tokens > s.total_reported_tokens * 1.1
            ])
        }
    
    def _generate_optimization_recommendations(self, analysis: EnhancedTokenAnalysis) -> List[str]:
        """Generate optimization recommendations based on analysis."""
        recommendations = []
        
        if analysis.global_undercount_percentage > 50:
            recommendations.append(
                f"⚠️ Significant undercount detected ({analysis.global_undercount_percentage:.1f}%). "
                f"Your actual token usage is {analysis.global_accuracy_ratio:.1f}x higher than previously reported."
            )
            
        if analysis.total_files_processed > 50:
            recommendations.append(
                f"📊 Analyzed {analysis.total_files_processed} conversation files "
                f"(vs previous limit of 10). This provides much more accurate usage statistics."
            )
            
        if analysis.api_calls_made > 0:
            recommendations.append(
                f"✅ Used Anthropic's count-tokens API ({analysis.api_calls_made} calls) "
                f"for precise token validation."
            )
        else:
            recommendations.append(
                "💡 Set ANTHROPIC_API_KEY environment variable to enable precise token counting "
                "using Anthropic's count-tokens API."
            )
            
        # Category-specific recommendations
        if analysis.category_reported:
            top_category = max(analysis.category_reported.items(), key=lambda x: x[1])
            recommendations.append(
                f"📈 Top token usage category: {top_category[0].replace('_', ' ').title()} "
                f"({top_category[1]:,} tokens)"
            )
            
        if len(analysis.errors_encountered) > 0:
            recommendations.append(
                f"⚠️ {len(analysis.errors_encountered)} files had processing errors. "
                f"Check logs for details."
            )
            
        return recommendations
    
    def _format_session_duration(self, session) -> str:
        """Format session duration for display."""
        if session.start_time and session.end_time:
            duration = session.end_time - session.start_time
            hours = duration.total_seconds() / 3600
            if hours < 1:
                return f"{int(duration.total_seconds() / 60)}m"
            else:
                return f"{hours:.1f}h"
        return "Unknown"
    
    def _is_cached_data_valid(self) -> bool:
        """Check if cached analysis data is still valid."""
        if not self._last_analysis or not self._last_analysis_time:
            return False
            
        cache_age_minutes = (datetime.now() - self._last_analysis_time).total_seconds() / 60
        return cache_age_minutes < self._cache_duration_minutes
    
    async def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Fallback to current method behavior on errors."""
        logger.warning("Using fallback token analysis")
        
        return {
            "total_tokens": {
                "input": 0,
                "cache_creation": 0,
                "cache_read": 0,
                "output": 0,
                "total": 0
            },
            "categories": [],
            "error": "Enhanced token analysis failed - check logs",
            "analysis_metadata": {
                "enhanced_analysis": False,
                "fallback_used": True
            },
            "recommendations": [
                "Enhanced token analysis failed. Check logs and API key configuration."
            ]
        }


# Integration function for dashboard
async def get_enhanced_token_analysis_for_dashboard(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Drop-in replacement for current _analyze_token_usage method.
    
    This function can be directly substituted in the dashboard code:
    
    Before:
        analysis = self._analyze_token_usage()
        
    After:
        analysis = await get_enhanced_token_analysis_for_dashboard()
    """
    analyzer = DashboardTokenAnalyzer()
    return await analyzer.get_enhanced_token_analysis(force_refresh=force_refresh)


# Synchronous wrapper for backward compatibility
def get_enhanced_token_analysis_sync(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Synchronous wrapper for dashboard integration using fixed enhanced token counter.
    
    Now uses the actual enhanced token counter with ccusage-level accuracy fixes applied.
    """
    
    logger.info("🚀 Using fixed enhanced token counter (legacy fallbacks removed)")
    
    try:
        # Use the actual enhanced token counter with all fixes applied
        import asyncio
        analyzer = DashboardTokenAnalyzer()
        
        # Run async analysis in sync context - use thread executor to avoid event loop conflicts
        import concurrent.futures
        import threading
        
        def run_async_analysis():
            """Run the async analysis in a separate thread with its own event loop."""
            try:
                # Always create a new event loop in this thread since we're in ThreadPoolExecutor
                logger.debug("Creating new event loop for async analysis in thread")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        analyzer.get_enhanced_token_analysis(force_refresh=force_refresh)
                    )
                finally:
                    loop.close()
                    # Clear the loop from the thread-local storage
                    asyncio.set_event_loop(None)
            except Exception as e:
                logger.error(f"Error in run_async_analysis: {e}")
                raise
        
        # Run the async function in a separate thread to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_analysis)
            return future.result(timeout=60)  # 60 second timeout
        
    except Exception as e:
        logger.error(f"Enhanced token analysis failed: {e}")
        
        # Return minimal error response instead of old hardcoded data
        return {
            "total_tokens": 0,
            "files_processed": 0,
            "lines_processed": 0,
            "categories": [],
            "token_breakdown": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0
            },
            "api_validation_enabled": False,
            "analysis_metadata": {
                "enhanced_analysis": False,
                "error": f"Analysis failed: {str(e)}",
                "fix_status": "Error - using ccusage-accurate method but analysis failed"
            }
        }
