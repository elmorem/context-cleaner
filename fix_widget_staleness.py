#!/usr/bin/env python3
"""
Widget Staleness Fix Script for Context Cleaner

This script diagnoses and provides solutions for widget data staleness issues.
It implements the comprehensive 4-agent ULTRATHINK analysis findings to help users
identify and resolve widget data problems once and for all.

Usage:
    python fix_widget_staleness.py --port 8110
    python fix_widget_staleness.py --check-only    # Just diagnose, don't fix
    python fix_widget_staleness.py --verbose       # Detailed logging
"""

import argparse
import json
import requests
import sys
import time
from datetime import datetime
from typing import Dict, Any, List

class WidgetStalenessAnalyzer:
    """Comprehensive widget staleness diagnosis and fix tool"""

    def __init__(self, dashboard_port: int = 8110, host: str = "localhost"):
        self.base_url = f"http://{host}:{dashboard_port}"
        self.session = requests.Session()
        self.session.timeout = 30

    def analyze_and_fix(self, check_only: bool = False, verbose: bool = False) -> Dict[str, Any]:
        """Run comprehensive analysis and optionally apply fixes"""

        print("🔍 WIDGET STALENESS ANALYZER")
        print("=" * 50)
        print(f"Dashboard URL: {self.base_url}")
        print(f"Analysis time: {datetime.now()}")
        print()

        results = {
            "timestamp": datetime.now().isoformat(),
            "dashboard_url": self.base_url,
            "diagnosis": {},
            "fixes_applied": [],
            "recommendations": []
        }

        # Step 1: Check dashboard connectivity
        print("📡 Step 1: Testing dashboard connectivity...")
        connectivity = self._test_connectivity()
        results["diagnosis"]["connectivity"] = connectivity

        if not connectivity["success"]:
            print(f"❌ Dashboard not accessible: {connectivity['error']}")
            print("\n💡 SOLUTION: Start Context Cleaner dashboard:")
            print("   context-cleaner run --dashboard-port 8110")
            return results

        print("✅ Dashboard is accessible")

        # Step 2: Check telemetry availability
        print("\n🔧 Step 2: Checking telemetry system...")
        telemetry_status = self._check_telemetry_status()
        results["diagnosis"]["telemetry"] = telemetry_status

        if not telemetry_status["available"]:
            print("❌ Telemetry system unavailable")
            print(f"   Reason: {telemetry_status.get('reason', 'unknown')}")

            if telemetry_status.get("reason") == "telemetry_disabled":
                print("\n💡 ROOT CAUSE IDENTIFIED: Telemetry stack not initialised")
                print("\n🚀 SOLUTION:")
                print("   1. Stop current Context Cleaner: context-cleaner stop")
                print("   2. Start with full services: context-cleaner run")
                print("   3. This will enable ClickHouse database for real telemetry data")
                results["recommendations"].append("restart_with_full_services")
                return results
            else:
                print("\n💡 SOLUTION: Check service logs and restart telemetry services")
                results["recommendations"].append("check_service_logs")
        else:
            print("✅ Telemetry system is available")

        # Step 3: Test individual widgets
        print("\n📊 Step 3: Testing individual widgets...")
        widget_tests = self._test_all_widgets(verbose)
        results["diagnosis"]["widgets"] = widget_tests

        problem_widgets = [name for name, data in widget_tests.items()
                         if not data.get("success") or data.get("is_fallback") or data.get("zero_fields")]

        if problem_widgets:
            print(f"⚠️  Found {len(problem_widgets)} widgets with issues:")
            for widget in problem_widgets:
                widget_data = widget_tests[widget]
                if not widget_data.get("success"):
                    print(f"   ❌ {widget}: Error - {widget_data.get('error', 'unknown')}")
                elif widget_data.get("is_fallback"):
                    print(f"   🔄 {widget}: Fallback mode")
                elif widget_data.get("zero_fields"):
                    print(f"   🚫 {widget}: Zero values in {widget_data['zero_fields']}")
        else:
            print("✅ All widgets working correctly")

        # Step 4: Check data freshness
        print("\n🕐 Step 4: Analyzing data freshness...")
        freshness_data = self._analyze_data_freshness(verbose)
        results["diagnosis"]["freshness"] = freshness_data

        # Step 5: Apply fixes if requested
        if not check_only and problem_widgets:
            print("\n🔧 Step 5: Applying fixes...")
            fixes_applied = self._apply_fixes(telemetry_status, widget_tests, verbose)
            results["fixes_applied"] = fixes_applied
        elif check_only:
            print("\n📋 Check-only mode: No fixes applied")

        # Step 6: Provide comprehensive recommendations
        print("\n💡 RECOMMENDATIONS:")
        recommendations = self._generate_recommendations(telemetry_status, widget_tests, freshness_data)
        results["recommendations"].extend(recommendations)

        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")

        return results

    def _test_connectivity(self) -> Dict[str, Any]:
        """Test basic dashboard connectivity"""
        try:
            response = self.session.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            return {"success": True, "status": response.json().get("status", "unknown")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _check_telemetry_status(self) -> Dict[str, Any]:
        """Check telemetry system availability"""
        try:
            response = self.session.get(f"{self.base_url}/api/telemetry/data-freshness")

            if response.status_code == 404:
                return {"available": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            data = response.json()

            return {
                "available": True,
                "service_availability": data.get("service_availability", {}),
                "cache_status": data.get("cache_status", {}),
                "fallback_widgets": len(data.get("fallback_detection", {}))
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _test_all_widgets(self, verbose: bool = False) -> Dict[str, Dict[str, Any]]:
        """Test all widget endpoints"""
        widgets = [
            "error-monitor", "cost-tracker", "timeout-risk",
            "tool-optimizer", "model-efficiency", "context-rot-meter"
        ]

        results = {}

        for widget in widgets:
            if verbose:
                print(f"   Testing {widget}...")

            try:
                response = self.session.get(f"{self.base_url}/api/telemetry-widget/{widget}")

                if response.status_code == 200:
                    data = response.json()

                    # Check for fallback indicators
                    widget_data = data.get("data", {})
                    is_fallback = widget_data.get("fallback_mode", False) or "Demo" in data.get("title", "")

                    # Check for zero values
                    zero_fields = []
                    for key, value in widget_data.items():
                        if isinstance(value, (int, float)) and value == 0:
                            zero_fields.append(key)

                    results[widget] = {
                        "success": True,
                        "status": data.get("status", "unknown"),
                        "title": data.get("title", ""),
                        "is_fallback": is_fallback,
                        "zero_fields": zero_fields,
                        "alerts": data.get("alerts", [])
                    }
                else:
                    results[widget] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "response": response.text[:200]
                    }

            except Exception as e:
                results[widget] = {
                    "success": False,
                    "error": str(e)
                }

        return results

    def _analyze_data_freshness(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze data freshness patterns"""
        try:
            response = self.session.get(f"{self.base_url}/api/telemetry/data-freshness")

            if response.status_code == 404:
                return {"available": False, "reason": "telemetry_disabled"}

            response.raise_for_status()
            data = response.json()

            if verbose:
                print(f"   Cache status: {data.get('cache_status', {})}")
                print(f"   Service availability: {data.get('service_availability', {})}")

            return {
                "available": True,
                "cached_widgets": data.get("cache_status", {}).get("cached_widgets", 0),
                "service_availability": data.get("service_availability", {}),
                "freshness_data": data.get("data_freshness", {}),
                "fallback_detection": data.get("fallback_detection", {})
            }

        except Exception as e:
            return {"available": False, "error": str(e)}

    def _apply_fixes(self, telemetry_status: Dict, widget_tests: Dict, verbose: bool = False) -> List[str]:
        """Apply available fixes for detected issues"""
        fixes_applied = []

        # Fix 1: Clear widget cache if telemetry is available
        if telemetry_status.get("available"):
            try:
                print("   🔄 Clearing widget cache...")
                response = self.session.post(f"{self.base_url}/api/telemetry/clear-cache")

                if response.status_code == 200:
                    fixes_applied.append("cache_cleared")
                    print("   ✅ Widget cache cleared successfully")

                    # Wait a moment and re-test one widget
                    time.sleep(2)
                    test_response = self.session.get(f"{self.base_url}/api/telemetry-widget/error-monitor")
                    if test_response.status_code == 200:
                        fixes_applied.append("widget_retested")
                        print("   ✅ Widget data refreshed after cache clear")
                else:
                    print(f"   ❌ Cache clear failed: HTTP {response.status_code}")

            except Exception as e:
                print(f"   ❌ Cache clear error: {e}")

        return fixes_applied

    def _generate_recommendations(self, telemetry_status: Dict, widget_tests: Dict,
                                freshness_data: Dict) -> List[str]:
        """Generate specific recommendations based on analysis"""
        recommendations = []

        if not telemetry_status.get("available"):
            if telemetry_status.get("reason") == "telemetry_disabled":
                recommendations.append("CRITICAL: Run 'context-cleaner telemetry init' to enable real data")
            else:
                recommendations.append("Check ClickHouse container status and telemetry service logs")

        problem_widgets = [name for name, data in widget_tests.items()
                         if not data.get("success") or data.get("is_fallback")]

        if problem_widgets:
            recommendations.append(f"Investigate {len(problem_widgets)} problematic widgets")
            recommendations.append("Monitor service logs during widget data generation")

        if freshness_data.get("cached_widgets", 0) > 5:
            recommendations.append("High cache usage detected - consider clearing cache periodically")

        service_availability = freshness_data.get("service_availability", {})
        unavailable_services = [name for name, available in service_availability.items() if not available]
        if unavailable_services:
            recommendations.append(f"Unavailable services detected: {', '.join(unavailable_services)}")

        return recommendations


def main():
    parser = argparse.ArgumentParser(description="Fix Context Cleaner widget staleness issues")
    parser.add_argument("--port", type=int, default=8110, help="Dashboard port (default: 8110)")
    parser.add_argument("--host", default="localhost", help="Dashboard host (default: localhost)")
    parser.add_argument("--check-only", action="store_true", help="Only diagnose, don't apply fixes")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()

    analyzer = WidgetStalenessAnalyzer(args.port, args.host)

    try:
        results = analyzer.analyze_and_fix(args.check_only, args.verbose)

        print("\n" + "=" * 50)
        print("📋 ANALYSIS COMPLETE")
        print("=" * 50)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"💾 Results saved to {args.output}")

        # Exit with appropriate code
        if results["recommendations"]:
            critical_issues = any("CRITICAL" in rec for rec in results["recommendations"])
            sys.exit(1 if critical_issues else 0)
        else:
            print("✅ No issues detected")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Analysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
