"""
Debug commands for Context Cleaner process registry and service orchestration.

This module provides comprehensive debug commands to validate and troubleshoot:
- Service orchestration system and lifecycle management
- Process registry functionality and health monitoring
- Docker container states and integration
- Service dependency resolution and startup ordering  
- Cross-process communication and discovery
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

import click
import psutil

from ...services.process_registry import (
    get_process_registry,
    get_discovery_engine,
    ProcessEntry,
    ProcessRegistryDatabase,
    ProcessDiscoveryEngine,
)
from ...config.settings import ContextCleanerConfig


@click.group(name="debug")
def debug():
    """Debug commands for process registry and service orchestration."""
    pass


@debug.command("list-processes")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format")
@click.option("--service-type", "-t", help="Filter by service type")
@click.option("--status", "-s", help="Filter by status")
@click.pass_context
def list_processes(ctx, format, service_type, status):
    """List all registered processes in the process registry."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        registry = get_process_registry()
        processes = registry.get_all_processes()
        
        # Apply filters
        if service_type:
            processes = [p for p in processes if p.service_type == service_type]
        if status:
            processes = [p for p in processes if p.status == status]
        
        if not processes:
            click.echo("No processes found in registry")
            return
            
        if format == "json":
            output = []
            for process in processes:
                output.append({
                    "pid": process.pid,
                    "service_type": process.service_type,
                    "status": process.status,
                    "start_time": process.start_time.isoformat(),
                    "port": process.port,
                    "host": process.host,
                    "command_line": process.command_line,
                    "session_id": process.session_id,
                    "parent_orchestrator": process.parent_orchestrator,
                    "registration_source": process.registration_source,
                    "last_health_check": process.last_health_check.isoformat() if process.last_health_check else None,
                    "last_health_status": process.last_health_status
                })
            click.echo(json.dumps(output, indent=2))
        else:
            # Table format
            click.echo("Registered Context Cleaner Processes:")
            click.echo("=" * 100)
            click.echo(f"{'PID':<8} {'Service':<15} {'Status':<10} {'Port':<6} {'Start Time':<20} {'Health':<8}")
            click.echo("-" * 100)
            
            for process in processes:
                health_status = "✓" if process.last_health_status else "✗" if process.last_health_check else "?"
                start_time_str = process.start_time.strftime("%m-%d %H:%M:%S")
                port_str = str(process.port) if process.port else "-"
                
                click.echo(f"{process.pid:<8} {process.service_type:<15} {process.status:<10} {port_str:<6} {start_time_str:<20} {health_status:<8}")
            
            click.echo(f"\nTotal: {len(processes)} processes")
            
    except Exception as e:
        click.echo(f"❌ Error listing processes: {e}", err=True)
        sys.exit(1)


