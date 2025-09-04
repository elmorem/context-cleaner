#!/usr/bin/env python3
"""
Context Cleaner - Real World Usage Launcher
Launches comprehensive dashboard with all Phase 1-3 features
"""

import sys
import asyncio
from pathlib import Path

# Add context cleaner to path  
sys.path.insert(0, "/Users/markelmore/_code/context-cleaner/src")

def main():
    print("🚀 Context Cleaner - Real World Usage")
    print("=" * 50)
    print("Features Enabled:")
    print("  ✅ Phase 1: Critical Telemetry Infrastructure")
    print("  ✅ Phase 2: Enhanced Analytics & Dashboard")  
    print("  ✅ Phase 3: Advanced Orchestration & ML Learning")
    print()
    
    try:
        from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
        from context_cleaner.config.settings import ContextCleanerConfig
        
        # Load configuration
        config_path = Path("/Users/markelmore/_code/context-cleaner/context_cleaner_config.json")
        if config_path.exists():
            print(f"📝 Using config: {config_path}")
            # Load custom config here if needed
        
        config = ContextCleanerConfig.default()
        
        # Create and start dashboard
        print("🌐 Starting comprehensive dashboard...")
        dashboard = ComprehensiveHealthDashboard(config=config)
        
        print("🎯 Dashboard features:")
        print("  • Real-time telemetry monitoring")
        print("  • ML-powered workflow optimization")  
        print("  • Intelligent agent orchestration")
        print("  • Performance analytics")
        print("  • Cost optimization tracking")
        print()
        
        print("📊 Dashboard URL: http://localhost:8081")
        print("🔄 Use Ctrl+C to stop")
        print()
        
        # Start the dashboard
        dashboard.start_server(host="localhost", port=8081, debug=False)
        
    except KeyboardInterrupt:
        print("\n👋 Context Cleaner stopped")
    except Exception as e:
        print(f"❌ Error starting Context Cleaner: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
