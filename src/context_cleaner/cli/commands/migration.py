"""
Migration CLI Commands

Provides comprehensive command-line interface for migration operations including:
- Discovery: discover-jsonl --path /data --output manifest.json
- Migration: migrate-historical --manifest manifest.json --batch-size 2000
- Status: migration-status --show-progress --show-errors
- Resume: resume-migration --checkpoint checkpoint.json
- Validation: validate-migration --verify-counts --check-integrity

Designed for both development and production migration scenarios.
"""

import asyncio
import json
import logging
import click
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ...migration.jsonl_discovery import JSONLDiscoveryService
from ...migration.migration_engine import MigrationEngine
from ...migration.progress_tracker import ProgressTracker
from ...migration.validation import MigrationValidator
from ...services.token_analysis_bridge import TokenAnalysisBridge

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging for CLI commands."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def migration(ctx, verbose):
    """Migration commands for Enhanced Token Analysis historical data."""
    setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@migration.command()
@click.option(
    "--path",
    "-p",
    multiple=True,
    help="Search paths for JSONL files (can specify multiple)",
)
@click.option(
    "--pattern", default="*.jsonl", help="File pattern to match (default: *.jsonl)"
)
@click.option("--output", "-o", help="Output manifest file path")
@click.option("--max-files", type=int, help="Maximum number of files to discover")
@click.option("--max-age-days", type=int, help="Maximum file age in days")
@click.option("--min-size-mb", type=float, help="Minimum file size in MB")
@click.option("--max-size-mb", type=float, help="Maximum file size in MB")
@click.option(
    "--sort-by",
    type=click.Choice(["modified_desc", "size_desc", "size_asc", "priority_asc"]),
    default="priority_asc",
    help="Sort order for processing",
)
@click.option(
    "--check-integrity", is_flag=True, help="Check file integrity during discovery"
)
@click.option(
    "--analyze-content", is_flag=True, help="Analyze file content for estimates"
)
@click.pass_context
def discover_jsonl(
    ctx,
    path,
    pattern,
    output,
    max_files,
    max_age_days,
    min_size_mb,
    max_size_mb,
    sort_by,
    check_integrity,
    analyze_content,
):
    """Discover and catalog JSONL files for migration."""

    async def run_discovery():
        # Prepare search paths
        search_paths = list(path) if path else None

        # Prepare filter criteria
        filter_criteria = {}
        if max_age_days is not None:
            filter_criteria["max_age_days"] = max_age_days
        if min_size_mb is not None:
            filter_criteria["min_size_mb"] = min_size_mb
        if max_size_mb is not None:
            filter_criteria["max_size_mb"] = max_size_mb

        # Initialize discovery service
        discovery_service = JSONLDiscoveryService(
            default_search_paths=search_paths,
            file_patterns=[pattern],
            max_file_age_days=max_age_days,
            enable_integrity_check=check_integrity,
            enable_content_analysis=analyze_content,
        )

        click.echo("🔍 Starting JSONL file discovery...")

        try:
            # Perform discovery
            result = await discovery_service.discover_files(
                search_paths=search_paths,
                filter_criteria=filter_criteria if filter_criteria else None,
                max_files=max_files,
                sort_by=sort_by,
            )

            # Display results
            click.echo(f"\n✅ Discovery completed successfully!")
            click.echo(f"   📁 Files found: {result.total_files_found}")
            click.echo(f"   📏 Total size: {result.total_size_mb:.1f} MB")
            click.echo(f"   📊 Estimated records: {result.estimated_total_lines:,}")
            click.echo(f"   🎯 Estimated tokens: {result.estimated_total_tokens:,}")

            if result.recent_files:
                click.echo(f"   🆕 Recent files (≤7 days): {len(result.recent_files)}")
            if result.large_files:
                click.echo(f"   📦 Large files (>100MB): {len(result.large_files)}")
            if result.corrupt_files:
                click.echo(f"   ⚠️  Corrupt files: {len(result.corrupt_files)}")

            # Show errors and warnings
            if result.errors:
                click.echo(f"\n❌ Errors encountered:")
                for error in result.errors[:5]:  # Show first 5 errors
                    click.echo(f"   • {error}")
                if len(result.errors) > 5:
                    click.echo(f"   ... and {len(result.errors) - 5} more errors")

            if result.warnings:
                click.echo(f"\n⚠️  Warnings:")
                for warning in result.warnings[:3]:  # Show first 3 warnings
                    click.echo(f"   • {warning}")
                if len(result.warnings) > 3:
                    click.echo(f"   ... and {len(result.warnings) - 3} more warnings")

            # Save manifest if requested
            if output:
                output_path = Path(output).expanduser().resolve()
                success = await discovery_service.save_manifest(
                    result, str(output_path)
                )
                if success:
                    click.echo(f"\n💾 Manifest saved to: {output_path}")
                else:
                    click.echo(f"\n❌ Failed to save manifest to: {output_path}")
                    return 1

            # Show top priority files for preview
            if result.processing_manifest:
                click.echo(f"\n📋 Processing order preview (top 5 files):")
                for i, file_info in enumerate(result.processing_manifest[:5]):
                    priority_icon = "🔥" if file_info.processing_priority == 0 else "📄"
                    click.echo(
                        f"   {i+1}. {priority_icon} {file_info.filename} "
                        f"({file_info.size_mb:.1f}MB, ~{file_info.estimated_tokens:,} tokens)"
                    )

            return 0

        except Exception as e:
            click.echo(f"\n❌ Discovery failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    # Run async discovery
    return asyncio.run(run_discovery())


@migration.command()
@click.option("--manifest", "-m", help="Discovery manifest file to use")
@click.option(
    "--path", "-p", multiple=True, help="Search paths if no manifest provided"
)
@click.option(
    "--batch-size", "-b", default=1000, type=int, help="Batch size for processing"
)
@click.option(
    "--max-concurrent",
    "-c",
    default=3,
    type=int,
    help="Maximum concurrent file processing",
)
@click.option(
    "--max-memory-mb", default=1500, type=int, help="Maximum memory usage in MB"
)
@click.option(
    "--checkpoint-interval", default=10, type=int, help="Files between checkpoints"
)
@click.option(
    "--dry-run", is_flag=True, help="Validate without actually migrating data"
)
@click.option("--resume-from", help="Checkpoint ID to resume from")
@click.option("--force", is_flag=True, help="Force migration even if validation fails")
@click.pass_context
def migrate_historical(
    ctx,
    manifest,
    path,
    batch_size,
    max_concurrent,
    max_memory_mb,
    checkpoint_interval,
    dry_run,
    resume_from,
    force,
):
    """Migrate historical JSONL data to ClickHouse database."""

    async def run_migration():
        # Initialize services
        bridge_service = TokenAnalysisBridge()
        progress_tracker = ProgressTracker()

        migration_engine = MigrationEngine(
            bridge_service=bridge_service,
            progress_tracker=progress_tracker,
            batch_size=batch_size,
            max_concurrent_files=max_concurrent,
            max_memory_mb=max_memory_mb,
            checkpoint_interval_files=checkpoint_interval,
        )

        # Prepare source directories
        source_directories = list(path) if path else None

        # Load manifest if provided
        if manifest:
            manifest_path = Path(manifest).expanduser().resolve()
            if not manifest_path.exists():
                click.echo(f"❌ Manifest file not found: {manifest_path}")
                return 1
            click.echo(f"📋 Using manifest: {manifest_path}")

        # Setup progress callback
        def progress_callback(progress):
            if progress.current_phase == "processing":
                files_pct = progress.files_progress_percentage
                records_pct = progress.records_progress_percentage
                eta_text = ""
                if progress.eta_seconds:
                    eta_minutes = progress.eta_seconds / 60
                    eta_text = f", ETA: {eta_minutes:.1f}m"

                click.echo(
                    f"\r🔄 Progress: {files_pct:.1f}% files, {records_pct:.1f}% records"
                    f", {progress.current_processing_rate_records_per_second:.0f} rec/s{eta_text}",
                    nl=False,
                )

        click.echo("🚀 Starting historical data migration...")
        if dry_run:
            click.echo("⚠️  DRY RUN MODE - No data will actually be migrated")

        try:
            # Run migration
            result = await migration_engine.migrate_all_historical_data(
                source_directories=source_directories,
                dry_run=dry_run,
                resume_from_checkpoint=resume_from,
                progress_callback=progress_callback,
            )

            click.echo("\n")  # New line after progress updates

            # Display results
            if result.success:
                click.echo("✅ Migration completed successfully!")
            else:
                click.echo("❌ Migration completed with errors")

            click.echo(f"\n📊 Migration Summary:")
            click.echo(
                f"   📁 Files processed: {result.total_files_processed}/{result.total_files_discovered}"
            )
            click.echo(f"   ✅ Files succeeded: {result.files_succeeded}")
            click.echo(f"   ❌ Files failed: {result.files_failed}")
            click.echo(f"   ⏭️  Files skipped: {result.files_skipped}")
            click.echo(f"   📝 Sessions created: {result.total_sessions_created:,}")
            click.echo(f"   📊 Records inserted: {result.total_records_inserted:,}")
            click.echo(f"   🎯 Tokens migrated: {result.total_tokens_migrated:,}")

            click.echo(f"\n⚡ Performance Metrics:")
            click.echo(f"   ⏱️  Duration: {result.processing_duration_seconds:.1f}s")
            click.echo(
                f"   📄 Files/min: {result.average_processing_rate_files_per_minute:.1f}"
            )
            click.echo(
                f"   🎯 Tokens/sec: {result.average_processing_rate_tokens_per_second:.0f}"
            )
            click.echo(f"   💾 Peak memory: {result.peak_memory_usage_mb:.1f}MB")

            if result.checkpoints_created:
                click.echo(f"\n🔄 Checkpoints: {result.checkpoints_created} created")
                if result.final_checkpoint_id:
                    click.echo(f"   📍 Final checkpoint: {result.final_checkpoint_id}")

            # Show errors and warnings
            if result.errors:
                click.echo(f"\n❌ Errors ({len(result.errors)}):")
                for error in result.errors[:3]:
                    click.echo(f"   • {error}")
                if len(result.errors) > 3:
                    click.echo(f"   ... and {len(result.errors) - 3} more errors")

            if result.warnings:
                click.echo(f"\n⚠️  Warnings ({len(result.warnings)}):")
                for warning in result.warnings[:3]:
                    click.echo(f"   • {warning}")
                if len(result.warnings) > 3:
                    click.echo(f"   ... and {len(result.warnings) - 3} more warnings")

            return 0 if result.success or force else 1

        except Exception as e:
            click.echo(f"\n❌ Migration failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    # Run async migration
    return asyncio.run(run_migration())


@migration.command()
@click.option("--migration-id", "-m", help="Specific migration ID to check")
@click.option(
    "--show-progress", is_flag=True, help="Show detailed progress information"
)
@click.option("--show-errors", is_flag=True, help="Show recent errors and warnings")
@click.option("--show-performance", is_flag=True, help="Show performance metrics")
@click.option("--watch", "-w", is_flag=True, help="Watch progress in real-time")
@click.option(
    "--refresh-interval",
    default=5,
    type=int,
    help="Refresh interval for watch mode (seconds)",
)
@click.pass_context
def migration_status(
    ctx,
    migration_id,
    show_progress,
    show_errors,
    show_performance,
    watch,
    refresh_interval,
):
    """Show migration status and progress."""

    async def show_status():
        # Initialize services
        migration_engine = MigrationEngine()
        progress_tracker = ProgressTracker()

        try:
            if migration_id:
                # Show specific migration status
                status = await migration_engine.get_migration_status(migration_id)
                if not status:
                    click.echo(f"❌ Migration {migration_id} not found")
                    return 1

                migration_result = status.get("migration_result")
                current_progress = status.get("current_progress")

                click.echo(f"📊 Migration Status: {migration_id}")
                click.echo(f"   Type: {migration_result['migration_type']}")
                click.echo(
                    f"   Status: {'✅ Success' if migration_result['success'] else '❌ Failed'}"
                )
                click.echo(
                    f"   Progress: {migration_result['completion_percentage']:.1f}%"
                )

                if current_progress and show_progress:
                    click.echo(f"\n🔄 Current Progress:")
                    click.echo(f"   Phase: {current_progress['current_phase']}")
                    click.echo(
                        f"   Files: {current_progress['files_completed']}/{current_progress['files_total']}"
                    )
                    click.echo(
                        f"   Records: {current_progress['records_processed']:,}/{current_progress['records_total']:,}"
                    )
                    click.echo(
                        f"   Tokens: {current_progress['tokens_processed']:,}/{current_progress['tokens_total']:,}"
                    )

            else:
                # Show general migration system status
                current_progress = progress_tracker.get_current_progress()

                if current_progress:
                    click.echo(f"🔄 Active Migration: {current_progress.migration_id}")
                    click.echo(f"   Type: {current_progress.migration_type}")
                    click.echo(f"   Phase: {current_progress.current_phase}")
                    click.echo(
                        f"   Overall Progress: {current_progress.overall_progress_percentage:.1f}%"
                    )

                    if show_progress:
                        click.echo(f"\n📊 Detailed Progress:")
                        click.echo(
                            f"   Files: {current_progress.files_completed}/{current_progress.files_total} "
                            f"({current_progress.files_progress_percentage:.1f}%)"
                        )
                        click.echo(
                            f"   Records: {current_progress.records_processed:,}/{current_progress.records_total:,} "
                            f"({current_progress.records_progress_percentage:.1f}%)"
                        )
                        click.echo(
                            f"   Tokens: {current_progress.tokens_processed:,}/{current_progress.tokens_total:,} "
                            f"({current_progress.tokens_progress_percentage:.1f}%)"
                        )

                    if show_performance:
                        click.echo(f"\n⚡ Performance:")
                        click.echo(
                            f"   Records/sec: {current_progress.current_processing_rate_records_per_second:.0f}"
                        )
                        click.echo(
                            f"   Tokens/sec: {current_progress.current_processing_rate_tokens_per_second:.0f}"
                        )
                        click.echo(
                            f"   Elapsed: {current_progress.elapsed_time_seconds:.0f}s"
                        )
                        if current_progress.eta_seconds:
                            click.echo(
                                f"   ETA: {current_progress.eta_seconds/60:.1f}m"
                            )

                    if show_errors:
                        click.echo(f"\n🚨 Issues:")
                        click.echo(f"   Errors: {current_progress.errors_count}")
                        click.echo(f"   Warnings: {current_progress.warnings_count}")
                        if current_progress.last_error:
                            click.echo(f"   Last error: {current_progress.last_error}")
                else:
                    click.echo("ℹ️  No active migration")

                # Show available checkpoints
                checkpoints = await migration_engine.list_available_checkpoints()
                if checkpoints:
                    click.echo(f"\n🔄 Available Checkpoints ({len(checkpoints)}):")
                    for checkpoint in checkpoints[:3]:
                        click.echo(
                            f"   • {checkpoint['checkpoint_id']} "
                            f"({checkpoint['timestamp']})"
                        )

            return 0

        except Exception as e:
            click.echo(f"❌ Status check failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    # Handle watch mode
    if watch:

        async def watch_status():
            import time

            try:
                while True:
                    click.clear()
                    click.echo(
                        f"🔍 Migration Status (refreshing every {refresh_interval}s)"
                    )
                    click.echo("=" * 60)
                    await show_status()
                    click.echo(
                        f"\n⏰ Last updated: {datetime.now().strftime('%H:%M:%S')}"
                    )
                    click.echo("Press Ctrl+C to exit")
                    await asyncio.sleep(refresh_interval)
            except KeyboardInterrupt:
                click.echo("\n👋 Exiting status watch")
                return 0

        return asyncio.run(watch_status())
    else:
        return asyncio.run(show_status())


@migration.command()
@click.option("--checkpoint", "-c", required=True, help="Checkpoint ID to resume from")
@click.option(
    "--batch-size", "-b", default=1000, type=int, help="Batch size for processing"
)
@click.option(
    "--max-concurrent", default=3, type=int, help="Maximum concurrent file processing"
)
@click.option("--force", is_flag=True, help="Force resume even with warnings")
@click.pass_context
def resume_migration(ctx, checkpoint, batch_size, max_concurrent, force):
    """Resume migration from a checkpoint."""

    async def run_resume():
        try:
            # Initialize services
            migration_engine = MigrationEngine(
                batch_size=batch_size,
                max_concurrent_files=max_concurrent,
            )

            click.echo(f"🔄 Resuming migration from checkpoint: {checkpoint}")

            # Resume migration
            result = await migration_engine.migrate_all_historical_data(
                resume_from_checkpoint=checkpoint
            )

            # Display results (similar to migrate_historical)
            if result.success:
                click.echo("✅ Resumed migration completed successfully!")
            else:
                click.echo("❌ Resumed migration completed with errors")

            click.echo(f"\n📊 Results:")
            click.echo(f"   📁 Files processed: {result.total_files_processed}")
            click.echo(f"   🎯 Tokens migrated: {result.total_tokens_migrated:,}")
            click.echo(f"   ⏱️  Duration: {result.processing_duration_seconds:.1f}s")

            return 0 if result.success or force else 1

        except Exception as e:
            click.echo(f"❌ Resume failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    return asyncio.run(run_resume())


@migration.command()
@click.option("--verify-counts", is_flag=True, help="Verify token and record counts")
@click.option("--check-integrity", is_flag=True, help="Check data integrity")
@click.option("--sample-size", default=100, type=int, help="Sample size for validation")
@click.option(
    "--tolerance", default=0.001, type=float, help="Tolerance for count verification"
)
@click.option("--output", "-o", help="Output validation report file")
@click.pass_context
def validate_migration(
    ctx, verify_counts, check_integrity, sample_size, tolerance, output
):
    """Validate migration data integrity and consistency."""

    async def run_validation():
        try:
            # Initialize validation service
            validator = MigrationValidator()

            click.echo("🔍 Starting migration validation...")

            # Run validation
            result = await validator.validate_migration_integrity(
                sample_size=sample_size,
                full_validation=check_integrity,
                tolerance=tolerance,
                verify_counts=verify_counts,
            )

            # Display results
            if result.validation_passed:
                click.echo("✅ Migration validation passed!")
            else:
                click.echo("❌ Migration validation failed")

            click.echo(f"\n📊 Validation Results:")
            click.echo(f"   🎯 Accuracy score: {result.accuracy_score:.2f}%")
            click.echo(f"   📊 Records checked: {result.records_validated:,}")
            click.echo(f"   ⚠️  Issues found: {len(result.issues)}")

            if result.token_count_variance is not None:
                click.echo(f"   🔢 Token variance: {result.token_count_variance:.3f}%")

            # Show issues
            if result.issues:
                click.echo(f"\n🚨 Validation Issues:")
                for issue in result.issues[:5]:
                    click.echo(f"   • {issue}")
                if len(result.issues) > 5:
                    click.echo(f"   ... and {len(result.issues) - 5} more issues")

            # Save report if requested
            if output:
                output_path = Path(output).expanduser().resolve()
                with open(output_path, "w") as f:
                    json.dump(result.to_dict(), f, indent=2, default=str)
                click.echo(f"\n💾 Validation report saved to: {output_path}")

            return 0 if result.validation_passed else 1

        except Exception as e:
            click.echo(f"❌ Validation failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    return asyncio.run(run_validation())


@migration.command()
@click.option("--list-checkpoints", is_flag=True, help="List available checkpoints")
@click.option("--cleanup-old", is_flag=True, help="Clean up old checkpoints and data")
@click.option(
    "--max-age-days", default=30, type=int, help="Maximum age for cleanup (days)"
)
@click.pass_context
def manage(ctx, list_checkpoints, cleanup_old, max_age_days):
    """Manage migration data and checkpoints."""

    async def run_management():
        try:
            migration_engine = MigrationEngine()

            if list_checkpoints:
                click.echo("🔄 Available Checkpoints:")
                checkpoints = await migration_engine.list_available_checkpoints()

                if not checkpoints:
                    click.echo("   No checkpoints found")
                else:
                    for checkpoint in checkpoints:
                        age_days = (
                            datetime.now()
                            - datetime.fromisoformat(checkpoint["timestamp"])
                        ).days
                        click.echo(
                            f"   • {checkpoint['checkpoint_id']} "
                            f"({checkpoint['timestamp']}, {age_days}d old)"
                        )

            if cleanup_old:
                click.echo(f"🧹 Cleaning up data older than {max_age_days} days...")
                result = await migration_engine.cleanup_old_data(max_age_days)
                click.echo(f"   Cleaned {result['checkpoints_cleaned']} checkpoints")

            return 0

        except Exception as e:
            click.echo(f"❌ Management operation failed: {str(e)}")
            if ctx.obj.get("verbose"):
                import traceback

                click.echo(traceback.format_exc())
            return 1

    return asyncio.run(run_management())


if __name__ == "__main__":
    migration()