@debug.command("discover-services")
@click.option("--register", is_flag=True, help="Register discovered processes in the registry")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format")
@click.pass_context
def discover_services(ctx, register, format):
    """Discover Context Cleaner processes running on the system."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        discovery_engine = get_discovery_engine()
        discovered = discovery_engine.discover_all_processes()
        
        if not discovered:
            click.echo("No Context Cleaner processes discovered")
            return
            
        if format == "json":
            output = []
            for process in discovered:
                output.append({
                    "pid": process.pid,
                    "service_type": process.service_type,
                    "command_line": process.command_line,
                    "start_time": process.start_time.isoformat(),
                    "port": process.port,
                    "registration_source": process.registration_source
                })
            click.echo(json.dumps(output, indent=2))
        else:
            # Table format
            click.echo("Discovered Context Cleaner Processes:")
            click.echo("=" * 100)
            click.echo(f"{'PID':<8} {'Service':<15} {'Port':<6} {'Start Time':<20} {'Command':<45}")
            click.echo("-" * 100)
            
            for process in discovered:
                start_time_str = process.start_time.strftime("%m-%d %H:%M:%S")
                port_str = str(process.port) if process.port else "-"
                command_short = process.command_line[:42] + "..." if len(process.command_line) > 45 else process.command_line
                
                click.echo(f"{process.pid:<8} {process.service_type:<15} {port_str:<6} {start_time_str:<20} {command_short:<45}")
            
            click.echo(f"\nTotal: {len(discovered)} processes")
            
        # Register if requested
        if register:
            registry = get_process_registry()
            registered_count = 0
            
            for process in discovered:
                try:
                    if registry.register_process(process):
                        registered_count += 1
                except Exception as e:
                    if verbose:
                        click.echo(f"⚠️  Failed to register PID {process.pid}: {e}")
                        
            click.echo(f"📝 Registered {registered_count} new processes in registry")
            
    except Exception as e:
        click.echo(f"❌ Error discovering services: {e}", err=True)
        sys.exit(1)


@debug.command("registry-stats")
@click.pass_context
def registry_stats(ctx):
    """Show process registry statistics and health information."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        registry = get_process_registry()
        stats = registry.get_registry_stats()
        
        click.echo("Process Registry Statistics:")
        click.echo("=" * 50)
        click.echo(f"Database Path: {stats['database_path']}")
        click.echo(f"Total Processes: {stats['total_processes']}")
        click.echo(f"Running Processes: {stats['running_processes']}")
        click.echo(f"Failed Processes: {stats['failed_processes']}")
        click.echo(f"Stale Entries: {stats['stale_entries']}")
        click.echo()
        
        # Service type breakdown
        if stats['service_types']:
            click.echo("Service Types:")
            for service_type, count in stats['service_types'].items():
                click.echo(f"  {service_type}: {count}")
            click.echo()
        
        # Registration sources
        if stats['registration_sources']:
            click.echo("Registration Sources:")
            for source, count in stats['registration_sources'].items():
                click.echo(f"  {source}: {count}")
            click.echo()
        
        # Health status
        click.echo("Health Status:")
        click.echo(f"  Healthy: {stats['healthy_processes']}")
        click.echo(f"  Unhealthy: {stats['unhealthy_processes']}")
        click.echo(f"  Unknown: {stats['unknown_health_processes']}")
        click.echo()
        
        # Port usage
        if stats['ports_in_use']:
            click.echo("Ports in Use:")
            for port in sorted(stats['ports_in_use']):
                click.echo(f"  {port}")
            click.echo()
        
        # Database info
        click.echo("Database Info:")
        click.echo(f"  Size: {stats['database_size_bytes']} bytes")
        click.echo(f"  Last Cleanup: {stats['last_cleanup_time']}")
        
    except Exception as e:
        click.echo(f"❌ Error getting registry stats: {e}", err=True)
        sys.exit(1)


