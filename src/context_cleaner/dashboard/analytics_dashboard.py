"""
Advanced Analytics Dashboard with Interactive Visualizations

Comprehensive web-based dashboard that provides real-time productivity insights,
trend visualizations, health scoring displays, and interactive analytics for
Context Cleaner's productivity tracking system.
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import webbrowser
import threading
import time

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder

from ..analytics.productivity_analyzer import ProductivityAnalyzer, ProductivityMetrics
from ..analytics.context_health_scorer import ContextHealthScorer, HealthScore, HealthScoringModel
from ..analytics.recommendation_engine import RecommendationEngine, Recommendation
from ..analytics.trend_analyzer import TrendAnalyzer, TrendAnalysis, Pattern
from ..config.settings import ContextCleanerConfig
from ..tracking.session_tracker import SessionTracker

logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    """
    Advanced web-based analytics dashboard with real-time updates.
    
    Features:
    - Interactive productivity trend charts
    - Real-time health score monitoring
    - Pattern visualization and insights
    - Recommendation display with priority ranking
    - Context size and complexity analytics
    - Session timeline with drill-down capabilities
    - Export functionality for reports
    - WebSocket support for real-time updates
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None):
        """
        Initialize analytics dashboard.
        
        Args:
            config: Context Cleaner configuration
        """
        self.config = config or ContextCleanerConfig.from_env()
        
        # Initialize analytics components
        self.productivity_analyzer = ProductivityAnalyzer(config)
        self.health_scorer = ContextHealthScorer(config)
        self.recommendation_engine = RecommendationEngine(config)
        self.trend_analyzer = TrendAnalyzer(config)
        self.session_tracker = SessionTracker(config)
        
        # Dashboard configuration
        self.host = '127.0.0.1'
        self.port = 8080
        self.debug = False
        
        # Flask app setup
        self.app = Flask(__name__, 
                        template_folder=self._get_templates_dir(),
                        static_folder=self._get_static_dir())
        self.app.config['SECRET_KEY'] = 'context-cleaner-dashboard-2024'
        
        # SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Dashboard state
        self.dashboard_data = {}
        self.last_update = datetime.now()
        self.auto_refresh_enabled = True
        self.refresh_interval = 30  # seconds
        
        # Setup routes
        self._setup_routes()
        self._setup_socketio_events()
        
        logger.info("AnalyticsDashboard initialized")
    
    def _get_templates_dir(self) -> str:
        """Get templates directory path."""
        return str(Path(__file__).parent / "templates")
    
    def _get_static_dir(self) -> str:
        """Get static files directory path."""
        return str(Path(__file__).parent / "static")
    
    def _setup_routes(self):
        """Setup Flask routes for dashboard."""
        
        @self.app.route('/')
        def dashboard_home():
            """Main dashboard page."""
            return render_template('dashboard.html', 
                                 title="Context Cleaner Analytics Dashboard",
                                 refresh_interval=self.refresh_interval * 1000)
        
        @self.app.route('/api/dashboard-data')
        def get_dashboard_data():
            """Get complete dashboard data."""
            try:
                data = self._generate_dashboard_data()
                return jsonify(data)
            except Exception as e:
                logger.error(f"Dashboard data generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/productivity-chart')
        def get_productivity_chart():
            """Get productivity trend chart data."""
            try:
                days = request.args.get('days', 30, type=int)
                chart_data = self._generate_productivity_chart(days)
                return jsonify(chart_data)
            except Exception as e:
                logger.error(f"Productivity chart generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health-score-chart')
        def get_health_score_chart():
            """Get health score trend chart data."""
            try:
                days = request.args.get('days', 30, type=int)
                chart_data = self._generate_health_score_chart(days)
                return jsonify(chart_data)
            except Exception as e:
                logger.error(f"Health score chart generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/pattern-visualization')
        def get_pattern_visualization():
            """Get pattern analysis visualization."""
            try:
                pattern_type = request.args.get('type', 'all')
                chart_data = self._generate_pattern_visualization(pattern_type)
                return jsonify(chart_data)
            except Exception as e:
                logger.error(f"Pattern visualization generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/recommendations')
        def get_recommendations():
            """Get current recommendations."""
            try:
                recommendations = self._get_current_recommendations()
                return jsonify([r.to_dict() for r in recommendations])
            except Exception as e:
                logger.error(f"Recommendations generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/session-timeline')
        def get_session_timeline():
            """Get session timeline data."""
            try:
                days = request.args.get('days', 7, type=int)
                timeline_data = self._generate_session_timeline(days)
                return jsonify(timeline_data)
            except Exception as e:
                logger.error(f"Session timeline generation failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/export/<format>')
        def export_data(format):
            """Export dashboard data in various formats."""
            try:
                if format == 'json':
                    return jsonify(self._generate_export_data())
                elif format == 'csv':
                    # TODO: Implement CSV export
                    return jsonify({'error': 'CSV export not yet implemented'}), 501
                else:
                    return jsonify({'error': 'Unsupported export format'}), 400
            except Exception as e:
                logger.error(f"Data export failed: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/health')
        def health_check():
            """Dashboard health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0',
                'components': {
                    'productivity_analyzer': True,
                    'health_scorer': True,
                    'recommendation_engine': True,
                    'trend_analyzer': True,
                    'session_tracker': True
                }
            })
    
    def _setup_socketio_events(self):
        """Setup SocketIO events for real-time updates."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            logger.info(f"Dashboard client connected")
            # Send initial data
            emit('dashboard_update', self._generate_dashboard_data())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            logger.info("Dashboard client disconnected")
        
        @self.socketio.on('request_update')
        def handle_update_request():
            """Handle manual update request from client."""
            logger.info("Manual dashboard update requested")
            emit('dashboard_update', self._generate_dashboard_data())
        
        @self.socketio.on('toggle_auto_refresh')
        def handle_auto_refresh_toggle(data):
            """Handle auto-refresh toggle."""
            self.auto_refresh_enabled = data.get('enabled', True)
            logger.info(f"Auto-refresh {'enabled' if self.auto_refresh_enabled else 'disabled'}")
    
    def _generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate comprehensive dashboard data."""
        try:
            # Get recent session data
            sessions = self._get_recent_sessions(30)  # Last 30 days
            
            if not sessions:
                return self._generate_empty_dashboard()
            
            # Generate analytics data
            trend_analysis = self.trend_analyzer.analyze_trends(sessions)
            recommendations = self._get_current_recommendations()
            
            # Current metrics
            current_session = self.session_tracker.get_current_session()
            current_metrics = self._get_current_metrics()
            
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'data_period': {
                    'start': (datetime.now() - timedelta(days=30)).isoformat(),
                    'end': datetime.now().isoformat()
                },
                'summary': {
                    'total_sessions': len(sessions),
                    'avg_productivity': self._calculate_average_productivity(sessions),
                    'avg_health_score': self._calculate_average_health_score(sessions),
                    'active_recommendations': len(recommendations),
                    'current_session_active': current_session is not None
                },
                'current_metrics': current_metrics,
                'trends': {
                    'productivity': {
                        'direction': trend_analysis.productivity_trend.direction.value,
                        'strength': trend_analysis.productivity_trend.strength,
                        'confidence': trend_analysis.productivity_trend.confidence.value
                    },
                    'health_score': {
                        'direction': trend_analysis.health_score_trend.direction.value,
                        'strength': trend_analysis.health_score_trend.strength,
                        'confidence': trend_analysis.health_score_trend.confidence.value
                    }
                },
                'patterns': [
                    {
                        'type': p.type.value,
                        'name': p.name,
                        'strength': p.strength,
                        'description': p.description
                    } for p in trend_analysis.patterns[:5]  # Top 5 patterns
                ],
                'recommendations': [r.to_dict() for r in recommendations[:3]],  # Top 3 recommendations
                'insights': trend_analysis.key_insights[:3],  # Top 3 insights
                'anomalies': trend_analysis.anomalies[:3],  # Top 3 anomalies
                'charts': {
                    'productivity_chart': self._generate_productivity_chart_data(sessions),
                    'health_score_chart': self._generate_health_score_chart_data(sessions),
                    'session_distribution': self._generate_session_distribution_chart(sessions)
                }
            }
            
            self.dashboard_data = dashboard_data
            self.last_update = datetime.now()
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Dashboard data generation failed: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'summary': {'error': 'Data generation failed'}
            }
    
    def _generate_productivity_chart(self, days: int = 30) -> Dict[str, Any]:
        """Generate productivity trend chart."""
        try:
            sessions = self._get_recent_sessions(days)
            
            if not sessions:
                return {'error': 'No session data available'}
            
            # Prepare data for chart
            dates = []
            productivity_scores = []
            
            for session in sorted(sessions, key=lambda x: x.get('start_time', '')):
                date = datetime.fromisoformat(session.get('start_time', '')).date()
                score = session.get('productivity_score', 0)
                
                if score > 0:
                    dates.append(date.isoformat())
                    productivity_scores.append(score)
            
            # Create Plotly chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=productivity_scores,
                mode='lines+markers',
                name='Productivity Score',
                line=dict(color='#2E86C1', width=3),
                marker=dict(size=6)
            ))
            
            # Add trend line if enough data
            if len(productivity_scores) > 3:
                # Simple moving average
                window_size = min(5, len(productivity_scores) // 2)
                moving_avg = []
                for i in range(len(productivity_scores)):
                    start_idx = max(0, i - window_size // 2)
                    end_idx = min(len(productivity_scores), i + window_size // 2 + 1)
                    moving_avg.append(sum(productivity_scores[start_idx:end_idx]) / (end_idx - start_idx))
                
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=moving_avg,
                    mode='lines',
                    name='Trend',
                    line=dict(color='#E74C3C', width=2, dash='dash')
                ))
            
            fig.update_layout(
                title='Productivity Trend Over Time',
                xaxis_title='Date',
                yaxis_title='Productivity Score',
                yaxis=dict(range=[0, 100]),
                hovermode='x unified',
                template='plotly_white'
            )
            
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
            
        except Exception as e:
            logger.error(f"Productivity chart generation failed: {e}")
            return {'error': str(e)}
    
    def _generate_health_score_chart(self, days: int = 30) -> Dict[str, Any]:
        """Generate health score trend chart."""
        try:
            sessions = self._get_recent_sessions(days)
            
            if not sessions:
                return {'error': 'No session data available'}
            
            dates = []
            health_scores = []
            
            for session in sorted(sessions, key=lambda x: x.get('start_time', '')):
                date = datetime.fromisoformat(session.get('start_time', '')).date()
                score = session.get('health_score', 0)
                
                if score > 0:
                    dates.append(date.isoformat())
                    health_scores.append(score)
            
            # Create multi-trace chart for health components
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=health_scores,
                mode='lines+markers',
                name='Overall Health Score',
                line=dict(color='#27AE60', width=3),
                marker=dict(size=6)
            ))
            
            # Add health score ranges
            fig.add_hline(y=80, line_dash="dash", line_color="green", 
                         annotation_text="Excellent (80+)")
            fig.add_hline(y=60, line_dash="dash", line_color="orange", 
                         annotation_text="Good (60+)")
            fig.add_hline(y=40, line_dash="dash", line_color="red", 
                         annotation_text="Needs Improvement (40+)")
            
            fig.update_layout(
                title='Context Health Score Over Time',
                xaxis_title='Date',
                yaxis_title='Health Score',
                yaxis=dict(range=[0, 100]),
                hovermode='x unified',
                template='plotly_white'
            )
            
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
            
        except Exception as e:
            logger.error(f"Health score chart generation failed: {e}")
            return {'error': str(e)}
    
    def _generate_pattern_visualization(self, pattern_type: str = 'all') -> Dict[str, Any]:
        """Generate pattern analysis visualization."""
        try:
            sessions = self._get_recent_sessions(14)  # 2 weeks for pattern analysis
            
            if not sessions:
                return {'error': 'No session data available'}
            
            trend_analysis = self.trend_analyzer.analyze_trends(sessions)
            
            # Create pattern visualization based on type
            if pattern_type == 'daily' or pattern_type == 'all':
                # Daily productivity pattern
                hourly_data = {}
                for session in sessions:
                    start_time = datetime.fromisoformat(session.get('start_time', ''))
                    hour = start_time.hour
                    productivity = session.get('productivity_score', 0)
                    
                    if productivity > 0:
                        if hour not in hourly_data:
                            hourly_data[hour] = []
                        hourly_data[hour].append(productivity)
                
                # Calculate averages
                hours = sorted(hourly_data.keys())
                avg_productivity = [
                    sum(hourly_data[hour]) / len(hourly_data[hour]) 
                    for hour in hours
                ]
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=[f"{h:02d}:00" for h in hours],
                    y=avg_productivity,
                    name='Average Productivity by Hour',
                    marker_color='#3498DB'
                ))
                
                fig.update_layout(
                    title='Daily Productivity Pattern',
                    xaxis_title='Hour of Day',
                    yaxis_title='Average Productivity Score',
                    template='plotly_white'
                )
                
                return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
            
            return {'error': f'Pattern type {pattern_type} not supported yet'}
            
        except Exception as e:
            logger.error(f"Pattern visualization generation failed: {e}")
            return {'error': str(e)}
    
    def _generate_session_timeline(self, days: int = 7) -> Dict[str, Any]:
        """Generate session timeline visualization."""
        try:
            sessions = self._get_recent_sessions(days)
            
            if not sessions:
                return {'error': 'No session data available'}
            
            # Prepare timeline data
            timeline_data = []
            
            for session in sessions:
                start_time = datetime.fromisoformat(session.get('start_time', ''))
                duration = session.get('duration_minutes', 0)
                end_time = start_time + timedelta(minutes=duration)
                
                timeline_data.append({
                    'session_id': session.get('session_id', 'unknown'),
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'duration_minutes': duration,
                    'productivity_score': session.get('productivity_score', 0),
                    'context_size': session.get('context_size', 0),
                    'focus_time_minutes': session.get('focus_time_minutes', 0)
                })
            
            # Create Gantt-style chart
            fig = go.Figure()
            
            for i, session in enumerate(timeline_data):
                fig.add_trace(go.Scatter(
                    x=[session['start'], session['end']],
                    y=[i, i],
                    mode='lines',
                    line=dict(width=10, color=f'rgb({min(255, session["productivity_score"]*2.55)}, {255-min(255, session["productivity_score"]*2.55)}, 100)'),
                    name=f'Session {i+1}',
                    hovertemplate=f'<b>Session {i+1}</b><br>' +
                                f'Duration: {session["duration_minutes"]} min<br>' +
                                f'Productivity: {session["productivity_score"]}<br>' +
                                f'Context Size: {session["context_size"]} tokens<br>' +
                                '<extra></extra>'
                ))
            
            fig.update_layout(
                title='Session Timeline',
                xaxis_title='Time',
                yaxis_title='Sessions',
                yaxis=dict(tickmode='linear', tick0=0, dtick=1),
                hovermode='closest',
                template='plotly_white',
                showlegend=False
            )
            
            return json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
            
        except Exception as e:
            logger.error(f"Session timeline generation failed: {e}")
            return {'error': str(e)}
    
    def _get_current_recommendations(self) -> List[Recommendation]:
        """Get current recommendations."""
        try:
            # Get current context data (mock for now)
            current_context = {
                'size': 25000,
                'file_count': 8,
                'complexity_score': 65
            }
            
            # Get recent sessions for pattern analysis
            sessions = self._get_recent_sessions(14)
            session_dicts = [self._session_to_dict(s) for s in sessions]
            
            # Generate recommendations
            recommendations = self.recommendation_engine.generate_recommendations(
                current_context,
                session_dicts
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Current recommendations generation failed: {e}")
            return []
    
    def _get_recent_sessions(self, days: int) -> List[Dict[str, Any]]:
        """Get recent session data."""
        try:
            # Get sessions from session tracker
            sessions = self.session_tracker.get_recent_sessions(days)
            
            # Convert to dictionaries
            session_dicts = [self._session_to_dict(session) for session in sessions]
            
            return session_dicts
            
        except Exception as e:
            logger.error(f"Recent sessions retrieval failed: {e}")
            return []
    
    def _session_to_dict(self, session) -> Dict[str, Any]:
        """Convert session object to dictionary."""
        try:
            if hasattr(session, 'to_dict'):
                return session.to_dict()
            
            # Manual conversion for basic session data
            return {
                'session_id': getattr(session, 'session_id', 'unknown'),
                'start_time': getattr(session, 'start_time', datetime.now()).isoformat(),
                'end_time': getattr(session, 'end_time', datetime.now()).isoformat() if hasattr(session, 'end_time') and session.end_time else None,
                'duration_minutes': getattr(session, 'duration_minutes', 0),
                'productivity_score': getattr(session, 'productivity_score', 0),
                'health_score': getattr(session, 'health_score', 0),
                'context_size': getattr(session, 'context_size', 0),
                'focus_time_minutes': getattr(session, 'focus_time_minutes', 0),
                'complexity_score': getattr(session, 'complexity_score', 0)
            }
            
        except Exception as e:
            logger.error(f"Session to dict conversion failed: {e}")
            return {
                'session_id': 'error',
                'start_time': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current session metrics."""
        try:
            current_session = self.session_tracker.get_current_session()
            
            if current_session:
                return {
                    'session_active': True,
                    'session_id': current_session.session_id,
                    'duration_minutes': getattr(current_session, 'duration_minutes', 0),
                    'productivity_score': getattr(current_session, 'productivity_score', 0),
                    'health_score': getattr(current_session, 'health_score', 0),
                    'context_size': getattr(current_session, 'context_size', 0),
                    'focus_time_minutes': getattr(current_session, 'focus_time_minutes', 0)
                }
            else:
                return {
                    'session_active': False,
                    'last_session_end': None  # TODO: Get from session tracker
                }
                
        except Exception as e:
            logger.error(f"Current metrics retrieval failed: {e}")
            return {'error': str(e), 'session_active': False}
    
    def _calculate_average_productivity(self, sessions: List[Dict[str, Any]]) -> float:
        """Calculate average productivity from sessions."""
        try:
            productivity_scores = [
                s.get('productivity_score', 0) 
                for s in sessions 
                if s.get('productivity_score', 0) > 0
            ]
            
            if productivity_scores:
                return round(sum(productivity_scores) / len(productivity_scores), 1)
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_average_health_score(self, sessions: List[Dict[str, Any]]) -> float:
        """Calculate average health score from sessions."""
        try:
            health_scores = [
                s.get('health_score', 0) 
                for s in sessions 
                if s.get('health_score', 0) > 0
            ]
            
            if health_scores:
                return round(sum(health_scores) / len(health_scores), 1)
            return 0.0
            
        except Exception:
            return 0.0
    
    def _generate_productivity_chart_data(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate productivity chart data for dashboard."""
        # Simplified version for dashboard embedding
        try:
            dates = []
            scores = []
            
            for session in sorted(sessions, key=lambda x: x.get('start_time', '')):
                if session.get('productivity_score', 0) > 0:
                    dates.append(session.get('start_time', ''))
                    scores.append(session.get('productivity_score', 0))
            
            return {
                'labels': dates[-10:],  # Last 10 data points
                'data': scores[-10:],
                'type': 'line'
            }
            
        except Exception:
            return {'labels': [], 'data': [], 'type': 'line'}
    
    def _generate_health_score_chart_data(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate health score chart data for dashboard."""
        try:
            dates = []
            scores = []
            
            for session in sorted(sessions, key=lambda x: x.get('start_time', '')):
                if session.get('health_score', 0) > 0:
                    dates.append(session.get('start_time', ''))
                    scores.append(session.get('health_score', 0))
            
            return {
                'labels': dates[-10:],  # Last 10 data points
                'data': scores[-10:],
                'type': 'line'
            }
            
        except Exception:
            return {'labels': [], 'data': [], 'type': 'line'}
    
    def _generate_session_distribution_chart(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate session distribution chart data."""
        try:
            # Duration distribution
            durations = [s.get('duration_minutes', 0) for s in sessions if s.get('duration_minutes', 0) > 0]
            
            # Categorize durations
            short = sum(1 for d in durations if d < 30)
            medium = sum(1 for d in durations if 30 <= d <= 120)
            long = sum(1 for d in durations if d > 120)
            
            return {
                'labels': ['Short (<30min)', 'Medium (30-120min)', 'Long (>120min)'],
                'data': [short, medium, long],
                'type': 'pie'
            }
            
        except Exception:
            return {'labels': [], 'data': [], 'type': 'pie'}
    
    def _generate_empty_dashboard(self) -> Dict[str, Any]:
        """Generate empty dashboard for no data scenario."""
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_sessions': 0,
                'avg_productivity': 0,
                'avg_health_score': 0,
                'active_recommendations': 0,
                'current_session_active': False,
                'message': 'No session data available. Start using Context Cleaner to see analytics.'
            },
            'current_metrics': {'session_active': False},
            'trends': {},
            'patterns': [],
            'recommendations': [],
            'insights': ['Start tracking sessions to generate insights'],
            'anomalies': [],
            'charts': {
                'productivity_chart': {'labels': [], 'data': []},
                'health_score_chart': {'labels': [], 'data': []},
                'session_distribution': {'labels': [], 'data': []}
            }
        }
    
    def _generate_export_data(self) -> Dict[str, Any]:
        """Generate export data."""
        return {
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '1.0.0',
            'dashboard_data': self.dashboard_data,
            'sessions': self._get_recent_sessions(90),  # Last 3 months
            'metadata': {
                'total_sessions': len(self._get_recent_sessions(365)),
                'analysis_capabilities': [
                    'productivity_tracking',
                    'context_health_scoring', 
                    'recommendation_generation',
                    'trend_analysis',
                    'pattern_detection'
                ]
            }
        }
    
    def start_dashboard(self, host: str = None, port: int = None, debug: bool = False, open_browser: bool = True):
        """
        Start the analytics dashboard server.
        
        Args:
            host: Host to bind to
            port: Port to bind to  
            debug: Enable debug mode
            open_browser: Whether to open browser automatically
        """
        self.host = host or self.host
        self.port = port or self.port
        self.debug = debug
        
        # Start auto-refresh thread
        if self.auto_refresh_enabled:
            refresh_thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
            refresh_thread.start()
        
        logger.info(f"Starting analytics dashboard on http://{self.host}:{self.port}")
        
        if open_browser:
            # Open browser after a short delay
            threading.Timer(1.0, lambda: webbrowser.open(f'http://{self.host}:{self.port}')).start()
        
        try:
            self.socketio.run(self.app, 
                            host=self.host, 
                            port=self.port, 
                            debug=self.debug,
                            allow_unsafe_werkzeug=True)
        except Exception as e:
            logger.error(f"Dashboard server error: {e}")
            raise
    
    def _auto_refresh_loop(self):
        """Auto-refresh loop for real-time updates."""
        while self.auto_refresh_enabled:
            try:
                time.sleep(self.refresh_interval)
                
                if self.auto_refresh_enabled:
                    # Generate new data and emit to all connected clients
                    dashboard_data = self._generate_dashboard_data()
                    self.socketio.emit('dashboard_update', dashboard_data)
                    
            except Exception as e:
                logger.error(f"Auto-refresh error: {e}")
                time.sleep(5)  # Wait before retrying
    
    def stop_dashboard(self):
        """Stop the dashboard server."""
        self.auto_refresh_enabled = False
        logger.info("Analytics dashboard stopped")


def main():
    """Main function for running dashboard standalone."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Context Cleaner Analytics Dashboard')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')
    
    args = parser.parse_args()
    
    try:
        dashboard = AnalyticsDashboard()
        dashboard.start_dashboard(
            host=args.host,
            port=args.port,
            debug=args.debug,
            open_browser=not args.no_browser
        )
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Dashboard error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()