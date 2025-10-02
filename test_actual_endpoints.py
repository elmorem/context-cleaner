#!/usr/bin/env python3
"""
Test all the actual API endpoints discovered in the dashboard HTML
to verify which ones are working vs which ones are broken.
"""

import requests
import json
import time
import pytest

pytestmark = pytest.mark.skip("Endpoint probe script not part of automated suite")

def test_endpoint(url, method="GET"):
    """Test a single endpoint and return status info"""
    try:
        start_time = time.time()
        
        if method == "POST":
            response = requests.post(url, timeout=5, json={})
        else:
            response = requests.get(url, timeout=5)
            
        response_time = time.time() - start_time
        
        status_icon = "✅" if response.status_code == 200 else "❌" if response.status_code >= 400 else "⚠️"
        
        data_size = 0
        data_type = "unknown"
        sample_keys = []
        
        if response.status_code == 200:
            try:
                data = response.json()
                data_size = len(json.dumps(data))
                data_type = "json"
                if isinstance(data, dict):
                    sample_keys = list(data.keys())[:5]
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    sample_keys = list(data[0].keys())[:5]
            except:
                data_size = len(response.text)
                data_type = "text"
        
        return {
            "url": url,
            "status_code": response.status_code,
            "status_icon": status_icon,
            "response_time": response_time,
            "data_size": data_size,
            "data_type": data_type,
            "sample_keys": sample_keys,
            "working": response.status_code == 200
        }
        
    except requests.exceptions.Timeout:
        return {
            "url": url,
            "status_code": "TIMEOUT",
            "status_icon": "⏰",
            "response_time": 5.0,
            "data_size": 0,
            "data_type": "timeout",
            "sample_keys": [],
            "working": False
        }
    except requests.exceptions.ConnectionError:
        return {
            "url": url,
            "status_code": "CONNECTION_ERROR",
            "status_icon": "🔌",
            "response_time": 0.0,
            "data_size": 0,
            "data_type": "connection_error",
            "sample_keys": [],
            "working": False
        }
    except Exception as e:
        return {
            "url": url,
            "status_code": f"ERROR: {str(e)[:30]}",
            "status_icon": "💥",
            "response_time": 0.0,
            "data_size": 0,
            "data_type": "error",
            "sample_keys": [],
            "working": False
        }

def main():
    print("🧪 TESTING ALL ACTUAL API ENDPOINTS")
    print("=" * 50)
    print("Testing endpoints found in dashboard HTML on port 8080...")
    print()
    
    # All endpoints discovered from the dashboard HTML
    endpoints = [
        "/api/dashboard-metrics",
        "/api/context-window-usage",
        "/api/conversation-analytics",
        "/api/code-patterns-analytics",
        "/api/content-search",
        "/api/analytics/context-health",
        "/api/analytics/performance-trends",
        "/api/data-explorer/query",
        "/api/jsonl-processing-status",
        "/api/telemetry-widget/code-pattern-analysis",
        "/api/telemetry-widget/content-search-widget",
        "/api/telemetry-widget/conversation-timeline",
        "/api/telemetry/error-details?hours=24",
        "/api/telemetry/model-analytics",
        "/api/telemetry/tool-analytics"
    ]
    
    # Test each endpoint
    results = []
    base_url = "http://127.0.0.1:8080"
    
    for endpoint in endpoints:
        url = base_url + endpoint
        print(f"Testing: {endpoint}")
        
        # Try GET first
        result = test_endpoint(url, "GET")
        
        # If GET doesn't work and it's a content-search, try POST
        if not result["working"] and "content-search" in endpoint:
            print(f"  Retrying with POST...")
            result = test_endpoint(url, "POST")
        
        results.append(result)
        
        # Print immediate result
        print(f"  {result['status_icon']} {result['status_code']} - {result['response_time']:.2f}s - {result['data_size']} bytes")
        if result['sample_keys']:
            print(f"    Keys: {', '.join(result['sample_keys'])}")
        print()
    
    # Summary
    working = [r for r in results if r["working"]]
    broken = [r for r in results if not r["working"]]
    
    print("📊 SUMMARY")
    print("=" * 20)
    print(f"Total Endpoints: {len(results)}")
    print(f"✅ Working: {len(working)}")
    print(f"❌ Broken: {len(broken)}")
    print(f"Success Rate: {(len(working) / len(results)) * 100:.1f}%")
    
    if working:
        print(f"\n✅ WORKING ENDPOINTS ({len(working)})")
        print("-" * 30)
        for result in working:
            endpoint = result['url'].replace(base_url, '')
            print(f"  {endpoint}")
            print(f"    {result['data_size']} bytes, {result['response_time']:.2f}s")
            if result['sample_keys']:
                print(f"    Keys: {', '.join(result['sample_keys'])}")
    
    if broken:
        print(f"\n❌ BROKEN ENDPOINTS ({len(broken)})")
        print("-" * 30)
        for result in broken:
            endpoint = result['url'].replace(base_url, '')
            print(f"  {endpoint} - {result['status_code']}")
    
    # Generate corrected endpoint list for consistency checker
    print(f"\n🔧 CORRECTED ENDPOINT LIST FOR CONSISTENCY CHECKER")
    print("-" * 50)
    working_endpoints = [r['url'].replace(base_url, '') for r in working]
    print("known_endpoints = [")
    for endpoint in working_endpoints:
        print(f'    "{endpoint}",')
    print("]")

if __name__ == "__main__":
    main()