@debug.command("cleanup-stale")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without actually doing it")
@click.pass_context
def cleanup_stale(ctx, dry_run):
    """Clean up stale entries from the process registry."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        registry = get_process_registry()
        
        if dry_run:
            stale_entries = registry._find_stale_entries()
            
            if not stale_entries:
                click.echo("No stale entries found")
                return
                
            click.echo("Stale entries that would be removed:")
            click.echo("=" * 60)
            click.echo(f"{'PID':<8} {'Service':<15} {'Status':<10} {'Last Check':<20}")
            click.echo("-" * 60)
            
            for entry in stale_entries:
                last_check = entry.last_health_check.strftime("%m-%d %H:%M:%S") if entry.last_health_check else "Never"
                click.echo(f"{entry.pid:<8} {entry.service_type:<15} {entry.status:<10} {last_check:<20}")
                
            click.echo(f"\nTotal: {len(stale_entries)} stale entries")
            click.echo("\nRun without --dry-run to actually clean them up")
        else:
            removed_count = registry.cleanup_stale_entries()
            click.echo(f"🧹 Cleaned up {removed_count} stale entries from registry")
            
    except Exception as e:
        click.echo(f"❌ Error cleaning up stale entries: {e}", err=True)
        sys.exit(1)


@debug.command("health-check")
@click.option("--update-registry", is_flag=True, help="Update health status in registry")
@click.pass_context
def health_check(ctx, update_registry):
    """Perform health checks on all registered processes."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        registry = get_process_registry()
        processes = registry.get_all_processes()
        
        if not processes:
            click.echo("No processes in registry to check")
            return
            
        click.echo("Health Check Results:")
        click.echo("=" * 80)
        click.echo(f"{'PID':<8} {'Service':<15} {'Port':<6} {'Process':<8} {'Network':<8} {'Overall':<8}")
        click.echo("-" * 80)
        
        healthy_count = 0
        total_count = len(processes)
        
        for process in processes:
            # Check if process is still running
            process_alive = False
            try:
                psutil_process = psutil.Process(process.pid)
                process_alive = psutil_process.is_running()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_alive = False
            
            # Check network connectivity if port is specified
            network_ok = True
            if process.port:
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((process.host, process.port))
                    network_ok = result == 0
                    sock.close()
                except Exception:
                    network_ok = False
            
            # Overall health
            overall_healthy = process_alive and network_ok
            if overall_healthy:
                healthy_count += 1
            
            # Status indicators
            process_status = "✓" if process_alive else "✗"
            network_status = "✓" if network_ok else "✗" if process.port else "-"
            overall_status = "✓" if overall_healthy else "✗"
            port_str = str(process.port) if process.port else "-"
            
            click.echo(f"{process.pid:<8} {process.service_type:<15} {port_str:<6} {process_status:<8} {network_status:<8} {overall_status:<8}")
            
            # Update registry if requested
            if update_registry:
                process.last_health_check = datetime.now()
                process.last_health_status = overall_healthy
                if not process_alive:
                    process.status = "failed"
                registry.register_process(process)  # Uses INSERT OR REPLACE
        
        click.echo(f"\nHealth Summary: {healthy_count}/{total_count} processes healthy")
        
        if update_registry:
            click.echo("📝 Registry updated with health check results")
            
    except Exception as e:
        click.echo(f"❌ Error performing health check: {e}", err=True)
        sys.exit(1)


