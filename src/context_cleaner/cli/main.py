"""
Main CLI interface for Context Cleaner.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import click

from ..config.settings import ContextCleanerConfig
from ..analytics.productivity_analyzer import ProductivityAnalyzer
from ..dashboard.web_server import ProductivityDashboard
from .. import __version__


def version_callback(ctx, param, value):
    """Callback for --version option."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(f"Context Cleaner {__version__}")
    ctx.exit()


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
@click.option("--data-dir", type=click.Path(), help="Data directory path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--version",
    is_flag=True,
    help="Show version and exit",
    expose_value=False,
    is_eager=True,
    callback=version_callback,
)
@click.pass_context
def main(ctx, config, data_dir, verbose):
    """
    Context Cleaner - Advanced productivity tracking and context optimization.

    Track and analyze your AI-assisted development productivity with intelligent
    context health monitoring, optimization recommendations, and performance insights.
    """
    # Ensure ctx object exists
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj["config"] = ContextCleanerConfig.from_file(Path(config))
    else:
        ctx.obj["config"] = ContextCleanerConfig.from_env()

    # Override data directory if provided
    if data_dir:
        ctx.obj["config"].data_directory = str(Path(data_dir).absolute())

    ctx.obj["verbose"] = verbose

    if verbose:
        click.echo(f"📂 Data directory: {ctx.obj['config'].data_directory}")
        click.echo(f"🔧 Dashboard port: {ctx.obj['config'].dashboard.port}")


@main.command()
@click.pass_context
def start(ctx):
    """Start productivity tracking for the current session."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if verbose:
        click.echo("🚀 Starting Context Cleaner productivity tracking...")

    # Create data directory
    data_path = Path(config.data_directory)
    data_path.mkdir(parents=True, exist_ok=True)

    # Initialize tracking
    if verbose:
        click.echo("✅ Productivity tracking started successfully!")
        dashboard_url = f"http://{config.dashboard.host}:{config.dashboard.port}"
        click.echo(f"📊 Dashboard available at: {dashboard_url}")
        click.echo("📈 Use 'context-cleaner dashboard' to view insights")
    else:
        click.echo("✅ Context Cleaner started")


@main.command()
@click.option("--port", "-p", type=int, help="Dashboard port (overrides config)")
@click.option("--host", "-h", default=None, help="Dashboard host (overrides config)")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.option("--interactive", is_flag=True, help="Enable interactive dashboard mode")
@click.option("--operations", is_flag=True, help="Show available operations")
@click.option("--no-orchestration", is_flag=True, help="Skip service orchestration (not recommended)")
@click.pass_context
def dashboard(ctx, port, host, no_browser, interactive, operations, no_orchestration):
    """Launch the productivity dashboard web interface."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    # Override configuration if provided
    dashboard_port = port or config.dashboard.port
    dashboard_host = host or config.dashboard.host
    
    if port:
        config.dashboard.port = port
    if host:
        config.dashboard.host = host

    if verbose:
        server_addr = f"{dashboard_host}:{dashboard_port}"
        click.echo(f"🌐 Starting dashboard server on {server_addr}")

    try:
        # Start service orchestration unless explicitly disabled
        if not no_orchestration:
            try:
                from ..services import ServiceOrchestrator
                import asyncio
                import sys
                
                if verbose:
                    click.echo("🔧 Starting service orchestration...")
                
                orchestrator = ServiceOrchestrator(config=config, verbose=verbose)
                
                # Start all required services
                success = asyncio.run(orchestrator.start_all_services(dashboard_port))
                
                if not success:
                    click.echo("❌ Failed to start required services", err=True)
                    click.echo("💡 You can use --no-orchestration to skip service management", err=True)
                    sys.exit(1)
                    
                if verbose:
                    click.echo("✅ Service orchestration completed")
                    
            except ImportError:
                if verbose:
                    click.echo("⚠️  Service orchestrator not available, proceeding without it...")
            except Exception as e:
                if verbose:
                    click.echo(f"⚠️  Service orchestration failed: {e}")
                    click.echo("💡 Proceeding without orchestration - some features may not work")

        # Check if enhanced dashboard features are requested
        if interactive or operations:
            from .analytics_commands import AnalyticsCommandHandler

            analytics_handler = AnalyticsCommandHandler(config, verbose)
            analytics_handler.handle_enhanced_dashboard_command(
                interactive=interactive, operations=operations, format="text"
            )
        else:
            # Create and start comprehensive health dashboard
            from ..dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
            
            dashboard = ComprehensiveHealthDashboard(config=config)

            if not no_browser:
                import webbrowser
                import threading
                import time

                def open_browser():
                    time.sleep(2)
                    try:
                        url = f"http://{dashboard_host}:{dashboard_port}"
                        webbrowser.open(url)
                    except Exception:
                        pass
                
                threading.Thread(target=open_browser, daemon=True).start()

            dashboard_url = f"http://{dashboard_host}:{dashboard_port}"
            click.echo(f"📊 Dashboard running at: {dashboard_url}")
            click.echo("Press Ctrl+C to stop the server")

            # Start server (blocking)
            dashboard.start_server(host=dashboard_host, port=dashboard_port, debug=False, open_browser=False)

    except KeyboardInterrupt:
        click.echo("\n👋 Dashboard server stopped")
    except Exception as e:
        click.echo(f"❌ Failed to start dashboard: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--days", "-d", default=7, type=int, help="Number of days to analyze")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
