#!/usr/bin/env python3
"""
Real-World Multi-Directory Context Monitoring
Monitors your actual project directories with Context Cleaner
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import List, Dict
import subprocess

# Add context cleaner to path  
sys.path.insert(0, "/Users/markelmore/_code/context-cleaner/src")

class RealDirectoryMonitor:
    """Monitor real project directories with Context Cleaner"""
    
    def __init__(self):
        self.config_path = Path("/Users/markelmore/_code/context-cleaner/context_cleaner_config.json")
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """Load configuration"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Config not found: {self.config_path}")
    
    def get_monitored_directories(self) -> List[Path]:
        """Get list of directories to monitor"""
        paths = self.config["context_cleaner"]["directories"]["monitored_paths"]
        return [Path(p) for p in paths if Path(p).exists()]
    
    def get_directory_stats(self, directory: Path) -> Dict:
        """Get stats for a directory"""
        try:
            # Count files
            total_files = len(list(directory.rglob("*"))) if directory.exists() else 0
            
            # Check for .claude directories
            claude_dirs = list(directory.rglob(".claude"))
            
            # Check for recent activity (git commits in last 7 days)
            recent_activity = False
            if (directory / ".git").exists():
                try:
                    result = subprocess.run(
                        ["git", "log", "--since=7.days.ago", "--oneline"],
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    recent_activity = len(result.stdout.strip().split('\n')) > 0 if result.stdout.strip() else False
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    recent_activity = False
            
            return {
                "path": str(directory),
                "exists": directory.exists(),
                "total_files": total_files,
                "has_claude_context": len(claude_dirs) > 0,
                "claude_dirs": len(claude_dirs),
                "recent_git_activity": recent_activity,
                "size_mb": self.get_directory_size(directory)
            }
        except Exception as e:
            return {
                "path": str(directory),
                "exists": False,
                "error": str(e)
            }
    
    def get_directory_size(self, directory: Path) -> float:
        """Get approximate directory size in MB"""
        try:
            result = subprocess.run(
                ["du", "-sm", str(directory)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return float(result.stdout.split()[0])
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        return 0.0
    
    async def start_monitoring(self):
        """Start monitoring all configured directories"""
        print("🚀 Context Cleaner - Real Directory Monitoring")
        print("=" * 60)
        print()
        
        directories = self.get_monitored_directories()
        
        print(f"📁 Found {len(directories)} directories to monitor:")
        print()
        
        # Analyze each directory
        for i, directory in enumerate(directories, 1):
            print(f"  {i}. {directory.name}")
            stats = self.get_directory_stats(directory)
            
            if stats.get("exists", False):
                print(f"     📊 {stats['total_files']:,} files")
                print(f"     💾 {stats['size_mb']:.1f} MB")
                
                if stats['has_claude_context']:
                    print(f"     ✅ Claude context available ({stats['claude_dirs']} dirs)")
                else:
                    print("     📝 No Claude context found")
                
                if stats['recent_git_activity']:
                    print("     🔥 Recent git activity (last 7 days)")
                else:
                    print("     💤 No recent git activity")
            else:
                print("     ❌ Directory not accessible")
            print()
        
        # Import and start context cleaner
        try:
            from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
            from context_cleaner.config.settings import ContextCleanerConfig
            
            print("🌐 Starting Context Cleaner with multi-directory monitoring...")
            print("🎯 Features enabled:")
            print("  • Phase 1: Critical Telemetry Infrastructure")
            print("  • Phase 2: Enhanced Analytics Dashboard")
            print("  • Phase 3: Advanced Orchestration & ML Learning")
            print("  • Real-time multi-directory monitoring")
            print()
            
            # Create config
            config = ContextCleanerConfig.default()
            
            # Start dashboard
            dashboard = ComprehensiveHealthDashboard(config=config)
            
            print("📊 Dashboard URL: http://localhost:8081")
            print("🔄 Monitoring directories in real-time...")
            print("📈 Use the dashboard to view telemetry and orchestration insights")
            print()
            print("Press Ctrl+C to stop monitoring")
            print("=" * 60)
            
            # Start the dashboard server
            dashboard.start_server(host="localhost", port=8081, debug=False)
            
        except KeyboardInterrupt:
            print("\n👋 Directory monitoring stopped")
        except Exception as e:
            print(f"❌ Error starting monitoring: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main entry point"""
    monitor = RealDirectoryMonitor()
    asyncio.run(monitor.start_monitoring())

if __name__ == "__main__":
    main()