#!/usr/bin/env python3
"""
Context Cleaner - Production Server Launcher
Launches comprehensive dashboard with Gunicorn (production WSGI server)
"""

import sys
import os
import argparse
from pathlib import Path

# Add context cleaner to path  
sys.path.insert(0, "/Users/markelmore/_code/context-cleaner/src")

def main():
    parser = argparse.ArgumentParser(
        description="Context Cleaner Production Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_context_cleaner_production.py                    # Default production settings
  python start_context_cleaner_production.py --host 0.0.0.0    # Bind to all interfaces
  python start_context_cleaner_production.py --workers 4       # Use 4 worker processes
  python start_context_cleaner_production.py --no-browser      # Don't open browser
        """
    )
    
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="Host to bind server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8081, 
        help="Port to bind server to (default: 8081)"
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        help="Number of Gunicorn workers (default: CPU count * 2 + 1)"
    )
    parser.add_argument(
        "--no-browser", 
        action="store_true", 
        help="Don't automatically open browser"
    )
    parser.add_argument(
        "--dev", 
        action="store_true", 
        help="Use development server instead of production (for testing)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Context Cleaner - Production Dashboard")
    print("=" * 50)
    
    if args.dev:
        print("⚠️  Using DEVELOPMENT server (not for production!)")
        print("Features Enabled:")
        print("  ✅ Phase 1: Critical Telemetry Infrastructure")
        print("  ✅ Phase 2: Enhanced Analytics & Dashboard")  
        print("  ✅ Phase 3: Advanced Orchestration & ML Learning")
        print("  ⚠️  Flask Development Server (Werkzeug)")
    else:
        print("🔒 Using PRODUCTION server (Gunicorn)")
        print("Features Enabled:")
        print("  ✅ Phase 1: Critical Telemetry Infrastructure")
        print("  ✅ Phase 2: Enhanced Analytics & Dashboard")  
        print("  ✅ Phase 3: Advanced Orchestration & ML Learning")
        print("  🚀 Gunicorn Production WSGI Server")
        print(f"  👥 Workers: {args.workers or 'auto'}")
    
    print()
    
    try:
        from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
        from context_cleaner.config.settings import ContextCleanerConfig
        
        # Load configuration
        config_path = Path("/Users/markelmore/_code/context-cleaner/context_cleaner_config.json")
        if config_path.exists():
            print(f"📝 Using config: {config_path}")
        
        config = ContextCleanerConfig.default()
        
        # Create and start dashboard
        if not args.dev:
            print("🌐 Starting production dashboard with Gunicorn...")
            print("🎯 Production features:")
            print("  • Multiple worker processes for scalability")
            print("  • Gevent async worker class for high concurrency")
            print("  • Request limiting and connection pooling")
            print("  • Production logging and monitoring")
            print("  • Graceful worker recycling")
        else:
            print("🌐 Starting development dashboard...")
            print("🎯 Development features:")
            print("  • Single-threaded for easier debugging")
            print("  • Real-time code reloading disabled")
            print("  • Extended error reporting")
        
        print()
        
        dashboard = ComprehensiveHealthDashboard(config=config)
        
        print(f"📊 Dashboard URL: http://{args.host}:{args.port}")
        print("🔄 Press Ctrl+C to stop")
        print()
        
        # Start the server
        dashboard.start_server(
            host=args.host,
            port=args.port,
            debug=False,  # Never debug in production
            open_browser=not args.no_browser,
            production=not args.dev,  # Use production server unless --dev specified
            gunicorn_workers=args.workers,
        )
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Ensure Context Cleaner dependencies are installed")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\\n🛑 Shutting down Context Cleaner Dashboard...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()