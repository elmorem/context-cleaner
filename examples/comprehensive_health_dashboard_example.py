#!/usr/bin/env python3
"""
Comprehensive Health Dashboard Example (PR16)

This example demonstrates how to use the new Comprehensive Health Dashboard
that provides detailed context health analysis as specified in CLEAN-CONTEXT-GUIDE.md.

Features demonstrated:
- Complete health metrics analysis (focus, redundancy, recency, size)
- Professional CLI formatting with color-coded indicators
- Usage-weighted insights from PR15.3 cache intelligence
- Optimization recommendations
- Multiple output formats (CLI, web, JSON)
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for example
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_cleaner.dashboard.comprehensive_health_dashboard import (
    ComprehensiveHealthDashboard
)


async def main():
    """Demonstrate comprehensive health dashboard usage."""
    print("🎯 Comprehensive Context Health Dashboard Example")
    print("=" * 60)
    
    # Initialize the dashboard
    dashboard = ComprehensiveHealthDashboard()
    
    # Example context data (this would normally come from the actual context)
    example_context = {
        "items": [
            # Current work items
            {
                "type": "todo",
                "content": "Implement user authentication system",
                "status": "in_progress",
                "priority": "high",
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "file_read",
                "file_path": "/src/auth/authentication.py",
                "access_count": 3,
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "conversation",
                "content": "Discussing OAuth2 implementation details",
                "timestamp": datetime.now().isoformat()
            },
            
            # Some completed items that could be cleaned up
            {
                "type": "todo",
                "content": "Fix CSS styling issues",
                "status": "completed",
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat()
            },
            {
                "type": "error",
                "content": "TypeError in user profile loading - RESOLVED",
                "status": "resolved",
                "timestamp": (datetime.now() - timedelta(days=1)).isoformat()
            },
            
            # Some stale context from previous work
            {
                "type": "file_read",
                "file_path": "/src/old_feature/deprecated.py",
                "timestamp": (datetime.now() - timedelta(days=5)).isoformat()
            },
            {
                "type": "conversation",
                "content": "Old discussion about feature that was cancelled",
                "timestamp": (datetime.now() - timedelta(days=3)).isoformat()
            },
            
            # Duplicate file reads
            {
                "type": "file_read",
                "file_path": "/src/auth/authentication.py",
                "access_count": 1,
                "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat()
            },
            {
                "type": "file_read",
                "file_path": "/src/auth/authentication.py", 
                "access_count": 1,
                "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat()
            },
            
            # Active tasks with clear steps
            {
                "type": "todo",
                "content": "Step 1: Create JWT token validation middleware",
                "status": "pending",
                "timestamp": datetime.now().isoformat()
            },
            {
                "type": "todo",
                "content": "Step 2: Implement password hashing with bcrypt",
                "status": "pending",
                "timestamp": datetime.now().isoformat()
            }
        ],
        "session_info": {
            "start_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "current_task": "Building authentication system",
            "session_type": "feature_development"
        }
    }
    
    print("📊 Analyzing context health...")
    
    # Generate comprehensive health report
    report = await dashboard.generate_comprehensive_health_report(
        context_data=example_context,
        include_usage_intelligence=True
    )
    
    print(f"✅ Analysis completed in {report.context_analysis_duration:.2f}s")
    print(f"📈 Overall Health Score: {report.overall_health_score:.1%} {report.overall_health_color.value}")
    print(f"🎯 Confidence: {report.confidence_score:.1%}\n")
    
    # Display the comprehensive CLI dashboard
    print("🖥️ COMPREHENSIVE HEALTH DASHBOARD:")
    print("=" * 60)
    cli_output = await dashboard.display_health_dashboard(report, format="cli")
    print(cli_output)
    
    # Show top recommendations
    if report.optimization_recommendations:
        print("\n🚀 QUICK ACTIONS YOU CAN TAKE:")
        print("-" * 40)
        for i, rec in enumerate(report.optimization_recommendations[:3], 1):
            priority_emoji = {
                'high': '🔥',
                'medium': '⚡',
                'low': '💡'
            }.get(rec['priority'], '📝')
            
            print(f"{i}. {priority_emoji} [{rec['priority'].upper()}] {rec['category'].title()}")
            print(f"   Action: {rec['action']}")
            print(f"   Impact: {rec['estimated_impact']}")
            print()
    
    # Show usage insights if available
    if report.usage_insights:
        print("💡 USAGE INSIGHTS:")
        print("-" * 20)
        for insight in report.usage_insights[:2]:
            confidence_emoji = "🎯" if insight['confidence'] > 0.8 else "📊" if insight['confidence'] > 0.6 else "💭"
            print(f"{confidence_emoji} {insight['message']}")
            if insight.get('action_recommended'):
                print(f"   → Recommended action: {insight['action_recommended']}")
        print()
    
    # Demonstrate different output formats
    print("📋 EXPORT OPTIONS:")
    print("-" * 20)
    
    # JSON export
    json_output = await dashboard.display_health_dashboard(report, format="json")
    print(f"📄 JSON export: {len(json_output):,} characters")
    print("   Can be used for external analysis or API integration")
    
    # Web export
    web_output = await dashboard.display_health_dashboard(report, format="web")
    print(f"🌐 Web HTML export: {len(web_output):,} characters")
    print("   Can be embedded in web dashboards or reports")
    
    print("\n" + "=" * 60)
    print("📚 INTERPRETATION GUIDE:")
    print("🟢 EXCELLENT (80%+) - Context is well-organized and focused")
    print("🟡 GOOD (60-79%) - Minor cleanup could improve focus")
    print("🔴 POOR (30-59%) - Cleanup recommended for better performance")
    print("🔥 CRITICAL (<30%) - Immediate cleanup needed")
    
    print("\n🎉 Example completed! This dashboard can be integrated into:")
    print("   • CLI commands for `/clean-context --dashboard`")
    print("   • Web interfaces for visual health monitoring")
    print("   • Automated scripts for context maintenance")
    print("   • Analytics pipelines for usage pattern analysis")
    
    return report


if __name__ == "__main__":
    # Run the example
    report = asyncio.run(main())
    print(f"\n📊 Final Health Score: {report.overall_health_score:.1%}")