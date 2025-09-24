"""
Main CLI interface for Context Cleaner.
"""

import logging

from context_cleaner.utils.eventlet_support import ensure_eventlet_monkey_patch

ensure_eventlet_monkey_patch(patch_threads=False)
logging.getLogger(__name__).debug("Eventlet monkey patch ensured in CLI entrypoint")

import asyncio
import json
import os
import sys
import threading
import time
import webbrowser
import concurrent.futures
from typing import Any, Dict
from datetime import datetime
from pathlib import Path
from contextlib import suppress

import click

from context_cleaner.telemetry.context_rot.config import get_config, ApplicationConfig
from context_cleaner.analytics.productivity_analyzer import ProductivityAnalyzer
from context_cleaner.dashboard.web_server import ProductivityDashboard
from context_cleaner.services.service_supervisor import ServiceSupervisor, SupervisorConfig
from context_cleaner.services.service_watchdog import ServiceWatchdog
from context_cleaner.ipc.client import default_supervisor_endpoint
from context_cleaner import __version__

LOGGER = logging.getLogger(__name__)


def _run_asyncio(coro):
    """Run an async coroutine using an isolated event loop."""
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        result_holder = {}
        error_holder = {}

        def _thread_runner() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result_holder["value"] = loop.run_until_complete(coro)
            except Exception as exc:  # pragma: no cover - defensive
                error_holder["error"] = exc
            finally:
                with suppress(Exception):
                    loop.run_until_complete(loop.shutdown_asyncgens())
                asyncio.set_event_loop(None)
                loop.close()

        thread = threading.Thread(target=_thread_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder.get("value")

    if hasattr(asyncio, "Runner"):
        with asyncio.Runner() as runner:  # type: ignore[attr-defined]
            return runner.run(coro)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        with suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        asyncio.set_event_loop(None)
        loop.close()


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
        ctx.obj["config"] = ApplicationConfig.from_file(Path(config))
    else:
        ctx.obj["config"] = ApplicationConfig.from_env()

    # Override data directory if provided
    if data_dir:
        ctx.obj["config"].data_directory = str(Path(data_dir).absolute())

    ctx.obj["verbose"] = verbose

    if verbose:
        click.echo(f"📂 Data directory: {ctx.obj['config'].data_directory}")
        click.echo(f"🔧 Dashboard port: {ctx.obj['config'].dashboard.port}")


# REMOVED: Conflicting start command - use 'run' command instead
# The simple 'start' command has been removed to avoid confusion with the comprehensive 'run' command
# which provides full orchestration, process management, and monitoring.


# REMOVED: Conflicting dashboard command - use 'run' command instead
# The standalone 'dashboard' command has been removed to avoid confusion with the comprehensive 'run' command
# which provides full orchestration, process management, and the dashboard through ServiceOrchestrator.
# Use 'context-cleaner run' for complete service orchestration including dashboard functionality.


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
        results = _run_asyncio(_run_productivity_analysis(config, days))

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
            from context_cleaner.optimization.personalized_strategies import StrategyType

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
        from context_cleaner.tracking.session_tracker import SessionTracker

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
        from context_cleaner.tracking.session_tracker import SessionTracker

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
        from context_cleaner.tracking.session_tracker import SessionTracker

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
        from context_cleaner.tracking.session_tracker import SessionTracker

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
        from context_cleaner.monitoring.real_time_monitor import RealTimeMonitor
        from context_cleaner.monitoring.session_observer import SessionObserver

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
        _run_asyncio(monitor.start_monitoring())

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
        _run_asyncio(run_monitoring())

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
        from context_cleaner.monitoring.real_time_monitor import RealTimeMonitor

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
        from context_cleaner.monitoring.real_time_monitor import RealTimeMonitor

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
        _run_asyncio(run_live_dashboard())

    except Exception as e:
        click.echo(f"❌ Live dashboard error: {e}", err=True)
        sys.exit(1)


async def _run_productivity_analysis(config: ApplicationConfig, days: int) -> dict:
    """Run productivity analysis for specified number of days."""
    from datetime import datetime, timedelta
    from pathlib import Path

    # Use enhanced cache discovery system
    from context_cleaner.analysis.discovery import CacheDiscoveryService
    from context_cleaner.analytics.effectiveness_tracker import EffectivenessTracker

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


def _export_all_data(config: ApplicationConfig) -> dict:
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


@main.command("update-data")
@click.option("--dashboard-port", "-p", type=int, default=8110, help="Dashboard port to check")
@click.option("--host", default="localhost", help="Dashboard host")
@click.option("--check-only", is_flag=True, help="Only diagnose issues, don't apply fixes")
@click.option("--clear-cache", is_flag=True, help="Clear widget cache to force fresh data")
@click.option("--output", type=click.Path(), help="Save detailed results to JSON file")
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def update_data(ctx, dashboard_port, host, check_only, clear_cache, output, format):
    """Diagnose and fix widget data staleness issues.

    This command analyzes why dashboard widgets might be showing zeros or stale data
    and provides clear guidance on how to resolve the issues. It detects common
    problems like running with --no-docker flags that disable real telemetry data.

    Examples:
        context-cleaner update-data                    # Diagnose and fix issues
        context-cleaner update-data --check-only       # Only diagnose, don't fix
        context-cleaner update-data --clear-cache      # Force cache refresh
        context-cleaner update-data --output report.json  # Save detailed report
    """
    import requests
    import time
    from datetime import datetime

    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    base_url = f"http://{host}:{dashboard_port}"

    if verbose:
        click.echo(f"🔍 Analyzing widget data staleness at {base_url}")

    # Results dictionary for detailed reporting
    results = {
        "timestamp": datetime.now().isoformat(),
        "dashboard_url": base_url,
        "diagnosis": {},
        "fixes_applied": [],
        "recommendations": []
    }

    def output_result(message, level="info"):
        """Output message based on format"""
        if format == "json":
            return  # Store in results, output at end

        if level == "error":
            click.echo(click.style(message, fg="red"), err=True)
        elif level == "warning":
            click.echo(click.style(message, fg="yellow"))
        elif level == "success":
            click.echo(click.style(message, fg="green"))
        else:
            click.echo(message)

    # Step 1: Check dashboard connectivity
    output_result("📡 Step 1: Testing dashboard connectivity...")

    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        response.raise_for_status()

        health_data = response.json()
        results["diagnosis"]["connectivity"] = {"success": True, "status": health_data.get("status", "unknown")}
        output_result("✅ Dashboard is accessible", "success")

    except Exception as e:
        results["diagnosis"]["connectivity"] = {"success": False, "error": str(e)}
        output_result(f"❌ Dashboard not accessible: {e}", "error")
        output_result("\n💡 SOLUTION: Start Context Cleaner dashboard:", "warning")
        output_result("   context-cleaner run --dashboard-port 8110")

        if format == "json":
            click.echo(json.dumps(results, indent=2))
        elif output:
            with open(output, 'w') as f:
                json.dump(results, f, indent=2)
            output_result(f"💾 Results saved to {output}")

        sys.exit(1)

    # Step 2: Check telemetry availability
    output_result("\n🔧 Step 2: Checking telemetry system...")

    try:
        response = requests.get(f"{base_url}/api/telemetry/data-freshness", timeout=10)

        if response.status_code == 404:
            results["diagnosis"]["telemetry"] = {"available": False, "reason": "telemetry_disabled"}
            output_result("❌ Telemetry system unavailable", "error")
            output_result("   Reason: telemetry_disabled", "warning")
            output_result("\n💡 ROOT CAUSE IDENTIFIED: Context Cleaner running with --no-docker flag", "warning")
            output_result("\n🚀 SOLUTION:")
            output_result("   1. Stop current Context Cleaner: context-cleaner stop")
            output_result("   2. Start with full services: context-cleaner run")
            output_result("   3. This will enable ClickHouse database for real telemetry data")

            results["recommendations"].append("restart_with_full_services")

            if format == "json":
                click.echo(json.dumps(results, indent=2))
            elif output:
                with open(output, 'w') as f:
                    json.dump(results, f, indent=2)
                output_result(f"💾 Results saved to {output}")

            sys.exit(1)

        response.raise_for_status()
        telemetry_data = response.json()

        results["diagnosis"]["telemetry"] = {
            "available": True,
            "service_availability": telemetry_data.get("service_availability", {}),
            "cache_status": telemetry_data.get("cache_status", {}),
            "fallback_widgets": len(telemetry_data.get("fallback_detection", {}))
        }

        output_result("✅ Telemetry system is available", "success")

    except Exception as e:
        results["diagnosis"]["telemetry"] = {"available": False, "error": str(e)}
        output_result(f"❌ Telemetry check failed: {e}", "error")
        results["recommendations"].append("check_service_logs")

    # Step 3: Test individual widgets
    output_result("\n📊 Step 3: Testing individual widgets...")

    widgets = ["error-monitor", "cost-tracker", "timeout-risk", "tool-optimizer", "model-efficiency", "context-rot-meter"]
    widget_results = {}
    problem_widgets = []

    for widget in widgets:
        if verbose:
            output_result(f"   Testing {widget}...")

        try:
            response = requests.get(f"{base_url}/api/telemetry-widget/{widget}", timeout=10)

            if response.status_code == 200:
                data = response.json()
                widget_data = data.get("data", {})

                # Check for fallback indicators
                is_fallback = widget_data.get("fallback_mode", False) or "Demo" in data.get("title", "")

                # Check for zero values
                zero_fields = [key for key, value in widget_data.items()
                             if isinstance(value, (int, float)) and value == 0]

                widget_results[widget] = {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "title": data.get("title", ""),
                    "is_fallback": is_fallback,
                    "zero_fields": zero_fields,
                    "alerts": data.get("alerts", [])
                }

                if not widget_results[widget]["success"] or is_fallback or zero_fields:
                    problem_widgets.append(widget)

            else:
                widget_results[widget] = {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                problem_widgets.append(widget)

        except Exception as e:
            widget_results[widget] = {
                "success": False,
                "error": str(e)
            }
            problem_widgets.append(widget)

    results["diagnosis"]["widgets"] = widget_results

    if problem_widgets:
        output_result(f"⚠️  Found {len(problem_widgets)} widgets with issues:", "warning")
        for widget in problem_widgets:
            widget_data = widget_results[widget]
            if not widget_data.get("success"):
                output_result(f"   ❌ {widget}: Error - {widget_data.get('error', 'unknown')}", "error")
            elif widget_data.get("is_fallback"):
                output_result(f"   🔄 {widget}: Fallback mode", "warning")
            elif widget_data.get("zero_fields"):
                output_result(f"   🚫 {widget}: Zero values in {widget_data['zero_fields']}", "warning")
    else:
        output_result("✅ All widgets working correctly", "success")

    # Step 4: Apply fixes if requested
    fixes_applied = []

    if not check_only and (clear_cache or problem_widgets):
        output_result("\n🔧 Step 4: Applying fixes...")

        if clear_cache or problem_widgets:
            try:
                output_result("   🔄 Clearing widget cache...")
                response = requests.post(f"{base_url}/api/telemetry/clear-cache", timeout=10)

                if response.status_code == 200:
                    fixes_applied.append("cache_cleared")
                    output_result("   ✅ Widget cache cleared successfully", "success")

                    # Wait and re-test one widget
                    time.sleep(2)
                    test_response = requests.get(f"{base_url}/api/telemetry-widget/error-monitor", timeout=10)
                    if test_response.status_code == 200:
                        fixes_applied.append("widget_retested")
                        output_result("   ✅ Widget data refreshed after cache clear", "success")
                else:
                    output_result(f"   ❌ Cache clear failed: HTTP {response.status_code}", "error")

            except Exception as e:
                output_result(f"   ❌ Cache clear error: {e}", "error")

    results["fixes_applied"] = fixes_applied

    # Generate recommendations
    recommendations = []

    if not results["diagnosis"]["telemetry"].get("available"):
        if results["diagnosis"]["telemetry"].get("reason") == "telemetry_disabled":
            recommendations.append("CRITICAL: Restart Context Cleaner without --no-docker flag to enable real data")
        else:
            recommendations.append("Check ClickHouse container status and telemetry service logs")

    if problem_widgets:
        recommendations.append(f"Investigate {len(problem_widgets)} problematic widgets")
        recommendations.append("Monitor service logs during widget data generation")

    if results["diagnosis"]["telemetry"].get("cache_status", {}).get("cached_widgets", 0) > 5:
        recommendations.append("High cache usage detected - consider clearing cache periodically")

    service_availability = results["diagnosis"]["telemetry"].get("service_availability", {})
    unavailable_services = [name for name, available in service_availability.items() if not available]
    if unavailable_services:
        recommendations.append(f"Unavailable services detected: {', '.join(unavailable_services)}")

    results["recommendations"] = recommendations

    # Output final results
    if recommendations:
        output_result("\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            level = "error" if "CRITICAL" in rec else "warning"
            output_result(f"   {i}. {rec}", level)
    else:
        output_result("\n✅ No issues detected", "success")

    # Output in requested format
    if format == "json":
        click.echo(json.dumps(results, indent=2))
    elif output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        output_result(f"\n💾 Results saved to {output}")

    # Exit with appropriate code
    critical_issues = any("CRITICAL" in rec for rec in recommendations)
    sys.exit(1 if critical_issues else 0)


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


# Add the enhanced stop command for comprehensive service shutdown
@main.command()
@click.option("--force", is_flag=True, help="Force stop all services without confirmation")
@click.option("--docker-only", is_flag=True, help="Stop only Docker services")
@click.option("--processes-only", is_flag=True, help="Stop only background processes")
@click.option("--no-discovery", is_flag=True, help="Skip process discovery, use basic method")
@click.option("--show-discovery", is_flag=True, help="Show discovered processes before shutdown")
@click.option("--registry-cleanup", is_flag=True, help="Also clean up process registry entries")
@click.option("--use-script", is_flag=True, help="Use stop-context-cleaner.sh script for comprehensive cleanup")
@click.option(
    "--service",
    "services",
    multiple=True,
    help="Target specific services by name; repeat option to select multiple",
)
@click.option(
    "--no-dependents",
    is_flag=True,
    help="Do not automatically stop dependent services when targeting specific services",
)
@click.pass_context
def stop(ctx, force, docker_only, processes_only, no_discovery, show_discovery, registry_cleanup, use_script, services, no_dependents):
    """
    🛑 ENHANCED STOP - Comprehensive service shutdown with process discovery.
    
    This command provides intelligent shutdown of all Context Cleaner services:
    
    ✅ ORCHESTRATED SHUTDOWN:
    • Uses service orchestrator for dependency-aware cleanup
    • Graceful termination with proper signal handling
    • Registry-aware process management

    ✅ LIVE SUPERVISOR STREAMING:
    • Streams shutdown progress directly from the supervisor when available
    • Displays remaining services and transition progress in real time
    • Automatically falls back to legacy orchestrator shutdown if supervisor unreachable
    
    ✅ PROCESS DISCOVERY:
    • Automatically discovers all Context Cleaner processes
    • Handles processes started through different pathways
    • Cleans up orphaned processes bypassing orchestration
    
    ✅ COMPREHENSIVE CLEANUP:
    • Docker services (ClickHouse + OpenTelemetry)
    • JSONL processing and bridge services  
    • Dashboard web servers on all ports
    • Background monitoring processes
    • Process registry entries (optional)
    
    MODES:
      context-cleaner stop                 # Full orchestrated shutdown
      context-cleaner stop --show-discovery # Preview discovered processes
      context-cleaner stop --docker-only    # Only Docker containers
      context-cleaner stop --processes-only # Only background processes
      context-cleaner stop --force          # Skip confirmations
      context-cleaner stop --registry-cleanup # Also clean registry
      context-cleaner stop --use-script     # Use stop-context-cleaner.sh script
    
    This solves the orphaned process problem by discovering and stopping
    ALL Context Cleaner processes regardless of how they were started.
    """
    import subprocess
    import signal
    import os
    import sys
    import asyncio
    import psutil
    from pathlib import Path
    
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    if docker_only and processes_only:
        raise click.UsageError("Use either --docker-only or --processes-only, not both")

    target_services = [svc.strip() for svc in services if svc and svc.strip()]
    include_dependents = not no_dependents

    if target_services and (docker_only or processes_only):
        raise click.UsageError("--service cannot be combined with --docker-only/--processes-only filters")

    # Use shell script if requested
    if use_script:
        if verbose:
            click.echo("🛑 Using stop-context-cleaner.sh for comprehensive cleanup...")

        script_path = Path.cwd() / "stop-context-cleaner.sh"
        if not script_path.exists():
            click.echo(f"❌ Script not found: {script_path}", err=True)
            click.echo("💡 Make sure stop-context-cleaner.sh is in the current directory", err=True)
            sys.exit(1)

        if not force:
            click.echo("🛑 This will run stop-context-cleaner.sh to kill all context-cleaner processes")
            if not click.confirm("Continue with shell script cleanup?"):
                click.echo("❌ Shutdown cancelled")
                return

        try:
            result = subprocess.run([str(script_path)], capture_output=True, text=True)
            if verbose:
                if result.stdout:
                    click.echo(result.stdout)
                if result.stderr:
                    click.echo(result.stderr, err=True)

            if result.returncode == 0:
                click.echo("✅ Shell script cleanup completed successfully")
            else:
                click.echo(f"⚠️  Shell script completed with exit code {result.returncode}")
        except Exception as e:
            click.echo(f"❌ Failed to run shell script: {e}", err=True)
            sys.exit(1)

        return

    if target_services and show_discovery:
        click.echo("⚠️  --show-discovery is ignored when targeting specific services", err=True)

    perform_discovery = not no_discovery and not target_services
    discovered_processes = []

    if verbose:
        click.echo("🛑 Starting enhanced Context Cleaner shutdown...")
        click.echo("🔍 Using process discovery and orchestration integration")
        if target_services:
            click.echo(f"🎯 Targeted services: {', '.join(target_services)}")
            if include_dependents:
                click.echo("   Dependent services will also be stopped")
            else:
                click.echo("   Dependent services will NOT be stopped automatically")
            if perform_discovery is False and not no_discovery:
                click.echo("   Skipping process discovery for targeted shutdown")
    
    # Initialize orchestrator and discovery systems
    try:
        from context_cleaner.services import ServiceOrchestrator
        orchestrator = ServiceOrchestrator(config=config, verbose=verbose)
        discovery_engine = orchestrator.discovery_engine
        process_registry = orchestrator.process_registry
        
        if verbose:
            click.echo("✅ Service orchestrator and discovery engine initialized")
    
    except ImportError as e:
        if verbose:
            click.echo(f"⚠️  Service orchestrator not available: {e}")
            click.echo("🔄 Falling back to basic process cleanup")
        
        # Fallback to basic cleanup if orchestrator unavailable
        _run_asyncio(_basic_stop_fallback(ctx, force, docker_only, processes_only, verbose))
        return
    
    except Exception as e:
        click.echo(f"❌ Failed to initialize orchestrator: {e}", err=True)
        if not force:
            sys.exit(1)
        # Continue with basic cleanup
        _run_asyncio(_basic_stop_fallback(ctx, force, docker_only, processes_only, verbose))
        return
    
    # 1. ENHANCED PROCESS DISCOVERY PHASE
    if perform_discovery:
        try:
            if verbose:
                click.echo("\n🔍 PHASE 1: Enhanced Process Discovery")
            
            # Use both the orchestrator discovery engine AND manual discovery
            discovered_processes = discovery_engine.discover_all_processes()
            registered_processes = process_registry.get_all_processes()
            
            # Add comprehensive manual discovery for processes the orchestrator misses
            manual_processes = _discover_all_context_cleaner_processes(verbose)
            
            # Combine and deduplicate processes
            all_pids = set()
            combined_processes = []
            
            # Add orchestrator-discovered processes
            for proc in discovered_processes:
                if proc.pid not in all_pids:
                    combined_processes.append(proc)
                    all_pids.add(proc.pid)
            
            # Add manually discovered processes
            for proc in manual_processes:
                if proc.pid not in all_pids:
                    combined_processes.append(proc)
                    all_pids.add(proc.pid)
            
            discovered_processes = combined_processes
            
            discovery_summary = {
                "discovered_count": len(discovered_processes),
                "registered_count": len(registered_processes),
                "by_service_type": {}
            }
            
            # Group discovered processes by service type
            for process in discovered_processes:
                service_type = getattr(process, 'service_type', 'unknown')
                if service_type not in discovery_summary["by_service_type"]:
                    discovery_summary["by_service_type"][service_type] = []
                discovery_summary["by_service_type"][service_type].append({
                    "pid": process.pid,
                    "name": getattr(process, 'name', 'unknown'),
                    "path": getattr(process, 'path', 'N/A'),
                    "command_line": process.command_line[:60] + "..." if len(process.command_line) > 60 else process.command_line
                })
            
            if verbose:
                click.echo(f"   📊 Found {discovery_summary['discovered_count']} running processes")
                click.echo(f"   📝 Found {discovery_summary['registered_count']} registered processes")
                
                if discovery_summary["by_service_type"]:
                    click.echo("   📋 Discovered processes by type:")
                    for service_type, processes in discovery_summary["by_service_type"].items():
                        click.echo(f"      • {service_type}: {len(processes)} processes")
                        if verbose and show_discovery:
                            for proc in processes[:3]:  # Show first 3
                                click.echo(f"        - PID {proc['pid']} ({proc['name']}) [{proc['path']}]: {proc['command_line']}")
                            if len(processes) > 3:
                                click.echo(f"        - ... and {len(processes) - 3} more")
            
            # Show discovery results if requested
            if show_discovery:
                click.echo("\n📋 DISCOVERED PROCESSES PREVIEW:")
                click.echo("=" * 50)
                
                if discovery_summary["discovered_count"] == 0:
                    click.echo("No Context Cleaner processes found running")
                else:
                    for service_type, processes in discovery_summary["by_service_type"].items():
                        click.echo(f"\n🔧 {service_type.upper()} ({len(processes)} processes):")
                        for proc in processes:
                            click.echo(f"   PID {proc['pid']} ({proc['name']}) [{proc['path']}]: {proc['command_line']}")
                
                click.echo("\n" + "=" * 50)
                if not force and not click.confirm("Proceed with shutdown of these processes?"):
                    click.echo("❌ Shutdown cancelled")
                    return
        
        except Exception as e:
            if verbose:
                click.echo(f"⚠️  Process discovery failed: {e}")
            if not force:
                click.echo("💡 Use --no-discovery to skip discovery and use basic cleanup")
                sys.exit(1)
            # Continue without discovery
            discovered_processes = []
    
    else:
        if verbose:
            if no_discovery:
                click.echo("⚠️  Process discovery skipped (--no-discovery)")
            elif target_services:
                click.echo("⚠️  Process discovery skipped for targeted shutdown")
        discovered_processes = []
    
    # 2. CONFIRMATION PHASE
    if not force and not show_discovery:
        click.echo("\n🛑 This will stop all Context Cleaner services:")
        if not docker_only:
            click.echo("   • All discovered Context Cleaner processes")
            click.echo("   • Background JSONL processing and bridge services")
            click.echo("   • Dashboard web servers on all ports")
        if not processes_only:
            click.echo("   • Docker containers (ClickHouse + OpenTelemetry)")
        if registry_cleanup:
            click.echo("   • Process registry entries cleanup")
        
        if perform_discovery and discovered_processes:
            click.echo(f"\n📊 Processes to stop: {len(discovered_processes)} Context Cleaner processes")
            # Show summary of what will be stopped
            process_summary = {}
            for proc in discovered_processes:
                service_type = getattr(proc, 'service_type', 'unknown')
                if service_type not in process_summary:
                    process_summary[service_type] = []
                process_summary[service_type].append(proc)

            for service_type, processes in process_summary.items():
                click.echo(f"   • {service_type}: {len(processes)} process(es)")
                for proc in processes[:2]:  # Show first 2 per type
                    proc_name = getattr(proc, 'name', 'unknown')
                    proc_path = getattr(proc, 'path', 'N/A')
                    click.echo(f"     - PID {proc.pid} ({proc_name}) [{proc_path}]")
                if len(processes) > 2:
                    click.echo(f"     - ... and {len(processes) - 2} more")
        else:
            if target_services:
                click.echo(f"\n📊 Targeted services for shutdown: {', '.join(target_services)}")
            else:
                processes_count = "unknown number of"
                click.echo(f"\n📊 Processes to stop: {processes_count} Context Cleaner processes")
        click.echo()
        
        if not click.confirm("Continue with comprehensive shutdown?"):
            click.echo("❌ Shutdown cancelled")
            return
    
    # 3. ORCHESTRATED SHUTDOWN PHASE
    shutdown_summary: Dict[str, Any] | None = None

    if not processes_only:
        try:
            if verbose:
                click.echo("\n🔧 PHASE 2: Orchestrated Service Shutdown")

            supervisor_used, supervisor_success = _supervisor_stream_shutdown(
                verbose=verbose,
                docker_only=docker_only,
                processes_only=processes_only,
                services=target_services,
                include_dependents=include_dependents,
            )

            if supervisor_used and not supervisor_success:
                if verbose:
                    click.echo("   ⚠️  Supervisor reported shutdown issues, falling back to local orchestrator")

            if supervisor_used and supervisor_success:
                orchestrated_success = True
            else:
                shutdown_summary = _run_asyncio(
                    orchestrator.shutdown_all(
                        docker_only=docker_only,
                        processes_only=processes_only,
                        services=target_services if target_services else None,
                        include_dependents=include_dependents,
                    )
                )
                orchestrated_success = shutdown_summary.get("success", False)
                if shutdown_summary.get("invalid"):
                    click.echo(
                        "   ⚠️  Unknown services requested: "
                        + ", ".join(shutdown_summary["invalid"]),
                        err=True,
                    )

            if orchestrated_success:
                if verbose:
                    click.echo("   ✅ Orchestrated services stopped successfully")
            else:
                if verbose:
                    click.echo("   ⚠️  Some orchestrated services had issues during shutdown")
                if shutdown_summary and shutdown_summary.get("errors") and verbose:
                    for name, error_msg in shutdown_summary["errors"].items():
                        click.echo(f"      - {name}: {error_msg}", err=True)
        except Exception as e:
            if verbose:
                click.echo(f"   ❌ Orchestrated shutdown failed: {e}")
            if not force:
                click.echo("💡 Use --force to continue with manual cleanup")
                sys.exit(1)
    
    # 4. DISCOVERED PROCESS CLEANUP PHASE  
    if perform_discovery and discovered_processes:
        if verbose:
            click.echo("\n🧹 PHASE 3: Discovered Process Cleanup")
        
        cleaned_processes = 0
        failed_cleanups = 0
        
        for process in discovered_processes:
            if process.pid == os.getpid():
                continue  # Don't kill ourselves
            
            try:
                # Check if process is still running
                try:
                    proc = psutil.Process(process.pid)
                    if not proc.is_running():
                        continue  # Already stopped
                except psutil.NoSuchProcess:
                    continue  # Already gone
                
                # Enhanced termination with signal escalation
                success = _terminate_process_with_escalation(proc, verbose)
                
                if success:
                    cleaned_processes += 1
                    service_type = getattr(process, 'service_type', 'unknown')
                    if verbose:
                        click.echo(f"   ✅ Stopped PID {process.pid} ({service_type})")
                else:
                    failed_cleanups += 1
                    if verbose:
                        click.echo(f"   ❌ Failed to stop PID {process.pid} after escalation")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone or can't access it
                continue
            except Exception as e:
                failed_cleanups += 1
                if verbose:
                    click.echo(f"   ❌ Failed to stop PID {process.pid}: {e}")
        
        if verbose:
            click.echo(f"   📊 Process cleanup: {cleaned_processes} stopped, {failed_cleanups} failed")
    
    # 5. DOCKER CLEANUP PHASE - Enhanced with robust ClickHouse shutdown
    if not processes_only:
        if verbose:
            click.echo("\n🐳 PHASE 4: Enhanced Docker Services Cleanup")

        # First, use our robust ClickHouse shutdown function
        clickhouse_results = _shutdown_clickhouse_containers_robust(verbose)

        # Report ClickHouse shutdown results
        if verbose:
            if clickhouse_results["containers_stopped"]:
                click.echo(f"   📊 ClickHouse containers stopped: {', '.join(clickhouse_results['containers_stopped'])}")
            if clickhouse_results["processes_terminated"]:
                click.echo(f"   📊 ClickHouse processes terminated: {len(clickhouse_results['processes_terminated'])} PIDs")
            if clickhouse_results["remaining_issues"]:
                click.echo(f"   ⚠️  ClickHouse shutdown issues: {len(clickhouse_results['remaining_issues'])}")
                for issue in clickhouse_results["remaining_issues"]:
                    click.echo(f"      - {issue}")

        # Traditional compose cleanup as fallback/supplement
        compose_file = Path("docker-compose.yml")
        if compose_file.exists():
            try:
                if verbose:
                    click.echo("   🔄 Running traditional docker-compose down for cleanup...")

                result = subprocess.run(
                    ["docker", "compose", "down"],
                    capture_output=True, text=True, timeout=30
                )

                if result.returncode == 0:
                    if verbose:
                        click.echo("   ✅ Docker compose down completed")
                else:
                    if verbose:
                        click.echo(f"   ⚠️  Docker compose down had issues: {result.stderr}")

            except subprocess.TimeoutExpired:
                if verbose:
                    click.echo("   ⚠️  Docker compose down timed out, trying force methods...")
                try:
                    subprocess.run(["docker", "compose", "kill"], timeout=10)
                    subprocess.run(["docker", "compose", "down"], timeout=10)
                    if verbose:
                        click.echo("   ✅ Docker services force-stopped with compose")
                except Exception as e:
                    if verbose:
                        click.echo(f"   ❌ Failed to force-stop Docker services: {e}")
            except Exception as e:
                if verbose:
                    click.echo(f"   ❌ Error with docker compose: {e}")
        else:
            if verbose:
                click.echo("   ⚠️  No docker-compose.yml found, relying on direct container shutdown")
    
    # 6. REGISTRY CLEANUP PHASE
    if registry_cleanup:
        if verbose:
            click.echo("\n🗂️  PHASE 5: Process Registry Cleanup")
        
        try:
            # Clean up stale registry entries
            all_registered = process_registry.get_all_processes()
            cleaned_entries = 0
            
            for registered_process in all_registered:
                try:
                    # Check if process is still running
                    proc = psutil.Process(registered_process.pid)
                    if not proc.is_running():
                        process_registry.unregister_process(registered_process.pid)
                        cleaned_entries += 1
                except psutil.NoSuchProcess:
                    # Process is definitely gone, remove from registry
                    process_registry.unregister_process(registered_process.pid)
                    cleaned_entries += 1
            
            if verbose:
                click.echo(f"   📊 Registry cleanup: {cleaned_entries} stale entries removed")
        
        except Exception as e:
            if verbose:
                click.echo(f"   ❌ Registry cleanup failed: {e}")
    
    # 7. POST-SHUTDOWN VERIFICATION
    if verbose:
        click.echo("\n🔍 Verifying shutdown completeness...")
    
    # Enhanced verification with retry mechanism
    verification_attempts = 3
    verification_processes = []
    
    for attempt in range(verification_attempts):
        try:
            # Use both discovery methods for verification
            orchestrator_processes = discovery_engine.discover_all_processes()
            manual_processes = _discover_all_context_cleaner_processes(verbose=False)
            
            # Combine processes for verification
            all_verification_pids = set()
            verification_processes = []
            
            for proc in orchestrator_processes + manual_processes:
                if proc.pid not in all_verification_pids:
                    verification_processes.append(proc)
                    all_verification_pids.add(proc.pid)
            
            if len(verification_processes) == 0:
                break  # All processes stopped
            
            if attempt < verification_attempts - 1:
                if verbose:
                    click.echo(f"   🔄 Verification attempt {attempt + 1}: {len(verification_processes)} processes still running, retrying...")
                import time
                time.sleep(2)  # Wait before retry
            else:
                if verbose:
                    click.echo(f"   Found {len(verification_processes)} remaining processes after {verification_attempts} attempts")
                    
        except Exception as e:
            if verbose:
                click.echo(f"   ⚠️  Verification discovery failed (attempt {attempt + 1}): {e}")
    
    # Check if common ports are still bound (expanded range)
    remaining_ports = []
    common_ports = list(range(8050, 8110)) + list(range(8200, 8210)) + list(range(8300, 8310)) + \
                   list(range(8400, 8410)) + list(range(8500, 8510)) + list(range(8600, 8610)) + \
                   list(range(8700, 8710)) + list(range(8800, 8810)) + list(range(8900, 8910)) + \
                   list(range(9000, 9010)) + list(range(9100, 9110)) + list(range(9200, 9210)) + \
                   list(range(9900, 10000))
    
    for port in common_ports:
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                result = sock.connect_ex(('127.0.0.1', port))
                if result == 0:
                    remaining_ports.append(port)
        except:
            pass
    
    # Report verification results
    shutdown_complete = len(verification_processes) == 0 and len(remaining_ports) == 0
    
    if shutdown_complete:
        # 8. FINAL SUCCESS REPORT
        click.echo("\n🎯 COMPREHENSIVE SHUTDOWN COMPLETE!")
        click.echo("✅ All Context Cleaner services have been stopped")
        click.echo("✅ Shutdown verification passed")
    else:
        # 8. FINAL WARNING REPORT
        click.echo("\n⚠️  SHUTDOWN INCOMPLETE!")
        if verification_processes:
            click.echo(f"❌ {len(verification_processes)} processes still running")
            click.echo(f"\n📋 Remaining processes:")
            for proc in verification_processes[:10]:  # Show up to 10
                proc_name = getattr(proc, 'name', 'unknown')
                proc_path = getattr(proc, 'path', 'N/A')
                command_preview = proc.command_line[:60] + "..." if len(proc.command_line) > 60 else proc.command_line
                click.echo(f"   • PID {proc.pid} ({proc_name}) [{proc_path}]: {command_preview}")
            if len(verification_processes) > 10:
                click.echo(f"   • ... and {len(verification_processes) - 10} more processes")
            if verbose:
                for i, proc in enumerate(verification_processes[:5]):  # Show first 5 in verbose
                    proc_name = getattr(proc, 'name', 'unknown')
                    proc_path = getattr(proc, 'path', 'N/A')
                    click.echo(f"   [{i+1}] PID {proc.pid} ({proc_name}) [{proc_path}]: {proc.command_line}")
        if remaining_ports:
            click.echo(f"❌ {len(remaining_ports)} ports still bound: {remaining_ports}")
        
        click.echo("\n💡 To force cleanup remaining processes:")
        if verification_processes:
            # Show specific pkill commands for the remaining processes
            unique_names = set(getattr(proc, 'name', 'unknown') for proc in verification_processes[:5])
            for name in unique_names:
                click.echo(f"   sudo pkill -f '{name}'")
            if len(verification_processes) > 5:
                click.echo("   sudo pkill -f 'start_context_cleaner'  # Catch-all for remaining")
        else:
            click.echo("   sudo pkill -f 'start_context_cleaner'")
        click.echo("   context-cleaner debug processes  # Check what's still running (enhanced details above)")
    
    if verbose:
        click.echo("\n📋 Summary:")
        if not no_discovery:
            click.echo(f"   • Process discovery: {len(discovered_processes)} processes found")
        click.echo("   • Orchestrated services: Stopped")
        if not processes_only:
            click.echo("   • Docker services: Stopped")
        if registry_cleanup:
            click.echo("   • Process registry: Cleaned")
        
        click.echo("\n💡 To start services again:")
        click.echo("   context-cleaner run              # Full orchestrated startup")
        click.echo("   context-cleaner debug processes  # Check for remaining processes")


def _discover_all_context_cleaner_processes(verbose: bool = False):
    """Comprehensive manual process discovery for all Context Cleaner processes.
    
    This function uses multiple discovery methods to find all Context Cleaner processes,
    including those started by different methods that the orchestrator might miss.
    """
    import psutil
    from collections import namedtuple
    
    ProcessInfo = namedtuple('ProcessInfo', ['pid', 'name', 'path', 'command_line', 'service_type'])
    found_processes = []
    
    # Comprehensive patterns based on all Context Cleaner startup methods
    search_patterns = [
        # Direct script invocations
        "python start_context_cleaner.py",
        "python start_context_cleaner_production.py",
        "start_context_cleaner.py",
        "start_context_cleaner_production.py",

        # CLI module invocations
        "python -m context_cleaner.cli.main run",
        "context_cleaner run",
        "context_cleaner.cli.main run",

        # WSGI/production deployments
        "context_cleaner_wsgi",
        "gunicorn.*context_cleaner",

        # Dashboard services
        "ComprehensiveHealthDashboard",
        "context_cleaner.*dashboard",

        # Background services
        "context_cleaner.*jsonl",
        "jsonl_background_service",
        "context_cleaner.*bridge",
        "context_cleaner.*monitor",

        # Python path variations
        "PYTHONPATH.*context-cleaner",
        "PYTHONPATH.*context_cleaner",

        # Docker container processes - ClickHouse and OpenTelemetry
        "clickhouse-server",
        "/usr/bin/clickhouse-server",
        "clickhouse-otel",
        "otel-collector",
        "otel/opentelemetry-collector",
        "docker.*clickhouse",
        "containerd-shim.*clickhouse",

        # Docker compose processes
        "docker-compose.*clickhouse",
        "docker compose.*clickhouse",
    ]
    
    try:
        # Iterate through all running processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                if not proc.info['cmdline']:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'])
                
                # Check against all search patterns
                for pattern in search_patterns:
                    if pattern.lower() in cmdline.lower():
                        # EXCLUDE management commands that shouldn't be killed
                        # These are CLI commands that manage the system, not runtime services

                        # Check for management subcommands (stop, debug, status, help)
                        management_subcommands = ["stop", "debug", "status", "--help", "help"]
                        is_management_command = False

                        # Look for context-cleaner or context_cleaner followed by management commands
                        cmdline_lower = cmdline.lower()
                        if any(f"context-cleaner {cmd}" in cmdline_lower or
                               f"context_cleaner {cmd}" in cmdline_lower or
                               f"context_cleaner.cli.main {cmd}" in cmdline_lower
                               for cmd in management_subcommands):
                            is_management_command = True

                        # Also exclude the current process (self-exclusion)
                        current_pid = os.getpid()
                        if proc.info['pid'] == current_pid:
                            is_management_command = True

                        if is_management_command:
                            if verbose:
                                print(f"   🚫 Excluding management command: PID {proc.info['pid']}")
                            continue

                        # Determine service type from command line
                        service_type = "dashboard"
                        if "clickhouse" in cmdline.lower():
                            service_type = "clickhouse_database"
                        elif "otel" in cmdline.lower() or "opentelemetry" in cmdline.lower():
                            service_type = "otel_collector"
                        elif "containerd-shim" in cmdline.lower():
                            service_type = "docker_container_process"
                        elif "jsonl" in cmdline.lower():
                            service_type = "jsonl_processing"
                        elif "bridge" in cmdline.lower():
                            service_type = "bridge_service"
                        elif "monitor" in cmdline.lower():
                            service_type = "monitoring"
                        elif "production" in cmdline.lower():
                            service_type = "production_dashboard"
                        elif "gunicorn" in cmdline.lower() or "wsgi" in cmdline.lower():
                            service_type = "wsgi_server"
                        
                        # Get process path safely
                        try:
                            process_path = proc.info.get('exe', 'N/A')
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            process_path = 'N/A'

                        process_info = ProcessInfo(
                            pid=proc.info['pid'],
                            name=proc.info.get('name', 'unknown'),
                            path=process_path,
                            command_line=cmdline,
                            service_type=service_type
                        )
                        found_processes.append(process_info)
                        
                        if verbose:
                            proc_name = proc.info.get('name', 'unknown')
                            print(f"   🔍 Found PID {proc.info['pid']} ({proc_name}): {service_type} - {cmdline[:60]}...")
                        break  # Found match, move to next process
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process disappeared or we can't access it
                continue
                
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Process discovery error: {e}")
    
    if verbose:
        print(f"   📊 Manual discovery found {len(found_processes)} Context Cleaner processes")

    return found_processes


def _supervisor_stream_shutdown(
    *,
    verbose: bool,
    docker_only: bool,
    processes_only: bool,
    services: list[str],
    include_dependents: bool,
) -> tuple[bool, bool]:
    """Attempt to shut down services via the supervisor streaming API.

    Returns a tuple of (used_streaming, success).
    """

    try:
        from context_cleaner.ipc.client import SupervisorClient
        from context_cleaner.ipc.transport.base import TransportError
    except ImportError:
        return False, False

    try:
        with SupervisorClient() as client:
            if verbose:
                click.echo("   🔄 Contacting supervisor for streaming shutdown...")

            response = None
            for kind, event in client.stream_shutdown(
                docker_only=docker_only,
                processes_only=processes_only,
                services=services or None,
                include_dependents=include_dependents,
            ):
                if kind == "chunk":
                    _render_shutdown_chunk(event, verbose)
                else:
                    response = event

            if response is None:
                if verbose:
                    click.echo("   ⚠️  Supervisor stream ended without final response")
                return True, False

            if response.status == "ok":
                if verbose:
                    click.echo("   ✅ Supervisor reported successful shutdown")
                return True, True

            if verbose:
                click.echo(f"   ⚠️  Supervisor reported shutdown error: {response.status}")
            return True, False

    except (TransportError, OSError) as exc:
        if verbose:
            click.echo(f"   ⚠️  Supervisor streaming unavailable: {exc}")
        return False, False
    except Exception as exc:  # pragma: no cover - defensive
        if verbose:
            click.echo(f"   ⚠️  Unexpected supervisor streaming error: {exc}")
        return False, False


def _render_shutdown_chunk(chunk, verbose: bool) -> None:
    """Display supervisor shutdown progress information."""

    try:
        payload = json.loads(chunk.payload.decode("utf-8"))
    except Exception:
        click.echo("   ⏳ Supervisor progress update received")
        return

    stage = payload.get("stage")
    running = payload.get("running_services")
    transitioning = payload.get("transitioning", {}) or {}
    required_failed = payload.get("required_failed", []) or []

    if stage == "initiated":
        click.echo("   ⏳ Supervisor acknowledged shutdown request")
        if running is not None:
            click.echo(f"      Services running: {running}")
    elif stage == "progress":
        if running is not None:
            click.echo(f"   ⏳ Supervisor progress: {running} service(s) still running")
        stopping = transitioning.get("stopping", [])
        if stopping and verbose:
            click.echo(f"      Stopping: {', '.join(stopping)}")
        if required_failed and verbose:
            click.echo(f"      Required service issues: {', '.join(required_failed)}")
    elif stage == "completed":
        success = payload.get("success")
        if success:
            click.echo("   ✅ Supervisor reports shutdown complete")
        else:
            click.echo("   ⚠️  Supervisor reports shutdown failure")
        if running:
            click.echo(f"      Services still running: {running}")
        if required_failed:
            click.echo(f"      Required service issues: {', '.join(required_failed)}")
    else:
        click.echo("   ⏳ Supervisor progress update received")


def _terminate_process_with_escalation(proc, verbose: bool = False):
    """Terminate a process with signal escalation and timeout handling.

    Uses a progressive approach:
    1. SIGTERM (graceful termination)
    2. Wait with timeout
    3. SIGKILL (force kill)
    4. Process group cleanup if needed
    """
    import signal
    import time

    try:
        # First, try graceful termination
        proc.terminate()

        # Wait up to 5 seconds for graceful termination
        try:
            proc.wait(timeout=5)
            return True  # Successfully terminated
        except psutil.TimeoutExpired:
            if verbose:
                print(f"   ⏱️  PID {proc.pid} didn't respond to SIGTERM, escalating to SIGKILL")

        # If still running, force kill
        if proc.is_running():
            proc.kill()

            # Wait up to 3 more seconds for force kill
            try:
                proc.wait(timeout=3)
                return True
            except psutil.TimeoutExpired:
                if verbose:
                    print(f"   ⚠️  PID {proc.pid} didn't respond to SIGKILL, trying process group cleanup")

        # If STILL running, try process group termination
        if proc.is_running():
            try:
                # Try to kill the entire process group
                import os
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                time.sleep(2)

                if proc.is_running():
                    os.killpg(pgid, signal.SIGKILL)
                    time.sleep(1)

                return not proc.is_running()

            except (ProcessLookupError, OSError):
                # Process group doesn't exist or we can't access it
                pass

        return not proc.is_running()

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        # Process is gone or we can't access it - consider this success
        return True
    except Exception as e:
        if verbose:
            print(f"   ❌ Process termination error for PID {proc.pid}: {e}")
        return False


def _shutdown_clickhouse_containers_robust(verbose: bool = False):
    """Robust ClickHouse container shutdown with multiple fallback methods.

    This function ensures ClickHouse containers are completely stopped using:
    1. Docker compose stop/down (if compose file exists)
    2. Direct docker container stop (by name and ID)
    3. Process-level termination of clickhouse-server processes
    4. Verification and cleanup of persistent processes

    Returns: dict with shutdown results and any remaining issues
    """
    import subprocess
    import time
    import os
    from pathlib import Path

    shutdown_results = {
        "compose_shutdown": False,
        "direct_container_shutdown": False,
        "process_termination": False,
        "containers_stopped": [],
        "processes_terminated": [],
        "remaining_issues": [],
        "success": True
    }

    if verbose:
        print("   🐳 Starting robust ClickHouse container shutdown...")

    # Method 1: Docker Compose shutdown (standard approach)
    compose_file = Path("docker-compose.yml")
    if compose_file.exists():
        try:
            if verbose:
                print("   📁 Found docker-compose.yml, attempting compose shutdown...")

            # Stop ClickHouse service specifically first
            result = subprocess.run(
                ["docker", "compose", "stop", "clickhouse"],
                capture_output=True, text=True, timeout=15
            )

            if result.returncode == 0:
                shutdown_results["compose_shutdown"] = True
                if verbose:
                    print("   ✅ Docker compose stop clickhouse succeeded")

                # Also stop otel-collector which depends on ClickHouse
                subprocess.run(
                    ["docker", "compose", "stop", "otel-collector"],
                    capture_output=True, text=True, timeout=10
                )

                # Full compose down for cleanup
                subprocess.run(
                    ["docker", "compose", "down"],
                    capture_output=True, text=True, timeout=20
                )

            else:
                if verbose:
                    print(f"   ⚠️  Docker compose stop failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            if verbose:
                print("   ⚠️  Docker compose stop timed out, trying force methods...")
        except Exception as e:
            if verbose:
                print(f"   ❌ Docker compose error: {e}")

    # Method 2: Direct Docker container shutdown by name and discovery
    # First, discover ClickHouse containers by image
    discovered_containers = []

    try:
        # Find containers by ClickHouse image pattern
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "ancestor=clickhouse/clickhouse-server"],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            image_containers = result.stdout.strip().split('\n')
            discovered_containers.extend(image_containers)
            if verbose:
                print(f"   🔍 Found ClickHouse containers by image: {image_containers}")
    except:
        pass

    # Add known container names
    container_names = ["clickhouse-otel", "otel-collector"] + discovered_containers
    # Remove duplicates while preserving order
    container_names = list(dict.fromkeys(container_names))

    for container_name in container_names:
        try:
            if verbose:
                print(f"   🔍 Checking container {container_name}...")

            # Check if container exists and is running
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0 and result.stdout.strip().lower() == "true":
                if verbose:
                    print(f"   🛑 Stopping running container {container_name}...")

                # Try graceful stop first
                stop_result = subprocess.run(
                    ["docker", "stop", "-t", "10", container_name],
                    capture_output=True, text=True, timeout=15
                )

                if stop_result.returncode == 0:
                    shutdown_results["containers_stopped"].append(container_name)
                    shutdown_results["direct_container_shutdown"] = True
                    if verbose:
                        print(f"   ✅ Container {container_name} stopped gracefully")
                else:
                    # Force kill if graceful stop failed
                    if verbose:
                        print(f"   ⚠️  Graceful stop failed, force killing {container_name}...")

                    kill_result = subprocess.run(
                        ["docker", "kill", container_name],
                        capture_output=True, text=True, timeout=5
                    )

                    if kill_result.returncode == 0:
                        shutdown_results["containers_stopped"].append(f"{container_name} (forced)")
                        shutdown_results["direct_container_shutdown"] = True
                        if verbose:
                            print(f"   ✅ Container {container_name} force killed")
                    else:
                        shutdown_results["remaining_issues"].append(f"Failed to stop container {container_name}")
                        if verbose:
                            print(f"   ❌ Failed to force kill {container_name}")

        except subprocess.TimeoutExpired:
            shutdown_results["remaining_issues"].append(f"Container {container_name} operations timed out")
            if verbose:
                print(f"   ⏱️  Operations for {container_name} timed out")
        except Exception as e:
            shutdown_results["remaining_issues"].append(f"Container {container_name} error: {str(e)}")
            if verbose:
                print(f"   ❌ Error with {container_name}: {e}")

    # Method 3: Process-level termination of ClickHouse processes
    # This catches processes that might be running outside Docker or stuck processes
    try:
        if verbose:
            print("   🔍 Searching for ClickHouse server processes...")

        import psutil
        clickhouse_processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not proc.info['cmdline']:
                    continue

                cmdline = ' '.join(proc.info['cmdline']).lower()

                # Look for ClickHouse server processes
                if any(pattern in cmdline for pattern in [
                    'clickhouse-server',
                    '/usr/bin/clickhouse-server',
                    'clickhouse/clickhouse-server',
                    '--daemon'  # ClickHouse daemon flag
                ]):
                    clickhouse_processes.append(proc.info['pid'])
                    if verbose:
                        print(f"   🔍 Found ClickHouse process PID {proc.info['pid']}")

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Terminate discovered ClickHouse processes
        for pid in clickhouse_processes:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    success = _terminate_process_with_escalation(proc, verbose)
                    if success:
                        shutdown_results["processes_terminated"].append(pid)
                        shutdown_results["process_termination"] = True
                        if verbose:
                            print(f"   ✅ Terminated ClickHouse process PID {pid}")
                    else:
                        shutdown_results["remaining_issues"].append(f"Failed to terminate process PID {pid}")
                        if verbose:
                            print(f"   ❌ Failed to terminate PID {pid}")

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue  # Process already gone

    except Exception as e:
        shutdown_results["remaining_issues"].append(f"Process termination error: {str(e)}")
        if verbose:
            print(f"   ❌ Process termination phase error: {e}")

    # Method 4: Final verification and cleanup
    time.sleep(2)  # Give processes time to fully shutdown

    try:
        if verbose:
            print("   🔍 Final verification of ClickHouse shutdown...")

        # Check if ClickHouse port is still bound
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 8123))
                if result == 0:
                    shutdown_results["remaining_issues"].append("ClickHouse HTTP port 8123 still responding")
                    shutdown_results["success"] = False
                    if verbose:
                        print("   ⚠️  ClickHouse HTTP port 8123 still responding")
        except:
            pass  # Port check failed, but that's okay

        # Check if any containers are still running
        for container_name in container_names:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                    capture_output=True, text=True, timeout=3
                )

                if result.returncode == 0 and result.stdout.strip().lower() == "true":
                    shutdown_results["remaining_issues"].append(f"Container {container_name} still running")
                    shutdown_results["success"] = False
                    if verbose:
                        print(f"   ⚠️  Container {container_name} still running after shutdown attempts")

            except:
                pass  # Container doesn't exist or Docker error

    except Exception as e:
        shutdown_results["remaining_issues"].append(f"Verification error: {str(e)}")

    # Set overall success flag
    if shutdown_results["remaining_issues"]:
        shutdown_results["success"] = False

    if verbose:
        if shutdown_results["success"]:
            print("   🎯 ClickHouse containers shutdown successfully!")
        else:
            print(f"   ⚠️  ClickHouse shutdown completed with {len(shutdown_results['remaining_issues'])} remaining issues")
            for issue in shutdown_results["remaining_issues"]:
                print(f"      - {issue}")

    return shutdown_results


