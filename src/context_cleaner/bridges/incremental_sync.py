"""
Incremental Synchronization Service - Continuation of September 9th Analysis Plan

This service implements the automated JSONL-to-database synchronization identified
in the September 9th analysis as a critical need for ongoing data flow.

Key Requirements from Sept 9th Analysis:
1. "Implement automated JSONL-to-database synchronization service"
2. "Implement real-time token tracking for new conversations" 
3. "Incremental Processing: Implement delta processing to avoid reprocessing all files"

Architecture:
- File system monitoring for new JSONL files and modifications
- Incremental processing to only analyze new/changed content
- Real-time sync to database as new conversations happen
- State tracking to avoid reprocessing existing data
"""

import logging
import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor

# Import conversation processing
from ..telemetry.jsonl_enhancement.full_content_processor import FullContentBatchProcessor

# Optional dependency for file system monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    # Create mock classes for when watchdog is not available
    class FileSystemEventHandler:
        pass
    class Observer:
        def __init__(self): pass
        def schedule(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def join(self): pass

# Internal imports
from .token_analysis_bridge import TokenAnalysisBridgeService, TokenUsageSummaryRecord
from ..analysis.dashboard_integration import get_enhanced_token_analysis_sync

logger = logging.getLogger(__name__)

@dataclass
class FileProcessingState:
    """Track processing state for each JSONL file."""
    file_path: str
    last_modified: float
    last_processed: datetime
    lines_processed: int
    file_hash: str
    total_tokens: int = 0
    last_sync_time: Optional[datetime] = None

@dataclass 
class SyncStats:
    """Statistics for incremental sync operations."""
    files_monitored: int = 0
    new_files_detected: int = 0
    modified_files_detected: int = 0
    lines_processed: int = 0
    tokens_synced: int = 0
    sync_operations: int = 0
    last_sync_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

class JSONLFileHandler(FileSystemEventHandler):
    """Handle file system events for JSONL files."""
    
    def __init__(self, sync_service: 'IncrementalSyncService'):
        self.sync_service = sync_service
        
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith('.jsonl'):
            logger.info(f"JSONL file modified: {event.src_path}")
            # Use thread-safe call to schedule async operation
            self.sync_service._schedule_file_processing(event.src_path, is_new=False)
            
    def on_created(self, event):
        """Handle new file creation events."""
        if not event.is_directory and event.src_path.endswith('.jsonl'):
            logger.info(f"New JSONL file created: {event.src_path}")
            # Use thread-safe call to schedule async operation
            self.sync_service._schedule_file_processing(event.src_path, is_new=True)

class IncrementalSyncService:
    """
    Incremental synchronization service for JSONL-to-database sync.
    
    Implements the automated synchronization strategy outlined in the September 9th analysis.
    """
    
    def __init__(self, 
                 bridge_service: TokenAnalysisBridgeService,
                 watch_directory: str = None,
                 state_file: str = None):
        self.bridge_service = bridge_service
        self.watch_directory = Path(watch_directory or Path.home() / ".claude" / "projects")
        self.state_file = Path(state_file or self.watch_directory / ".sync_state.json")
        
        # Processing state
        self.file_states: Dict[str, FileProcessingState] = {}
        self.stats = SyncStats()
        self.observer: Optional[Observer] = None
        self.running = False
        self._sync_lock = asyncio.Lock()
        
        # Event loop and threading for cross-thread async communication
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jsonl-sync")
        
        # Load existing state
        self._load_state()
        
    def _load_state(self):
        """Load processing state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                    
                # Reconstruct file states
                for file_path, state_dict in state_data.get('file_states', {}).items():
                    self.file_states[file_path] = FileProcessingState(
                        file_path=state_dict['file_path'],
                        last_modified=state_dict['last_modified'],
                        last_processed=datetime.fromisoformat(state_dict['last_processed']),
                        lines_processed=state_dict['lines_processed'],
                        file_hash=state_dict['file_hash'],
                        total_tokens=state_dict.get('total_tokens', 0),
                        last_sync_time=datetime.fromisoformat(state_dict['last_sync_time']) if state_dict.get('last_sync_time') else None
                    )
                    
                logger.info(f"Loaded state for {len(self.file_states)} files")
        except Exception as e:
            logger.warning(f"Could not load sync state: {e}")
            
    def _save_state(self):
        """Save processing state to disk."""
        try:
            state_data = {
                'file_states': {
                    file_path: {
                        'file_path': state.file_path,
                        'last_modified': state.last_modified,
                        'last_processed': state.last_processed.isoformat(),
                        'lines_processed': state.lines_processed,
                        'file_hash': state.file_hash,
                        'total_tokens': state.total_tokens,
                        'last_sync_time': state.last_sync_time.isoformat() if state.last_sync_time else None
                    }
                    for file_path, state in self.file_states.items()
                },
                'last_save': datetime.now().isoformat()
            }
            
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Could not save sync state: {e}")
            
    def _get_file_hash(self, file_path: str) -> str:
        """Get SHA256 hash of file for change detection."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Could not hash file {file_path}: {e}")
            return ""
    
    def _schedule_file_processing(self, file_path: str, is_new: bool = False):
        """Thread-safe method to schedule async file processing from watchdog events."""
        if self._main_loop is not None and not self._main_loop.is_closed():
            # Schedule the coroutine on the main event loop
            if is_new:
                future = asyncio.run_coroutine_threadsafe(
                    self.process_new_file(file_path), self._main_loop
                )
            else:
                future = asyncio.run_coroutine_threadsafe(
                    self.process_file_change(file_path), self._main_loop
                )
            # Don't wait for result to avoid blocking the watchdog thread
        else:
            logger.warning(f"No event loop available to process file: {file_path}")
            
    async def discover_new_files(self) -> List[str]:
        """
        Discover new JSONL files that haven't been processed.
        
        Implements incremental discovery to avoid reprocessing all files.
        """
        new_files = []
        
        try:
            # Find all JSONL files
            jsonl_files = list(self.watch_directory.glob("**/*.jsonl"))
            self.stats.files_monitored = len(jsonl_files)
            
            for file_path in jsonl_files:
                file_str = str(file_path)
                
                # Check if file is new or modified
                if file_str not in self.file_states:
                    new_files.append(file_str)
                    self.stats.new_files_detected += 1
                    logger.info(f"New file discovered: {file_str}")
                else:
                    # Check if file was modified
                    current_mtime = file_path.stat().st_mtime
                    current_hash = self._get_file_hash(file_str)
                    
                    stored_state = self.file_states[file_str]
                    
                    if (current_mtime > stored_state.last_modified or 
                        current_hash != stored_state.file_hash):
                        new_files.append(file_str)
                        self.stats.modified_files_detected += 1
                        logger.info(f"Modified file detected: {file_str}")
                        
        except Exception as e:
            error_msg = f"Error discovering files: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            
        return new_files
        
    async def process_file_incremental(self, file_path: str) -> bool:
        """
        Process a single file incrementally.
        
        Only processes new lines since last processing to avoid recomputing all data.
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return False
                
            # Get current file state
            current_mtime = file_path_obj.stat().st_mtime
            current_hash = self._get_file_hash(file_path)
            
            # Get stored state
            stored_state = self.file_states.get(file_path)
            start_line = stored_state.lines_processed if stored_state else 0
            
            # Read new lines only
            new_lines = []
            malformed_lines = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= start_line:  # Only process new lines
                        line_content = line.strip()
                        if not line_content:  # Skip empty lines
                            continue
                        try:
                            entry = json.loads(line_content)
                            new_lines.append(entry)
                        except json.JSONDecodeError as e:
                            malformed_lines += 1
                            logger.warning(f"Malformed JSON at line {i+1} in {file_path}: {e}")
                            logger.debug(f"Problematic line content: {line_content[:200]}{'...' if len(line_content) > 200 else ''}")
                            continue
            
            if malformed_lines > 0:
                logger.warning(f"Skipped {malformed_lines} malformed JSON lines in {file_path}")
                            
            if not new_lines:
                logger.debug(f"No new lines in {file_path}")
                return True
                
            logger.info(f"Processing {len(new_lines)} new lines from {file_path}")
            
            # Extract actual tokens from new JSONL entries (ccusage approach)
            estimated_tokens = 0
            successful_extractions = 0
            for entry in new_lines:
                # Try to get actual token usage from JSONL entry
                # Fix: Usage data is nested under 'message' key
                usage_data = entry.get('message', {}).get('usage')
                if usage_data and isinstance(usage_data, dict):
                    # Use actual token metrics when available (ccusage method)
                    # Ensure all values are integers to prevent type errors
                    input_tokens = usage_data.get('input_tokens', 0)
                    output_tokens = usage_data.get('output_tokens', 0)
                    cache_creation_tokens = usage_data.get('cache_creation_input_tokens', 0)
                    cache_read_tokens = usage_data.get('cache_read_input_tokens', 0)
                    
                    # Convert to int if they are not already
                    input_tokens = int(input_tokens) if isinstance(input_tokens, (int, float)) else 0
                    output_tokens = int(output_tokens) if isinstance(output_tokens, (int, float)) else 0
                    cache_creation_tokens = int(cache_creation_tokens) if isinstance(cache_creation_tokens, (int, float)) else 0
                    cache_read_tokens = int(cache_read_tokens) if isinstance(cache_read_tokens, (int, float)) else 0
                    
                    actual_tokens = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
                    if actual_tokens > 0:
                        estimated_tokens += actual_tokens
                        successful_extractions += 1
                        logger.debug(f"Extracted {actual_tokens} actual tokens from JSONL entry (input: {input_tokens}, output: {output_tokens}, cache_creation: {cache_creation_tokens}, cache_read: {cache_read_tokens})")
                    # Skip entries without actual token usage data to maintain accuracy
                else:
                    # Log when usage data is not found to help with debugging
                    entry_type = entry.get('type', 'unknown')
                    message_role = entry.get('message', {}).get('role', 'unknown')
                    logger.debug(f"No usage data found for entry type={entry_type}, role={message_role}")
                
            # Update file state
            new_state = FileProcessingState(
                file_path=file_path,
                last_modified=current_mtime,
                last_processed=datetime.now(),
                lines_processed=start_line + len(new_lines),
                file_hash=current_hash,
                total_tokens=int(estimated_tokens),
                last_sync_time=datetime.now()
            )
            
            self.file_states[file_path] = new_state
            self.stats.lines_processed += len(new_lines)
            self.stats.tokens_synced += int(estimated_tokens)
            
            # Process conversation data alongside token extraction
            conversations_processed = 0
            try:
                processor = FullContentBatchProcessor(self.bridge_service.clickhouse_client)
                conversation_stats = await processor.process_jsonl_entries(new_lines)
                conversations_processed = conversation_stats.get('messages_processed', 0)
                logger.info(f"Conversation processing complete: {conversations_processed} messages processed")
            except Exception as e:
                logger.error(f"Error processing conversations for {file_path}: {e}")
            
            # Enhanced logging for observability
            logger.info(f"File processing complete: {file_path}")
            logger.info(f"  Lines processed: {len(new_lines)}")
            logger.info(f"  Successful token extractions: {successful_extractions}/{len(new_lines)}")
            logger.info(f"  Total tokens extracted: {estimated_tokens}")
            
            if successful_extractions == 0 and len(new_lines) > 0:
                logger.warning(f"WARNING: No tokens extracted from {len(new_lines)} entries in {file_path}. This may indicate a data structure issue.")
            
            return True
            
        except Exception as e:
            error_msg = f"Error processing file {file_path}: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            return False
            
    async def sync_incremental_changes(self) -> int:
        """
        Sync incremental changes to database.
        
        This implements the "automated JSONL-to-database synchronization" from Sept 9th analysis.
        """
        async with self._sync_lock:
            try:
                logger.info("Starting incremental sync operation...")
                
                # Discover new/changed files
                changed_files = await self.discover_new_files()
                
                if not changed_files:
                    logger.info("No changed files detected")
                    return 0
                    
                logger.info(f"Processing {len(changed_files)} changed files")
                
                # Process each changed file
                total_synced = 0
                for file_path in changed_files:
                    success = await self.process_file_incremental(file_path)
                    if success:
                        total_synced += 1
                        
                # Update dashboard data and sync to database
                if total_synced > 0:
                    await self._sync_aggregated_data()
                    
                self.stats.sync_operations += 1
                self.stats.last_sync_time = datetime.now()
                
                # Save state
                self._save_state()
                
                logger.info(f"Incremental sync complete: {total_synced} files processed")
                return total_synced
                
            except Exception as e:
                error_msg = f"Incremental sync failed: {e}"
                logger.error(error_msg)
                self.stats.errors.append(error_msg)
                return 0
                
    async def _sync_aggregated_data(self):
        """Sync aggregated token data to database using bridge service."""
        try:
            # Get latest enhanced analysis (this includes incremental changes)
            dashboard_data = get_enhanced_token_analysis_sync()
            
            # Convert to bridge format and sync
            analysis = self.bridge_service._convert_dashboard_to_analysis(dashboard_data)
            
            # Transform to database records
            records = await self.bridge_service._transform_analysis_to_records(analysis)
            
            if records and self.bridge_service.clickhouse_client:
                # Insert updated data (SummingMergeTree automatically handles aggregation)
                await self.bridge_service._batch_insert_records(records, batch_size=100)
                logger.info(f"Synced {len(records)} updated records to database")
            else:
                logger.warning("No database client available for sync")
                
        except Exception as e:
            logger.error(f"Failed to sync aggregated data: {e}")
            
    async def start_file_monitoring(self):
        """
        Start real-time file system monitoring.
        
        Implements "real-time token tracking for new conversations" from Sept 9th analysis.
        """
        # Capture the current event loop for cross-thread communication
        self._main_loop = asyncio.get_running_loop()
        
        if self.running:
            logger.warning("File monitoring already running")
            return
            
        if not _WATCHDOG_AVAILABLE:
            logger.warning("Watchdog library not available - using polling mode instead")
            # Fall back to polling mode
            await self._start_polling_mode()
            return
            
        try:
            logger.info(f"Starting file system monitoring on {self.watch_directory}")
            
            # Set up file system observer
            event_handler = JSONLFileHandler(self)
            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.watch_directory), recursive=True)
            
            # Start monitoring
            self.observer.start()
            self.running = True
            
            logger.info("Real-time file monitoring started")
            
            # Process any existing unprocessed files on startup
            logger.info("Performing startup catch-up for existing files...")
            await self.sync_incremental_changes()
            logger.info("Startup catch-up completed")
            
        except Exception as e:
            error_msg = f"Failed to start file monitoring: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            
    async def _start_polling_mode(self):
        """Fallback polling mode when watchdog is not available."""
        logger.info("Starting polling mode file monitoring (checking every 30 seconds)")
        self.running = True
        
        while self.running:
            try:
                await self.sync_incremental_changes()
                await asyncio.sleep(30)  # Poll every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling mode error: {e}")
                await asyncio.sleep(60)  # Wait before retry
            
    async def stop_file_monitoring(self):
        """Stop file system monitoring."""
        if not self.running:
            return
            
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                
            self.running = False
            self._save_state()
            
            logger.info("File monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping file monitoring: {e}")
            
    async def process_file_change(self, file_path: str):
        """Handle file modification event."""
        try:
            logger.info(f"Processing file change: {file_path}")
            await self.process_file_incremental(file_path)
            await self._sync_aggregated_data()
            
        except Exception as e:
            logger.error(f"Error processing file change {file_path}: {e}")
            
    async def process_new_file(self, file_path: str):
        """Handle new file creation event."""
        try:
            logger.info(f"Processing new file: {file_path}")
            # Wait a bit for file to be fully written
            await asyncio.sleep(1)
            await self.process_file_incremental(file_path)
            await self._sync_aggregated_data()
            
        except Exception as e:
            logger.error(f"Error processing new file {file_path}: {e}")
            
    async def run_scheduled_sync(self, interval_minutes: int = 15):
        """
        Run scheduled incremental sync operations.
        
        Implements the automated synchronization service from Sept 9th analysis.
        """
        logger.info(f"Starting scheduled sync every {interval_minutes} minutes")
        
        while self.running:
            try:
                await self.sync_incremental_changes()
                await asyncio.sleep(interval_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("Scheduled sync cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduled sync error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
                
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        return {
            "service_name": "IncrementalSyncService",
            "running": self.running,
            "watch_directory": str(self.watch_directory),
            "stats": {
                "files_monitored": self.stats.files_monitored,
                "new_files_detected": self.stats.new_files_detected,
                "modified_files_detected": self.stats.modified_files_detected,
                "lines_processed": self.stats.lines_processed,
                "tokens_synced": self.stats.tokens_synced,
                "sync_operations": self.stats.sync_operations,
                "last_sync_time": self.stats.last_sync_time.isoformat() if self.stats.last_sync_time else None,
                "errors": len(self.stats.errors)
            },
            "file_states_count": len(self.file_states),
            "capabilities": {
                "incremental_processing": True,
                "real_time_monitoring": True,
                "scheduled_sync": True,
                "state_persistence": True
            }
        }

# Factory function
async def create_incremental_sync_service(
    bridge_service: TokenAnalysisBridgeService,
    watch_directory: str = None
) -> IncrementalSyncService:
    """Create and initialize incremental sync service."""
    
    sync_service = IncrementalSyncService(
        bridge_service=bridge_service,
        watch_directory=watch_directory
    )
    
    logger.info("IncrementalSyncService created successfully")
    return sync_service