@debug.command("process-tree")
@click.option("--show-all", is_flag=True, help="Show all processes (not just Context Cleaner)")
@click.pass_context
def process_tree(ctx, show_all):
    """Show process tree for Context Cleaner processes."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        def find_context_cleaner_processes():
            """Find all Context Cleaner related processes."""
            cc_processes = []
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'create_time']):
                try:
                    info = proc.info
                    cmdline = ' '.join(info['cmdline']) if info['cmdline'] else ''
                    
                    # Check if it's a Context Cleaner process
                    if ('context_cleaner' in cmdline or 
                        'context-cleaner' in cmdline or
                        (info['name'] and 'python' in info['name'] and 'context_cleaner' in cmdline)):
                        
                        cc_processes.append({
                            'pid': info['pid'],
                            'ppid': info['ppid'],
                            'name': info['name'],
                            'cmdline': cmdline,
                            'create_time': datetime.fromtimestamp(info['create_time']),
                            'proc': proc
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return cc_processes
        
        def build_tree(processes):
            """Build process tree structure."""
            tree = {}
            orphans = []
            
            # Create parent-child mapping
            for proc in processes:
                pid = proc['pid']
                ppid = proc['ppid']
                
                if ppid not in [p['pid'] for p in processes]:
                    # Parent not in our Context Cleaner processes
                    orphans.append(proc)
                else:
                    if ppid not in tree:
                        tree[ppid] = []
                    tree[ppid].append(proc)
            
            return tree, orphans
        
        def print_tree(processes, tree, parent_pid=None, indent=0):
            """Print process tree recursively."""
            if parent_pid is None:
                # Print orphans first
                for proc in processes:
                    if proc['pid'] not in tree:
                        continue
                    print_process(proc, indent)
                    print_tree([], tree, proc['pid'], indent + 2)
            else:
                if parent_pid in tree:
                    for child in tree[parent_pid]:
                        print_process(child, indent)
                        print_tree([], tree, child['pid'], indent + 2)
        
        def print_process(proc, indent):
            """Print a single process with indentation."""
            indent_str = "  " * indent
            create_time_str = proc['create_time'].strftime("%H:%M:%S")
            cmdline_short = proc['cmdline'][:60] + "..." if len(proc['cmdline']) > 63 else proc['cmdline']
            
            click.echo(f"{indent_str}├─ PID {proc['pid']} ({create_time_str}) {cmdline_short}")
        
        if show_all:
            # Show all processes (simplified view)
            click.echo("All System Processes (not implemented - use 'ps aux' or htop)")
            return
        
        # Find Context Cleaner processes
        processes = find_context_cleaner_processes()
        
        if not processes:
            click.echo("No Context Cleaner processes found")
            return
        
        tree, orphans = build_tree(processes)
        
        click.echo("Context Cleaner Process Tree:")
        click.echo("=" * 80)
        
        # Print orphan processes (no parent in our list)
        if orphans:
            click.echo("Root Processes:")
            for proc in orphans:
                print_process(proc, 0)
                print_tree([], tree, proc['pid'], 1)
            click.echo()
        
        # Print processes with parents in our list
        root_processes = [p for p in processes if p['pid'] in tree]
        if root_processes:
            click.echo("Process Tree:")
            for proc in root_processes:
                if proc['ppid'] not in [p['pid'] for p in processes]:
                    print_process(proc, 0)
                    print_tree([], tree, proc['pid'], 1)
        
        click.echo(f"\nTotal Context Cleaner processes: {len(processes)}")
        
    except Exception as e:
        click.echo(f"❌ Error showing process tree: {e}", err=True)
        sys.exit(1)


@debug.command("test-registry")
@click.pass_context 
def test_registry(ctx):
    """Test process registry operations (for development/debugging)."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        click.echo("Testing Process Registry Operations...")
        click.echo("=" * 50)
        
        registry = get_process_registry()
        
        # Test 1: Create a test process entry
        click.echo("1. Creating test process entry...")
        test_process = ProcessEntry(
            pid=99999,
            command_line="test_command --test",
            service_type="test_service",
            start_time=datetime.now(),
            registration_time=datetime.now(),
            port=9999,
            session_id="test_session",
            registration_source="debug_test"
        )
        
        success = registry.register_process(test_process)
        click.echo(f"   Registration: {'✓' if success else '✗'}")
        
        # Test 2: Retrieve the process
        click.echo("2. Retrieving test process...")
        retrieved = registry.get_process(99999)
        click.echo(f"   Retrieval: {'✓' if retrieved else '✗'}")
        
        if retrieved:
            click.echo(f"   Service Type: {retrieved.service_type}")
            click.echo(f"   Port: {retrieved.port}")
        
        # Test 3: Update the process
        click.echo("3. Updating test process...")
        if retrieved:
            retrieved.status = "testing"
            retrieved.last_health_check = datetime.now()
            retrieved.last_health_status = True
            update_success = registry.register_process(retrieved)  # Uses INSERT OR REPLACE
            click.echo(f"   Update: {'✓' if update_success else '✗'}")
        
        # Test 4: List processes (should include our test)
        click.echo("4. Listing all processes...")
        all_processes = registry.get_all_processes()
        test_found = any(p.pid == 99999 for p in all_processes)
        click.echo(f"   Test process in list: {'✓' if test_found else '✗'}")
        click.echo(f"   Total processes: {len(all_processes)}")
        
        # Test 5: Get statistics
        click.echo("5. Getting registry statistics...")
        stats = registry.get_registry_stats()
        click.echo(f"   Stats retrieved: {'✓' if stats else '✗'}")
        if stats:
            click.echo(f"   Total processes: {stats['total_processes']}")
        
        # Test 6: Clean up test process
        click.echo("6. Cleaning up test process...")
        cleanup_success = registry.unregister_process(99999)
        click.echo(f"   Cleanup: {'✓' if cleanup_success else '✗'}")
        
        # Verify cleanup
        after_cleanup = registry.get_process(99999)
        click.echo(f"   Verification: {'✓' if not after_cleanup else '✗'}")
        
        click.echo("\nRegistry test completed!")
        
    except Exception as e:
        click.echo(f"❌ Error testing registry: {e}", err=True)
        # Clean up test process if it exists
        try:
            registry = get_process_registry()
            registry.unregister_process(99999)
        except:
            pass
        sys.exit(1)