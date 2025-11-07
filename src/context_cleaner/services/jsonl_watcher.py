#!/usr/bin/env python3
"""
JSONL File Watcher Service

Monitors ~/.claude/projects for new JSONL files and automatically processes them
into the ClickHouse database for real-time dashboard updates.
"""

import asyncio
import os
import time
import logging
import threading
import queue
from pathlib import Path
from typing import Set, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from context_cleaner.telemetry.jsonl_enhancement.jsonl_processor_service import (
    JsonlProcessorService,
)
from context_cleaner.telemetry.clients.clickhouse_client import ClickHouseClient

logger = logging.getLogger(__name__)


class JSONLFileHandler(FileSystemEventHandler):
    """Handles JSONL file system events."""

    def __init__(self, processor: JsonlProcessorService):
        self.processor = processor
        self.processed_files: Set[str] = set()
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self.thread_safe_queue: queue.Queue = queue.Queue()
        self.event_loop = None

    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            logger.info(f"New JSONL file detected: {event.src_path}")
            self._queue_file_thread_safe(event.src_path)

    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".jsonl"):
            # Only process if file hasn't been processed recently
            if event.src_path not in self.processed_files:
                logger.info(f"Modified JSONL file detected: {event.src_path}")
                self._queue_file_thread_safe(event.src_path)

    def _queue_file_thread_safe(self, file_path: str):
        """Thread-safe method to queue file for processing."""
        try:
            self.thread_safe_queue.put_nowait(file_path)
            # Use call_soon_threadsafe if event loop is available
            if self.event_loop and not self.event_loop.is_closed():
                self.event_loop.call_soon_threadsafe(self._notify_async_queue)
        except Exception as e:
            logger.error(f"Error queuing file {file_path}: {e}")

    def _notify_async_queue(self):
        """Notify the async queue that new items are available."""
        try:
            while not self.thread_safe_queue.empty():
                file_path = self.thread_safe_queue.get_nowait()
                # Use asyncio.create_task safely from the correct event loop context
                asyncio.create_task(self._queue_file_for_processing(file_path))
        except Exception as e:
            logger.error(f"Error in async queue notification: {e}")

    async def _queue_file_for_processing(self, file_path: str):
        """Queue a file for processing."""
        await self.processing_queue.put(file_path)

    async def process_queue(self):
        """Process queued files."""
        while True:
            try:
                file_path = await asyncio.wait_for(
                    self.processing_queue.get(), timeout=5.0
                )
                await self._process_file(file_path)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in processing queue: {e}")
                await asyncio.sleep(5)

    async def _process_file(self, file_path: str):
        """Process a single JSONL file."""
        try:
            # Wait a moment to ensure file is fully written
            await asyncio.sleep(2)

            # Check file size to avoid processing incomplete files
            file_size = os.path.getsize(file_path)
            if file_size < 100:  # Skip very small files
                return

            logger.info(f"Processing JSONL file: {file_path} ({file_size/1024:.1f}KB)")

            # Process the file
            from pathlib import Path

            result = await self.processor.process_jsonl_file(
                Path(file_path), batch_size=100
            )

            # Result contains stats directly (no success wrapper)
            self.processed_files.add(file_path)
            logger.info(f"Successfully processed {file_path}: {result}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")