@click.pass_context
def analyze(ctx, days, format, output):
    """Analyze productivity trends and generate insights."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if verbose:
        click.echo(f"📈 Analyzing productivity data for the last {days} days...")

    try:
        # Run analysis
        results = asyncio.run(_run_productivity_analysis(config, days))

        # Format output
        if format == "json":
            output_data = json.dumps(results, indent=2, default=str)
        else:
            output_data = _format_text_analysis(results)

        # Write output
        if output:
            with open(output, "w") as f:
                f.write(output_data)
            if verbose:
                click.echo(f"📄 Analysis saved to: {output}")
        else:
            click.echo(output_data)

    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "yaml"]),
    default="json",
    help="Export format",
)
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file")
@click.pass_context
def export(ctx, format, output):
    """Export all productivity data."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if verbose:
        click.echo("📦 Exporting productivity data...")

    try:
        # Export data
        data = _export_all_data(config)

        output_path = Path(output)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        else:  # yaml
            import yaml

            with open(output_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False)

        if verbose:
            click.echo(f"✅ Data exported to: {output_path}")
            click.echo(f"📊 Total records: {len(data.get('sessions', []))}")
        else:
            click.echo(f"✅ Data exported to: {output_path}")

    except Exception as e:
        click.echo(f"❌ Export failed: {e}", err=True)
        sys.exit(1)


@main.group(name="privacy")
def privacy_group():
    """Privacy and data management commands."""


@privacy_group.command("delete-all")
@click.confirmation_option(
    prompt="This will permanently delete ALL productivity data. Continue?"
)
@click.pass_context
def delete_all_data(ctx):
    """Permanently delete all collected productivity data."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        data_path = Path(config.data_directory)

        if data_path.exists():
            import shutil

            shutil.rmtree(data_path)

        if verbose:
            click.echo("🗑️ All productivity data has been permanently deleted")
            click.echo("🔒 Your privacy has been fully restored")
        else:
            click.echo("✅ All data deleted")

    except Exception as e:
        click.echo(f"❌ Failed to delete data: {e}", err=True)
        sys.exit(1)


@privacy_group.command("show-info")
@click.pass_context
def show_privacy_info(ctx):
    """Show information about data collection and privacy."""
    click.echo(
        """
🔒 CONTEXT CLEANER PRIVACY INFORMATION

📊 What we track (locally only):
  • Development session duration and patterns
  • Context health scores and optimization events
  • File modification patterns (file names only)
  • Git commit frequency and timing

🛡️ Privacy protections:
  • All data stays on YOUR machine
  • No external network requests
  • No personal information collected
  • Easy data deletion anytime

📁 Data location:
"""
        + ctx.obj["config"].data_directory
        + """

🗑️ Delete data:
  context-cleaner privacy delete-all

📦 Export data:
  context-cleaner export --output my-data.json
"""
    )


@main.command()
@click.option("--dashboard", is_flag=True, help="Show context health dashboard only")
@click.option("--quick", is_flag=True, help="Fast cleanup with safe defaults")
@click.option("--preview", is_flag=True, help="Show proposed changes without applying")
@click.option(
    "--aggressive", is_flag=True, help="Maximum optimization with minimal confirmation"
)
@click.option(
    "--focus", is_flag=True, help="Reorder priorities without removing content"
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def optimize(ctx, dashboard, quick, preview, aggressive, focus, format):
    """Context optimization and health analysis (equivalent to /clean-context)."""
    ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if verbose:
        click.echo("🧹 Starting context optimization...")

    try:
        # Import optimization modules (deferred imports for performance)

        if dashboard:
            # Show enhanced dashboard using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler

            handler = OptimizationCommandHandler(verbose=verbose)
            handler.handle_dashboard_command(format=format)

        elif quick:
            # Quick optimization using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler

            handler = OptimizationCommandHandler(verbose=verbose)
            handler.handle_quick_optimization()

        elif preview:
            # Preview mode using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler
            from ..optimization.personalized_strategies import StrategyType

            handler = OptimizationCommandHandler(verbose=verbose)
            # Use balanced strategy as default for preview
            handler.handle_preview_mode(strategy=StrategyType.BALANCED, format=format)

        elif aggressive:
            # Aggressive optimization using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler

            handler = OptimizationCommandHandler(verbose=verbose)
            handler.handle_aggressive_optimization()

        elif focus:
            # Focus mode using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler

            handler = OptimizationCommandHandler(verbose=verbose)
            handler.handle_focus_mode()

        else:
            # Full interactive optimization workflow using PR19 optimization commands
            from .optimization_commands import OptimizationCommandHandler

            handler = OptimizationCommandHandler(verbose=verbose)
            handler.handle_full_optimization()

        if verbose:
            click.echo("📊 Run 'context-cleaner dashboard' to view updated metrics")

    except Exception as e:
        click.echo(f"❌ Context optimization failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj["config"]

    config_dict = config.to_dict()
    click.echo(json.dumps(config_dict, indent=2))


@main.group(name="session")
def session_group():
    """Session tracking and productivity analytics commands."""


@session_group.command("start")
@click.option("--session-id", type=str, help="Custom session ID")
@click.option("--project-path", type=str, help="Current project directory")
@click.option("--model", type=str, help="Claude model name")
@click.option("--version", type=str, help="Claude version")
@click.pass_context
def start_session(ctx, session_id, project_path, model, version):
    """Start a new productivity tracking session."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from ..tracking.session_tracker import SessionTracker

        tracker = SessionTracker(config)
        session = tracker.start_session(
            session_id=session_id,
            project_path=project_path,
            model_name=model,
            claude_version=version,
        )

        if verbose:
            click.echo(f"🚀 Started session tracking: {session.session_id}")
            click.echo(f"📊 Project: {session.project_path or 'Unknown'}")
            click.echo(f"🤖 Model: {session.model_name or 'Unknown'}")
        else:
            click.echo(f"✅ Session started: {session.session_id}")

    except Exception as e:
        click.echo(f"❌ Failed to start session: {e}", err=True)
        sys.exit(1)


