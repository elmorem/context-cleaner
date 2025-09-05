#!/usr/bin/env python3
"""
Directory Monitor for Context Cleaner Real-World Usage
Monitors multiple directories and triggers analysis
"""

import asyncio
import time
from pathlib import Path
import sys

# Add context cleaner to path
sys.path.insert(0, "/Users/markelmore/_code/context-cleaner/src")

from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
from context_cleaner.config.settings import ContextCleanerConfig

class MultiDirectoryMonitor:
    def __init__(self):
        self.monitored_dirs = ['/Users/markelmore/code', '/Users/markelmore/projects', '/Users/markelmore/workspace']
        self.config = ContextCleanerConfig.default()
        self.dashboard = ComprehensiveHealthDashboard(config=self.config)
    
    async def monitor_directories(self):
        """Monitor all configured directories"""
        print("🔍 Starting directory monitoring...")
        
        for directory in self.monitored_dirs:
            dir_path = Path(directory)
            if dir_path.exists():
                print(f"📁 Monitoring: {directory}")
            else:
                print(f"⚠️  Directory not found: {directory}")
        
        # Start monitoring loop
        while True:
            await self.scan_directories()
            await asyncio.sleep(300)  # Scan every 5 minutes
    
    async def scan_directories(self):
        """Scan directories for changes and update analytics"""
        for directory in self.monitored_dirs:
            dir_path = Path(directory)
            if dir_path.exists():
                # Trigger analysis for this directory
                print(f"🔍 Scanning {directory}...")
                # Add your analysis logic here
    
    def start_dashboard(self):
        """Start the web dashboard"""
        print("🌐 Starting dashboard at http://localhost:8080")
        self.dashboard.run(host="localhost", port=8080)

if __name__ == "__main__":
    monitor = MultiDirectoryMonitor()
    
    # Start dashboard in separate thread
    import threading
    dashboard_thread = threading.Thread(target=monitor.start_dashboard)
    dashboard_thread.daemon = True
    dashboard_thread.start()
    
    # Start monitoring
    asyncio.run(monitor.monitor_directories())
