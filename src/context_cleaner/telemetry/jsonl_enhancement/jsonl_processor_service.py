"""JSONL Processing Service - Integrates with existing telemetry system."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient
from .full_content_processor import FullContentBatchProcessor
from .full_content_queries import FullContentQueries

logger = logging.getLogger(__name__)


class JsonlProcessorService:
    """Service for processing JSONL files and integrating with telemetry system."""

    def __init__(
        self, clickhouse_client: ClickHouseClient, privacy_level: str = "standard"
    ):
        self.clickhouse = clickhouse_client
        self.privacy_level = privacy_level
        self.processor = FullContentBatchProcessor(clickhouse_client, privacy_level)
        self.queries = FullContentQueries(clickhouse_client)

    async def process_jsonl_file(
        self, file_path: Path, batch_size: int = 100
    ) -> Dict[str, Any]:
        """Process a single JSONL file and store content in ClickHouse."""
        if not file_path.exists():
            raise FileNotFoundError(f"JSONL file not found: {file_path}")

        logger.info(f"Processing JSONL file: {file_path}")

        total_stats = {
            "file_path": str(file_path),
            "total_entries": 0,
            "messages_processed": 0,
            "files_processed": 0,
            "tools_processed": 0,
            "errors": 0,
            "batches_processed": 0,
            "processing_time_seconds": 0,
        }

        start_time = datetime.now()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                batch = []

                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line.strip())
                        batch.append(entry)
                        total_stats["total_entries"] += 1

                        # Process batch when it reaches batch_size
                        if len(batch) >= batch_size:
                            batch_stats = await self.processor.process_jsonl_entries(
                                batch
                            )
                            self._aggregate_stats(total_stats, batch_stats)
                            total_stats["batches_processed"] += 1

                            logger.info(
                                f"Processed batch {total_stats['batches_processed']}: "
                                f"{len(batch)} entries (line {line_num})"
                            )
                            batch = []

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON on line {line_num}: {e}")
                        total_stats["errors"] += 1
                    except Exception as e:
                        logger.error(f"Error processing line {line_num}: {e}")
                        total_stats["errors"] += 1

                # Process remaining batch
                if batch:
                    batch_stats = await self.processor.process_jsonl_entries(batch)
                    self._aggregate_stats(total_stats, batch_stats)
                    total_stats["batches_processed"] += 1

                    logger.info(f"Processed final batch: {len(batch)} entries")

        except Exception as e:
            logger.error(f"Error processing JSONL file {file_path}: {e}")
            total_stats["errors"] += 1
            raise

        end_time = datetime.now()
        total_stats["processing_time_seconds"] = (end_time - start_time).total_seconds()

        logger.info(f"Completed processing {file_path}: {total_stats}")
        return total_stats

    async def process_jsonl_directory(
        self, directory_path: Path, pattern: str = "*.jsonl", batch_size: int = 100
    ) -> Dict[str, Any]:
        """Process all JSONL files in a directory."""
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        jsonl_files = list(directory_path.glob(pattern))
        if not jsonl_files:
            logger.warning(
                f"No JSONL files found in {directory_path} with pattern {pattern}"
            )
            return {"total_files": 0, "files_processed": 0}

        logger.info(f"Found {len(jsonl_files)} JSONL files to process")

        directory_stats = {
            "directory_path": str(directory_path),
            "pattern": pattern,
            "total_files": len(jsonl_files),
            "files_processed": 0,
            "total_entries": 0,
            "messages_processed": 0,
            "files_processed": 0,
            "tools_processed": 0,
            "errors": 0,
            "processing_time_seconds": 0,
        }

        start_time = datetime.now()

        for jsonl_file in jsonl_files:
            try:
                file_stats = await self.process_jsonl_file(jsonl_file, batch_size)
                self._aggregate_stats(directory_stats, file_stats)
                directory_stats["files_processed"] += 1

                logger.info(
                    f"Completed file {jsonl_file.name}: "
                    f"{file_stats['total_entries']} entries processed"
                )

            except Exception as e:
                logger.error(f"Failed to process file {jsonl_file}: {e}")
                directory_stats["errors"] += 1

        end_time = datetime.now()
        directory_stats["processing_time_seconds"] = (
            end_time - start_time
        ).total_seconds()

        logger.info(f"Directory processing completed: {directory_stats}")
        return directory_stats

    async def search_conversation_content(
        self, search_term: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search through conversation content."""
        return await self.queries.search_conversation_content(search_term, limit)

    async def search_file_content(
        self, search_term: str, language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search through file content."""
        return await self.queries.search_file_content(search_term, language)

    async def get_complete_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """Get complete conversation for a session."""
        return await self.queries.get_complete_conversation(session_id)

    async def get_content_statistics(self) -> Dict[str, Any]:
        """Get comprehensive content statistics."""
        return await self.queries.get_content_statistics()

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get current status of JSONL content processing."""
        try:
            # Get basic content statistics
            stats = await self.clickhouse.get_jsonl_content_stats()

            # Add health check
            is_healthy = await self.clickhouse.health_check()

            # Check if content tables exist
            table_check_query = """
            SELECT name 
            FROM system.tables 
            WHERE database = 'otel' 
            AND name IN ('claude_message_content', 'claude_file_content', 'claude_tool_results')
            ORDER BY name
            """

            tables = await self.clickhouse.execute_query(table_check_query)
            existing_tables = [t["name"] for t in tables]

            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "database_connection": is_healthy,
                "content_tables_available": len(existing_tables) == 3,
                "existing_tables": existing_tables,
                "privacy_level": self.privacy_level,
                "content_stats": stats,
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_updated": datetime.now().isoformat(),
            }

    def _aggregate_stats(
        self, total_stats: Dict[str, Any], batch_stats: Dict[str, Any]
    ):
        """Aggregate batch statistics into total statistics."""
        total_stats["messages_processed"] += batch_stats.get("messages_processed", 0)
        total_stats["files_processed"] += batch_stats.get("files_processed", 0)
        total_stats["tools_processed"] += batch_stats.get("tools_processed", 0)
        total_stats["errors"] += batch_stats.get("errors", 0)
