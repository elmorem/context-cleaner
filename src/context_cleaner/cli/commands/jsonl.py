"""CLI commands for JSONL content processing and analysis."""

import asyncio
import click
import sys
from pathlib import Path
from typing import Optional
import logging

from ...telemetry import ClickHouseClient
from ...telemetry.jsonl_enhancement.jsonl_processor_service import JsonlProcessorService

logger = logging.getLogger(__name__)


async def get_jsonl_service(privacy_level: str = "standard") -> JsonlProcessorService:
    """Get configured JSONL processor service."""
    client = ClickHouseClient()

    # Check if telemetry system is available
    if not await client.health_check():
        raise click.ClickException(
            "Telemetry system is not available. Initialise it with:\n"
            "  context-cleaner telemetry init"
        )

    return JsonlProcessorService(client, privacy_level)


@click.group()
def jsonl():
    """JSONL content processing and analysis commands."""
    pass


@jsonl.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--batch-size", default=100, help="Batch size for processing entries")
@click.option(
    "--privacy-level",
    default="standard",
    type=click.Choice(["minimal", "standard", "strict"]),
    help="Privacy level for content sanitization",
)
def process_file(file_path: str, batch_size: int, privacy_level: str):
    """Process a single JSONL file and store content in ClickHouse."""

    async def _process():
        try:
            service = await get_jsonl_service(privacy_level)
            file_path_obj = Path(file_path)

            click.echo(f"🔄 Processing JSONL file: {file_path}")
            click.echo(f"📊 Privacy level: {privacy_level}")
            click.echo(f"📦 Batch size: {batch_size}")
            click.echo()

            # Process the file
            stats = await service.process_jsonl_file(file_path_obj, batch_size)

            # Display results
            click.echo("✅ Processing completed!")
            click.echo("=" * 50)
            click.echo(f"Total entries:      {stats['total_entries']:,}")
            click.echo(f"Messages processed: {stats['messages_processed']:,}")
            click.echo(f"Files processed:    {stats['files_processed']:,}")
            click.echo(f"Tools processed:    {stats['tools_processed']:,}")
            click.echo(f"Batches processed:  {stats['batches_processed']:,}")
            click.echo(f"Errors:             {stats['errors']:,}")
            click.echo(f"Processing time:    {stats['processing_time_seconds']:.2f}s")

            if stats["errors"] > 0:
                error_rate = (stats["errors"] / stats["total_entries"]) * 100
                click.echo(f"Error rate:         {error_rate:.2f}%")

            # Show efficiency metrics
            if stats["processing_time_seconds"] > 0:
                entries_per_sec = (
                    stats["total_entries"] / stats["processing_time_seconds"]
                )
                click.echo(f"Processing rate:    {entries_per_sec:.0f} entries/sec")

        except Exception as e:
            click.echo(f"❌ Processing failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_process())


@jsonl.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option("--pattern", default="*.jsonl", help="File pattern to match")
@click.option("--batch-size", default=100, help="Batch size for processing entries")
@click.option(
    "--privacy-level",
    default="standard",
    type=click.Choice(["minimal", "standard", "strict"]),
    help="Privacy level for content sanitization",
)
def process_directory(
    directory_path: str, pattern: str, batch_size: int, privacy_level: str
):
    """Process all JSONL files in a directory."""

    async def _process():
        try:
            service = await get_jsonl_service(privacy_level)
            dir_path_obj = Path(directory_path)

            click.echo(f"🔄 Processing JSONL directory: {directory_path}")
            click.echo(f"🔍 Pattern: {pattern}")
            click.echo(f"📊 Privacy level: {privacy_level}")
            click.echo(f"📦 Batch size: {batch_size}")
            click.echo()

            # Process the directory
            stats = await service.process_jsonl_directory(
                dir_path_obj, pattern, batch_size
            )

            # Display results
            click.echo("✅ Directory processing completed!")
            click.echo("=" * 50)
            click.echo(f"Total files found:  {stats['total_files']:,}")
            click.echo(f"Files processed:    {stats['files_processed']:,}")
            click.echo(f"Total entries:      {stats['total_entries']:,}")
            click.echo(f"Messages processed: {stats['messages_processed']:,}")
            click.echo(f"Files accessed:     {stats['files_processed']:,}")
            click.echo(f"Tools executed:     {stats['tools_processed']:,}")
            click.echo(f"Errors:             {stats['errors']:,}")
            click.echo(f"Processing time:    {stats['processing_time_seconds']:.2f}s")

            if stats["total_files"] > 0:
                success_rate = (stats["files_processed"] / stats["total_files"]) * 100
                click.echo(f"Success rate:       {success_rate:.1f}%")

            if stats["processing_time_seconds"] > 0:
                files_per_min = (
                    stats["files_processed"] / stats["processing_time_seconds"]
                ) * 60
                click.echo(f"Processing rate:    {files_per_min:.1f} files/min")

        except Exception as e:
            click.echo(f"❌ Directory processing failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_process())


@jsonl.command()
@click.argument("search_term")
@click.option("--limit", default=50, help="Maximum number of results")
@click.option(
    "--type",
    "search_type",
    default="messages",
    type=click.Choice(["messages", "files", "tools"]),
    help="Type of content to search",
)
@click.option("--language", help="Programming language filter (for file search)")
def search(search_term: str, limit: int, search_type: str, language: Optional[str]):
    """Search through processed JSONL content."""

    async def _search():
        try:
            service = await get_jsonl_service()

            click.echo(f"🔍 Searching {search_type} for: '{search_term}'")
            if language and search_type == "files":
                click.echo(f"🔤 Language filter: {language}")
            click.echo(f"📊 Limit: {limit} results")
            click.echo()

            # Perform search based on type
            if search_type == "messages":
                results = await service.search_conversation_content(search_term, limit)

                if not results:
                    click.echo("No messages found containing the search term.")
                    return

                click.echo(f"Found {len(results)} message(s):")
                click.echo("=" * 60)

                for result in results:
                    timestamp = result.get("timestamp", "Unknown")
                    session_id = result.get("session_id", "Unknown")[:12]
                    role = result.get("role", "unknown")
                    preview = result.get(
                        "context_snippet", result.get("message_preview", "")
                    )[:200]

                    role_icon = "👤" if role == "user" else "🤖"
                    click.echo(
                        f"{role_icon} {role.upper()} | {timestamp} | Session: {session_id}"
                    )
                    click.echo(f"   {preview}")
                    click.echo()

            elif search_type == "files":
                results = await service.search_file_content(search_term, language)

                if not results:
                    click.echo("No files found containing the search term.")
                    return

                click.echo(f"Found {len(results)} file(s):")
                click.echo("=" * 60)

                for result in results:
                    file_path = result.get("file_path", "Unknown")
                    timestamp = result.get("timestamp", "Unknown")
                    lang = result.get("programming_language", "unknown")
                    file_size = result.get("file_size", 0)
                    snippet = result.get("code_snippet", "")[:300]

                    click.echo(f"📁 {file_path}")
                    click.echo(
                        f"   Language: {lang} | Size: {file_size} bytes | {timestamp}"
                    )
                    if snippet:
                        click.echo(f"   Context: {snippet}")
                    click.echo()

            else:  # tools
                click.echo("Tool search not yet implemented.")
                return

        except Exception as e:
            click.echo(f"❌ Search failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_search())


@jsonl.command()
@click.argument("session_id")
def conversation(session_id: str):
    """Get complete conversation for a session."""

    async def _conversation():
        try:
            service = await get_jsonl_service()

            click.echo(f"💬 Retrieving conversation: {session_id}")
            click.echo()

            messages = await service.get_complete_conversation(session_id)

            if not messages:
                click.echo("No messages found for this session.")
                return

            click.echo(f"Found {len(messages)} message(s) in conversation:")
            click.echo("=" * 70)

            for i, message in enumerate(messages, 1):
                timestamp = message.get("timestamp", "Unknown")
                role = message.get("role", "unknown")
                content_preview = message.get("message_content", "")[:200]
                tokens_in = message.get("input_tokens", 0)
                tokens_out = message.get("output_tokens", 0)
                cost = message.get("cost_usd", 0)

                role_icon = "👤" if role == "user" else "🤖"
                click.echo(f"{i}. {role_icon} {role.upper()} | {timestamp}")

                if tokens_in or tokens_out:
                    click.echo(
                        f"   Tokens: {tokens_in:,} in, {tokens_out:,} out | Cost: ${cost:.4f}"
                    )

                click.echo(f"   {content_preview}...")
                click.echo()

            # Summary statistics
            total_cost = sum(m.get("cost_usd", 0) for m in messages)
            total_input = sum(m.get("input_tokens", 0) for m in messages)
            total_output = sum(m.get("output_tokens", 0) for m in messages)

            click.echo("📊 Conversation Summary:")
            click.echo(f"   Total messages: {len(messages)}")
            click.echo(f"   Total cost: ${total_cost:.4f}")
            click.echo(
                f"   Total tokens: {total_input + total_output:,} ({total_input:,} in, {total_output:,} out)"
            )

        except Exception as e:
            click.echo(f"❌ Failed to retrieve conversation: {e}", err=True)
            sys.exit(1)

    asyncio.run(_conversation())


@jsonl.command()
def status():
    """Check JSONL processing system status."""

    async def _status():
        try:
            service = await get_jsonl_service()

            click.echo("🔍 Checking JSONL processing system status...")
            click.echo()

            status = await service.get_processing_status()

            # System health
            health_icon = "✅" if status["status"] == "healthy" else "❌"
            click.echo(f"{health_icon} System Status: {status['status'].upper()}")
            click.echo(
                f"🔗 Database Connection: {'OK' if status['database_connection'] else 'FAILED'}"
            )
            click.echo(
                f"📊 Content Tables: {'Available' if status['content_tables_available'] else 'Missing'}"
            )
            click.echo(f"🔒 Privacy Level: {status['privacy_level']}")
            click.echo()

            if status["existing_tables"]:
                click.echo("📋 Available Content Tables:")
                for table in status["existing_tables"]:
                    click.echo(f"   • {table}")
                click.echo()

            # Content statistics
            content_stats = status.get("content_stats", {})
            if content_stats:
                click.echo("📈 Content Statistics (Last 30 days):")

                # Messages
                messages = content_stats.get("messages", {})
                if messages:
                    click.echo(f"💬 Messages:")
                    click.echo(f"   Total: {messages.get('total_messages', 0):,}")
                    click.echo(f"   Sessions: {messages.get('unique_sessions', 0):,}")
                    click.echo(
                        f"   Characters: {messages.get('total_characters', 0):,}"
                    )
                    click.echo(
                        f"   With code: {messages.get('messages_with_code', 0):,}"
                    )
                    click.echo(f"   Cost: ${messages.get('total_cost', 0):.2f}")

                # Files
                files = content_stats.get("files", {})
                if files:
                    click.echo(f"📁 Files:")
                    click.echo(f"   Accessed: {files.get('total_file_accesses', 0):,}")
                    click.echo(f"   Unique: {files.get('unique_files', 0):,}")
                    click.echo(f"   Size: {files.get('total_file_bytes', 0):,} bytes")
                    click.echo(
                        f"   With secrets: {files.get('files_with_secrets', 0):,}"
                    )

                # Tools
                tools = content_stats.get("tools", {})
                if tools:
                    click.echo(f"🛠️  Tools:")
                    click.echo(
                        f"   Executions: {tools.get('total_tool_executions', 0):,}"
                    )
                    click.echo(f"   Unique tools: {tools.get('unique_tools', 0):,}")
                    click.echo(f"   Success rate: {tools.get('success_rate', 0):,}%")

            click.echo(f"\n🕒 Last updated: {status['last_updated']}")

        except Exception as e:
            click.echo(f"❌ Status check failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_status())


@jsonl.command()
def stats():
    """Get comprehensive JSONL content statistics."""

    async def _stats():
        try:
            service = await get_jsonl_service()

            click.echo("📊 Retrieving comprehensive content statistics...")
            click.echo()

            stats = await service.get_content_statistics()

            if not stats:
                click.echo("No statistics available. Process some JSONL files first.")
                return

            click.echo("📈 Comprehensive Content Statistics:")
            click.echo("=" * 60)

            # Messages statistics
            messages = stats.get("messages", {})
            if messages:
                click.echo("💬 Message Content:")
                click.echo(f"   Total messages: {messages.get('total_messages', 0):,}")
                click.echo(
                    f"   Unique sessions: {messages.get('unique_sessions', 0):,}"
                )
                click.echo(
                    f"   Total characters: {messages.get('total_characters', 0):,}"
                )
                click.echo(
                    f"   Avg message length: {messages.get('avg_message_length', 0):.0f} chars"
                )
                click.echo(
                    f"   Input tokens: {messages.get('total_input_tokens', 0):,}"
                )
                click.echo(
                    f"   Output tokens: {messages.get('total_output_tokens', 0):,}"
                )
                click.echo(f"   Total cost: ${messages.get('total_cost', 0):.2f}")
                click.echo(
                    f"   Messages with code: {messages.get('messages_with_code', 0):,}"
                )
                if messages.get("top_languages"):
                    click.echo(f"   Top languages: {messages.get('top_languages')}")
                click.echo()

            # Files statistics
            files = stats.get("files", {})
            if files:
                click.echo("📁 File Content:")
                click.echo(f"   File accesses: {files.get('total_file_accesses', 0):,}")
                click.echo(f"   Unique files: {files.get('unique_files', 0):,}")
                click.echo(f"   Total bytes: {files.get('total_file_bytes', 0):,}")
                click.echo(
                    f"   Avg file size: {files.get('avg_file_size', 0):.0f} bytes"
                )
                click.echo(f"   Avg line count: {files.get('avg_line_count', 0):.0f}")
                click.echo(
                    f"   Files with secrets: {files.get('files_with_secrets', 0):,}"
                )
                click.echo(
                    f"   Files with imports: {files.get('files_with_imports', 0):,}"
                )
                if files.get("top_file_languages"):
                    click.echo(f"   Top languages: {files.get('top_file_languages')}")
                click.echo()

            # Tools statistics
            tools = stats.get("tools", {})
            if tools:
                click.echo("🛠️  Tool Execution:")
                click.echo(
                    f"   Total executions: {tools.get('total_tool_executions', 0):,}"
                )
                click.echo(f"   Unique tools: {tools.get('unique_tools', 0):,}")
                click.echo(f"   Successful: {tools.get('successful_executions', 0):,}")
                click.echo(
                    f"   Success rate: {tools.get('overall_success_rate', 0):.1f}%"
                )
                click.echo(f"   Output bytes: {tools.get('total_output_bytes', 0):,}")
                if tools.get("most_used_tools"):
                    click.echo(f"   Most used tools: {tools.get('most_used_tools')}")

        except Exception as e:
            click.echo(f"❌ Statistics failed: {e}", err=True)
            sys.exit(1)

    asyncio.run(_stats())


# Add to main CLI integration
def add_jsonl_commands(main_cli):
    """Add JSONL commands to the main CLI."""
    main_cli.add_command(jsonl)
