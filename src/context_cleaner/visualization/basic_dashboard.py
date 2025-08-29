#!/usr/bin/env python3
"""
Basic Dashboard - Performance-first visualization implementation
Provides safe context visualization with comprehensive error handling and performance limits.
"""

import asyncio
import json
import time
import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class DashboardSummary:
    """Structured dashboard summary result."""
    health_score: int
    health_status: str
    size_category: str
    estimated_tokens: int
    session_count: int
    avg_session_duration: float
    trend_direction: str
    last_update: str
    recommendations: List[str]
    render_duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'health_score': self.health_score,
            'health_status': self.health_status,
            'size_category': self.size_category,
            'estimated_tokens': self.estimated_tokens,
            'session_count': self.session_count,
            'avg_session_duration': self.avg_session_duration,
            'trend_direction': self.trend_direction,
            'last_update': self.last_update,
            'recommendations': self.recommendations,
            'render_duration': self.render_duration
        }


class SimpleCache:
    """Simple in-memory cache for dashboard results."""
    
    def __init__(self, ttl: int = 300):  # 5 minutes
        self.ttl = ttl
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        if time.time() - self._timestamps[key] > self.ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        """Set cached value."""
        self._cache[key] = value
        self._timestamps[key] = time.time()


class SessionDataLoader:
    """Safe loader for session data from storage."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.max_files_to_read = 100  # Limit for performance
    
    def load_recent_sessions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Load recent session data safely."""
        try:
            if not self.data_dir.exists():
                logger.warning(f"Data directory does not exist: {self.data_dir}")
                return []
            
            # Get session files
            session_files = list(self.data_dir.glob("session_*.json"))
            if not session_files:
                logger.info("No session files found")
                return []
            
            # Sort by modification time (newest first)
            session_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Limit files to read for performance
            session_files = session_files[:self.max_files_to_read]
            
            # Load recent sessions
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_sessions = []
            
            for session_file in session_files:
                try:
                    # Quick check of file modification time
                    file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        continue
                    
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)
                    
                    # Validate session data
                    if self._is_valid_session(session_data):
                        recent_sessions.append(session_data)
                    
                    # Limit total sessions for performance
                    if len(recent_sessions) >= 50:
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to load session file {session_file}: {e}")
                    continue
            
            return recent_sessions
            
        except Exception as e:
            logger.error(f"Failed to load recent sessions: {e}")
            return []
    
    def _is_valid_session(self, session_data: Dict[str, Any]) -> bool:
        """Validate session data structure."""
        required_fields = ['session_id', 'timestamp', 'basic_metrics']
        return all(field in session_data for field in required_fields)


