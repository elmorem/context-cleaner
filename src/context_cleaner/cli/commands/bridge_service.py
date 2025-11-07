"""
CLI Commands for Token Analysis Bridge Service - PR22.4

Provides command-line interface for the bridge service that resolves the critical
2.768 billion token data loss issue identified in the September 9th analysis.

Commands:
- bridge-backfill: Execute historical data backfill
- bridge-status: Show bridge service status
- bridge-validate: Validate end-to-end data flow
- bridge-sync: Sync real-time token usage
"""

import click
import asyncio
import json
from datetime import datetime, date, timedelta
from typing import Optional

from ...bridges.token_analysis_bridge import (
    TokenAnalysisBridgeService,
    create_token_bridge_service,
    execute_bridge_backfill,
)
from ...bridges.incremental_sync import (
    IncrementalSyncService,
    create_incremental_sync_service,
)


@click.group()
def bridge():
    """Token Analysis Bridge Service commands - resolves 2.768B token data loss."""
    pass


@bridge.command("backfill")
@click.option(
    "--clickhouse-url", default="http://localhost:8123", help="ClickHouse server URL"
)
@click.option("--batch-size", default=1000, help="Batch size for database inserts")
@click.option("--start-date", help="Start date for backfill (YYYY-MM-DD)")
@click.option("--end-date", help="End date for backfill (YYYY-MM-DD)")
@click.option(
    "--dry-run", is_flag=True, help="Simulate backfill without database writes"
)
@click.option("--verbose", is_flag=True, help="Verbose logging output")
def backfill_command(
    clickhouse_url, batch_size, start_date, end_date, dry_run, verbose
):
    """
    Execute historical data backfill of 2.768B tokens from JSONL analysis to database.

    This resolves the critical data loss issue where enhanced token analysis results
    were not being transferred to the database that the dashboard reads from.

    Examples:
        context-cleaner bridge backfill --dry-run                    # Test run
        context-cleaner bridge backfill                              # Full backfill
        context-cleaner bridge backfill --batch-size 2000           # Larger batches
        context-cleaner bridge backfill --start-date 2025-09-01     # Custom date range
    """

    async def run_backfill():
        click.echo("🔄 Starting Token Analysis Bridge Backfill...")
        click.echo(f"   ClickHouse URL: {clickhouse_url}")
        click.echo(f"   Batch size: {batch_size}")
        click.echo(f"   Dry run: {dry_run}")

        if start_date:
            click.echo(f"   Start date: {start_date}")
        if end_date:
            click.echo(f"   End date: {end_date}")

        click.echo()

        try:
            # Execute backfill
            stats = await execute_bridge_backfill(
                clickhouse_url=clickhouse_url, batch_size=batch_size, dry_run=dry_run
            )

            # Display results
            click.echo("✅ Backfill completed successfully!")
            click.echo()
            click.echo("📊 Results:")
            click.echo(f"   Sessions processed: {stats.sessions_processed:,}")
            click.echo(f"   Tokens transferred: {stats.total_tokens_transferred:,}")
            click.echo(f"   Database records: {stats.database_records_inserted:,}")
            click.echo(f"   Processing time: {stats.processing_time_seconds:.2f}s")

            if stats.errors_encountered:
                click.echo()
                click.echo(f"⚠️  Errors encountered: {len(stats.errors_encountered)}")
                for error in stats.errors_encountered:
                    click.echo(f"   - {error}")
            else:
                click.echo()
                click.echo("🎉 No errors encountered - data transfer successful!")

            if not dry_run and stats.total_tokens_transferred > 0:
                click.echo()
                click.echo("🔍 Next steps:")
                click.echo(
                    "   1. Run 'context-cleaner bridge validate' to verify data flow"
                )
                click.echo("   2. Check dashboard for updated token counts")
                click.echo(
                    "   3. Monitor bridge service with 'context-cleaner bridge status'"
                )

        except Exception as e:
            click.echo(f"❌ Backfill failed: {str(e)}")
            raise click.Abort()

    # Run async function
    asyncio.run(run_backfill())


