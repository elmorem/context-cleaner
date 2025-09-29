#!/usr/bin/env python3
"""
Widget Data Flow Debug Script

This script helps debug and verify the data staleness issues in Context Cleaner dashboard widgets.
It tests all widget endpoints, checks data freshness, and provides detailed logging.

Usage:
    python debug_widget_data_flow.py --dashboard-port 8110 --verbose
"""

import argparse
import asyncio
import json
import logging
import requests
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WidgetDataFlowTester:
    """Test widget data flow and diagnose staleness issues"""

    def __init__(self, base_url: str = "http://localhost:8110"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 30

    def test_dashboard_health(self) -> Dict[str, Any]:
        """Test basic dashboard health and connectivity"""
        logger.info("Testing dashboard health...")

        try:
            response = self.session.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            health_data = response.json()

            logger.info(f"Dashboard health: {health_data.get('status', 'unknown')}")
            return health_data

        except Exception as e:
            logger.error(f"Dashboard health check failed: {e}")
            return {"status": "error", "error": str(e)}

    def test_telemetry_availability(self) -> Dict[str, Any]:
        """Test telemetry system availability"""
        logger.info("Testing telemetry availability...")

        try:
            response = self.session.get(f"{self.base_url}/api/telemetry/data-freshness")
            if response.status_code == 404:
                logger.warning("Telemetry not available (404) - telemetry stack may not be initialised")
                return {"available": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            freshness_data = response.json()

            logger.info("Telemetry system is available")
            return {"available": True, "freshness_data": freshness_data}

        except Exception as e:
            logger.error(f"Telemetry availability check failed: {e}")
            return {"available": False, "error": str(e)}

    def test_widget_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """Test all widget endpoints"""
        logger.info("Testing widget endpoints...")

        widget_endpoints = [
            "error-monitor",
            "cost-tracker",
            "timeout-risk",
            "tool-optimizer",
            "model-efficiency",
            "context-rot-meter"
        ]

        results = {}

        for widget_type in widget_endpoints:
            logger.info(f"Testing widget: {widget_type}")

            try:
                url = f"{self.base_url}/api/telemetry-widget/{widget_type}"
                response = self.session.get(url, params={"timeRange": "7days"})

                result = {
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                    "timestamp": datetime.now().isoformat()
                }

                if response.status_code == 200:
                    data = response.json()
                    result["success"] = True
                    result["widget_status"] = data.get("status", "unknown")
                    result["title"] = data.get("title", "Unknown")
                    result["last_updated"] = data.get("last_updated")
                    result["alerts"] = data.get("alerts", [])
                    result["data_keys"] = list(data.get("data", {}).keys())

                    # Check for fallback/error indicators
                    widget_data = data.get("data", {})
                    if "error" in widget_data:
                        result["is_fallback"] = True
                        result["error_message"] = widget_data["error"]
                    elif "fallback_mode" in widget_data:
                        result["is_fallback"] = widget_data["fallback_mode"]
                    else:
                        result["is_fallback"] = False

                    # Check for zero values (staleness indicators)
                    zero_fields = []
                    for key, value in widget_data.items():
                        if isinstance(value, (int, float)) and value == 0:
                            zero_fields.append(key)
                    result["zero_fields"] = zero_fields

                    logger.info(f"  ✓ {widget_type}: {result['widget_status']} (fallback: {result['is_fallback']})")
                    if zero_fields:
                        logger.warning(f"    Zero fields detected: {zero_fields}")
                else:
                    result["success"] = False
                    result["error"] = response.text
                    logger.error(f"  ✗ {widget_type}: HTTP {response.status_code}")

                results[widget_type] = result

            except Exception as e:
                logger.error(f"  ✗ {widget_type}: Exception - {e}")
                results[widget_type] = {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

        return results

    def test_data_freshness_api(self) -> Dict[str, Any]:
        """Test the data freshness API we implemented"""
        logger.info("Testing data freshness API...")

        try:
            response = self.session.get(f"{self.base_url}/api/telemetry/data-freshness")

            if response.status_code == 404:
                logger.warning("Data freshness API not available - telemetry disabled")
                return {"available": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            freshness_data = response.json()

            logger.info("Data freshness report retrieved successfully")

            # Analyze freshness data
            analysis = {
                "available": True,
                "service_availability": freshness_data.get("service_availability", {}),
                "cached_widgets": freshness_data.get("cache_status", {}).get("cached_widgets", 0),
                "fallback_widgets": len(freshness_data.get("fallback_detection", {})),
                "fresh_widgets": len(freshness_data.get("data_freshness", {})),
                "raw_data": freshness_data
            }

            # Log key findings
            service_availability = analysis["service_availability"]
            logger.info(f"Service availability: {service_availability}")
            logger.info(f"Cached widgets: {analysis['cached_widgets']}")
            logger.info(f"Fallback widgets: {analysis['fallback_widgets']}")
            logger.info(f"Fresh widgets: {analysis['fresh_widgets']}")

            return analysis

        except Exception as e:
            logger.error(f"Data freshness API test failed: {e}")
            return {"available": False, "error": str(e)}

    def test_widget_health_summary(self) -> Dict[str, Any]:
        """Test the widget health summary API"""
        logger.info("Testing widget health summary...")

        try:
            response = self.session.get(f"{self.base_url}/api/telemetry/widget-health")

            if response.status_code == 404:
                logger.warning("Widget health API not available - telemetry disabled")
                return {"available": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            health_data = response.json()

            logger.info("Widget health summary retrieved successfully")

            # Analyze health data
            widget_health = health_data.get("widget_health", {})
            error_widgets = [name for name, status in widget_health.items() if "Error" in status]
            fresh_widgets = [name for name, status in widget_health.items() if "Fresh" in status]
            not_loaded_widgets = [name for name, status in widget_health.items() if "Not yet loaded" in status]

            analysis = {
                "available": True,
                "overall_status": health_data.get("overall_status", "unknown"),
                "total_widgets": len(widget_health),
                "error_widgets": error_widgets,
                "fresh_widgets": fresh_widgets,
                "not_loaded_widgets": not_loaded_widgets,
                "raw_data": health_data
            }

            logger.info(f"Overall status: {analysis['overall_status']}")
            logger.info(f"Error widgets: {error_widgets}")
            logger.info(f"Fresh widgets: {fresh_widgets}")
            logger.info(f"Not loaded widgets: {not_loaded_widgets}")

            return analysis

        except Exception as e:
            logger.error(f"Widget health summary test failed: {e}")
            return {"available": False, "error": str(e)}

    def clear_widget_cache(self) -> Dict[str, Any]:
        """Clear widget cache to test fresh data retrieval"""
        logger.info("Clearing widget cache...")

        try:
            response = self.session.post(f"{self.base_url}/api/telemetry/clear-cache")

            if response.status_code == 404:
                logger.warning("Cache clear API not available - telemetry disabled")
                return {"success": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            result = response.json()

            logger.info("Widget cache cleared successfully")
            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return {"success": False, "error": str(e)}

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        logger.info("🔍 Starting comprehensive widget data flow test...")

        test_results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard_url": self.base_url,
            "tests": {}
        }

        # Test 1: Dashboard Health
        test_results["tests"]["dashboard_health"] = self.test_dashboard_health()

        # Test 2: Telemetry Availability
        test_results["tests"]["telemetry_availability"] = self.test_telemetry_availability()

        # Test 3: Widget Endpoints
        test_results["tests"]["widget_endpoints"] = self.test_widget_endpoints()

        # Test 4: Data Freshness API
        test_results["tests"]["data_freshness"] = self.test_data_freshness_api()

        # Test 5: Widget Health Summary
        test_results["tests"]["widget_health"] = self.test_widget_health_summary()

        # Test 6: Cache Clear (if available)
        if test_results["tests"]["telemetry_availability"].get("available"):
            logger.info("Clearing cache and retesting...")
            test_results["tests"]["cache_clear"] = self.clear_widget_cache()

            # Re-test one widget after cache clear
            time.sleep(2)  # Give cache clear time to take effect
            logger.info("Retesting error-monitor widget after cache clear...")
            try:
                response = self.session.get(f"{self.base_url}/api/telemetry-widget/error-monitor")
                if response.status_code == 200:
                    data = response.json()
                    test_results["tests"]["post_cache_clear_test"] = {
                        "success": True,
                        "status": data.get("status"),
                        "last_updated": data.get("last_updated")
                    }
                    logger.info(f"Post-cache clear test: {data.get('status')}")
            except Exception as e:
                test_results["tests"]["post_cache_clear_test"] = {
                    "success": False,
                    "error": str(e)
                }

        return test_results

    def analyze_results(self, results: Dict[str, Any]) -> None:
        """Analyze test results and provide recommendations"""
        logger.info("📊 Analyzing test results...")

        # Count widget issues
        widget_tests = results["tests"].get("widget_endpoints", {})
        total_widgets = len(widget_tests)
        successful_widgets = len([w for w in widget_tests.values() if w.get("success")])
        fallback_widgets = len([w for w in widget_tests.values() if w.get("is_fallback")])
        zero_value_widgets = len([w for w in widget_tests.values() if w.get("zero_fields")])

        # Summary
        print("\n" + "="*60)
        print("🔍 WIDGET DATA STALENESS ANALYSIS SUMMARY")
        print("="*60)
        print(f"Dashboard URL: {results['dashboard_url']}")
        print(f"Test Time: {results['timestamp']}")
        print()

        # Dashboard connectivity
        dashboard_health = results["tests"].get("dashboard_health", {})
        print(f"📡 Dashboard Health: {dashboard_health.get('status', 'unknown')}")

        # Telemetry availability
        telemetry_avail = results["tests"].get("telemetry_availability", {})
        if telemetry_avail.get("available"):
            print("✅ Telemetry System: Available")
        else:
            print(f"❌ Telemetry System: Unavailable - {telemetry_avail.get('reason', 'unknown')}")

        # Widget performance
        print(f"\n📊 Widget Status: {successful_widgets}/{total_widgets} successful")
        print(f"⚠️  Fallback Mode: {fallback_widgets} widgets")
        print(f"🔄 Zero Values: {zero_value_widgets} widgets showing zeros")

        # Specific issues
        print("\n🔍 Specific Widget Issues:")
        for widget_name, widget_data in widget_tests.items():
            if not widget_data.get("success"):
                print(f"  ❌ {widget_name}: {widget_data.get('error', 'unknown error')}")
            elif widget_data.get("is_fallback"):
                print(f"  ⚠️  {widget_name}: Running in fallback mode")
            elif widget_data.get("zero_fields"):
                print(f"  🔄 {widget_name}: Zero values in {widget_data['zero_fields']}")
            else:
                print(f"  ✅ {widget_name}: Healthy")

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")

        if not telemetry_avail.get("available"):
            print("  1. ⚠️  CRITICAL: Telemetry system is disabled")
            print("     - The telemetry stack may not be initialised")
            print("     - ClickHouse database is required for live widget data")
            print("     - Widgets will show zeros or fallback demo data until enabled")
            print("     - Solution: Run 'context-cleaner telemetry init' and restart the dashboard")

        if fallback_widgets > 0:
            print(f"  2. ⚠️  {fallback_widgets} widgets in fallback mode")
            print("     - Check service logs for connection errors")
            print("     - Verify ClickHouse container is running")
            print("     - Try clearing widget cache via API")

        if zero_value_widgets > 0:
            print(f"  3. 🔄 {zero_value_widgets} widgets showing zero values")
            print("     - May indicate no data has been collected yet")
            print("     - Or data pipeline is broken")
            print("     - Check telemetry data ingestion")

        # Data freshness insights
        freshness_data = results["tests"].get("data_freshness", {})
        if freshness_data.get("available"):
            print("  4. ✅ Data freshness tracking is working")
            service_avail = freshness_data.get("service_availability", {})
            unavailable_services = [name for name, available in service_avail.items() if not available]
            if unavailable_services:
                print(f"     - Unavailable services: {unavailable_services}")

        print("\n🚀 TESTING COMMANDS:")
        print(f"  curl {results['dashboard_url']}/api/telemetry/data-freshness")
        print(f"  curl {results['dashboard_url']}/api/telemetry/widget-health")
        print(f"  curl -X POST {results['dashboard_url']}/api/telemetry/clear-cache")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="Debug Context Cleaner widget data flow")
    parser.add_argument("--dashboard-port", type=int, default=8110, help="Dashboard port")
    parser.add_argument("--host", default="localhost", help="Dashboard host")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()

    if not args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    base_url = f"http://{args.host}:{args.dashboard_port}"
    tester = WidgetDataFlowTester(base_url)

    try:
        results = tester.run_comprehensive_test()
        tester.analyze_results(results)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {args.output}")

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
