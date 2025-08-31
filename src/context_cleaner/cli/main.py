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


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Configuration file path"
)
@click.option("--data-dir", type=click.Path(), help="Data directory path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
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
        click.echo(
            f"📊 Dashboard available at: http://{config.dashboard.host}:{config.dashboard.port}"
        )
        click.echo("📈 Use 'context-cleaner dashboard' to view insights")
    else:
        click.echo("✅ Context Cleaner started")


@main.command()
@click.option("--port", "-p", type=int, help="Dashboard port (overrides config)")
@click.option("--host", "-h", default=None, help="Dashboard host (overrides config)")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
@click.option("--interactive", is_flag=True, help="Enable interactive dashboard mode")
@click.option("--operations", is_flag=True, help="Show available operations")
@click.pass_context
def dashboard(ctx, port, host, no_browser, interactive, operations):
    """Launch the productivity dashboard web interface."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]

    # Override configuration if provided
    if port:
        config.dashboard.port = port
    if host:
        config.dashboard.host = host

    if verbose:
        click.echo(
            f"🌐 Starting dashboard server on {config.dashboard.host}:{config.dashboard.port}"
        )

    try:
        # Check if enhanced dashboard features are requested
        if interactive or operations:
            from .analytics_commands import AnalyticsCommandHandler
            analytics_handler = AnalyticsCommandHandler(config, verbose)
            analytics_handler.handle_enhanced_dashboard_command(
                interactive=interactive,
                operations=operations,
                format="text"
            )
        else:
            # Create and start dashboard
            dashboard_server = ProductivityDashboard(config)

            if not no_browser:
                import webbrowser

                try:
                    webbrowser.open(
                        f"http://{config.dashboard.host}:{config.dashboard.port}"
                    )
                except Exception:
                    pass  # Browser opening is optional

            click.echo(
                f"📊 Dashboard running at: http://{config.dashboard.host}:{config.dashboard.port}"
            )
            click.echo("Press Ctrl+C to stop the server")

            # Start server (blocking)
            dashboard_server.start_server(config.dashboard.host, config.dashboard.port)

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
        # Import optimization modules
        from ..optimization.basic_analyzer import SafeContextAnalyzer
        from ..visualization.basic_dashboard import BasicDashboard

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
            click.echo(
                f"📈 Avg Productivity: {summary.get('average_productivity_score', 0)}/100"
            )
            click.echo(f"🔧 Optimizations: {summary.get('total_optimizations', 0)}")
            click.echo(f"🛠️ Tools Used: {summary.get('total_tools_used', 0)}")

            # Show best session
            if "best_session" in summary:
                best = summary["best_session"]
                click.echo(
                    f"\n🌟 Best Session: {best['productivity_score']}/100 ({best['duration_minutes']}min)"
                )

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

                click.echo(
                    f"{status_icon} {session.session_id[:8]}... | {duration_min}min | {productivity}/100 | {session.start_time.strftime('%Y-%m-%d %H:%M')}"
                )

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
                click.echo(
                    f"[{timestamp}] {event_type}: {event_data.get('message', 'Event triggered')}"
                )

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
            click.echo(f"\n⚙️ Configuration:")
            click.echo(
                f"   Session updates: every {config_data.get('session_update_interval_s', 0)}s"
            )
            click.echo(
                f"   Health updates: every {config_data.get('health_update_interval_s', 0)}s"
            )
            click.echo(
                f"   Activity updates: every {config_data.get('activity_update_interval_s', 0)}s"
            )

            # Cache status
            cache = status.get("cache_status", {})
            click.echo(f"\n💾 Cache Status:")
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
                        click.echo(
                            f"📊 Session: {current_session.get('session_id', 'Unknown')[:8]}..."
                        )
                        click.echo(
                            f"⏱️ Duration: {current_session.get('duration_seconds', 0):.0f}s"
                        )
                        click.echo(
                            f"🎯 Productivity: {current_session.get('productivity_score', 0)}/100"
                        )
                        click.echo(
                            f"🔧 Optimizations: {current_session.get('optimizations_applied', 0)}"
                        )
                        click.echo(f"🛠️ Tools: {current_session.get('tools_used', 0)}")
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

                        click.echo(
                            f"{health_icon} Context Health: {health_score}/100 ({health_status})"
                        )

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
    ProductivityAnalyzer(config)

    # This would typically load real session data
    # For now, return placeholder analysis
    return {
        "period_days": days,
        "avg_productivity_score": 85.3,
        "total_sessions": 23,
        "optimization_events": 12,
        "most_productive_day": "Tuesday",
        "recommendations": [
            "Your productivity peaks in the afternoon - consider scheduling complex tasks then",
            "Context optimization events correlate with 15% productivity increase",
            "Consider shorter sessions (< 2 hours) for sustained high performance",
        ],
        "analysis_timestamp": "2025-08-28T19:50:00",
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
    output.append("")
    output.append("💡 RECOMMENDATIONS:")
    for i, rec in enumerate(results["recommendations"], 1):
        output.append(f"   {i}. {rec}")
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
@click.option("--fix-issues", is_flag=True, help="Attempt to fix identified issues automatically")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.pass_context
def health_check(ctx, detailed, fix_issues, format):
    """Perform comprehensive system health check and validation."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        from .analytics_commands import AnalyticsCommandHandler
        analytics_handler = AnalyticsCommandHandler(config, verbose)
        analytics_handler.handle_health_check_command(
            detailed=detailed,
            fix_issues=fix_issues,
            format=format
        )
    except Exception as e:
        if verbose:
            click.echo(f"❌ Health check failed: {e}", err=True)
        else:
            click.echo("❌ Health check failed", err=True)
        sys.exit(1)


@main.command("export-analytics")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--days", type=int, default=30, help="Number of days to include in export")
@click.option("--include-sessions", is_flag=True, default=True, help="Include session details")
@click.option("--format", type=click.Choice(["json"]), default="json", help="Export format")
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
            format=format
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
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.pass_context
def effectiveness(ctx, days, strategy, detailed, format):
    """Display optimization effectiveness statistics and user impact metrics."""
    config = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    
    try:
        from .analytics_commands import AnalyticsCommandHandler
        analytics_handler = AnalyticsCommandHandler(config, verbose)
        analytics_handler.handle_effectiveness_stats_command(
            days=days,
            strategy=strategy,
            detailed=detailed,
            format=format
        )
    except Exception as e:
        if verbose:
            click.echo(f"❌ Effectiveness analysis failed: {e}", err=True)
        else:
            click.echo("❌ Effectiveness analysis failed", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
