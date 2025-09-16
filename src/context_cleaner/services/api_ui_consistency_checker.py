"""
API/UI Consistency Checker

This module provides comprehensive monitoring of API endpoint availability
versus dashboard UI display consistency. It helps identify when APIs return
valid data but the dashboard UI shows loading states or stale data.
"""

import asyncio
import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from datetime import datetime, timedelta

try:
    from ..config.settings import ContextCleanerConfig
except ImportError:
    # Fallback for testing
    ContextCleanerConfig = None


class ConsistencyStatus(Enum):
    CONSISTENT = "consistent"
    API_WORKING_UI_LOADING = "api_working_ui_loading"
    API_ERROR_UI_SHOWING_DATA = "api_error_ui_showing_data"
    BOTH_FAILING = "both_failing"
    UNKNOWN = "unknown"


@dataclass
class APIEndpointTest:
    """Configuration for testing a specific API endpoint"""
    path: str
    method: str = "GET"
    expected_keys: List[str] = field(default_factory=list)
    timeout: float = 5.0
    critical: bool = True
    
    
@dataclass
class ConsistencyCheckResult:
    """Result of an API/UI consistency check"""
    endpoint: str
    api_status: str
    api_response_time: float
    api_data_size: int
    api_error: Optional[str]
    ui_status: str
    ui_error: Optional[str]
    consistency_status: ConsistencyStatus
    timestamp: datetime
    recommendations: List[str] = field(default_factory=list)