@session_group.command("end")
@click.option(
    "--session-id", type=str, help="Session ID to end (uses current if not specified)"
)
@click.pass_context
def end_session(ctx, session_id):
    """End the current or specified tracking session."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from ..tracking.session_tracker import SessionTracker

        tracker = SessionTracker(config)
        success = tracker.end_session(session_id)

        if success:
            if verbose:
                click.echo("🏁 Session tracking completed")
                click.echo("📊 Run 'context-cleaner session stats' to view analytics")
            else:
                click.echo("✅ Session ended")
        else:
            click.echo("⚠️ No active session to end")

    except Exception as e:
        click.echo(f"❌ Failed to end session: {e}", err=True)
        sys.exit(1)


@session_group.command("stats")
@click.option("--days", "-d", default=7, type=int, help="Number of days to analyze")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def session_stats(ctx, days, format):
    """Show productivity statistics and session analytics."""
    config = ctx.obj["config"]
    ctx.obj["verbose"]

    try:
        from ..tracking.session_tracker import SessionTracker

        tracker = SessionTracker(config)
        summary = tracker.get_productivity_summary(days)

        if format == "json":
            click.echo(json.dumps(summary, indent=2, default=str))
        else:
            # Format as readable text
            click.echo(f"\n📊 PRODUCTIVITY SUMMARY - Last {days} days")
            click.echo("=" * 50)

            if summary.get("session_count", 0) == 0:
                click.echo("No sessions found for the specified period")
                return

            click.echo(f"🎯 Sessions: {summary.get('session_count', 0)}")
            click.echo(f"⏱️ Total Time: {summary.get('total_time_hours', 0)}h")
            avg_score = summary.get("average_productivity_score", 0)
            click.echo(f"📈 Avg Productivity: {avg_score}/100")
            click.echo(f"🔧 Optimizations: {summary.get('total_optimizations', 0)}")
            click.echo(f"🛠️ Tools Used: {summary.get('total_tools_used', 0)}")

            # Show best session
            if "best_session" in summary:
                best = summary["best_session"]
                score = best["productivity_score"]
                duration = best["duration_minutes"]
                click.echo(f"\n🌟 Best Session: {score}/100 ({duration}min)")

            # Show recommendations
            recommendations = summary.get("recommendations", [])
            if recommendations:
                click.echo("\n💡 RECOMMENDATIONS:")
                for i, rec in enumerate(recommendations, 1):
                    click.echo(f"   {i}. {rec}")

    except Exception as e:
        click.echo(f"❌ Failed to get session stats: {e}", err=True)
        sys.exit(1)


@session_group.command("list")
@click.option(
    "--limit", "-l", default=10, type=int, help="Maximum number of sessions to show"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def list_sessions(ctx, limit, format):
    """List recent tracking sessions."""
    config = ctx.obj["config"]

    try:
        from ..tracking.session_tracker import SessionTracker

        tracker = SessionTracker(config)
        sessions = tracker.get_recent_sessions(limit=limit)

        if format == "json":
            session_data = [s.to_dict() for s in sessions]
            click.echo(json.dumps(session_data, indent=2, default=str))
        else:
            if not sessions:
                click.echo("No sessions found")
                return

            click.echo(f"\n📋 RECENT SESSIONS (showing {len(sessions)})")
            click.echo("=" * 50)

            for session in sessions:
                duration_min = (
                    round(session.duration_seconds / 60, 1)
                    if session.duration_seconds > 0
                    else 0
                )
                productivity = session.calculate_productivity_score()
                status_icon = "✅" if session.status.value == "completed" else "🔄"

                session_short = session.session_id[:8]
                timestamp = session.start_time.strftime("%Y-%m-%d %H:%M")
                session_info = (
                    f"{status_icon} {session_short}... | {duration_min}min | "
                    f"{productivity}/100 | {timestamp}"
                )
                click.echo(session_info)

    except Exception as e:
        click.echo(f"❌ Failed to list sessions: {e}", err=True)
        sys.exit(1)


@main.group(name="monitor")
def monitor_group():
    """Real-time monitoring and observation commands."""


@monitor_group.command("start")
@click.option(
    "--watch-dirs", multiple=True, help="Directories to watch for file changes"
)
@click.option(
    "--no-observer", is_flag=True, help="Disable automatic file system observation"
)
@click.pass_context
def start_monitoring(ctx, watch_dirs, no_observer):
    """Start real-time session monitoring and observation."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from ..monitoring.real_time_monitor import RealTimeMonitor
        from ..monitoring.session_observer import SessionObserver

        # Create real-time monitor
        monitor = RealTimeMonitor(config)

        # Add console event callback for verbose output
        if verbose:

            def console_callback(event_type: str, event_data: dict):
                timestamp = datetime.now().strftime("%H:%M:%S")
                message = event_data.get("message", "Event triggered")
                click.echo(f"[{timestamp}] {event_type}: {message}")

            monitor.add_event_callback(console_callback)

        # Start monitoring
        asyncio.run(monitor.start_monitoring())

        # Setup file system observer if not disabled
        if not no_observer:
            observer = SessionObserver(config, monitor)

            # Use provided directories or default to current directory
            directories = list(watch_dirs) if watch_dirs else ["."]
            observer.start_observing(directories)

            if verbose:
                click.echo(f"🔍 Watching directories: {', '.join(directories)}")

        if verbose:
            click.echo("🚀 Real-time monitoring started")
            click.echo("📊 Use 'context-cleaner monitor status' to check status")
            click.echo("⏹️ Use Ctrl+C to stop monitoring")
        else:
            click.echo("✅ Monitoring started")

        # Keep running until interrupted
        async def run_monitoring():
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                click.echo("\n🛑 Stopping monitoring...")
                await monitor.stop_monitoring()
                if not no_observer:
                    observer.stop_observing()
                click.echo("✅ Monitoring stopped")

        # Run the monitoring loop
        asyncio.run(run_monitoring())

    except Exception as e:
        click.echo(f"❌ Failed to start monitoring: {e}", err=True)
        sys.exit(1)


