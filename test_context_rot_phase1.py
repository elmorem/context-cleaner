#!/usr/bin/env python3
"""
Test script for Context Rot Meter Phase 1: Core Infrastructure Integration
"""

import asyncio
import sys
import os
import pytest

pytestmark = pytest.mark.skip("Context rot exploratory script; skip in automated suite")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.context_cleaner.telemetry.dashboard.widgets import TelemetryWidgetManager, TelemetryWidgetType
from src.context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from src.context_cleaner.telemetry.cost_optimization.engine import CostOptimizationEngine
from src.context_cleaner.telemetry.error_recovery.manager import ErrorRecoveryManager
from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer


async def test_telemetry_widget_integration():
    """Test Context Rot Meter integration with TelemetryWidgetManager."""
    print("🧪 Testing Context Rot Meter Phase 1 Integration...")
    
    # Initialize components
    clickhouse_client = ClickHouseClient()
    
    # Check ClickHouse connection
    print("📡 Testing ClickHouse connection...")
    healthy = await clickhouse_client.health_check()
    if not healthy:
        print("❌ ClickHouse connection failed - make sure ClickHouse is running")
        return False
    print("✅ ClickHouse connection OK")
    
    # Initialize required components
    print("🔧 Initializing telemetry infrastructure...")
    
    # Mock cost optimization engine
    class MockCostOptimizationEngine:
        async def analyze_session_cost(self, session_id): return {}
        async def get_cost_recommendations(self): return []
        async def optimize_model_selection(self, context): return {}
    
    cost_engine = MockCostOptimizationEngine()
    
    # Mock telemetry client for error recovery
    class MockTelemetryClient:
        async def get_recent_errors(self, hours=24): return []
        async def get_session_metrics(self, session_id): return None
    
    mock_client = MockTelemetryClient()
    recovery_manager = ErrorRecoveryManager(mock_client, max_retries=3)
    
    # Initialize TelemetryWidgetManager
    try:
        widget_manager = TelemetryWidgetManager(
            telemetry_client=clickhouse_client,
            cost_engine=cost_engine,
            recovery_manager=recovery_manager
        )
        print("✅ TelemetryWidgetManager initialized")
    except Exception as e:
        print(f"❌ Failed to initialize TelemetryWidgetManager: {e}")
        return False
    
    # Test that CONTEXT_ROT_METER is in the enum
    print("🔍 Testing TelemetryWidgetType enum...")
    try:
        context_rot_type = TelemetryWidgetType.CONTEXT_ROT_METER
        print(f"✅ CONTEXT_ROT_METER widget type found: {context_rot_type.value}")
    except AttributeError:
        print("❌ CONTEXT_ROT_METER not found in TelemetryWidgetType enum")
        return False
    
    # Test widget manager can handle context rot widget
    print("📊 Testing Context Rot Meter widget data generation...")
    try:
        widget_data = await widget_manager.get_widget_data(
            TelemetryWidgetType.CONTEXT_ROT_METER, 
            session_id=None,  # Global view
            time_range_days=1
        )
        
        print(f"✅ Widget data generated successfully")
        print(f"   Title: {widget_data.title}")
        print(f"   Status: {widget_data.status}")
        print(f"   Widget Type: {widget_data.widget_type.value}")
        print(f"   Alerts: {len(widget_data.alerts)}")
        
        # Check if we have valid data structure
        if hasattr(widget_data, 'data') and isinstance(widget_data.data, dict):
            print(f"   Data Keys: {list(widget_data.data.keys())}")
            
            # Check for expected data structure
            if 'context_rot' in widget_data.data:
                context_rot_data = widget_data.data['context_rot']
                print(f"   Context Rot Data Type: {type(context_rot_data)}")
                
                # Check for expected attributes
                expected_attrs = [
                    'current_rot_score', 
                    'confidence_level', 
                    'session_health_status',
                    'trend_direction',
                    'measurements_count',
                    'recommendations'
                ]
                
                found_attrs = []
                for attr in expected_attrs:
                    if hasattr(context_rot_data, attr):
                        found_attrs.append(attr)
                        value = getattr(context_rot_data, attr)
                        print(f"   {attr}: {value}")
                
                print(f"✅ Found {len(found_attrs)}/{len(expected_attrs)} expected attributes")
        
    except Exception as e:
        print(f"❌ Widget data generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test session-specific widget data
    print("👤 Testing session-specific Context Rot analysis...")
    try:
        session_widget_data = await widget_manager.get_widget_data(
            TelemetryWidgetType.CONTEXT_ROT_METER,
            session_id="test_session_phase1_001",
            time_range_days=1
        )
        
        print(f"✅ Session-specific widget data generated")
        print(f"   Title: {session_widget_data.title}")
        print(f"   Status: {session_widget_data.status}")
        
    except Exception as e:
        print(f"⚠️  Session-specific widget failed (expected for empty data): {e}")
    
    # Test all widgets to ensure Context Rot doesn't break existing functionality
    print("🔄 Testing all telemetry widgets...")
    try:
        all_widgets = await widget_manager.get_all_widget_data()
        
        widget_count = len(all_widgets)
        print(f"✅ Generated {widget_count} total widgets")
        
        # Check that Context Rot Meter is included
        if TelemetryWidgetType.CONTEXT_ROT_METER.value in all_widgets:
            print("✅ Context Rot Meter found in all widgets")
            crm_widget = all_widgets[TelemetryWidgetType.CONTEXT_ROT_METER.value]
            print(f"   CRM Widget Status: {crm_widget.status}")
        else:
            print("❌ Context Rot Meter NOT found in all widgets")
            return False
        
    except Exception as e:
        print(f"❌ All widgets test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("🎉 Context Rot Meter Phase 1 integration tests completed successfully!")
    return True


async def test_context_rot_widget_standalone():
    """Test the Context Rot Widget in standalone mode."""
    print("\n🎯 Testing Context Rot Widget standalone functionality...")
    
    try:
        from src.context_cleaner.telemetry.context_rot.widget import ContextRotWidget
        from src.context_cleaner.telemetry.context_rot.analyzer import ContextRotAnalyzer
        
        # Initialize components
        clickhouse_client = ClickHouseClient()
        
        # Mock error recovery for analyzer
        class MockTelemetryClient:
            async def get_recent_errors(self, hours=24): return []
            async def get_session_metrics(self, session_id): return None
        
        mock_client = MockTelemetryClient()
        recovery_manager = ErrorRecoveryManager(mock_client, max_retries=3)
        
        # Initialize Context Rot components
        analyzer = ContextRotAnalyzer(clickhouse_client, recovery_manager)
        widget = ContextRotWidget(clickhouse_client, analyzer)
        
        print("✅ Context Rot Widget initialized successfully")
        
        # Test widget data generation
        widget_data = await widget.get_widget_data(
            session_id=None,
            time_window_minutes=60
        )
        
        print(f"✅ Widget data generated")
        print(f"   Title: {widget_data.title}")
        print(f"   Status: {widget_data.status}")
        print(f"   Data keys: {list(widget_data.data.keys()) if widget_data.data else 'None'}")
        
        # Test widget status summary
        status_summary = await widget.get_widget_status_summary()
        print(f"✅ Widget status summary: {status_summary}")
        
        return True
        
    except Exception as e:
        print(f"❌ Standalone widget test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_import_paths():
    """Test that all import paths work correctly."""
    print("\n📦 Testing import paths...")
    
    try:
        # Test dashboard imports
        from src.context_cleaner.telemetry.dashboard import (
            TelemetryWidgetManager, 
            TelemetryWidgetType, 
            ContextRotMeterData
        )
        print("✅ Dashboard imports successful")
        
        # Test context rot imports
        from src.context_cleaner.telemetry.context_rot import (
            ContextRotAnalyzer,
            ContextRotWidget,
            ContextRotMeterData
        )
        print("✅ Context rot imports successful")
        
        # Test that enum includes new type
        assert hasattr(TelemetryWidgetType, 'CONTEXT_ROT_METER')
        print("✅ CONTEXT_ROT_METER enum value present")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all Phase 1 integration tests."""
    print("🚀 Starting Context Rot Meter Phase 1 Integration Tests\n")
    
    test_results = []
    
    try:
        # Test 1: Import paths
        result1 = await test_import_paths()
        test_results.append(("Import Paths", result1))
        
        if not result1:
            print("💥 Import tests failed - skipping other tests")
            return 1
        
        # Test 2: Standalone widget functionality  
        result2 = await test_context_rot_widget_standalone()
        test_results.append(("Standalone Widget", result2))
        
        # Test 3: Full telemetry integration
        result3 = await test_telemetry_widget_integration()
        test_results.append(("Telemetry Integration", result3))
        
        # Summary
        print(f"\n📋 Test Results Summary:")
        passed = 0
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n🏁 Overall: {passed}/{len(test_results)} tests passed")
        
        if passed == len(test_results):
            print("🎊 All Phase 1 integration tests passed! Context Rot Meter is ready for dashboard deployment.")
            return 0
        else:
            print("💥 Some Phase 1 tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