class SafeVisualizationRenderer:
    """Safe visualization renderer with performance limits."""
    
    # Performance constants
    MAX_RENDER_TIME = 3.0    # seconds
    MAX_DATA_POINTS = 1000   
    CACHE_TTL = 300         # 5 minutes
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.cache = SimpleCache(ttl=self.CACHE_TTL)
        self.data_loader = SessionDataLoader(data_dir)
    
    def _get_fallback_summary(self) -> DashboardSummary:
        """Get fallback dashboard summary."""
        return DashboardSummary(
            health_score=50,
            health_status='Unknown',
            size_category='unknown',
            estimated_tokens=0,
            session_count=0,
            avg_session_duration=0.0,
            trend_direction='stable',
            last_update=datetime.now().isoformat(),
            recommendations=['Dashboard unavailable - using fallback data'],
            render_duration=0.0
        )
    
    def _analyze_sessions(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze session data for dashboard insights."""
        if not sessions:
            return {
                'health_score': 50,
                'avg_tokens': 0,
                'avg_duration': 0,
                'trend': 'stable',
                'session_count': 0
            }
        
        # Extract metrics
        health_scores = []
        token_counts = []
        session_durations = []
        
        for session in sessions:
            try:
                metrics = session.get('basic_metrics', {})
                
                if 'health_score' in metrics:
                    health_scores.append(metrics['health_score'])
                
                if 'estimated_tokens' in metrics:
                    token_counts.append(metrics['estimated_tokens'])
                
                # Calculate session duration (rough estimate)
                session_durations.append(3600)  # Default to 1 hour
                
            except Exception as e:
                logger.warning(f"Failed to analyze session: {e}")
                continue
        
        # Calculate aggregates
        avg_health = statistics.mean(health_scores) if health_scores else 50
        avg_tokens = statistics.mean(token_counts) if token_counts else 0
        avg_duration = statistics.mean(session_durations) if session_durations else 0
        
        # Determine trend (simple: recent vs older sessions)
        if len(health_scores) >= 4:
            recent_health = statistics.mean(health_scores[:len(health_scores)//2])
            older_health = statistics.mean(health_scores[len(health_scores)//2:])
            
            if recent_health > older_health + 5:
                trend = 'improving'
            elif recent_health < older_health - 5:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'health_score': int(avg_health),
            'avg_tokens': int(avg_tokens),
            'avg_duration': avg_duration,
            'trend': trend,
            'session_count': len(sessions)
        }
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate simple text recommendations."""
        recommendations = []
        
        health_score = analysis.get('health_score', 50)
        avg_tokens = analysis.get('avg_tokens', 0)
        trend = analysis.get('trend', 'stable')
        
        # Health-based recommendations
        if health_score >= 80:
            recommendations.append("✅ Context health is excellent - keep up the good work!")
        elif health_score >= 60:
            recommendations.append("👍 Context health is good - minor optimizations may help")
        elif health_score >= 40:
            recommendations.append("⚠️ Context health is fair - consider cleanup")
        else:
            recommendations.append("🚨 Context health needs attention - cleanup recommended")
        
        # Size-based recommendations
        if avg_tokens > 50000:
            recommendations.append("📏 Context size is large - regular cleanup will improve performance")
        elif avg_tokens > 20000:
            recommendations.append("📊 Context size is moderate - monitor for growth")
        else:
            recommendations.append("📋 Context size is manageable")
        
        # Trend-based recommendations
        if trend == 'declining':
            recommendations.append("📉 Context health is declining - review recent patterns")
        elif trend == 'improving':
            recommendations.append("📈 Context health is improving - current approach is working")
        
        return recommendations[:4]  # Limit to top 4 recommendations
    
    def _format_dashboard_output(self, summary: DashboardSummary) -> str:
        """Format dashboard summary as readable text."""
        output_lines = []
        
        # Header
        output_lines.append("🎯 CONTEXT HEALTH DASHBOARD")
        output_lines.append("=" * 40)
        
        # Health status
        if summary.health_score >= 80:
            health_emoji = "🟢"
        elif summary.health_score >= 60:
            health_emoji = "🟡"
        else:
            health_emoji = "🔴"
        
        output_lines.append(f"{health_emoji} Health: {summary.health_status} ({summary.health_score}/100)")
        
        # Size info
        if summary.estimated_tokens > 0:
            output_lines.append(f"📊 Size: {summary.size_category} (~{summary.estimated_tokens:,} tokens)")
        
        # Session info
        if summary.session_count > 0:
            duration_hours = summary.avg_session_duration / 3600
            output_lines.append(f"⏱️ Sessions: {summary.session_count} (avg {duration_hours:.1f}h)")
        
        # Trend
        if summary.trend_direction == 'improving':
            trend_emoji = "📈"
        elif summary.trend_direction == 'declining':
            trend_emoji = "📉"
        else:
            trend_emoji = "➡️"
        
        output_lines.append(f"{trend_emoji} Trend: {summary.trend_direction.title()}")
        
        # Recommendations
        if summary.recommendations:
            output_lines.append("")
            output_lines.append("💡 RECOMMENDATIONS")
            output_lines.append("-" * 20)
            for rec in summary.recommendations:
                output_lines.append(f"  {rec}")
        
        # Footer
        output_lines.append("")
        output_lines.append(f"🕐 Last Updated: {summary.last_update}")
        output_lines.append(f"⚡ Render Time: {summary.render_duration:.3f}s")
        
        return "\n".join(output_lines)
    
    async def _perform_render(self) -> DashboardSummary:
        """Perform the actual dashboard rendering."""
        render_start = time.time()
        
        try:
            # Load recent session data
            sessions = self.data_loader.load_recent_sessions(hours=24)
            
            # Limit data points for performance
            if len(sessions) > self.MAX_DATA_POINTS:
                sessions = sessions[:self.MAX_DATA_POINTS]
            
            # Analyze sessions
            analysis = self._analyze_sessions(sessions)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(analysis)
            
            # Determine health status
            health_score = analysis['health_score']
            if health_score >= 80:
                health_status = 'Excellent'
            elif health_score >= 60:
                health_status = 'Good'
            elif health_score >= 40:
                health_status = 'Fair'
            else:
                health_status = 'Needs Attention'
            
            # Size category
            avg_tokens = analysis['avg_tokens']
            if avg_tokens < 10000:
                size_category = 'small'
            elif avg_tokens < 50000:
                size_category = 'medium'
            else:
                size_category = 'large'
            
            render_duration = time.time() - render_start
            
            return DashboardSummary(
                health_score=health_score,
                health_status=health_status,
                size_category=size_category,
                estimated_tokens=avg_tokens,
                session_count=analysis['session_count'],
                avg_session_duration=analysis['avg_duration'],
                trend_direction=analysis['trend'],
                last_update=datetime.now().isoformat(),
                recommendations=recommendations,
                render_duration=render_duration
            )
            
        except Exception as e:
            logger.error(f"Dashboard rendering failed: {e}")
            raise
    
    async def render_safely(self) -> Optional[DashboardSummary]:
        """Render dashboard with comprehensive safety measures."""
        # Check cache first
        cache_key = "dashboard_summary"
        cached_result = self.cache.get(cache_key)
        
        if cached_result is not None:
            logger.debug("Returning cached dashboard summary")
            return cached_result
        
        try:
            # Perform rendering with timeout
            summary = await asyncio.wait_for(
                self._perform_render(),
                timeout=self.MAX_RENDER_TIME
            )
            
            # Cache successful result
            self.cache.set(cache_key, summary)
            
            return summary
            
        except asyncio.TimeoutError:
            logger.error(f"Dashboard rendering timed out after {self.MAX_RENDER_TIME}s")
            return self._get_fallback_summary()
            
        except Exception as e:
            logger.error(f"Dashboard rendering failed: {e}")
            return self._get_fallback_summary()
    
    def render_sync(self) -> Optional[DashboardSummary]:
        """Synchronous wrapper for dashboard rendering."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.render_safely())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Synchronous dashboard rendering failed: {e}")
            return self._get_fallback_summary()


class BasicDashboard:
    """Main dashboard interface."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            # Default to project data directory
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            data_dir = project_root / '.context_visualizer' / 'data' / 'sessions'
        
        self.renderer = SafeVisualizationRenderer(data_dir)
    
    async def generate_summary(self) -> Optional[DashboardSummary]:
        """Generate dashboard summary safely."""
        return await self.renderer.render_safely()
    
    def generate_summary_sync(self) -> Optional[DashboardSummary]:
        """Generate dashboard summary synchronously."""
        return self.renderer.render_sync()
    
    def get_formatted_output(self) -> str:
        """Get formatted dashboard output."""
        summary = self.generate_summary_sync()
        if summary is None:
            return "❌ Dashboard unavailable - please try again later"
        
        return self.renderer._format_dashboard_output(summary)
    
    def get_json_output(self) -> Dict[str, Any]:
        """Get dashboard data as JSON."""
        summary = self.generate_summary_sync()
        if summary is None:
            return {"error": "Dashboard unavailable"}
        
        return summary.to_dict()


# Convenience functions
def get_dashboard(data_dir: Optional[Path] = None) -> BasicDashboard:
    """Get dashboard instance."""
    return BasicDashboard(data_dir)


def get_dashboard_summary() -> str:
    """Get formatted dashboard summary."""
    dashboard = get_dashboard()
    return dashboard.get_formatted_output()


def get_dashboard_json() -> Dict[str, Any]:
    """Get dashboard data as JSON."""
    dashboard = get_dashboard()
    return dashboard.get_json_output()


# Main function for testing
if __name__ == "__main__":
    print("Testing Basic Dashboard...")
    
    # Test dashboard generation
    dashboard = get_dashboard()
    
    print("\n" + "=" * 50)
    print("FORMATTED DASHBOARD OUTPUT:")
    print("=" * 50)
    print(dashboard.get_formatted_output())
    
    print("\n" + "=" * 50)
    print("JSON DASHBOARD DATA:")
    print("=" * 50)
    json_data = dashboard.get_json_output()
    print(json.dumps(json_data, indent=2))
    
    print("\n✅ Dashboard test completed!")