@bridge.command("status")
@click.option(
    "--clickhouse-url", default="http://localhost:8123", help="ClickHouse server URL"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def status_command(clickhouse_url, output_format):
    """
    Show current status of the Token Analysis Bridge Service.

    Displays service health, statistics, and configuration information.
    """

    async def get_status():
        try:
            # Create bridge service
            service = await create_token_bridge_service(clickhouse_url)

            # Get status
            status = service.get_bridge_status()

            if output_format == "json":
                click.echo(json.dumps(status, indent=2, default=str))
            else:
                click.echo("🌉 Token Analysis Bridge Service Status")
                click.echo("=" * 45)
                click.echo(f"Service: {status['service_name']}")
                click.echo(f"Status: {status['status']}")
                click.echo(
                    f"ClickHouse Client: {'✅ Connected' if status['has_clickhouse_client'] else '❌ Not Available'}"
                )
                click.echo()

                stats = status["stats"]
                click.echo("📈 Statistics:")
                click.echo(f"   Sessions processed: {stats['sessions_processed']:,}")
                click.echo(
                    f"   Tokens transferred: {stats['total_tokens_transferred']:,}"
                )
                click.echo(
                    f"   Database records: {stats['database_records_inserted']:,}"
                )
                click.echo(
                    f"   Processing time: {stats['processing_time_seconds']:.2f}s"
                )

                if stats["last_successful_sync"]:
                    click.echo(f"   Last sync: {stats['last_successful_sync']}")
                else:
                    click.echo("   Last sync: Never")

                if stats["errors_encountered"]:
                    click.echo(f"   Errors: {len(stats['errors_encountered'])}")
                else:
                    click.echo("   Errors: None")

                click.echo()
                capabilities = status["capabilities"]
                click.echo("🔧 Capabilities:")
                for capability, available in capabilities.items():
                    status_icon = "✅" if available else "❌"
                    click.echo(
                        f"   {status_icon} {capability.replace('_', ' ').title()}"
                    )

        except Exception as e:
            click.echo(f"❌ Failed to get bridge status: {str(e)}")
            raise click.Abort()

    asyncio.run(get_status())


@bridge.command("validate")
@click.option(
    "--clickhouse-url", default="http://localhost:8123", help="ClickHouse server URL"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def validate_command(clickhouse_url, output_format):
    """
    Validate end-to-end data flow from JSONL files to database to dashboard.

    Performs comprehensive validation of the complete data pipeline to ensure
    the 2.768B token data loss issue has been resolved.
    """

    async def run_validation():
        click.echo("🔍 Validating Token Analysis Bridge Data Flow...")
        click.echo()

        try:
            # Create bridge service
            service = await create_token_bridge_service(clickhouse_url)

            # Run validation
            results = await service.validate_data_flow()

            if output_format == "json":
                click.echo(json.dumps(results, indent=2, default=str))
            else:
                # Display validation results
                click.echo("📋 Validation Results:")
                click.echo("=" * 25)

                checks = [
                    ("JSONL Analysis", results["jsonl_analysis_working"]),
                    ("Database Access", results["database_accessible"]),
                    ("Data Flow Complete", results["data_flow_complete"]),
                    ("Token Count Matches", results["token_count_matches"]),
                ]

                all_passed = True
                for check_name, passed in checks:
                    status_icon = "✅" if passed else "❌"
                    click.echo(f"   {status_icon} {check_name}")
                    if not passed:
                        all_passed = False

                click.echo()

                if results["errors"]:
                    click.echo("⚠️  Issues found:")
                    for error in results["errors"]:
                        click.echo(f"   - {error}")
                    click.echo()

                if all_passed:
                    click.echo(
                        "🎉 All validations passed! Data flow is working correctly."
                    )
                    click.echo(
                        "   The 2.768B token data loss issue appears to be resolved."
                    )
                else:
                    click.echo("🔧 Some issues found - see details above.")
                    click.echo("   Run 'context-cleaner bridge backfill' if needed.")

        except Exception as e:
            click.echo(f"❌ Validation failed: {str(e)}")
            raise click.Abort()

    asyncio.run(run_validation())


@bridge.command("sync")
@click.option(
    "--clickhouse-url", default="http://localhost:8123", help="ClickHouse server URL"
)
@click.option("--watch-directory", help="Directory to monitor for JSONL files")
@click.option("--interval", default=15, help="Sync interval in minutes")
@click.option("--once", is_flag=True, help="Run sync once instead of continuously")
@click.option(
    "--start-monitoring", is_flag=True, help="Start real-time file monitoring"
)
def sync_command(clickhouse_url, watch_directory, interval, once, start_monitoring):
    """
    Start incremental synchronization service for new JSONL data.

    Implements the automated JSONL-to-database synchronization identified
    in the September 9th analysis as critical for ongoing data flow.

    Examples:
        context-cleaner bridge sync --once                    # Single sync run
        context-cleaner bridge sync --interval 5              # Sync every 5 minutes
        context-cleaner bridge sync --start-monitoring        # Real-time file monitoring
    """

    async def run_sync():
        try:
            click.echo("🔄 Starting Incremental Synchronization Service...")
            click.echo(f"   ClickHouse URL: {clickhouse_url}")
            click.echo(f"   Watch directory: {watch_directory or '~/.claude/projects'}")

            if once:
                click.echo("   Mode: Single sync operation")
            elif start_monitoring:
                click.echo("   Mode: Real-time file monitoring")
            else:
                click.echo(f"   Mode: Scheduled sync every {interval} minutes")

            click.echo()

            # Create bridge service
            bridge_service = await create_token_bridge_service(clickhouse_url)

            # Create incremental sync service
            sync_service = await create_incremental_sync_service(
                bridge_service=bridge_service, watch_directory=watch_directory
            )

            async def ensure_context_rot_backfill() -> None:
                """Run the historical context rot backfill once if needed."""
                if not sync_service.needs_context_rot_backfill:
                    return

                click.echo("🧮 Performing context rot historical backfill...")
                try:
                    events_generated = await sync_service.backfill_context_rot()
                except Exception as backfill_error:
                    click.echo(f"❌ Context rot backfill failed: {backfill_error}")
                    raise

                click.echo(
                    f"   Context rot backfill complete ({events_generated} events recorded)"
                )

            if once:
                # Single sync operation
                await ensure_context_rot_backfill()
                click.echo("🔍 Running single incremental sync...")
                files_synced = await sync_service.sync_incremental_changes()

                click.echo(f"✅ Sync complete! {files_synced} files processed")

                status = sync_service.get_sync_status()
                stats = status["stats"]
                click.echo(f"   Files monitored: {stats['files_monitored']}")
                click.echo(f"   New files: {stats['new_files_detected']}")
                click.echo(f"   Modified files: {stats['modified_files_detected']}")
                click.echo(f"   Lines processed: {stats['lines_processed']}")
                click.echo(f"   Tokens synced: {stats['tokens_synced']:,}")

            elif start_monitoring:
                # Real-time monitoring
                await ensure_context_rot_backfill()
                click.echo("👁️  Starting real-time file monitoring...")
                click.echo("   Press Ctrl+C to stop")

                await sync_service.start_file_monitoring()

                try:
                    # Keep running until interrupted - no timeout for service mode
                    while True:
                        try:

                            # Use timeout for sleep to make it interruptible
                            await asyncio.wait_for(asyncio.sleep(10), timeout=30.0)

                            # Show periodic status
                            status = sync_service.get_sync_status()
                            if status["stats"]["last_sync_time"]:
                                click.echo(
                                    f"   Last sync: {status['stats']['last_sync_time']}"
                                )

                        except asyncio.TimeoutError:
                            # Sleep timeout - continue loop but check for overall timeout
                            continue
                        except Exception as e:
                            click.echo(f"⚠️  Error in monitoring loop: {e}")
                            await asyncio.sleep(5)  # Brief pause before retrying

                except KeyboardInterrupt:
                    click.echo("\n🛑 Stopping file monitoring...")
                    await sync_service.stop_file_monitoring()

            else:
                # Scheduled sync
                await ensure_context_rot_backfill()
                click.echo(f"⏰ Starting scheduled sync every {interval} minutes...")
                click.echo("   Press Ctrl+C to stop")

                try:
                    await sync_service.run_scheduled_sync(interval_minutes=interval)
                except KeyboardInterrupt:
                    click.echo("\n🛑 Stopping scheduled sync...")

        except Exception as e:
            click.echo(f"❌ Sync service failed: {str(e)}")
            raise click.Abort()

    asyncio.run(run_sync())


@bridge.command("sync-status")
@click.option(
    "--clickhouse-url", default="http://localhost:8123", help="ClickHouse server URL"
)
@click.option("--watch-directory", help="Directory being monitored")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def sync_status_command(clickhouse_url, watch_directory, output_format):
    """
    Show status of incremental synchronization service.

    Displays current sync state, file monitoring status, and processing statistics.
    """

    async def get_sync_status():
        try:
            # Create services
            bridge_service = await create_token_bridge_service(clickhouse_url)
            sync_service = await create_incremental_sync_service(
                bridge_service=bridge_service, watch_directory=watch_directory
            )

            # Get status
            status = sync_service.get_sync_status()

            if output_format == "json":
                click.echo(json.dumps(status, indent=2, default=str))
            else:
                click.echo("🔄 Incremental Synchronization Status")
                click.echo("=" * 40)
                click.echo(f"Service: {status['service_name']}")
                click.echo(f"Running: {'✅ Yes' if status['running'] else '❌ No'}")
                click.echo(f"Watch directory: {status['watch_directory']}")
                click.echo()

                stats = status["stats"]
                click.echo("📊 Statistics:")
                click.echo(f"   Files monitored: {stats['files_monitored']:,}")
                click.echo(f"   New files detected: {stats['new_files_detected']:,}")
                click.echo(
                    f"   Modified files detected: {stats['modified_files_detected']:,}"
                )
                click.echo(f"   Lines processed: {stats['lines_processed']:,}")
                click.echo(f"   Tokens synced: {stats['tokens_synced']:,}")
                click.echo(f"   Sync operations: {stats['sync_operations']:,}")

                if stats["last_sync_time"]:
                    click.echo(f"   Last sync: {stats['last_sync_time']}")
                else:
                    click.echo("   Last sync: Never")

                if stats["errors"] > 0:
                    click.echo(f"   Errors: {stats['errors']}")
                else:
                    click.echo("   Errors: None")

                click.echo()
                click.echo("🔧 Capabilities:")
                capabilities = status["capabilities"]
                for capability, available in capabilities.items():
                    status_icon = "✅" if available else "❌"
                    click.echo(
                        f"   {status_icon} {capability.replace('_', ' ').title()}"
                    )

                click.echo()
                click.echo(f"📁 File states tracked: {status['file_states_count']:,}")

        except Exception as e:
            click.echo(f"❌ Failed to get sync status: {str(e)}")
            raise click.Abort()

    asyncio.run(get_sync_status())


@bridge.command("info")
def info_command():
    """
    Display information about the Token Analysis Bridge Service.

    Shows details about what the bridge service does and why it's needed.
    """

    click.echo("🌉 Token Analysis Bridge Service - Information")
    click.echo("=" * 50)
    click.echo()
    click.echo("📝 Purpose:")
    click.echo("   Resolves critical 2.768 billion token data loss issue identified")
    click.echo("   in September 9th analysis. Bridges gap between JSONL token analysis")
    click.echo("   and ClickHouse database that dashboard reads from.")
    click.echo()
    click.echo("🔄 Data Flow:")
    click.echo(
        "   JSONL Files → Enhanced Analysis → Bridge Service → ClickHouse → Dashboard"
    )
    click.echo()
    click.echo("🎯 Key Functions:")
    click.echo("   • Historical backfill of 2.768B tokens from JSONL files")
    click.echo("   • Real-time synchronization of new token usage")
    click.echo("   • Incremental processing to avoid reprocessing all files")
    click.echo("   • Data transformation from analysis results to database records")
    click.echo("   • End-to-end validation of complete data pipeline")
    click.echo()
    click.echo("⚡ Commands:")
    click.echo(
        "   context-cleaner bridge backfill       # Execute historical data transfer"
    )
    click.echo(
        "   context-cleaner bridge sync           # Start incremental synchronization"
    )
    click.echo("   context-cleaner bridge sync-status    # Show sync service status")
    click.echo("   context-cleaner bridge status         # Show bridge service status")
    click.echo("   context-cleaner bridge validate       # Validate data flow")
    click.echo("   context-cleaner bridge info           # Show this information")
    click.echo()
    click.echo("🔄 Sync Modes:")
    click.echo("   • One-time sync: bridge sync --once")
    click.echo("   • Scheduled sync: bridge sync --interval 5")
    click.echo("   • Real-time monitoring: bridge sync --start-monitoring")
    click.echo()
    click.echo("📚 Documentation:")
    click.echo("   See MIGRATION_IMPLEMENTATION_SUMMARY.md for technical details")
    click.echo("   Implements September 9th analysis recommendations")


# Add bridge commands to main CLI
def add_bridge_commands(main_cli):
    """Add bridge commands to main CLI group."""
    main_cli.add_command(bridge)