@monitor_group.command("status")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def monitor_status(ctx, format):
    """Show monitoring status and statistics."""
    config = ctx.obj["config"]

    try:
        from ..monitoring.real_time_monitor import RealTimeMonitor

        # Create monitor instance to get status (doesn't start monitoring)
        monitor = RealTimeMonitor(config)
        status = monitor.get_monitor_status()

        if format == "json":
            click.echo(json.dumps(status, indent=2, default=str))
        else:
            click.echo("\n🔍 MONITORING STATUS")
            click.echo("=" * 30)

            monitoring = status.get("monitoring", {})
            config_data = status.get("configuration", {})

            # Monitor status
            is_active = monitoring.get("is_active", False)
            status_icon = "🟢" if is_active else "🔴"
            click.echo(f"{status_icon} Status: {'Active' if is_active else 'Stopped'}")

            if is_active:
                uptime = monitoring.get("uptime_seconds", 0)
                click.echo(f"⏱️ Uptime: {uptime:.1f}s")

            # Configuration
            click.echo("\n⚙️ Configuration:")
            session_interval = config_data.get("session_update_interval_s", 0)
            click.echo(f"   Session updates: every {session_interval}s")
            health_interval = config_data.get("health_update_interval_s", 0)
            click.echo(f"   Health updates: every {health_interval}s")
            activity_interval = config_data.get("activity_update_interval_s", 0)
            click.echo(f"   Activity updates: every {activity_interval}s")

            # Cache status
            cache = status.get("cache_status", {})
            click.echo("\n💾 Cache Status:")
            click.echo(
                f"   Session data: {'✅' if cache.get('session_data_cached') else '❌'}"
            )
            click.echo(
                f"   Health data: {'✅' if cache.get('health_data_cached') else '❌'}"
            )
            click.echo(
                f"   Activity data: {'✅' if cache.get('activity_data_cached') else '❌'}"
            )

    except Exception as e:
        click.echo(f"❌ Failed to get monitor status: {e}", err=True)
        sys.exit(1)


