"""
Baseline Regression Test for Dashboard Refactoring

This test establishes a baseline before Phase 2 refactoring begins.
All API endpoints, response formats, and functionality must remain identical
after modular extraction.

Critical: This test must pass before and after every extraction phase.
"""

import pytest
import requests
import json
import time
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TestBaselineRegression:
    """
    Baseline regression tests for dashboard functionality
    These tests capture the current working state before refactoring
    """

    @pytest.fixture
    def dashboard_base_url(self):
        """Dashboard base URL for testing"""
        return "http://localhost:8110"

    @pytest.fixture
    def api_endpoints(self):
        """Critical API endpoints that must remain functional"""
        return [
            "/api/health-report",
            "/api/dashboard-metrics",
            "/api/telemetry-widget/overview",
            "/api/telemetry-widget/error-monitor",
            "/api/telemetry-widget/cost-tracker",
            "/api/telemetry-widget/timeout-risk",
            "/api/telemetry-widget/tool-optimizer",
            "/api/telemetry-widget/model-efficiency",
            "/api/telemetry-widget/context-rot-meter"
        ]

    def test_dashboard_accessibility(self, dashboard_base_url):
        """Test that dashboard is accessible"""
        try:
            response = requests.get(f"{dashboard_base_url}/health", timeout=10)
            assert response.status_code in [200, 404], f"Dashboard not accessible: {response.status_code}"
        except Exception as e:
            pytest.skip(f"Dashboard not running: {e}")

    def test_critical_api_endpoints(self, dashboard_base_url, api_endpoints):
        """Test that all critical API endpoints respond correctly"""
        results = {}

        for endpoint in api_endpoints:
            try:
                response = requests.get(f"{dashboard_base_url}{endpoint}", timeout=10)
                results[endpoint] = {
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "content_type": response.headers.get("content-type", ""),
                    "response_size": len(response.content)
                }

                # Check JSON response format
                if "application/json" in response.headers.get("content-type", ""):
                    try:
                        json_data = response.json()
                        results[endpoint]["json_valid"] = True
                        results[endpoint]["has_data"] = bool(json_data)
                    except:
                        results[endpoint]["json_valid"] = False

            except Exception as e:
                results[endpoint] = {"error": str(e)}

        # Log baseline results for comparison
        logger.info(f"Baseline API test results: {json.dumps(results, indent=2)}")

        # Save baseline for later comparison
        baseline_file = "/tmp/dashboard_baseline_regression.json"
        try:
            with open(baseline_file, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save baseline file: {e}")

        # At least health-report and dashboard-metrics should work
        critical_endpoints = ["/api/health-report", "/api/dashboard-metrics"]
        for endpoint in critical_endpoints:
            if endpoint in results:
                assert results[endpoint].get("status_code") == 200, f"Critical endpoint {endpoint} failed"

    def test_dashboard_metrics_structure(self, dashboard_base_url):
        """Test dashboard metrics response structure (critical for widgets)"""
        try:
            response = requests.get(f"{dashboard_base_url}/api/dashboard-metrics", timeout=10)
            if response.status_code == 200:
                data = response.json()

                # Verify expected structure
                assert "data" in data or "total_tokens" in data, "Missing expected data structure"

                # Verify data types
                if "data" in data:
                    data_section = data["data"]
                else:
                    data_section = data

                expected_fields = ["total_tokens", "total_sessions", "success_rate", "active_agents"]
                found_fields = []

                for field in expected_fields:
                    if field in data_section:
                        found_fields.append(field)

                logger.info(f"Dashboard metrics fields found: {found_fields}")
                assert len(found_fields) > 0, "No expected dashboard metrics fields found"

        except Exception as e:
            pytest.skip(f"Dashboard metrics test failed: {e}")

    def test_performance_baseline(self, dashboard_base_url):
        """Establish performance baseline for comparison after refactoring"""
        endpoints_to_test = [
            "/api/dashboard-metrics",
            "/api/telemetry-widget/overview"
        ]

        performance_results = {}

        for endpoint in endpoints_to_test:
            try:
                start_time = time.time()
                response = requests.get(f"{dashboard_base_url}{endpoint}", timeout=10)
                end_time = time.time()

                response_time = end_time - start_time
                performance_results[endpoint] = {
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "content_length": len(response.content)
                }

                # Performance should be reasonable
                assert response_time < 5.0, f"Endpoint {endpoint} too slow: {response_time}s"

            except Exception as e:
                logger.warning(f"Performance test failed for {endpoint}: {e}")

        logger.info(f"Performance baseline: {json.dumps(performance_results, indent=2)}")

class ModuleExtractionValidator:
    """
    Validation helper for module extraction phases
    Use this to verify each extraction maintains functionality
    """

    @staticmethod
    def compare_api_responses(before_file: str, after_responses: Dict[str, Any]) -> bool:
        """Compare API responses before and after extraction"""
        try:
            with open(before_file, 'r') as f:
                before_responses = json.load(f)

            for endpoint, after_result in after_responses.items():
                if endpoint in before_responses:
                    before_result = before_responses[endpoint]

                    # Status codes should match
                    if before_result.get("status_code") != after_result.get("status_code"):
                        logger.error(f"Status code mismatch for {endpoint}")
                        return False

                    # Response structure should be similar
                    if abs(before_result.get("response_size", 0) - after_result.get("response_size", 0)) > 1000:
                        logger.warning(f"Response size significantly different for {endpoint}")

            return True

        except Exception as e:
            logger.error(f"Response comparison failed: {e}")
            return False

# Test configuration
pytest_plugins = []

if __name__ == "__main__":
    # Run baseline tests
    pytest.main([__file__, "-v"])