async def _basic_stop_fallback(ctx, force: bool, docker_only: bool, processes_only: bool, verbose: bool):
    """Fallback basic stop implementation when orchestrator is unavailable."""
    import subprocess
    import signal
    import os
    import psutil
    from pathlib import Path
    
    if verbose:
        click.echo("🔄 Using basic fallback cleanup method")
    
    if not force:
        click.echo("🛑 This will stop Context Cleaner services using basic method:")
        if not docker_only:
            click.echo("   • Background processes (pattern matching)")
            click.echo("   • Dashboard servers on common ports")
        if not processes_only:
            click.echo("   • Docker containers")
        click.echo()
        
        if not click.confirm("Continue with basic shutdown?"):
            click.echo("❌ Shutdown cancelled")
            return
    
    stopped_services = []
    
    # Stop background processes if requested
    if not docker_only:
        try:
            # Use comprehensive process discovery for fallback as well
            manual_processes = _discover_all_context_cleaner_processes(verbose)
            
            for process in manual_processes:
                try:
                    proc = psutil.Process(process.pid)
                    if proc.is_running():
                        success = _terminate_process_with_escalation(proc, verbose)
                        if success and verbose:
                            click.echo(f"   ✅ Stopped PID {process.pid} ({process.service_type})")
                        elif not success and verbose:
                            click.echo(f"   ❌ Failed to stop PID {process.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue  # Process already gone or inaccessible
            
            # Also try pattern-based killing as backup
            patterns = [
                "start_context_cleaner",
                "context_cleaner.*run", 
                "context_cleaner.*jsonl", 
                "jsonl_background_service",
                "context_cleaner.*dashboard", 
                "context_cleaner.*bridge",
                "ComprehensiveHealthDashboard",
                "context_cleaner_wsgi"
            ]
            
            for pattern in patterns:
                subprocess.run(["pkill", "-f", pattern], capture_output=True)
            
            # Kill dashboard processes by port pattern
            ports_to_check = range(8080, 8200)  # Extended range
            for port in ports_to_check:
                try:
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
            
            stopped_services.append("background processes (basic)")
            
        except Exception as e:
            if verbose:
                click.echo(f"⚠️ Error stopping background processes: {e}")
    
    # Stop Docker services if requested - using enhanced ClickHouse shutdown
    if not processes_only:
        if verbose:
            click.echo("🐳 Using enhanced ClickHouse shutdown in fallback mode...")

        # Use robust ClickHouse shutdown even in fallback mode
        clickhouse_results = _shutdown_clickhouse_containers_robust(verbose)

        if clickhouse_results["success"]:
            stopped_services.append("ClickHouse containers (robust shutdown)")
        else:
            stopped_services.append("ClickHouse containers (partial shutdown)")
            if verbose:
                for issue in clickhouse_results["remaining_issues"]:
                    click.echo(f"   ⚠️  {issue}")

        # Traditional compose cleanup
        compose_file = Path("docker-compose.yml")
        if compose_file.exists():
            try:
                result = subprocess.run(
                    ["docker", "compose", "down"],
                    capture_output=True, text=True, timeout=30
                )

                if result.returncode == 0:
                    stopped_services.append("Docker compose cleanup")
                else:
                    stopped_services.append("Docker compose cleanup (with warnings)")

            except subprocess.TimeoutExpired:
                try:
                    subprocess.run(["docker", "compose", "kill"], timeout=10)
                    subprocess.run(["docker", "compose", "down"], timeout=10)
                    stopped_services.append("Docker compose (forced)")
                except:
                    click.echo("❌ Failed to stop Docker services", err=True)
            except Exception as e:
                click.echo(f"❌ Error stopping Docker services: {e}", err=True)
    
    # Summary
    if stopped_services:
        click.echo("🎯 Basic shutdown complete!")
        for service in stopped_services:
            click.echo(f"   ✅ {service}")
    else:
        click.echo("🤷 No services were found running")


# REMOVED: Conflicting dashboard-mgr command group - use 'run' and 'stop' commands instead
# The dashboard-mgr command group has been removed to avoid confusion with the comprehensive service
# orchestration provided by 'run' and 'stop' commands. Dashboard management is now integrated
# into the ServiceOrchestrator.
# Use 'context-cleaner run' and 'context-cleaner stop' for complete service management.


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
    
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"] or dev_mode
    
    # Handle custom config file
    if config_file:
        config = ApplicationConfig.from_file(Path(config_file))
        ctx.obj["config"] = config
    
    # Enable development mode
    if dev_mode:
        ctx.obj["verbose"] = True
        verbose = True
        click.echo("🔧 Development mode enabled - verbose logging active")
    
    # Import service orchestrator
    try:
        from context_cleaner.services import ServiceOrchestrator
    except ImportError:
        click.echo("❌ Service orchestrator not available", err=True)
        sys.exit(1)
    
    # Initialize orchestrator
    click.echo("🔍 DEBUG: Creating ServiceOrchestrator instance...")
    orchestrator = ServiceOrchestrator(config=config, verbose=verbose)
    click.echo("✅ DEBUG: ServiceOrchestrator instance created successfully")
    
    # Handle status-only mode
    click.echo("🔍 DEBUG: Checking status-only mode...")
    if status_only:
        click.echo("🔍 DEBUG: Status-only mode detected, getting service status...")
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
    click.echo("🔍 DEBUG: Configuring services...")
    if no_docker:
        click.echo("🔍 DEBUG: Disabling docker services (clickhouse, otel)...")
        orchestrator.services.pop("clickhouse", None)
        orchestrator.services.pop("otel", None)
        
        # Automatically disable JSONL service when Docker is disabled 
        # since it depends on ClickHouse
        if "jsonl_bridge" in orchestrator.services:
            click.echo("🔍 DEBUG: Auto-disabling jsonl_bridge service (depends on ClickHouse)...")
            orchestrator.services.pop("jsonl_bridge", None)
    
    if no_jsonl:
        click.echo("🔍 DEBUG: Disabling jsonl_bridge service...")
        orchestrator.services.pop("jsonl_bridge", None)
    
    click.echo("✅ DEBUG: Service configuration completed")

    supervisor_config = SupervisorConfig(
        endpoint=default_supervisor_endpoint(),
        audit_log_path=str(Path("logs/supervisor/audit.log")),
    )
    supervisor_state = {"instance": None}
    supervisor_restart_lock = threading.RLock()
    supervisor_loop = None
    supervisor_thread = None
    watchdog = None

    orchestrator_shutdown_initiated = False

    def _shutdown_orchestrator(**shutdown_kwargs) -> None:
        nonlocal orchestrator_shutdown_initiated
        if orchestrator_shutdown_initiated:
            return
        orchestrator_shutdown_initiated = True
        try:
            _run_orchestrator_coro(orchestrator.shutdown_all(**shutdown_kwargs))
        except Exception as exc:
            if verbose:
                click.echo(f"⚠️  Orchestrator shutdown encountered an error: {exc}")

    def _run_on_supervisor_loop(coro, *, timeout: float | None = None):
        if supervisor_loop is None:
            raise RuntimeError("Supervisor event loop is not running")

        future = asyncio.run_coroutine_threadsafe(coro, supervisor_loop)
        try:
            return future.result(timeout)
        except Exception:
            future.cancel()
            raise

    def _run_orchestrator_coro(coro, *, timeout: float | None = None):
        if supervisor_loop is not None:
            return _run_on_supervisor_loop(coro, timeout=timeout)
        return _run_asyncio(coro)

    def _start_supervisor() -> bool:
        nonlocal supervisor_loop, supervisor_thread
        with supervisor_restart_lock:
            if supervisor_state["instance"] is not None:
                return True

            try:
                supervisor = ServiceSupervisor(orchestrator, supervisor_config)
            except Exception as exc:
                if verbose:
                    click.echo(f"⚠️  Failed to initialize supervisor: {exc}")
                return False

            loop = asyncio.new_event_loop()

            def _loop_runner() -> None:
                asyncio.set_event_loop(loop)
                try:
                    loop.run_forever()
                finally:
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    for task in pending_tasks:
                        task.cancel()
                    if pending_tasks:
                        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    asyncio.set_event_loop(None)

            thread = threading.Thread(
                target=_loop_runner,
                name="context-cleaner-supervisor",
                daemon=True,
            )
            thread.start()

            future = asyncio.run_coroutine_threadsafe(supervisor.start(), loop)
            try:
                future.result(timeout=10)
            except Exception as exc:
                if verbose:
                    click.echo(f"⚠️  Supervisor start failed: {exc}")
                loop.call_soon_threadsafe(loop.stop)
                thread.join(timeout=5)
                loop.close()
                return False

            supervisor_state["instance"] = supervisor
            supervisor_loop = loop
            supervisor_thread = thread
            return True

    def _stop_supervisor() -> None:
        nonlocal supervisor_loop, supervisor_thread
        with supervisor_restart_lock:
            loop = supervisor_loop
            thread = supervisor_thread
            current = supervisor_state["instance"]
            supervisor_state["instance"] = None

            if current and loop:
                try:
                    future = asyncio.run_coroutine_threadsafe(current.stop(), loop)
                    future.result(timeout=5)
                except Exception as exc:
                    if verbose:
                        click.echo(f"⚠️  Supervisor stop encountered an error: {exc}")

            if loop:
                loop.call_soon_threadsafe(loop.stop)
            if thread and thread.is_alive():
                thread.join(timeout=5)
            if loop:
                loop.close()

            supervisor_loop = None
            supervisor_thread = None

    def _restart_supervisor() -> None:
        if verbose:
            LOGGER.debug("Watchdog requested supervisor restart")
        _stop_supervisor()
        _start_supervisor()

    if _start_supervisor():
        watchdog = ServiceWatchdog(restart_callback=_restart_supervisor)
        watchdog.start()
    else:
        supervisor_state["instance"] = None
        if verbose:
            click.echo("⚠️  Supervisor unavailable; using fallback event loop handling")
    
    try:
        # Start all services - handle event loop properly with enhanced debugging
        click.echo("🔍 DEBUG: Defining start_services() async function...")
        async def start_services():
            click.echo("🔍 DEBUG: Inside start_services(), calling orchestrator.start_all_services()...")
            try:
                return await orchestrator.start_all_services(dashboard_port)
            except Exception as e:
                click.echo(f"❌ DEBUG: Exception in start_all_services(): {str(e)}")
                raise
        
        if supervisor_loop is not None:
            click.echo("🔍 DEBUG: Starting services via supervisor event loop...")
        else:
            click.echo("🔍 DEBUG: Starting services via fallback event loop...")
        try:
            success = _run_orchestrator_coro(start_services())
        except Exception as e:
            click.echo(f"❌ DEBUG: Event loop handling failed: {str(e)}")
            raise

        click.echo(f"🔍 DEBUG: Service startup result: {success}")
        
        if not success:
            click.echo("❌ Failed to start all required services", err=True)
            sys.exit(1)
        
        # Start the dashboard (this is the main blocking operation)
        try:
            from context_cleaner.dashboard.comprehensive_health_dashboard import ComprehensiveHealthDashboard

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
            
            dashboard_url = f"http://{config.dashboard.host}:{dashboard_port}"
            orchestrator.register_external_service(
                "dashboard",
                pid=os.getpid(),
                stop_callback=dashboard.stop_server,
                metadata={
                    "port": dashboard_port,
                    "url": dashboard_url,
                    "command_line": f"dashboard-server:{dashboard_port}",
                },
            )
            dashboard_state = orchestrator.service_states.get("dashboard")
            if dashboard_state:
                dashboard_state.url = dashboard_url
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
            _shutdown_orchestrator()
            sys.exit(1)
    
    except KeyboardInterrupt:
        if verbose:
            click.echo("\n👋 Received shutdown signal")
        _shutdown_orchestrator()
        if watchdog:
            watchdog.stop()
            watchdog = None
        _stop_supervisor()
        if verbose:
            click.echo("✅ All services stopped cleanly")

    except Exception as e:
        click.echo(f"❌ Service orchestration failed: {e}", err=True)
        _shutdown_orchestrator()
        if watchdog:
            watchdog.stop()
            watchdog = None
        _stop_supervisor()
        sys.exit(1)

    finally:
        _shutdown_orchestrator()
        if watchdog:
            watchdog.stop()
            watchdog = None
        _stop_supervisor()



if __name__ == "__main__":
    main()
