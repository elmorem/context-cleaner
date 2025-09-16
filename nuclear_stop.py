#!/usr/bin/env python3
"""
Nuclear Context Cleaner Stop - Force Stop All Context Cleaner Processes

This script bypasses the normal Context Cleaner CLI and directly terminates
all Context Cleaner processes using enhanced discovery and termination methods.
Use this when the normal 'context-cleaner stop' command isn't working.
"""

import psutil
import signal
import time
import os
import subprocess
from collections import namedtuple

ProcessInfo = namedtuple('ProcessInfo', ['pid', 'command_line', 'service_type'])

def discover_all_context_cleaner_processes():
    """Enhanced process discovery that finds ALL Context Cleaner processes."""
    found_processes = []
    
    # Comprehensive patterns for Context Cleaner processes
    search_patterns = [
        "python start_context_cleaner.py",
        "python start_context_cleaner_production.py", 
        "start_context_cleaner.py",
        "start_context_cleaner_production.py",
        "python -m context_cleaner.cli.main run",
        "context_cleaner run",
        "context_cleaner.cli.main run",
        "context_cleaner_wsgi",
        "gunicorn.*context_cleaner",
        "ComprehensiveHealthDashboard",
        "context_cleaner.*dashboard",
        "context_cleaner.*jsonl",
        "jsonl_background_service",
        "context_cleaner.*bridge",
        "context_cleaner.*monitor",
        "PYTHONPATH.*context-cleaner",
        "PYTHONPATH.*context_cleaner",
    ]
    
    try:
        print("🔍 Scanning all running processes for Context Cleaner instances...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not proc.info['cmdline']:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'])
                
                # Check against all search patterns
                for pattern in search_patterns:
                    if pattern.lower() in cmdline.lower():
                        # Determine service type from command line
                        service_type = "dashboard"
                        if "jsonl" in cmdline.lower():
                            service_type = "jsonl_processing"
                        elif "bridge" in cmdline.lower():
                            service_type = "bridge_service"
                        elif "monitor" in cmdline.lower():
                            service_type = "monitoring"
                        elif "production" in cmdline.lower():
                            service_type = "production_dashboard"
                        elif "gunicorn" in cmdline.lower() or "wsgi" in cmdline.lower():
                            service_type = "wsgi_server"
                        
                        process_info = ProcessInfo(
                            pid=proc.info['pid'],
                            command_line=cmdline,
                            service_type=service_type
                        )
                        found_processes.append(process_info)
                        
                        print(f"   📍 Found PID {proc.info['pid']:5d}: {service_type} - {cmdline[:60]}...")
                        break  # Found match, move to next process
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
    except Exception as e:
        print(f"   ⚠️  Process discovery error: {e}")
    
    # Also look for processes using ports in Context Cleaner range
    port_processes = find_processes_on_context_cleaner_ports()
    
    # Combine and deduplicate
    all_pids = set(proc.pid for proc in found_processes)
    for proc in port_processes:
        if proc.pid not in all_pids:
            found_processes.append(proc)
    
    return found_processes

def find_processes_on_context_cleaner_ports():
    """Find processes bound to Context Cleaner ports."""
    port_processes = []
    port_ranges = [
        range(8050, 8110),  # Common Context Cleaner ports
        range(8200, 8210), 
        range(8300, 8310),
        range(8400, 8410),
        range(8500, 8510),
        range(8600, 8610),
        range(8700, 8710),
        range(8800, 8810),
        range(8900, 8910),
        range(9000, 9010),
        range(9100, 9110),
        range(9200, 9210),
        range(9900, 10000)
    ]
    
    try:
        for port_range in port_ranges:
            for port in port_range:
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid_str in pids:
                            try:
                                pid = int(pid_str)
                                proc = psutil.Process(pid)
                                cmdline = ' '.join(proc.cmdline())
                                
                                # Check if this looks like a Context Cleaner process
                                if any(pattern in cmdline.lower() for pattern in [
                                    'python', 'context', 'dashboard', 'server'
                                ]):
                                    process_info = ProcessInfo(
                                        pid=pid,
                                        command_line=cmdline,
                                        service_type=f"port_{port}_server"
                                    )
                                    port_processes.append(process_info)
                                    print(f"   🌐 Found port {port} process PID {pid}: {cmdline[:50]}...")
                                    
                            except (ValueError, psutil.NoSuchProcess):
                                continue
                except subprocess.SubprocessError:
                    continue
    except Exception as e:
        print(f"   ⚠️  Port scanning error: {e}")
    
    return port_processes

def terminate_process_with_escalation(proc_info, verbose=True):
    """Terminate a process with signal escalation."""
    try:
        proc = psutil.Process(proc_info.pid)
        
        if verbose:
            print(f"   🎯 Terminating PID {proc_info.pid} ({proc_info.service_type})")
        
        # First, try graceful termination
        proc.terminate()
        
        # Wait up to 3 seconds for graceful termination
        try:
            proc.wait(timeout=3)
            if verbose:
                print(f"   ✅ Gracefully stopped PID {proc_info.pid}")
            return True
        except psutil.TimeoutExpired:
            if verbose:
                print(f"   ⏰ PID {proc_info.pid} didn't respond to SIGTERM, escalating...")
        
        # If still running, force kill
        if proc.is_running():
            proc.kill()
            
            # Wait up to 2 more seconds for force kill
            try:
                proc.wait(timeout=2)
                if verbose:
                    print(f"   💀 Force killed PID {proc_info.pid}")
                return True
            except psutil.TimeoutExpired:
                if verbose:
                    print(f"   ⚠️  PID {proc_info.pid} still running after SIGKILL")
        
        # Try process group termination
        if proc.is_running():
            try:
                pgid = os.getpgid(proc_info.pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(1)
                
                if proc.is_running():
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(1)
                    
                if not proc.is_running():
                    if verbose:
                        print(f"   🗂️  Process group kill succeeded for PID {proc_info.pid}")
                    return True
                    
            except (ProcessLookupError, OSError):
                pass
        
        return not proc.is_running()
        
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Process is gone or we can't access it
        if verbose:
            print(f"   ✅ PID {proc_info.pid} already terminated")
        return True
    except Exception as e:
        if verbose:
            print(f"   ❌ Error terminating PID {proc_info.pid}: {e}")
        return False

def nuclear_stop():
    """Nuclear option: Find and kill ALL Context Cleaner processes."""
    print("🚨 NUCLEAR CONTEXT CLEANER STOP")
    print("=" * 50)
    print("This will forcibly terminate ALL Context Cleaner processes")
    print()
    
    # Discover all processes
    processes = discover_all_context_cleaner_processes()
    
    if not processes:
        print("✅ No Context Cleaner processes found running")
        return
    
    print(f"📊 Found {len(processes)} Context Cleaner processes")
    print()
    
    # Terminate all processes
    print("🎯 Terminating all processes...")
    successful = 0
    failed = 0
    
    for proc_info in processes:
        if proc_info.pid == os.getpid():
            continue  # Don't kill ourselves
            
        success = terminate_process_with_escalation(proc_info)
        if success:
            successful += 1
        else:
            failed += 1
    
    print()
    print("📊 TERMINATION SUMMARY:")
    print(f"   ✅ Successfully stopped: {successful}")
    print(f"   ❌ Failed to stop: {failed}")
    
    # Verification
    print()
    print("🔍 Verifying shutdown...")
    remaining_processes = discover_all_context_cleaner_processes()
    
    if not remaining_processes:
        print("🎯 SUCCESS: All Context Cleaner processes terminated!")
    else:
        print(f"⚠️  {len(remaining_processes)} processes still running:")
        for proc in remaining_processes[:5]:
            print(f"   • PID {proc.pid}: {proc.command_line[:60]}...")
        
        print()
        print("💡 To manually kill remaining processes:")
        print("   sudo pkill -f 'start_context_cleaner'")
        print("   sudo pkill -f 'context_cleaner.*run'")
        print("   sudo pkill -f 'ComprehensiveHealthDashboard'")

if __name__ == "__main__":
    nuclear_stop()