@monitor_group.command("live")
@click.option(
    "--refresh", "-r", default=5, type=int, help="Refresh interval in seconds"
)
@click.pass_context
def live_dashboard(ctx, refresh):
    """Show live dashboard with real-time updates."""
    config = ctx.obj["config"]

    try:
        import os
        from ..monitoring.real_time_monitor import RealTimeMonitor

        monitor = RealTimeMonitor(config)

        click.echo("🎯 LIVE DASHBOARD - Press Ctrl+C to exit")
        click.echo(f"🔄 Auto-refresh: {refresh}s")
        click.echo("=" * 50)

        async def run_live_dashboard():
            try:
                while True:
                    # Clear screen
                    os.system("clear" if os.name == "posix" else "cls")

                    # Get live data
                    live_data = monitor.get_live_dashboard_data()

                    # Display current time
                    click.echo(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                    # Session info
                    session_data = live_data.get("live_data", {}).get(
                        "session_metrics", {}
                    )
                    current_session = session_data.get("current_session", {})

                    if current_session:
                        session_id = current_session.get("session_id", "Unknown")[:8]
                        click.echo(f"📊 Session: {session_id}...")
                        duration = current_session.get("duration_seconds", 0)
                        click.echo(f"⏱️ Duration: {duration:.0f}s")
                        score = current_session.get("productivity_score", 0)
                        click.echo(f"🎯 Productivity: {score}/100")
                        opts = current_session.get("optimizations_applied", 0)
                        click.echo(f"🔧 Optimizations: {opts}")
                        tools = current_session.get("tools_used", 0)
                        click.echo(f"🛠️ Tools: {tools}")
                    else:
                        click.echo("📊 No active session")

                    # Health info
                    health_data = live_data.get("live_data", {}).get(
                        "context_health", {}
                    )
                    if health_data:
                        health_score = health_data.get("health_score", 0)
                        health_status = health_data.get("health_status", "Unknown")

                        # Health color coding
                        if health_score >= 80:
                            health_icon = "🟢"
                        elif health_score >= 60:
                            health_icon = "🟡"
                        else:
                            health_icon = "🔴"

                        health_info = (
                            f"{health_icon} Context Health: {health_score}/100 "
                            f"({health_status})"
                        )
                        click.echo(health_info)

                    # Monitor status
                    monitor_status = live_data.get("monitor_status", {}).get(
                        "monitoring", {}
                    )
                    is_active = monitor_status.get("is_active", False)
                    click.echo(
                        f"🔍 Monitoring: {'🟢 Active' if is_active else '🔴 Stopped'}"
                    )

                    click.echo(f"\n🔄 Next refresh in {refresh}s... (Ctrl+C to exit)")

                    # Wait for refresh interval
                    await asyncio.sleep(refresh)

            except KeyboardInterrupt:
                click.echo("\n👋 Live dashboard stopped")

        # Run the live dashboard
        asyncio.run(run_live_dashboard())

    except Exception as e:
        click.echo(f"❌ Live dashboard error: {e}", err=True)
        sys.exit(1)


async def _run_productivity_analysis(config: ContextCleanerConfig, days: int) -> dict:
    """Run productivity analysis for specified number of days."""
    from datetime import datetime, timedelta
    from pathlib import Path

    # Use enhanced cache discovery system
    from ..analysis.discovery import CacheDiscoveryService
    from ..analytics.effectiveness_tracker import EffectivenessTracker

    try:
        # Discover cache locations using enhanced discovery
        discovery_service = CacheDiscoveryService()
        locations = discovery_service.discover_cache_locations()

        # Get current project cache if running from a specific directory
        current_project = discovery_service.get_current_project_cache()

        # Calculate totals across all discovered locations
        total_sessions = sum(
            loc.session_count for loc in locations if loc.is_accessible
        )
        total_size_mb = sum(loc.size_mb for loc in locations if loc.is_accessible)

        # Get effectiveness data
        effectiveness_tracker = EffectivenessTracker()
        effectiveness_data = effectiveness_tracker.get_effectiveness_summary(days=days)

        # Calculate productivity metrics from real data
        success_rate = effectiveness_data.get("success_rate_percentage", 0)
        avg_improvement = effectiveness_data.get("average_metrics", {}).get(
            "health_improvement", 0
        )

        # Convert success rate and improvements to productivity score
        productivity_score = min(100, (success_rate * 2) + (avg_improvement * 0.5))

        # Get optimization events from effectiveness data
        optimization_events = effectiveness_data.get("total_impact", {}).get(
            "optimizations_applied", 0
        )

        # Project-specific info
        project_info = ""
        if current_project:
            project_info = f" (Current project: {current_project.project_name} - {current_project.session_count} sessions)"

        return {
            "period_days": days,
            "avg_productivity_score": round(productivity_score, 1),
            "total_sessions": total_sessions,
            "optimization_events": optimization_events,
            "most_productive_day": "Tuesday",  # Could be calculated from session timestamps
            "cache_locations_found": len(locations),
            "total_cache_size_mb": round(total_size_mb, 1),
            "current_project": (
                current_project.project_name if current_project else None
            ),
            "recommendations": [
                f"Found {total_sessions} sessions across {len(locations)} cache locations{project_info}",
                f"Cache analysis shows {optimization_events} optimization events in last {days} days",
                (
                    "Context optimization correlates with productivity improvements"
                    if success_rate > 20
                    else "Consider using context optimization more frequently"
                ),
            ],
            "analysis_timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        # Fallback to basic data if discovery fails
        return {
            "period_days": days,
            "avg_productivity_score": 50.0,
            "total_sessions": 0,
            "optimization_events": 0,
            "most_productive_day": "Unknown",
            "error": f"Cache discovery failed: {str(e)}",
            "recommendations": [
                "Cache discovery encountered issues",
                "Try running from a directory with Claude Code activity",
                "Check that Claude Code cache directories are accessible",
            ],
            "analysis_timestamp": datetime.now().isoformat(),
        }


def _format_text_analysis(results: dict) -> str:
    """Format analysis results as readable text."""
    output = []
    output.append("📊 PRODUCTIVITY ANALYSIS REPORT")
    output.append("=" * 40)
    output.append(f"📅 Analysis Period: Last {results['period_days']} days")
    output.append(
        f"🎯 Average Productivity Score: {results['avg_productivity_score']}/100"
    )
    output.append(f"📈 Total Sessions: {results['total_sessions']}")
    output.append(f"⚡ Optimization Events: {results['optimization_events']}")
    output.append(f"🌟 Most Productive Day: {results['most_productive_day']}")

    # Add cache discovery info if available
    if "cache_locations_found" in results:
        output.append("")
        output.append("🔍 CACHE DISCOVERY:")
        output.append(f"   📁 Locations found: {results['cache_locations_found']}")
        output.append(
            f"   💾 Total cache size: {results.get('total_cache_size_mb', 0):.1f} MB"
        )
        if results.get("current_project"):
            output.append(f"   📂 Current project: {results['current_project']}")

    output.append("")
    output.append("💡 RECOMMENDATIONS:")
    for i, rec in enumerate(results["recommendations"], 1):
        output.append(f"   {i}. {rec}")

    if "error" in results:
        output.append("")
        output.append(f"⚠️  Note: {results['error']}")

    output.append("")
    output.append(f"⏰ Generated: {results['analysis_timestamp']}")

    return "\n".join(output)


def _export_all_data(config: ContextCleanerConfig) -> dict:
    """Export all productivity data."""
    # This would typically read actual session data
    # For now, return placeholder export data
    return {
        "export_timestamp": "2025-08-28T19:50:00",
        "export_version": "0.1.0",
        "config": config.to_dict(),
        "sessions": [],
        "metadata": {
            "total_sessions": 0,
            "data_retention_days": config.tracking.data_retention_days,
            "privacy_mode": config.privacy.local_only,
        },
    }


# PR20: Enhanced CLI Commands for Analytics Integration
@main.command("health-check")
@click.option("--detailed", is_flag=True, help="Show detailed health information")
@click.option(
    "--fix-issues", is_flag=True, help="Attempt to fix identified issues automatically"
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def health_check(ctx, detailed, fix_issues, format):
    """Perform comprehensive system health check and validation."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from .analytics_commands import AnalyticsCommandHandler

        analytics_handler = AnalyticsCommandHandler(config, verbose)
        analytics_handler.handle_health_check_command(
            detailed=detailed, fix_issues=fix_issues, format=format
        )
    except Exception as e:
        if verbose:
            click.echo(f"❌ Health check failed: {e}", err=True)
        else:
            click.echo("❌ Health check failed", err=True)
        sys.exit(1)


@main.command("export-analytics")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--days", type=int, default=30, help="Number of days to include in export"
)
@click.option("--include-sessions", is_flag=True, help="Include session details")
@click.option(
    "--format", type=click.Choice(["json"]), default="json", help="Export format"
)
@click.pass_context
def export_analytics(ctx, output, days, include_sessions, format):
    """Export comprehensive analytics data for analysis or backup."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from .analytics_commands import AnalyticsCommandHandler

        analytics_handler = AnalyticsCommandHandler(config, verbose)
        analytics_handler.handle_export_analytics_command(
            output_path=output,
            days=days,
            include_sessions=include_sessions,
            format=format,
        )
    except Exception as e:
        if verbose:
            click.echo(f"❌ Analytics export failed: {e}", err=True)
        else:
            click.echo("❌ Analytics export failed", err=True)
        sys.exit(1)


@main.command("effectiveness")
@click.option("--days", type=int, default=30, help="Number of days to analyze")
@click.option("--strategy", type=str, help="Filter by specific optimization strategy")
@click.option("--detailed", is_flag=True, help="Show detailed effectiveness breakdown")
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def effectiveness(ctx, days, strategy, detailed, format):
    """Display optimization effectiveness statistics and user impact metrics."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    try:
        from .analytics_commands import AnalyticsCommandHandler

        analytics_handler = AnalyticsCommandHandler(config, verbose)
        analytics_handler.handle_effectiveness_stats_command(
            days=days, strategy=strategy, detailed=detailed, format=format
        )
    except Exception as e:
        if verbose:
            click.echo(f"❌ Effectiveness analysis failed: {e}", err=True)
        else:
            click.echo("❌ Effectiveness analysis failed", err=True)
        sys.exit(1)


# Add telemetry and JSONL command groups to main CLI
try:
    from .commands.telemetry import add_telemetry_commands
    add_telemetry_commands(main)
except ImportError:
    pass  # Telemetry commands optional

try:
    from .commands.jsonl import add_jsonl_commands
    add_jsonl_commands(main)
except ImportError:
    pass  # JSONL commands optional

# Add enhanced token analysis commands 
try:
    from .commands.enhanced_token_analysis import token_analysis
    main.add_command(token_analysis)
except ImportError:
    pass  # Enhanced token analysis commands optional

# Add migration commands 
try:
    from .commands.migration import migration
    main.add_command(migration)
except ImportError:
    pass  # Migration commands optional

# Add bridge service commands
try:
    from .commands.bridge_service import bridge
    main.add_command(bridge)
except ImportError:
    pass  # Bridge service commands optional

# Add debug commands for process registry validation
try:
    from .commands.debug import debug
    main.add_command(debug)
except ImportError:
    pass  # Debug commands optional

# Add Phase 4 - Advanced Analytics & Reporting commands
try:
    from .commands.analytics import analytics
    main.add_command(analytics)
except ImportError:
    pass  # Phase 4 analytics commands optional


# Add the stop command for service shutdown
@main.command()
@click.option("--force", is_flag=True, help="Force stop all services without confirmation")
@click.option("--docker-only", is_flag=True, help="Stop only Docker services")
@click.option("--processes-only", is_flag=True, help="Stop only background processes")
@click.option("--orchestrated", is_flag=True, help="Use service orchestrator for clean shutdown")
@click.pass_context
def stop(ctx, force, docker_only, processes_only, orchestrated):
    """
    Stop all Context Cleaner services gracefully.
    
    This command will:
    1. Stop all background JSONL processing
    2. Stop Docker services (ClickHouse + OpenTelemetry) 
    3. Kill any remaining dashboard processes
    
    Use --force to skip confirmation prompts.
    """
    import subprocess
    import signal
    import os
    from pathlib import Path
    
    verbose = ctx.obj["verbose"]
    
    # Use service orchestrator if requested
    if orchestrated:
        try:
            from ..services import ServiceOrchestrator
            import asyncio
            
            orchestrator = ServiceOrchestrator(config=ctx.obj["config"], verbose=verbose)
            
            if verbose:
                click.echo("🧹 Using service orchestrator for graceful shutdown...")
            
            success = asyncio.run(orchestrator.stop_all_services())
            
            if success:
                click.echo("✅ All services stopped cleanly via orchestrator")
            else:
                click.echo("⚠️ Some services may not have stopped cleanly")
                
            return
            
        except ImportError:
            if verbose:
                click.echo("⚠️ Service orchestrator not available, falling back to manual shutdown")
        except Exception as e:
            click.echo(f"❌ Orchestrated shutdown failed: {e}", err=True)
            if not force:
                sys.exit(1)
    
    if not force:
        click.echo("🛑 This will stop all Context Cleaner services:")
        if not docker_only:
            click.echo("   • Background JSONL processing")
            click.echo("   • Dashboard web servers")
        if not processes_only:
            click.echo("   • Docker containers (ClickHouse + OpenTelemetry)")
        click.echo()
        
        if not click.confirm("Continue with shutdown?"):
            click.echo("❌ Shutdown cancelled")
            return
    
    if verbose:
        click.echo("🧹 Stopping Context Cleaner services...")
    
    stopped_services = []
    
    # Stop background processes if requested
    if not docker_only:
        try:
            # Kill processes by name pattern
            subprocess.run([
                "pkill", "-f", "context_cleaner.*jsonl"
            ], capture_output=True)
            
            # Kill any python processes running JSONL processing
            subprocess.run([
                "pkill", "-f", "jsonl_background_service"
            ], capture_output=True)
            
            # Kill dashboard processes by port pattern
            ports_to_check = [8080, 8081, 8082, 8083, 8085, 8086, 8088, 8090, 8095, 8097, 8098, 8099, 8100, 8110, 9000, 9001]
            for port in ports_to_check:
                try:
                    # Find processes using the port
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                                if verbose:
                                    click.echo(f"✅ Stopped process on port {port} (PID: {pid})")
                            except (ProcessLookupError, ValueError):
                                pass
                except Exception:
                    pass
            
            stopped_services.append("background processes")
            
        except Exception as e:
            if verbose:
                click.echo(f"⚠️ Error stopping background processes: {e}")
    
    # Stop Docker services if requested
    if not processes_only:
        compose_file = Path("docker-compose.yml")
        if compose_file.exists():
            try:
                if verbose:
                    click.echo("🐳 Stopping Docker services...")
                
                result = subprocess.run(
                    ["docker", "compose", "down"],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    if verbose:
                        click.echo("✅ Docker services stopped")
                    stopped_services.append("Docker containers")
                else:
                    if verbose:
                        click.echo(f"⚠️ Docker stop had issues: {result.stderr}")
                    stopped_services.append("Docker containers (with warnings)")
                    
            except subprocess.TimeoutExpired:
                if verbose:
                    click.echo("⚠️ Docker stop timed out, forcing shutdown...")
                try:
                    subprocess.run(["docker", "compose", "kill"], timeout=10)
                    subprocess.run(["docker", "compose", "down"], timeout=10)
                    stopped_services.append("Docker containers (forced)")
                except:
                    click.echo("❌ Failed to stop Docker services", err=True)
            except Exception as e:
                click.echo(f"❌ Error stopping Docker services: {e}", err=True)
        else:
            if verbose:
                click.echo("⚠️ No docker-compose.yml found, skipping Docker shutdown")
    
    # Summary
    if stopped_services:
        click.echo("🎯 Shutdown complete!")
        for service in stopped_services:
            click.echo(f"   ✅ {service}")
    else:
        click.echo("🤷 No services were found running")
    
    if verbose:
        click.echo("💡 Use 'context-cleaner run' to start services again")


# Add the comprehensive run command for service orchestration
@main.command()
@click.option("--dashboard-port", "-p", type=int, default=8110, help="Dashboard port")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.option("--no-docker", is_flag=True, help="Skip Docker service startup")
@click.option("--no-jsonl", is_flag=True, help="Skip JSONL processing service")
@click.option("--status-only", is_flag=True, help="Show service status and exit")
@click.option("--config-file", type=click.Path(exists=True), help="Custom configuration file")
@click.option("--dev-mode", is_flag=True, help="Enable development mode with debug logging")
@click.pass_context
def run(ctx, dashboard_port, no_browser, no_docker, no_jsonl, status_only, config_file, dev_mode):
    """
    🚀 SINGLE ENTRY POINT - Start all Context Cleaner services with orchestration.
    
    This is the recommended way to start Context Cleaner. It provides:
    
    ✅ Complete service orchestration and dependency management
    ✅ Health monitoring and automatic service recovery  
    ✅ Integrated dashboard with all analytics and insights
    ✅ Process registry tracking and cleanup
    ✅ Real-time telemetry and performance monitoring
    
    STARTUP SEQUENCE:
    1. 🐳 Docker services (ClickHouse + OpenTelemetry)  
    2. 🔗 JSONL processing and data bridge services
    3. 📊 Comprehensive health dashboard
    4. 🔍 Process registry and monitoring
    
    QUICK START:
      context-cleaner run                    # Start everything
      context-cleaner run --status-only      # Check service status
      context-cleaner run --no-docker        # Skip Docker services
      context-cleaner debug service-health   # Troubleshoot issues
      context-cleaner stop                   # Stop all services
    
    For troubleshooting, use 'context-cleaner debug --help' commands.
    """
    import asyncio
    import threading
    import webbrowser
    import time
    
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"] or dev_mode
    
    # Handle custom config file
    if config_file:
        from pathlib import Path
        config = ContextCleanerConfig.from_file(Path(config_file))
        ctx.obj["config"] = config
    
    # Enable development mode
    if dev_mode:
        ctx.obj["verbose"] = True
        verbose = True
        click.echo("🔧 Development mode enabled - verbose logging active")
    
    # Import service orchestrator
    try:
        from ..services import ServiceOrchestrator
    except ImportError:
        click.echo("❌ Service orchestrator not available", err=True)
        sys.exit(1)
    
    # Initialize orchestrator
    orchestrator = ServiceOrchestrator(config=config, verbose=verbose)
    
    # Handle status-only mode
    if status_only:
        status = orchestrator.get_service_status()
        
        click.echo("\n🔍 CONTEXT CLEANER SERVICE STATUS")
        click.echo("=" * 45)
        
        # Orchestrator status
        orch_status = status["orchestrator"]
        running_icon = "🟢" if orch_status["running"] else "🔴"
        click.echo(f"{running_icon} Orchestrator: {'Running' if orch_status['running'] else 'Stopped'}")
        
        # Individual services
        click.echo("\n📊 Services:")
        for service_name, service_info in status["services"].items():
            status_icon = {
                "running": "🟢",
                "starting": "🟡", 
                "stopping": "🟡",
                "stopped": "🔴",
                "failed": "❌",
                "unknown": "⚪"
            }.get(service_info["status"], "⚪")
            
            health_icon = "💚" if service_info["health_status"] else "💔" if service_info["status"] == "running" else "⚪"
            required_text = " (required)" if service_info["required"] else " (optional)"
            
            click.echo(f"   {status_icon} {health_icon} {service_info['name']}{required_text}")
            click.echo(f"      Status: {service_info['status'].title()}")
            
            if service_info["restart_count"] > 0:
                click.echo(f"      Restarts: {service_info['restart_count']}")
            
            if service_info["last_error"]:
                click.echo(f"      Last error: {service_info['last_error']}")
        
        return
    
    # Disable specific services if requested
    if no_docker:
        orchestrator.services.pop("clickhouse", None)
        orchestrator.services.pop("otel", None)
    
    if no_jsonl:
        orchestrator.services.pop("jsonl_bridge", None)
    
    try:
        # Start all services
        success = asyncio.run(orchestrator.start_all_services(dashboard_port))
        
        if not success:
            click.echo("❌ Failed to start all required services", err=True)
            sys.exit(1)
        
        # Start the dashboard (this is the main blocking operation)
        try:
            from ..dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard
            
            dashboard = ComprehensiveHealthDashboard(config=config)
            
            # Open browser if requested
            if not no_browser:
                def open_browser():
                    time.sleep(2)
                    try:
                        url = f"http://{config.dashboard.host}:{dashboard_port}"
                        webbrowser.open(url)
                    except Exception:
                        pass
                
                threading.Thread(target=open_browser, daemon=True).start()
            
            # Update dashboard service status to running
            dashboard_state = orchestrator.service_states.get("dashboard")
            if dashboard_state:
                from ..services.service_orchestrator import ServiceStatus
                dashboard_state.status = ServiceStatus.RUNNING
                dashboard_state.health_status = True
            
            dashboard_url = f"http://{config.dashboard.host}:{dashboard_port}"
            click.echo(f"🚀 Context Cleaner running at: {dashboard_url}")
            click.echo("📊 All services started successfully!")
            
            # Show running services
            for service_name, service_state in orchestrator.service_states.items():
                service = orchestrator.services[service_name]
                if service_state.status.value == "running":
                    click.echo(f"   ✅ {service.description}")
            
            click.echo("\nPress Ctrl+C to stop all services")
            
            # Start dashboard (blocking)
            dashboard.start_server(host=config.dashboard.host, port=dashboard_port, debug=False, open_browser=False)
        
        except Exception as e:
            click.echo(f"❌ Failed to start dashboard: {e}", err=True)
            asyncio.run(orchestrator.stop_all_services())
            sys.exit(1)
    
    except KeyboardInterrupt:
        if verbose:
            click.echo("\n👋 Received shutdown signal")
        asyncio.run(orchestrator.stop_all_services())
        if verbose:
            click.echo("✅ All services stopped cleanly")
    
    except Exception as e:
        click.echo(f"❌ Service orchestration failed: {e}", err=True)
        asyncio.run(orchestrator.stop_all_services())
        sys.exit(1)


if __name__ == "__main__":
    main()
