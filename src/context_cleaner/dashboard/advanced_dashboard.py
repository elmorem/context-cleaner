"""
Advanced Dashboard System
Provides sophisticated dashboard functionality with custom widgets,
real-time updates, and flexible layout management.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Types of dashboard widgets"""
    METRIC_CARD = "metric_card"
    CHART = "chart"
    TABLE = "table"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    PROGRESS = "progress"
    LIST = "list"
    CUSTOM = "custom"


class UpdateFrequency(Enum):
    """Widget update frequencies"""
    REALTIME = "realtime"  # Updates immediately when data changes
    FAST = "fast"         # Every 5 seconds
    NORMAL = "normal"     # Every 30 seconds
    SLOW = "slow"         # Every 5 minutes
    MANUAL = "manual"     # Only when explicitly refreshed


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget"""
    widget_id: str
    widget_type: WidgetType
    title: str
    data_source: str
    position: Dict[str, int]  # x, y, width, height
    update_frequency: UpdateFrequency = UpdateFrequency.NORMAL
    config: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DashboardLayout:
    """Dashboard layout configuration"""
    layout_id: str
    name: str
    description: str
    widgets: List[WidgetConfig]
    grid_settings: Dict[str, Any]
    theme: str = "light"
    auto_refresh: bool = True
    refresh_interval: int = 30  # seconds
    created_by: str = "system"
    is_public: bool = False
    tags: List[str] = field(default_factory=list)


class DataSource:
    """Base class for dashboard data sources"""
    
    def __init__(self, source_id: str, config: Dict[str, Any]):
        self.source_id = source_id
        self.config = config
        self.cache = {}
        self.last_updated = None
    
    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get data from the source"""
        raise NotImplementedError
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get data schema for the source"""
        raise NotImplementedError
    
    def invalidate_cache(self):
        """Invalidate cached data"""
        self.cache.clear()
        self.last_updated = None


class ProductivityDataSource(DataSource):
    """Data source for productivity metrics"""
    
    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get productivity data"""
        # This would typically connect to the analytics system
        from ..analytics.productivity_analyzer import ProductivityAnalyzer
        
        analyzer = ProductivityAnalyzer()
        
        # Apply date range filter if provided
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        if filters:
            if 'start_date' in filters:
                start_date = datetime.fromisoformat(filters['start_date'])
            if 'end_date' in filters:
                end_date = datetime.fromisoformat(filters['end_date'])
        
        # Generate mock session data for the date range
        mock_sessions = []
        current_date = start_date
        while current_date <= end_date:
            sessions_per_day = 3 + int((current_date.weekday() < 5) * 2)  # More sessions on weekdays
            
            for session_num in range(sessions_per_day):
                session_start = current_date.replace(
                    hour=9 + session_num * 3,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                
                mock_sessions.append({
                    'timestamp': session_start,
                    'duration_minutes': 45 + (session_num * 15),
                    'active_time_minutes': 35 + (session_num * 12),
                    'context_switches': 5 + session_num,
                    'applications': ['code_editor', 'browser', 'terminal'][:session_num + 1]
                })
            
            current_date += timedelta(days=1)
        
        # Analyze productivity
        analysis = analyzer.analyze_productivity_patterns(mock_sessions)
        
        return {
            'productivity_score': analysis.get('overall_productivity_score', 75),
            'focus_time_hours': analysis.get('total_focus_time_hours', 6.5),
            'daily_averages': analysis.get('daily_productivity_averages', {}),
            'trend_direction': analysis.get('productivity_trend', 'stable'),
            'efficiency_ratio': analysis.get('efficiency_ratio', 0.85),
            'context_switches_avg': analysis.get('avg_context_switches_per_hour', 12),
            'most_productive_hours': analysis.get('peak_productivity_hours', [9, 10, 14, 15]),
            'total_sessions': len(mock_sessions),
            'active_days': len(set(session['timestamp'].date() for session in mock_sessions))
        }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for productivity data"""
        return {
            'productivity_score': {'type': 'number', 'min': 0, 'max': 100, 'unit': '%'},
            'focus_time_hours': {'type': 'number', 'min': 0, 'unit': 'hours'},
            'daily_averages': {'type': 'object'},
            'trend_direction': {'type': 'string', 'enum': ['upward', 'downward', 'stable']},
            'efficiency_ratio': {'type': 'number', 'min': 0, 'max': 1},
            'context_switches_avg': {'type': 'number', 'min': 0},
            'most_productive_hours': {'type': 'array', 'items': {'type': 'number'}},
            'total_sessions': {'type': 'number', 'min': 0},
            'active_days': {'type': 'number', 'min': 0}
        }


class HealthDataSource(DataSource):
    """Data source for health and wellness metrics"""
    
    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get health data"""
        # Mock health data - in real implementation, this would connect to health tracking systems
        import random
        
        base_date = datetime.now() - timedelta(days=30)
        daily_data = []
        
        for i in range(30):
            date = base_date + timedelta(days=i)
            daily_data.append({
                'date': date.date().isoformat(),
                'sleep_hours': 6.5 + random.uniform(-1.5, 1.5),
                'stress_level': random.randint(1, 10),
                'energy_level': random.randint(1, 10),
                'exercise_minutes': random.randint(0, 90),
                'screen_time_hours': 8 + random.uniform(-2, 4)
            })
        
        avg_sleep = sum(d['sleep_hours'] for d in daily_data) / len(daily_data)
        avg_stress = sum(d['stress_level'] for d in daily_data) / len(daily_data)
        avg_energy = sum(d['energy_level'] for d in daily_data) / len(daily_data)
        
        return {
            'average_sleep_hours': round(avg_sleep, 1),
            'average_stress_level': round(avg_stress, 1),
            'average_energy_level': round(avg_energy, 1),
            'total_exercise_minutes': sum(d['exercise_minutes'] for d in daily_data),
            'average_screen_time': round(sum(d['screen_time_hours'] for d in daily_data) / len(daily_data), 1),
            'daily_data': daily_data,
            'sleep_quality_trend': 'improving' if daily_data[-7:] > daily_data[:7] else 'stable',
            'wellness_score': min(100, max(0, (avg_energy * 10) - (avg_stress * 5) + (avg_sleep * 5)))
        }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for health data"""
        return {
            'average_sleep_hours': {'type': 'number', 'min': 0, 'max': 12, 'unit': 'hours'},
            'average_stress_level': {'type': 'number', 'min': 1, 'max': 10, 'unit': 'scale'},
            'average_energy_level': {'type': 'number', 'min': 1, 'max': 10, 'unit': 'scale'},
            'total_exercise_minutes': {'type': 'number', 'min': 0, 'unit': 'minutes'},
            'average_screen_time': {'type': 'number', 'min': 0, 'unit': 'hours'},
            'daily_data': {'type': 'array'},
            'sleep_quality_trend': {'type': 'string', 'enum': ['improving', 'declining', 'stable']},
            'wellness_score': {'type': 'number', 'min': 0, 'max': 100, 'unit': '%'}
        }


class TaskDataSource(DataSource):
    """Data source for task and project management data"""
    
    async def get_data(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get task management data"""
        import random
        from collections import defaultdict
        
        # Generate mock task data
        task_statuses = ['todo', 'in_progress', 'review', 'completed']
        priorities = ['low', 'medium', 'high', 'urgent']
        categories = ['development', 'research', 'documentation', 'meetings', 'planning']
        
        tasks = []
        task_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        
        for i in range(50):
            status = random.choice(task_statuses)
            priority = random.choice(priorities)
            category = random.choice(categories)
            
            created_date = datetime.now() - timedelta(days=random.randint(1, 30))
            
            task = {
                'id': f'task_{i}',
                'title': f'Task {i}: {category.title()} Work',
                'status': status,
                'priority': priority,
                'category': category,
                'created_date': created_date.isoformat(),
                'estimated_hours': random.randint(1, 16),
                'actual_hours': random.randint(1, 20) if status == 'completed' else 0,
                'progress': random.randint(0, 100) if status != 'todo' else 0
            }
            
            tasks.append(task)
            task_counts[status] += 1
            priority_counts[priority] += 1
        
        completed_tasks = [t for t in tasks if t['status'] == 'completed']
        completion_rate = len(completed_tasks) / len(tasks) * 100
        
        # Calculate velocity (completed tasks per week)
        recent_completions = [
            t for t in completed_tasks 
            if datetime.fromisoformat(t['created_date']) > datetime.now() - timedelta(days=7)
        ]
        
        return {
            'total_tasks': len(tasks),
            'task_counts_by_status': dict(task_counts),
            'priority_distribution': dict(priority_counts),
            'completion_rate': round(completion_rate, 1),
            'weekly_velocity': len(recent_completions),
            'average_task_duration': round(
                sum(t['actual_hours'] for t in completed_tasks) / max(len(completed_tasks), 1), 1
            ),
            'overdue_tasks': random.randint(2, 8),
            'upcoming_deadlines': random.randint(5, 15),
            'tasks_by_category': dict(defaultdict(int, {
                cat: len([t for t in tasks if t['category'] == cat]) 
                for cat in categories
            }))
        }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get schema for task data"""
        return {
            'total_tasks': {'type': 'number', 'min': 0},
            'task_counts_by_status': {'type': 'object'},
            'priority_distribution': {'type': 'object'},
            'completion_rate': {'type': 'number', 'min': 0, 'max': 100, 'unit': '%'},
            'weekly_velocity': {'type': 'number', 'min': 0, 'unit': 'tasks/week'},
            'average_task_duration': {'type': 'number', 'min': 0, 'unit': 'hours'},
            'overdue_tasks': {'type': 'number', 'min': 0},
            'upcoming_deadlines': {'type': 'number', 'min': 0},
            'tasks_by_category': {'type': 'object'}
        }


class WidgetRenderer:
    """Base class for widget rendering"""
    
    def __init__(self, widget_config: WidgetConfig):
        self.config = widget_config
    
    async def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Render widget with data"""
        raise NotImplementedError
    
    def get_client_config(self) -> Dict[str, Any]:
        """Get configuration for client-side rendering"""
        return {
            'widget_id': self.config.widget_id,
            'widget_type': self.config.widget_type.value,
            'title': self.config.title,
            'position': self.config.position,
            'config': self.config.config
        }


class MetricCardRenderer(WidgetRenderer):
    """Renderer for metric card widgets"""
    
    async def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Render metric card"""
        metric_key = self.config.config.get('metric_key', 'value')
        value = data.get(metric_key, 0)
        
        # Format value based on configuration
        format_type = self.config.config.get('format', 'number')
        if format_type == 'percentage':
            formatted_value = f"{value:.1f}%"
        elif format_type == 'currency':
            formatted_value = f"${value:,.2f}"
        elif format_type == 'time':
            hours = int(value)
            minutes = int((value - hours) * 60)
            formatted_value = f"{hours}h {minutes}m"
        else:
            formatted_value = f"{value:,.1f}" if isinstance(value, float) else str(value)
        
        # Determine trend
        trend_key = self.config.config.get('trend_key')
        trend = None
        if trend_key and trend_key in data:
            trend_value = data[trend_key]
            if isinstance(trend_value, str):
                trend = trend_value
            elif isinstance(trend_value, (int, float)):
                if trend_value > 5:
                    trend = 'up'
                elif trend_value < -5:
                    trend = 'down'
                else:
                    trend = 'stable'
        
        return {
            **self.get_client_config(),
            'value': formatted_value,
            'raw_value': value,
            'trend': trend,
            'description': self.config.config.get('description', ''),
            'color': self.config.config.get('color', '#007bff'),
            'icon': self.config.config.get('icon', 'bar-chart')
        }


class ChartRenderer(WidgetRenderer):
    """Renderer for chart widgets"""
    
    async def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Render chart widget"""
        chart_type = self.config.config.get('chart_type', 'line')
        data_key = self.config.config.get('data_key', 'daily_data')
        
        chart_data = data.get(data_key, [])
        
        # Transform data based on chart type
        if chart_type == 'line' or chart_type == 'area':
            # Time series data
            if isinstance(chart_data, list) and chart_data:
                labels = []
                values = []
                
                for item in chart_data:
                    if isinstance(item, dict):
                        # Extract date and value
                        date_key = self.config.config.get('x_axis_key', 'date')
                        value_key = self.config.config.get('y_axis_key', 'value')
                        
                        if date_key in item and value_key in item:
                            labels.append(item[date_key])
                            values.append(item[value_key])
                
                chart_data = {
                    'labels': labels,
                    'datasets': [{
                        'label': self.config.config.get('series_label', 'Value'),
                        'data': values,
                        'borderColor': self.config.config.get('color', '#007bff'),
                        'backgroundColor': self.config.config.get('background_color', 'rgba(0, 123, 255, 0.1)'),
                        'fill': chart_type == 'area'
                    }]
                }
        
        elif chart_type == 'bar' or chart_type == 'column':
            # Categorical data
            if isinstance(chart_data, dict):
                labels = list(chart_data.keys())
                values = list(chart_data.values())
                
                chart_data = {
                    'labels': labels,
                    'datasets': [{
                        'label': self.config.config.get('series_label', 'Count'),
                        'data': values,
                        'backgroundColor': self.config.config.get('colors', [
                            '#007bff', '#28a745', '#ffc107', '#dc3545', '#17a2b8'
                        ])[:len(labels)]
                    }]
                }
        
        elif chart_type == 'pie' or chart_type == 'doughnut':
            # Pie chart data
            if isinstance(chart_data, dict):
                labels = list(chart_data.keys())
                values = list(chart_data.values())
                
                chart_data = {
                    'labels': labels,
                    'datasets': [{
                        'data': values,
                        'backgroundColor': self.config.config.get('colors', [
                            '#007bff', '#28a745', '#ffc107', '#dc3545', '#17a2b8',
                            '#6f42c1', '#e83e8c', '#fd7e14', '#20c997', '#6c757d'
                        ])[:len(labels)]
                    }]
                }
        
        return {
            **self.get_client_config(),
            'chart_type': chart_type,
            'data': chart_data,
            'options': self.config.config.get('chart_options', {})
        }


class TableRenderer(WidgetRenderer):
    """Renderer for table widgets"""
    
    async def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Render table widget"""
        data_key = self.config.config.get('data_key', 'items')
        table_data = data.get(data_key, [])
        
        columns = self.config.config.get('columns', [])
        if not columns and isinstance(table_data, list) and table_data:
            # Auto-generate columns from first item
            if isinstance(table_data[0], dict):
                columns = [
                    {'key': key, 'title': key.replace('_', ' ').title()}
                    for key in table_data[0].keys()
                ]
        
        # Apply sorting if configured
        sort_column = self.config.config.get('sort_column')
        sort_order = self.config.config.get('sort_order', 'asc')
        
        if sort_column and isinstance(table_data, list):
            reverse = sort_order == 'desc'
            table_data = sorted(
                table_data,
                key=lambda x: x.get(sort_column, ''),
                reverse=reverse
            )
        
        # Apply pagination if configured
        page_size = self.config.config.get('page_size', 10)
        if page_size > 0:
            table_data = table_data[:page_size]
        
        return {
            **self.get_client_config(),
            'columns': columns,
            'data': table_data,
            'total_rows': len(data.get(data_key, [])),
            'sortable': self.config.config.get('sortable', True),
            'searchable': self.config.config.get('searchable', True)
        }


class GaugeRenderer(WidgetRenderer):
    """Renderer for gauge widgets"""
    
    async def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Render gauge widget"""
        value_key = self.config.config.get('value_key', 'value')
        value = data.get(value_key, 0)
        
        min_value = self.config.config.get('min_value', 0)
        max_value = self.config.config.get('max_value', 100)
        
        # Calculate percentage
        percentage = ((value - min_value) / (max_value - min_value)) * 100
        percentage = max(0, min(100, percentage))
        
        # Determine color based on thresholds
        thresholds = self.config.config.get('thresholds', {
            'good': 80,
            'warning': 60,
            'critical': 40
        })
        
        if percentage >= thresholds.get('good', 80):
            color = self.config.config.get('good_color', '#28a745')
            status = 'good'
        elif percentage >= thresholds.get('warning', 60):
            color = self.config.config.get('warning_color', '#ffc107')
            status = 'warning'
        else:
            color = self.config.config.get('critical_color', '#dc3545')
            status = 'critical'
        
        return {
            **self.get_client_config(),
            'value': value,
            'percentage': percentage,
            'min_value': min_value,
            'max_value': max_value,
            'color': color,
            'status': status,
            'unit': self.config.config.get('unit', ''),
            'show_value': self.config.config.get('show_value', True)
        }


class AdvancedDashboard:
    """Advanced dashboard system with custom widgets and layouts"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("dashboard_config.json")
        self.data_sources: Dict[str, DataSource] = {}
        self.widget_renderers: Dict[WidgetType, Callable] = {
            WidgetType.METRIC_CARD: MetricCardRenderer,
            WidgetType.CHART: ChartRenderer,
            WidgetType.TABLE: TableRenderer,
            WidgetType.GAUGE: GaugeRenderer,
        }
        self.layouts: Dict[str, DashboardLayout] = {}
        self.active_subscriptions: Dict[str, asyncio.Task] = {}
        
        # Initialize default data sources
        self._init_default_data_sources()
        
        # Load saved configuration
        self.load_configuration()
    
    def _init_default_data_sources(self):
        """Initialize default data sources"""
        self.data_sources = {
            'productivity': ProductivityDataSource('productivity', {}),
            'health': HealthDataSource('health', {}),
            'tasks': TaskDataSource('tasks', {})
        }
    
    def add_data_source(self, source_id: str, data_source: DataSource):
        """Add a custom data source"""
        self.data_sources[source_id] = data_source
    
    def register_widget_renderer(self, widget_type: WidgetType, renderer_class: type):
        """Register a custom widget renderer"""
        self.widget_renderers[widget_type] = renderer_class
    
    async def create_layout(self, layout_config: Dict[str, Any]) -> str:
        """Create a new dashboard layout"""
        layout_id = layout_config.get('layout_id', f"layout_{len(self.layouts) + 1}")
        
        # Convert widget configs
        widgets = []
        for widget_data in layout_config.get('widgets', []):
            widget_config = WidgetConfig(
                widget_id=widget_data['widget_id'],
                widget_type=WidgetType(widget_data['widget_type']),
                title=widget_data['title'],
                data_source=widget_data['data_source'],
                position=widget_data['position'],
                update_frequency=UpdateFrequency(widget_data.get('update_frequency', 'normal')),
                config=widget_data.get('config', {}),
                filters=widget_data.get('filters', {}),
                permissions=widget_data.get('permissions', [])
            )
            widgets.append(widget_config)
        
        layout = DashboardLayout(
            layout_id=layout_id,
            name=layout_config['name'],
            description=layout_config.get('description', ''),
            widgets=widgets,
            grid_settings=layout_config.get('grid_settings', {}),
            theme=layout_config.get('theme', 'light'),
            auto_refresh=layout_config.get('auto_refresh', True),
            refresh_interval=layout_config.get('refresh_interval', 30),
            created_by=layout_config.get('created_by', 'system'),
            is_public=layout_config.get('is_public', False),
            tags=layout_config.get('tags', [])
        )
        
        self.layouts[layout_id] = layout
        self.save_configuration()
        
        return layout_id
    
    async def get_layout(self, layout_id: str) -> Optional[DashboardLayout]:
        """Get a dashboard layout"""
        return self.layouts.get(layout_id)
    
    async def update_layout(self, layout_id: str, updates: Dict[str, Any]):
        """Update a dashboard layout"""
        if layout_id not in self.layouts:
            raise ValueError(f"Layout {layout_id} not found")
        
        layout = self.layouts[layout_id]
        
        # Update basic properties
        if 'name' in updates:
            layout.name = updates['name']
        if 'description' in updates:
            layout.description = updates['description']
        if 'theme' in updates:
            layout.theme = updates['theme']
        if 'auto_refresh' in updates:
            layout.auto_refresh = updates['auto_refresh']
        if 'refresh_interval' in updates:
            layout.refresh_interval = updates['refresh_interval']
        
        # Update widgets
        if 'widgets' in updates:
            widgets = []
            for widget_data in updates['widgets']:
                widget_config = WidgetConfig(
                    widget_id=widget_data['widget_id'],
                    widget_type=WidgetType(widget_data['widget_type']),
                    title=widget_data['title'],
                    data_source=widget_data['data_source'],
                    position=widget_data['position'],
                    update_frequency=UpdateFrequency(widget_data.get('update_frequency', 'normal')),
                    config=widget_data.get('config', {}),
                    filters=widget_data.get('filters', {}),
                    permissions=widget_data.get('permissions', [])
                )
                widgets.append(widget_config)
            layout.widgets = widgets
        
        layout.updated_at = datetime.now()
        self.save_configuration()
    
    async def delete_layout(self, layout_id: str):
        """Delete a dashboard layout"""
        if layout_id in self.layouts:
            del self.layouts[layout_id]
            self.save_configuration()
    
    async def render_layout(self, layout_id: str, user_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Render a complete dashboard layout"""
        layout = await self.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout {layout_id} not found")
        
        rendered_widgets = []
        
        for widget_config in layout.widgets:
            try:
                rendered_widget = await self.render_widget(widget_config, user_filters)
                rendered_widgets.append(rendered_widget)
            except Exception as e:
                logger.error(f"Error rendering widget {widget_config.widget_id}: {e}")
                # Add error widget
                rendered_widgets.append({
                    'widget_id': widget_config.widget_id,
                    'widget_type': 'error',
                    'title': widget_config.title,
                    'position': widget_config.position,
                    'error': str(e)
                })
        
        return {
            'layout_id': layout.layout_id,
            'name': layout.name,
            'description': layout.description,
            'theme': layout.theme,
            'grid_settings': layout.grid_settings,
            'widgets': rendered_widgets,
            'auto_refresh': layout.auto_refresh,
            'refresh_interval': layout.refresh_interval,
            'rendered_at': datetime.now().isoformat()
        }
    
    async def render_widget(self, widget_config: WidgetConfig, user_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Render a single widget"""
        # Get data source
        data_source = self.data_sources.get(widget_config.data_source)
        if not data_source:
            raise ValueError(f"Data source {widget_config.data_source} not found")
        
        # Combine widget filters with user filters
        combined_filters = {**widget_config.filters}
        if user_filters:
            combined_filters.update(user_filters)
        
        # Get data from source
        data = await data_source.get_data(combined_filters)
        
        # Get renderer
        renderer_class = self.widget_renderers.get(widget_config.widget_type)
        if not renderer_class:
            raise ValueError(f"No renderer found for widget type {widget_config.widget_type}")
        
        # Render widget
        renderer = renderer_class(widget_config)
        rendered_data = await renderer.render(data)
        
        return rendered_data
    
    async def get_widget_data(self, widget_id: str, layout_id: str, user_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get data for a specific widget"""
        layout = await self.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout {layout_id} not found")
        
        # Find widget in layout
        widget_config = None
        for widget in layout.widgets:
            if widget.widget_id == widget_id:
                widget_config = widget
                break
        
        if not widget_config:
            raise ValueError(f"Widget {widget_id} not found in layout {layout_id}")
        
        return await self.render_widget(widget_config, user_filters)
    
    def list_layouts(self, user: str = None, tags: List[str] = None) -> List[Dict[str, Any]]:
        """List available dashboard layouts"""
        layouts = []
        
        for layout_id, layout in self.layouts.items():
            # Filter by user permissions (simplified)
            if user and not layout.is_public and layout.created_by != user:
                continue
            
            # Filter by tags
            if tags and not any(tag in layout.tags for tag in tags):
                continue
            
            layouts.append({
                'layout_id': layout.layout_id,
                'name': layout.name,
                'description': layout.description,
                'widget_count': len(layout.widgets),
                'theme': layout.theme,
                'created_by': layout.created_by,
                'is_public': layout.is_public,
                'tags': layout.tags,
                'created_at': layout.created_at.isoformat(),
                'updated_at': layout.updated_at.isoformat()
            })
        
        return sorted(layouts, key=lambda x: x['updated_at'], reverse=True)
    
    def get_available_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available data sources with their schemas"""
        sources = {}
        
        for source_id, source in self.data_sources.items():
            sources[source_id] = {
                'source_id': source_id,
                'type': source.__class__.__name__,
                'config': source.config
            }
        
        return sources
    
    async def get_data_source_schema(self, source_id: str) -> Dict[str, Any]:
        """Get schema for a data source"""
        source = self.data_sources.get(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        
        return await source.get_schema()
    
    def get_widget_types(self) -> List[Dict[str, Any]]:
        """Get available widget types"""
        return [
            {
                'type': widget_type.value,
                'name': widget_type.value.replace('_', ' ').title(),
                'description': self._get_widget_type_description(widget_type)
            }
            for widget_type in self.widget_renderers.keys()
        ]
    
    def _get_widget_type_description(self, widget_type: WidgetType) -> str:
        """Get description for widget type"""
        descriptions = {
            WidgetType.METRIC_CARD: "Display a single key metric with trend indicator",
            WidgetType.CHART: "Display data as line, bar, pie, or other chart types",
            WidgetType.TABLE: "Display tabular data with sorting and filtering",
            WidgetType.GAUGE: "Display a metric as a gauge with thresholds",
            WidgetType.HEATMAP: "Display data as a color-coded heatmap",
            WidgetType.PROGRESS: "Display progress towards a goal",
            WidgetType.LIST: "Display a list of items",
            WidgetType.CUSTOM: "Custom widget with user-defined rendering"
        }
        return descriptions.get(widget_type, "Custom widget type")
    
    def start_real_time_updates(self, layout_id: str, callback: Callable):
        """Start real-time updates for a layout"""
        if layout_id in self.active_subscriptions:
            # Cancel existing subscription
            self.active_subscriptions[layout_id].cancel()
        
        # Start new subscription
        task = asyncio.create_task(self._real_time_update_loop(layout_id, callback))
        self.active_subscriptions[layout_id] = task
    
    def stop_real_time_updates(self, layout_id: str):
        """Stop real-time updates for a layout"""
        if layout_id in self.active_subscriptions:
            self.active_subscriptions[layout_id].cancel()
            del self.active_subscriptions[layout_id]
    
    async def _real_time_update_loop(self, layout_id: str, callback: Callable):
        """Real-time update loop for a layout"""
        layout = await self.get_layout(layout_id)
        if not layout:
            return
        
        while True:
            try:
                # Find widgets that need real-time updates
                realtime_widgets = [
                    w for w in layout.widgets 
                    if w.update_frequency in [UpdateFrequency.REALTIME, UpdateFrequency.FAST]
                ]
                
                if realtime_widgets:
                    updates = {}
                    
                    for widget_config in realtime_widgets:
                        try:
                            rendered_widget = await self.render_widget(widget_config)
                            updates[widget_config.widget_id] = rendered_widget
                        except Exception as e:
                            logger.error(f"Error updating widget {widget_config.widget_id}: {e}")
                    
                    if updates:
                        await callback(layout_id, updates)
                
                # Wait based on fastest update frequency
                fastest_interval = min([
                    5 if w.update_frequency == UpdateFrequency.FAST else 1
                    for w in realtime_widgets
                ], default=30)
                
                await asyncio.sleep(fastest_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in real-time update loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    def save_configuration(self):
        """Save dashboard configuration to file"""
        try:
            config_data = {
                'layouts': {}
            }
            
            for layout_id, layout in self.layouts.items():
                config_data['layouts'][layout_id] = {
                    'layout_id': layout.layout_id,
                    'name': layout.name,
                    'description': layout.description,
                    'theme': layout.theme,
                    'grid_settings': layout.grid_settings,
                    'auto_refresh': layout.auto_refresh,
                    'refresh_interval': layout.refresh_interval,
                    'created_by': layout.created_by,
                    'is_public': layout.is_public,
                    'tags': layout.tags,
                    'created_at': layout.created_at.isoformat(),
                    'updated_at': layout.updated_at.isoformat(),
                    'widgets': [
                        {
                            'widget_id': w.widget_id,
                            'widget_type': w.widget_type.value,
                            'title': w.title,
                            'data_source': w.data_source,
                            'position': w.position,
                            'update_frequency': w.update_frequency.value,
                            'config': w.config,
                            'filters': w.filters,
                            'permissions': w.permissions,
                            'created_at': w.created_at.isoformat(),
                            'updated_at': w.updated_at.isoformat()
                        }
                        for w in layout.widgets
                    ]
                }
            
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving dashboard configuration: {e}")
    
    def load_configuration(self):
        """Load dashboard configuration from file"""
        try:
            if not self.config_path.exists():
                # Create default configuration
                self._create_default_layouts()
                return
            
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load layouts
            for layout_id, layout_data in config_data.get('layouts', {}).items():
                widgets = []
                for widget_data in layout_data.get('widgets', []):
                    widget_config = WidgetConfig(
                        widget_id=widget_data['widget_id'],
                        widget_type=WidgetType(widget_data['widget_type']),
                        title=widget_data['title'],
                        data_source=widget_data['data_source'],
                        position=widget_data['position'],
                        update_frequency=UpdateFrequency(widget_data.get('update_frequency', 'normal')),
                        config=widget_data.get('config', {}),
                        filters=widget_data.get('filters', {}),
                        permissions=widget_data.get('permissions', []),
                        created_at=datetime.fromisoformat(widget_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(widget_data.get('updated_at', datetime.now().isoformat()))
                    )
                    widgets.append(widget_config)
                
                layout = DashboardLayout(
                    layout_id=layout_data['layout_id'],
                    name=layout_data['name'],
                    description=layout_data.get('description', ''),
                    widgets=widgets,
                    grid_settings=layout_data.get('grid_settings', {}),
                    theme=layout_data.get('theme', 'light'),
                    auto_refresh=layout_data.get('auto_refresh', True),
                    refresh_interval=layout_data.get('refresh_interval', 30),
                    created_by=layout_data.get('created_by', 'system'),
                    is_public=layout_data.get('is_public', False),
                    tags=layout_data.get('tags', [])
                )
                
                self.layouts[layout_id] = layout
                
        except Exception as e:
            logger.error(f"Error loading dashboard configuration: {e}")
            self._create_default_layouts()
    
    def _create_default_layouts(self):
        """Create default dashboard layouts"""
        # Create productivity overview layout
        productivity_layout = {
            'layout_id': 'productivity_overview',
            'name': 'Productivity Overview',
            'description': 'Main productivity metrics and trends',
            'theme': 'light',
            'widgets': [
                {
                    'widget_id': 'productivity_score',
                    'widget_type': 'metric_card',
                    'title': 'Productivity Score',
                    'data_source': 'productivity',
                    'position': {'x': 0, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'metric_key': 'productivity_score',
                        'format': 'percentage',
                        'color': '#28a745',
                        'icon': 'trending-up'
                    }
                },
                {
                    'widget_id': 'focus_time',
                    'widget_type': 'metric_card',
                    'title': 'Daily Focus Time',
                    'data_source': 'productivity',
                    'position': {'x': 3, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'metric_key': 'focus_time_hours',
                        'format': 'time',
                        'color': '#007bff',
                        'icon': 'clock'
                    }
                },
                {
                    'widget_id': 'efficiency_gauge',
                    'widget_type': 'gauge',
                    'title': 'Efficiency Ratio',
                    'data_source': 'productivity',
                    'position': {'x': 6, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'value_key': 'efficiency_ratio',
                        'min_value': 0,
                        'max_value': 1,
                        'thresholds': {'good': 0.8, 'warning': 0.6, 'critical': 0.4}
                    }
                },
                {
                    'widget_id': 'daily_productivity_chart',
                    'widget_type': 'chart',
                    'title': 'Daily Productivity Trend',
                    'data_source': 'productivity',
                    'position': {'x': 0, 'y': 2, 'width': 6, 'height': 4},
                    'config': {
                        'chart_type': 'line',
                        'data_key': 'daily_averages',
                        'color': '#28a745'
                    }
                }
            ]
        }
        
        asyncio.run(self.create_layout(productivity_layout))
        
        # Create wellness dashboard layout
        wellness_layout = {
            'layout_id': 'wellness_dashboard',
            'name': 'Wellness Dashboard',
            'description': 'Health and wellness metrics',
            'theme': 'light',
            'widgets': [
                {
                    'widget_id': 'wellness_score',
                    'widget_type': 'metric_card',
                    'title': 'Wellness Score',
                    'data_source': 'health',
                    'position': {'x': 0, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'metric_key': 'wellness_score',
                        'format': 'number',
                        'color': '#17a2b8',
                        'icon': 'heart'
                    }
                },
                {
                    'widget_id': 'sleep_hours',
                    'widget_type': 'metric_card',
                    'title': 'Average Sleep',
                    'data_source': 'health',
                    'position': {'x': 3, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'metric_key': 'average_sleep_hours',
                        'format': 'time',
                        'color': '#6f42c1',
                        'icon': 'moon'
                    }
                },
                {
                    'widget_id': 'stress_gauge',
                    'widget_type': 'gauge',
                    'title': 'Stress Level',
                    'data_source': 'health',
                    'position': {'x': 6, 'y': 0, 'width': 3, 'height': 2},
                    'config': {
                        'value_key': 'average_stress_level',
                        'min_value': 1,
                        'max_value': 10,
                        'thresholds': {'good': 3, 'warning': 6, 'critical': 8}
                    }
                }
            ]
        }
        
        asyncio.run(self.create_layout(wellness_layout))
    
    def cleanup(self):
        """Cleanup resources"""
        # Cancel all active subscriptions
        for task in self.active_subscriptions.values():
            task.cancel()
        self.active_subscriptions.clear()
        
        # Clear data source caches
        for source in self.data_sources.values():
            source.invalidate_cache()


# Example usage and testing functions
async def example_usage():
    """Example usage of the advanced dashboard system"""
    
    # Create dashboard instance
    dashboard = AdvancedDashboard()
    
    # List available layouts
    layouts = dashboard.list_layouts()
    print(f"Available layouts: {len(layouts)}")
    
    # Render productivity overview
    if layouts:
        layout_id = layouts[0]['layout_id']
        rendered = await dashboard.render_layout(layout_id)
        print(f"Rendered layout: {rendered['name']} with {len(rendered['widgets'])} widgets")
    
    # Create a custom layout
    custom_layout = {
        'layout_id': 'custom_dashboard',
        'name': 'Custom Dashboard',
        'description': 'A custom dashboard with task metrics',
        'widgets': [
            {
                'widget_id': 'task_completion_rate',
                'widget_type': 'metric_card',
                'title': 'Task Completion Rate',
                'data_source': 'tasks',
                'position': {'x': 0, 'y': 0, 'width': 4, 'height': 2},
                'config': {
                    'metric_key': 'completion_rate',
                    'format': 'percentage',
                    'color': '#28a745'
                }
            },
            {
                'widget_id': 'task_status_chart',
                'widget_type': 'chart',
                'title': 'Tasks by Status',
                'data_source': 'tasks',
                'position': {'x': 4, 'y': 0, 'width': 4, 'height': 4},
                'config': {
                    'chart_type': 'pie',
                    'data_key': 'task_counts_by_status'
                }
            }
        ]
    }
    
    custom_layout_id = await dashboard.create_layout(custom_layout)
    print(f"Created custom layout: {custom_layout_id}")
    
    # Render custom layout
    custom_rendered = await dashboard.render_layout(custom_layout_id)
    print(f"Custom layout has {len(custom_rendered['widgets'])} widgets")
    
    # Get data sources
    sources = dashboard.get_available_data_sources()
    print(f"Available data sources: {list(sources.keys())}")
    
    # Cleanup
    dashboard.cleanup()


if __name__ == "__main__":
    asyncio.run(example_usage())