class APIUIConsistencyChecker:
    """
    Monitors consistency between API endpoints and dashboard UI display.
    
    This service tests all dashboard API endpoints and attempts to verify
    that the UI is properly consuming and displaying the data.
    """
    
    def __init__(self, config: Optional[ContextCleanerConfig] = None, dashboard_host: str = "127.0.0.1", dashboard_port: int = 8080):
        # Use default config if none provided
        if config is None and ContextCleanerConfig is not None:
            self.config = ContextCleanerConfig.default()
        else:
            self.config = config
        self.dashboard_host = dashboard_host
        self.dashboard_port = dashboard_port
        self.base_url = f"http://{dashboard_host}:{dashboard_port}"
        self.logger = logging.getLogger(__name__)
        
        # Define all dashboard API endpoints to test
        self.api_endpoints = self._define_api_endpoints()
        
        # Results storage
        self.last_check_results: Dict[str, ConsistencyCheckResult] = {}
        self.check_history: List[Dict[str, ConsistencyCheckResult]] = []
        
        # Check intervals
        self.check_interval = 30.0  # seconds
        self.ui_check_timeout = 10.0  # seconds
        self.startup_delay = 15.0  # seconds - wait for dashboard to be ready
        
    def _define_api_endpoints(self) -> List[APIEndpointTest]:
        """Define all API endpoints that should be tested - these are the ACTUAL endpoints discovered from dashboard HTML"""
        return [
            # Core dashboard analytics endpoints
            APIEndpointTest("/api/dashboard-metrics", expected_keys=["active_agents", "last_updated", "model_efficiency", "orchestration_status", "success_rate"]),
            APIEndpointTest("/api/context-window-usage", expected_keys=["active_directories", "directories", "estimated_total_tokens", "success", "total_size_mb"]),
            APIEndpointTest("/api/conversation-analytics", expected_keys=["last_updated", "range", "summary", "timeline"]),
            APIEndpointTest("/api/code-patterns-analytics", expected_keys=["last_updated", "patterns"]),
            APIEndpointTest("/api/content-search", method="GET", expected_keys=["results", "status", "message"]),
            
            # Analytics endpoints
            APIEndpointTest("/api/analytics/context-health", expected_keys=["compression_rate", "context_size_kb", "error_rate", "relevance_score", "sessions_today"]),
            APIEndpointTest("/api/analytics/performance-trends", expected_keys=["cache_hit_rate", "events_prev_week", "events_this_week", "response_time_seconds", "status"]),
            
            # JSONL processing endpoints
            APIEndpointTest("/api/jsonl-processing-status", expected_keys=["database_healthy", "error_rate", "last_updated", "privacy_level", "processing_rate"]),
            
            # Telemetry widget endpoints (actual working endpoints)
            APIEndpointTest("/api/telemetry-widget/code-pattern-analysis", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            APIEndpointTest("/api/telemetry-widget/content-search-widget", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            APIEndpointTest("/api/telemetry-widget/conversation-timeline", expected_keys=["alerts", "data", "last_updated", "status", "title"]),
            
            # Telemetry analytics endpoints
            APIEndpointTest("/api/telemetry/error-details?hours=24", expected_keys=["error_breakdown", "error_summary", "raw_breakdown", "recent_errors"]),
            APIEndpointTest("/api/telemetry/model-analytics", expected_keys=["avg_response_time", "cost_efficiency_ratio", "cost_per_query_type", "detailed_analytics_available", "efficiency_score"]),
            APIEndpointTest("/api/telemetry/tool-analytics", expected_keys=["common_sequences", "efficiency_score", "optimization_suggestions", "tool_usage_stats"]),
            
            # Data explorer endpoint (now supports GET for health checks)
            APIEndpointTest("/api/data-explorer/query", method="GET", expected_keys=["status", "message", "example_query"], critical=False),
        ]
        
    async def test_api_endpoint(self, endpoint_test: APIEndpointTest) -> Tuple[str, float, int, Optional[str], Any]:
        """
        Test a single API endpoint and return status, response time, data size, error, and response data
        """
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=endpoint_test.timeout)) as session:
                url = f"{self.base_url}{endpoint_test.path}"
                
                async with session.request(endpoint_test.method, url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            data_size = len(json.dumps(data))
                            
                            # Check if expected keys are present
                            missing_keys = []
                            for key in endpoint_test.expected_keys:
                                if key not in data:
                                    missing_keys.append(key)
                            
                            if missing_keys:
                                return "partial", response_time, data_size, f"Missing keys: {missing_keys}", data
                            
                            return "success", response_time, data_size, None, data
                            
                        except json.JSONDecodeError as e:
                            return "invalid_json", response_time, 0, f"JSON decode error: {str(e)}", None
                            
                    else:
                        error_text = await response.text()
                        return "error", response_time, len(error_text), f"HTTP {response.status}: {error_text}", None
                        
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return "timeout", response_time, 0, f"Request timeout after {endpoint_test.timeout}s", None
            
        except Exception as e:
            response_time = time.time() - start_time
            return "error", response_time, 0, str(e), None
    
    async def check_ui_widget_status(self, endpoint_path: str) -> Tuple[str, Optional[str]]:
        """
        Attempt to check if UI widgets are properly displaying data
        This is a simplified check - in a full implementation, you'd use browser automation
        """
        try:
            # For now, we'll check if the main dashboard page loads
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.ui_check_timeout)) as session:
                async with session.get(self.base_url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        
                        # Simple heuristic checks
                        if "Loading..." in html_content:
                            return "loading", "Dashboard HTML contains 'Loading...' text"
                        elif "Error" in html_content or "error" in html_content.lower():
                            return "error", "Dashboard HTML contains error indicators"
                        elif len(html_content) < 1000:
                            return "minimal", "Dashboard HTML is suspiciously small"
                        else:
                            return "loaded", None
                    else:
                        return "error", f"Dashboard returned HTTP {response.status}"
                        
        except Exception as e:
            return "error", str(e)

    async def wait_for_dashboard_ready(self, max_wait: float = 60.0, check_interval: float = 2.0) -> bool:
        """Wait for the dashboard to be ready before starting consistency checks"""
        self.logger.info(f"Waiting for dashboard at {self.base_url} to be ready...")

        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5.0)) as session:
                    async with session.get(self.base_url) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            if len(html_content) > 1000:  # Basic check that we got a real dashboard
                                self.logger.info("✅ Dashboard is ready for consistency monitoring")
                                return True

            except Exception as e:
                self.logger.debug(f"Dashboard not ready yet: {e}")

            await asyncio.sleep(check_interval)

        self.logger.warning(f"Dashboard not ready after {max_wait}s, proceeding anyway")
        return False
    
    def determine_consistency_status(self, api_status: str, ui_status: str, api_data_size: int) -> ConsistencyStatus:
        """Determine the overall consistency status"""
        
        if api_status == "success" and ui_status == "loaded" and api_data_size > 0:
            return ConsistencyStatus.CONSISTENT
            
        elif api_status == "success" and api_data_size > 0 and ui_status in ["loading", "minimal"]:
            return ConsistencyStatus.API_WORKING_UI_LOADING
            
        elif api_status in ["error", "timeout"] and ui_status == "loaded":
            return ConsistencyStatus.API_ERROR_UI_SHOWING_DATA
            
        elif api_status in ["error", "timeout"] and ui_status in ["error", "loading"]:
            return ConsistencyStatus.BOTH_FAILING
            
        else:
            return ConsistencyStatus.UNKNOWN
    
    def generate_recommendations(self, result: ConsistencyCheckResult) -> List[str]:
        """Generate actionable recommendations based on the consistency check"""
        recommendations = []
        
        if result.consistency_status == ConsistencyStatus.API_WORKING_UI_LOADING:
            recommendations.extend([
                "API is returning data but UI shows loading state",
                "Check JavaScript console for frontend errors", 
                "Verify WebSocket connections for real-time updates",
                "Check if frontend is properly consuming API endpoints",
                "Consider clearing browser cache or restarting dashboard service"
            ])
            
        elif result.consistency_status == ConsistencyStatus.API_ERROR_UI_SHOWING_DATA:
            recommendations.extend([
                "UI is showing data but API is failing",
                "UI may be showing cached/stale data",
                "Check API endpoint implementation",
                "Verify database connections for API endpoints"
            ])
            
        elif result.consistency_status == ConsistencyStatus.BOTH_FAILING:
            recommendations.extend([
                "Both API and UI are failing",
                "Check dashboard service health",
                "Verify database connectivity", 
                "Check for system resource issues",
                "Consider restarting dashboard service"
            ])
            
        if result.api_response_time > 5.0:
            recommendations.append(f"API response time is slow ({result.api_response_time:.2f}s)")
            
        if result.api_data_size == 0 and result.api_status == "success":
            recommendations.append("API returned empty data - check data sources")
            
        return recommendations
    
    async def run_consistency_check(self) -> Dict[str, ConsistencyCheckResult]:
        """Run a comprehensive consistency check on all endpoints"""
        
        self.logger.info(f"Starting API/UI consistency check for {len(self.api_endpoints)} endpoints")
        
        results = {}
        
        for endpoint_test in self.api_endpoints:
            self.logger.debug(f"Testing endpoint: {endpoint_test.path}")
            
            # Test the API endpoint
            api_status, response_time, data_size, api_error, api_data = await self.test_api_endpoint(endpoint_test)
            
            # Check UI status (simplified for this endpoint)
            ui_status, ui_error = await self.check_ui_widget_status(endpoint_test.path)
            
            # Determine consistency status
            consistency_status = self.determine_consistency_status(api_status, ui_status, data_size)
            
            # Create result
            result = ConsistencyCheckResult(
                endpoint=endpoint_test.path,
                api_status=api_status,
                api_response_time=response_time,
                api_data_size=data_size,
                api_error=api_error,
                ui_status=ui_status,
                ui_error=ui_error,
                consistency_status=consistency_status,
                timestamp=datetime.now()
            )
            
            # Generate recommendations
            result.recommendations = self.generate_recommendations(result)
            
            results[endpoint_test.path] = result
            
        # Store results
        self.last_check_results = results
        self.check_history.append({
            "timestamp": datetime.now(),
            "results": results.copy()
        })
        
        # Keep only last 50 checks in history
        if len(self.check_history) > 50:
            self.check_history = self.check_history[-50:]
            
        self.logger.info(f"Consistency check completed. Found {self._count_inconsistencies(results)} inconsistencies")
        
        return results
    
    def _count_inconsistencies(self, results: Dict[str, ConsistencyCheckResult]) -> int:
        """Count the number of inconsistencies found"""
        return len([r for r in results.values() 
                   if r.consistency_status != ConsistencyStatus.CONSISTENT])
    
    def get_critical_issues(self) -> List[ConsistencyCheckResult]:
        """Get list of critical consistency issues that need immediate attention"""
        critical_issues = []
        
        for result in self.last_check_results.values():
            if result.consistency_status == ConsistencyStatus.API_WORKING_UI_LOADING:
                critical_issues.append(result)
            elif result.consistency_status == ConsistencyStatus.BOTH_FAILING:
                critical_issues.append(result)
                
        return critical_issues
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of the consistency check results"""
        if not self.last_check_results:
            return {"error": "No consistency check results available"}
            
        total_endpoints = len(self.last_check_results)
        consistent_count = len([r for r in self.last_check_results.values() 
                               if r.consistency_status == ConsistencyStatus.CONSISTENT])
        
        inconsistent_count = total_endpoints - consistent_count
        
        # Group by consistency status
        status_counts = {}
        for status in ConsistencyStatus:
            status_counts[status.value] = len([r for r in self.last_check_results.values() 
                                              if r.consistency_status == status])
        
        # Get worst offenders (slowest APIs)
        slow_apis = sorted([r for r in self.last_check_results.values()], 
                          key=lambda x: x.api_response_time, reverse=True)[:5]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_endpoints": total_endpoints,
            "consistent_endpoints": consistent_count,
            "inconsistent_endpoints": inconsistent_count,
            "consistency_percentage": (consistent_count / total_endpoints) * 100,
            "status_breakdown": status_counts,
            "critical_issues": len(self.get_critical_issues()),
            "slowest_apis": [
                {
                    "endpoint": r.endpoint,
                    "response_time": r.api_response_time,
                    "status": r.api_status
                } for r in slow_apis
            ],
            "recommendations": self._get_top_recommendations()
        }
    
    def _get_top_recommendations(self) -> List[str]:
        """Get the most common recommendations across all endpoints"""
        all_recommendations = []
        for result in self.last_check_results.values():
            all_recommendations.extend(result.recommendations)
            
        # Count recommendations and return most common ones
        from collections import Counter
        recommendation_counts = Counter(all_recommendations)
        return [rec for rec, count in recommendation_counts.most_common(10)]
    
    async def start_monitoring(self):
        """Start continuous monitoring of API/UI consistency"""
        self.logger.info("Starting API/UI consistency monitoring...")

        # Wait for dashboard to be ready before starting checks
        await self.wait_for_dashboard_ready()

        while True:
            try:
                await self.run_consistency_check()
                
                # Log critical issues
                critical_issues = self.get_critical_issues()
                if critical_issues:
                    self.logger.warning(f"Found {len(critical_issues)} critical API/UI consistency issues:")
                    for issue in critical_issues:
                        self.logger.warning(f"  {issue.endpoint}: {issue.consistency_status.value}")
                        
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in consistency monitoring loop: {str(e)}")
                await asyncio.sleep(self.check_interval)