class JSONLWatcherService:
    """Service to watch and process JSONL files automatically."""

    def __init__(self, claude_projects_dir: str = None):
        self.claude_projects_dir = claude_projects_dir or os.path.expanduser(
            "~/.claude/projects"
        )
        self.clickhouse_client = ClickHouseClient()
        self.processor = JsonlProcessorService(self.clickhouse_client)
        self.observer = Observer()
        self.handler = JSONLFileHandler(self.processor)
        self.running = False
        self.file_sizes: Dict[str, int] = (
            {}
        )  # Track file sizes for incremental processing

    async def start(self):
        """Start the JSONL watcher service."""
        logger.info(
            f"Starting JSONL watcher service for directory: {self.claude_projects_dir}"
        )

        if not os.path.exists(self.claude_projects_dir):
            logger.warning(
                f"Claude projects directory not found: {self.claude_projects_dir}"
            )
            return

        # Set event loop reference for thread-safe operations
        self.handler.event_loop = asyncio.get_running_loop()

        # Process any existing unprocessed files
        await self._process_existing_files()

        # Set up file system watcher
        self.observer.schedule(self.handler, self.claude_projects_dir, recursive=True)
        self.observer.start()

        # Start processing queue and periodic monitoring
        processing_task = asyncio.create_task(self.handler.process_queue())
        monitoring_task = asyncio.create_task(self._periodic_monitoring())

        self.running = True
        logger.info("JSONL watcher service started successfully")

        try:
            while self.running:
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            logger.info("Shutting down JSONL watcher service...")
        finally:
            await self.stop()
            processing_task.cancel()
            monitoring_task.cancel()

    async def stop(self):
        """Stop the JSONL watcher service."""
        self.running = False
        self.observer.stop()
        self.observer.join()
        logger.info("JSONL watcher service stopped")

    async def _periodic_monitoring(self):
        """Periodically check for file size changes to detect ongoing writes."""
        logger.info("Starting periodic file monitoring (every 30 seconds)")

        while self.running:
            try:
                await self._check_file_changes()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in periodic monitoring: {e}")
                await asyncio.sleep(30)

    async def _check_file_changes(self):
        """Check all JSONL files for size changes since last check."""
        try:
            for project_dir in os.listdir(self.claude_projects_dir):
                project_path = os.path.join(self.claude_projects_dir, project_dir)
                if not os.path.isdir(project_path):
                    continue

                for file_name in os.listdir(project_path):
                    if not file_name.endswith(".jsonl"):
                        continue

                    file_path = os.path.join(project_path, file_name)
                    current_size = os.path.getsize(file_path)
                    last_size = self.file_sizes.get(file_path, 0)

                    # If file has grown, it's been updated
                    if current_size > last_size:
                        # Only process if the file has grown significantly (>1KB)
                        if current_size - last_size > 1024:
                            logger.info(
                                f"File size change detected: {file_path} ({current_size-last_size} bytes added)"
                            )
                            await self.handler._queue_file_for_processing(file_path)

                        self.file_sizes[file_path] = current_size
                    elif file_path not in self.file_sizes:
                        # First time seeing this file
                        self.file_sizes[file_path] = current_size

        except Exception as e:
            logger.error(f"Error checking file changes: {e}")

    async def _process_existing_files(self):
        """Process any existing JSONL files that haven't been processed."""
        logger.info("Checking for existing unprocessed JSONL files...")

        try:
            client = self.clickhouse_client

            # Get sessions already in database
            db_sessions = await client.execute_query(
                """
                SELECT DISTINCT session_id FROM otel.claude_message_content
            """
            )
            processed_sessions = {row["session_id"] for row in db_sessions}

            # Find unprocessed files
            unprocessed_count = 0
            for project_dir in os.listdir(self.claude_projects_dir):
                project_path = os.path.join(self.claude_projects_dir, project_dir)
                if not os.path.isdir(project_path):
                    continue

                for file_name in os.listdir(project_path):
                    if not file_name.endswith(".jsonl"):
                        continue

                    session_id = file_name.replace(".jsonl", "")
                    file_path = os.path.join(project_path, file_name)

                    # Check if file is recent and not processed
                    if session_id not in processed_sessions and os.path.getmtime(
                        file_path
                    ) > time.time() - (
                        7 * 24 * 3600
                    ):  # Last 7 days

                        logger.info(f"Queuing unprocessed file: {file_path}")
                        await self.handler._queue_file_for_processing(file_path)
                        unprocessed_count += 1

            logger.info(f"Found {unprocessed_count} unprocessed JSONL files")

        except Exception as e:
            logger.error(f"Error checking existing files: {e}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Start the service
    service = JSONLWatcherService()
    asyncio.run(service.start())
