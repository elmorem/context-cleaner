#!/usr/bin/env python3
"""
Test script for the API/UI Consistency Checker system.
This will test the system against the current API/UI mismatch issue.
"""

import asyncio
import sys
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.skip("Manual consistency checker script; skip in automated suite")

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.context_cleaner.services.api_ui_consistency_checker import (
    APIUIConsistencyChecker, 
    ConsistencyStatus
)


async def test_consistency_checker():
    """Test the consistency checker against port 8080 where dashboard is running"""
    
    print("🧪 Testing API/UI Consistency Checker")
    print("=====================================")
    
    # Initialize the checker
    checker = APIUIConsistencyChecker(
        config=None,  # Use None for testing
        dashboard_host="127.0.0.1",
        dashboard_port=8085
    )
    
    print(f"📊 Checking {len(checker.api_endpoints)} API endpoints...")
    print()
    
    # Run a single consistency check
    results = await checker.run_consistency_check()
    
    # Display results
    print("📋 CONSISTENCY CHECK RESULTS")
    print("=" * 50)
    
    consistent_count = 0
    inconsistent_count = 0
    
    for endpoint, result in results.items():
        status_icon = "✅" if result.consistency_status == ConsistencyStatus.CONSISTENT else "❌"
        
        print(f"{status_icon} {endpoint}")
        print(f"   API Status: {result.api_status}")
        print(f"   API Response Time: {result.api_response_time:.2f}s")
        print(f"   API Data Size: {result.api_data_size} bytes")
        print(f"   UI Status: {result.ui_status}")
        print(f"   Consistency: {result.consistency_status.value}")
        
        if result.api_error:
            print(f"   API Error: {result.api_error}")
        if result.ui_error:
            print(f"   UI Error: {result.ui_error}")
            
        if result.recommendations:
            print("   Recommendations:")
            for rec in result.recommendations[:3]:  # Show first 3 recommendations
                print(f"     - {rec}")
        
        print()
        
        if result.consistency_status == ConsistencyStatus.CONSISTENT:
            consistent_count += 1
        else:
            inconsistent_count += 1
    
    # Summary
    print("📊 SUMMARY")
    print("=" * 20)
    print(f"Total Endpoints: {len(results)}")
    print(f"Consistent: {consistent_count}")
    print(f"Inconsistent: {inconsistent_count}")
    print(f"Consistency Rate: {(consistent_count / len(results)) * 100:.1f}%")
    print()
    
    # Get critical issues
    critical_issues = checker.get_critical_issues()
    if critical_issues:
        print("🚨 CRITICAL ISSUES")
        print("=" * 20)
        for issue in critical_issues:
            print(f"- {issue.endpoint}: {issue.consistency_status.value}")
        print()
    
    # Get summary report
    summary = checker.get_summary_report()
    if summary:
        print("📈 SUMMARY REPORT")
        print("=" * 20)
        print(f"Consistency Percentage: {summary['consistency_percentage']:.1f}%")
        print(f"Critical Issues: {summary['critical_issues']}")
        
        if summary['slowest_apis']:
            print("Slowest APIs:")
            for api in summary['slowest_apis'][:3]:
                print(f"  - {api['endpoint']}: {api['response_time']:.2f}s")
        
        if summary['recommendations']:
            print("Top Recommendations:")
            for rec in summary['recommendations'][:5]:
                print(f"  - {rec}")
    
    return results


if __name__ == "__main__":
    print("🔍 Starting API/UI Consistency Check Test")
    print("This will test against any dashboard running on port 8080")
    print()
    
    try:
        results = asyncio.run(test_consistency_checker())
        
        # Check if we found the API/UI mismatch issue
        mismatch_found = False
        for result in results.values():
            if result.consistency_status == ConsistencyStatus.API_WORKING_UI_LOADING:
                mismatch_found = True
                break
        
        if mismatch_found:
            print("🎯 SUCCESS: Found API/UI mismatch issues!")
            print("The consistency checker successfully identified the problem.")
        else:
            print("ℹ️  No API/UI mismatches detected.")
            print("Either the dashboard is not running or the issue has been resolved.")
            
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
