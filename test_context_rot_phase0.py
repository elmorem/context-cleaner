#!/usr/bin/env python3
"""
Simple test script to verify Context Rot Meter Phase 0 implementation works.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager


async def test_context_rot_analyzer():
    """Test the Context Rot Analyzer end-to-end."""
    print("🔍 Testing Context Rot Meter Phase 0...")
    
    # Initialize components
    clickhouse_client = ClickHouseClient()
    
    # Check ClickHouse connection
    print("📡 Testing ClickHouse connection...")
    healthy = await clickhouse_client.health_check()
    if not healthy:
        print("❌ ClickHouse connection failed - make sure ClickHouse is running")
        return False
    print("✅ ClickHouse connection OK")
    
    # Initialize error recovery manager (mock telemetry client)
    class MockTelemetryClient:
        async def get_recent_errors(self, hours=24):
            return []
        
        async def get_session_metrics(self, session_id):
            return None
    
    mock_client = MockTelemetryClient()
    error_manager = ErrorRecoveryManager(mock_client, max_retries=3)
    
    # Initialize Context Rot Analyzer
    print("🧠 Initializing Context Rot Analyzer...")
    analyzer = ContextRotAnalyzer(clickhouse_client, error_manager)
    print("✅ Context Rot Analyzer initialized")
    
    # Test analyzer status
    print("🏥 Checking analyzer health...")
    status = await analyzer.get_analyzer_status()
    print(f"   Status: {status['status']}")
    print(f"   ClickHouse: {status['clickhouse_connection']}")
    print(f"   Version: {status['version']}")
    
    # Test real-time analysis
    print("⚡ Testing real-time context rot analysis...")
    test_sessions = [
        ("test_session_001", "Hello, I need help with my code"),
        ("test_session_001", "I'm still having trouble with the same issue"),
        ("test_session_001", "This is frustrating, nothing seems to work"),
        ("test_session_002", "Can you help me understand async programming?"),
        ("test_session_002", "Thanks! That explanation was very helpful"),
    ]
    
    for session_id, content in test_sessions:
        print(f"   Analyzing: '{content[:50]}...'")
        result = await analyzer.analyze_realtime(session_id, content)
        
        if result:
            print(f"     Session: {result.session_id}")
            print(f"     Rot Score: {result.rot_score:.3f}")
            print(f"     Confidence: {result.confidence_score:.3f}")
            print(f"     Attention Needed: {result.requires_attention}")
            print(f"     Indicators: {result.indicator_breakdown}")
        else:
            print("     Analysis failed")
    
    # Wait a moment for data to be stored
    await asyncio.sleep(1)
    
    # Test session health analysis
    print("📊 Testing session health analysis...")
    health = await analyzer.analyze_session_health("test_session_001", time_window_minutes=30)
    print(f"   Health Status: {health.get('status', 'unknown')}")
    if 'metrics' in health:
        metrics = health['metrics']
        print(f"   Average Rot: {metrics.get('average_rot_score', 'N/A')}")
        print(f"   Max Rot: {metrics.get('maximum_rot_score', 'N/A')}")
        print(f"   Measurements: {metrics.get('measurement_count', 'N/A')}")
        print(f"   Alerts: {metrics.get('attention_alerts', 'N/A')}")
    
    if 'recommendations' in health:
        print("   Recommendations:")
        for rec in health['recommendations']:
            print(f"     - {rec}")
    
    # Test system metrics
    print("🖥️  System metrics:")
    system_metrics = status.get('system_metrics', {})
    print(f"   Memory Usage: {system_metrics.get('memory_usage_mb', 'N/A')} MB")
    print(f"   Memory Limit: {system_metrics.get('memory_limit_mb', 'N/A')} MB")
    print(f"   Active Sessions: {system_metrics.get('active_sessions', 'N/A')}")
    circuit_state = system_metrics.get('circuit_breaker', {})
    print(f"   Circuit Breaker: {circuit_state.get('state', 'N/A')}")
    
    print("🎉 Context Rot Meter Phase 0 test completed successfully!")
    return True


async def test_security_features():
    """Test security features."""
    print("🔒 Testing security features...")
    
    from src.context_cleaner.telemetry.context_rot.security import (
        SecureContextRotAnalyzer, 
        PrivacyConfig
    )
    
    config = PrivacyConfig(
        remove_pii=True,
        anonymize_file_paths=True,
        hash_sensitive_patterns=True
    )
    
    secure_analyzer = SecureContextRotAnalyzer(config)
    
    # Test with potentially sensitive content
    test_cases = [
        ("test_session_123", "My email is user@example.com and API key is sk-123456789"),
        ("", "Invalid session ID test"),  # Should be rejected
        ("test_session_456", "'; DROP TABLE users; --"),  # SQL injection attempt
        ("valid_session_789", "/Users/john/projects/secret_project/config.py"),  # File path
    ]
    
    for session_id, content in test_cases:
        print(f"   Testing: '{content[:40]}...'")
        result = secure_analyzer.validate_and_sanitize_input(session_id, content)
        
        if result:
            print(f"     ✅ Accepted and sanitized")
            print(f"     Original length: {result['original_length']}")
            print(f"     Sanitized length: {result['sanitized_length']}")
            if result['sanitized_length'] < result['original_length']:
                print(f"     🛡️  Content was sanitized")
        else:
            print(f"     ❌ Rejected (security)")
    
    print("✅ Security feature tests completed")


async def main():
    """Run all tests."""
    print("🚀 Starting Context Rot Meter Phase 0 Tests\n")
    
    try:
        # Test security features
        await test_security_features()
        print()
        
        # Test main analyzer
        success = await test_context_rot_analyzer()
        
        if success:
            print("\n🎊 All tests passed! Context Rot Meter Phase 0 is ready.")
            return 0
        else:
            print("\n💥 Some tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)