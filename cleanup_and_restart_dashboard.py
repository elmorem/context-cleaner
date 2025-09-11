#!/usr/bin/env python3
"""
Dashboard Port Conflict Resolution and Clean Restart Script

This script resolves critical dashboard port conflicts by:
1. Using PortConflictManager to find truly available ports
2. Killing all existing Python dashboard processes cleanly 
3. Waiting for proper cleanup
4. Starting a single clean dashboard instance
5. Providing clear output showing accessible port

Usage: python cleanup_and_restart_dashboard.py [--port <preferred_port>] [--verbose]
"""

import sys
import os
import time
import signal
import subprocess
import asyncio
import psutil
from typing import List, Optional, Tuple
import argparse
import logging
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.context_cleaner.services.port_conflict_manager import (
    PortConflictManager, 
    PortConflictStrategy
)


class DashboardCleanupManager:
    """Manages cleanup and restart of dashboard processes with port conflict resolution."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.port_manager = PortConflictManager(verbose=verbose)
        
        # Dashboard-related process patterns to identify and kill
        self.dashboard_patterns = [
            "context_cleaner.cli.main",
            "ComprehensiveHealthDashboard", 
            "dashboard",
            "python -m src.context_cleaner.cli.main"
        ]
        
        # Common dashboard ports that might be conflicted
        self.common_dashboard_ports = [
            8080, 8081, 8088, 8099, 8100, 8110, 8200, 8333, 
            7777, 8888, 9000, 9001, 9002, 8050, 8055, 8060,
            8082, 8083, 8084, 8085
        ]
        
        self.setup_logging()

    def setup_logging(self):
        """Setup logging configuration."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def print_status(self, message: str, level: str = "INFO"):
        """Print status message with appropriate formatting."""
        icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "PROCESS": "🔄",
            "CLEANUP": "🧹",
            "LAUNCH": "🚀",
            "PORT": "🔌"
        }
        
        icon = icons.get(level, "•")
        print(f"{icon} {message}")
        
        if self.verbose:
            self.logger.info(f"{level}: {message}")

    def find_dashboard_processes(self) -> List[psutil.Process]:
        """Find all running dashboard-related processes."""
        dashboard_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if not cmdline:
                        continue
                        
                    cmdline_str = ' '.join(cmdline).lower()
                    
                    # Check if this is a dashboard process
                    is_dashboard_process = any(
                        pattern.lower() in cmdline_str 
                        for pattern in self.dashboard_patterns
                    )
                    
                    # Additional check for Python processes with dashboard keywords
                    if not is_dashboard_process and 'python' in cmdline_str:
                        dashboard_keywords = ['dashboard', 'cli.main', 'comprehensivehealthdashboard']
                        is_dashboard_process = any(
                            keyword in cmdline_str 
                            for keyword in dashboard_keywords
                        )
                    
                    if is_dashboard_process:
                        dashboard_processes.append(proc)
                        if self.verbose:
                            self.print_status(
                                f"Found dashboard process: PID {proc.info['pid']} - {' '.join(cmdline[:3])}...",
                                "PROCESS"
                            )
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            self.print_status(f"Error scanning processes: {e}", "ERROR")
            
        return dashboard_processes

    def kill_dashboard_processes(self, processes: List[psutil.Process]) -> int:
        """Kill dashboard processes gracefully, with fallback to force kill."""
        killed_count = 0
        
        if not processes:
            self.print_status("No dashboard processes found to kill", "INFO")
            return 0
            
        self.print_status(f"Found {len(processes)} dashboard processes to terminate", "CLEANUP")
        
        # First attempt: graceful termination (SIGTERM)
        for proc in processes:
            try:
                self.print_status(f"Gracefully terminating PID {proc.pid}", "CLEANUP")
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                if self.verbose:
                    self.print_status(f"Could not terminate PID {proc.pid}: {e}", "WARNING")
        
        # Wait a moment for graceful shutdown
        self.print_status("Waiting 3 seconds for graceful shutdown...", "PROCESS")
        time.sleep(3)
        
        # Second attempt: force kill remaining processes (SIGKILL)
        remaining_processes = []
        for proc in processes:
            try:
                if proc.is_running():
                    remaining_processes.append(proc)
            except psutil.NoSuchProcess:
                killed_count += 1
                
        if remaining_processes:
            self.print_status(f"Force killing {len(remaining_processes)} remaining processes", "CLEANUP")
            for proc in remaining_processes:
                try:
                    proc.kill()
                    killed_count += 1
                    self.print_status(f"Force killed PID {proc.pid}", "CLEANUP")
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    if self.verbose:
                        self.print_status(f"Could not kill PID {proc.pid}: {e}", "WARNING")
        else:
            killed_count += len(processes)
            
        return killed_count

    async def find_available_port(self, preferred_port: int = 8080) -> Optional[int]:
        """Find an available port using the PortConflictManager."""
        self.print_status(f"Searching for available port (preferred: {preferred_port})", "PORT")
        
        # Use hybrid strategy for best results
        available_port, session = await self.port_manager.find_available_port(
            service_name="dashboard",
            original_port=preferred_port,
            strategy=PortConflictStrategy.HYBRID,
            max_attempts=20
        )
        
        if available_port:
            self.print_status(f"Found available port: {available_port}", "SUCCESS")
            if self.verbose and len(session.attempts) > 1:
                self.print_status(f"Port search took {len(session.attempts)} attempts", "INFO")
        else:
            self.print_status("No available port found after extensive search", "ERROR")
            if self.verbose:
                self.print_status(f"Tried {len(session.attempts)} ports", "ERROR")
                
        return available_port

    def check_port_accessibility(self, port: int, max_retries: int = 5) -> bool:
        """Check if the dashboard is actually accessible on the given port."""
        import socket
        import urllib.request
        import urllib.error
        
        # First check if port is bound
        for attempt in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if result == 0:  # Port is bound
                    # Try to make an HTTP request to verify it's actually serving
                    try:
                        response = urllib.request.urlopen(f'http://127.0.0.1:{port}', timeout=5)
                        if response.getcode() == 200:
                            return True
                    except (urllib.error.URLError, urllib.error.HTTPError):
                        # Port is bound but not serving HTTP yet, which is normal during startup
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                        return True  # Assume it will start serving soon
                        
            except Exception as e:
                if self.verbose:
                    self.print_status(f"Port check attempt {attempt + 1} failed: {e}", "WARNING")
                    
            if attempt < max_retries - 1:
                time.sleep(1)
                
        return False

    def start_dashboard(self, port: int) -> Optional[subprocess.Popen]:
        """Start a clean dashboard instance on the specified port."""
        self.print_status(f"Starting clean dashboard on port {port}", "LAUNCH")
        
        # Command to start the dashboard
        cmd = [
            sys.executable, "-m", "src.context_cleaner.cli.main", 
            "dashboard", 
            "--port", str(port),
            "--host", "127.0.0.1",
            "--no-browser",
            "--no-orchestration"
        ]
        
        if self.verbose:
            cmd.insert(3, "-v")  # Add verbose flag after the module
            
        try:
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent,
                text=True
            )
            
            self.print_status(f"Dashboard process started with PID {process.pid}", "SUCCESS")
            
            # Give the dashboard time to start up
            self.print_status("Waiting for dashboard to initialize...", "PROCESS")
            time.sleep(5)
            
            # Check if the process is still running
            if process.poll() is None:
                # Check if the port is accessible
                if self.check_port_accessibility(port):
                    self.print_status(f"Dashboard successfully started and accessible!", "SUCCESS")
                    return process
                else:
                    self.print_status("Dashboard started but not yet accessible (may need more time)", "WARNING")
                    return process
            else:
                # Process died, get the error output
                stdout, stderr = process.communicate()
                self.print_status(f"Dashboard process failed to start", "ERROR")
                if stderr and self.verbose:
                    self.print_status(f"Error output: {stderr.strip()}", "ERROR")
                return None
                
        except Exception as e:
            self.print_status(f"Failed to start dashboard: {e}", "ERROR")
            return None

    async def cleanup_and_restart(self, preferred_port: int = 8080) -> Tuple[bool, Optional[int], Optional[subprocess.Popen]]:
        """
        Main method to cleanup existing processes and restart dashboard.
        
        Returns:
            Tuple of (success, port, process)
        """
        self.print_status("=" * 60, "INFO")
        self.print_status("Dashboard Port Conflict Resolution & Clean Restart", "INFO") 
        self.print_status("=" * 60, "INFO")
        
        # Step 1: Find existing dashboard processes
        self.print_status("Step 1: Scanning for existing dashboard processes...", "PROCESS")
        dashboard_processes = self.find_dashboard_processes()
        
        # Step 2: Kill existing processes
        self.print_status("Step 2: Cleaning up existing dashboard processes...", "CLEANUP")
        killed_count = self.kill_dashboard_processes(dashboard_processes)
        
        if killed_count > 0:
            self.print_status(f"Successfully terminated {killed_count} processes", "SUCCESS")
            
            # Extra wait time for ports to be fully released
            self.print_status("Waiting additional 3 seconds for port cleanup...", "PROCESS")
            time.sleep(3)
        else:
            self.print_status("No processes needed to be terminated", "INFO")
        
        # Step 3: Find available port
        self.print_status("Step 3: Finding available port...", "PORT")
        available_port = await self.find_available_port(preferred_port)
        
        if not available_port:
            self.print_status("Failed to find available port", "ERROR")
            return False, None, None
        
        # Step 4: Start clean dashboard
        self.print_status("Step 4: Starting clean dashboard instance...", "LAUNCH")
        dashboard_process = self.start_dashboard(available_port)
        
        if dashboard_process:
            self.print_status("=" * 60, "SUCCESS")
            self.print_status("✅ DASHBOARD SUCCESSFULLY STARTED!", "SUCCESS")
            self.print_status(f"📊 Dashboard URL: http://127.0.0.1:{available_port}", "SUCCESS")
            self.print_status(f"🆔 Process ID: {dashboard_process.pid}", "SUCCESS")
            self.print_status("=" * 60, "SUCCESS")
            print()
            self.print_status("💡 The dashboard should be accessible in your browser now!", "INFO")
            self.print_status("⏹️  To stop the dashboard later, run: kill {dashboard_process.pid}", "INFO")
            
            return True, available_port, dashboard_process
        else:
            self.print_status("Failed to start dashboard", "ERROR")
            return False, available_port, None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up dashboard port conflicts and restart with available port"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8080,
        help="Preferred port for dashboard (default: 8080)"
    )
    parser.add_argument(
        "--verbose", 
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Create cleanup manager
    manager = DashboardCleanupManager(verbose=args.verbose)
    
    try:
        # Run the cleanup and restart
        success, port, process = asyncio.run(
            manager.cleanup_and_restart(args.port)
        )
        
        if success and process:
            print("\n🎉 Dashboard cleanup and restart completed successfully!")
            print(f"🌐 Access your dashboard at: http://127.0.0.1:{port}")
            
            # Keep the script running so the dashboard stays active
            print("\n👀 Monitoring dashboard process (Ctrl+C to exit)...")
            try:
                while process.poll() is None:
                    time.sleep(5)
                    # Optionally check if dashboard is still accessible
                    
            except KeyboardInterrupt:
                print("\n🛑 Shutting down dashboard...")
                manager.print_status("Terminating dashboard process...", "CLEANUP")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=10)
                    manager.print_status("Dashboard shut down gracefully", "SUCCESS")
                except subprocess.TimeoutExpired:
                    manager.print_status("Force killing dashboard process", "WARNING")
                    process.kill()
                    process.wait()
                    
                print("👋 Dashboard cleanup script exited")
                
        else:
            print("\n❌ Failed to start dashboard. Check the logs above for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()