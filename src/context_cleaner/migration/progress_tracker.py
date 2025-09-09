"""
Progress Tracker

Provides real-time progress monitoring with file/record/token counts, performance
metrics tracking, checkpoint system for resumable migrations, detailed logging
and error reporting, and integration with dashboard for migration status display.

Designed to handle large-scale migrations with accurate progress estimates and ETA.
"""

import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import aiofiles

logger = logging.getLogger(__name__)


@dataclass
class MigrationProgress:
    """Real-time migration progress tracking."""

    # Migration identification
    migration_id: str
    migration_type: str  # "historical", "incremental", "validation"

    # Current state
    current_phase: str
    current_file: Optional[str] = None
    current_batch: int = 0

    # File progress
    files_total: int = 0
    files_completed: int = 0
    files_failed: int = 0
    files_skipped: int = 0
    files_remaining: int = 0

    # Record progress
    records_total: int = 0
    records_processed: int = 0
    records_stored: int = 0
    records_failed: int = 0

    # Token progress
    tokens_total: int = 0
    tokens_processed: int = 0
    tokens_stored: int = 0

    # Performance metrics
    start_time: datetime = field(default_factory=datetime.now)
    last_update_time: datetime = field(default_factory=datetime.now)
    estimated_completion_time: Optional[datetime] = None

    # Processing rates
    current_processing_rate_records_per_second: float = 0.0
    current_processing_rate_tokens_per_second: float = 0.0
    average_processing_rate_records_per_second: float = 0.0
    average_processing_rate_tokens_per_second: float = 0.0

    # Error tracking
    errors_count: int = 0
    warnings_count: int = 0
    last_error: Optional[str] = None
    last_warning: Optional[str] = None

    # System resources
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None

    @property
    def elapsed_time_seconds(self) -> float:
        """Time elapsed since migration started."""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def files_progress_percentage(self) -> float:
        """Percentage of files completed."""
        if self.files_total == 0:
            return 0.0
        return (self.files_completed / self.files_total) * 100

    @property
    def records_progress_percentage(self) -> float:
        """Percentage of records processed."""
        if self.records_total == 0:
            return 0.0
        return (self.records_processed / self.records_total) * 100

    @property
    def tokens_progress_percentage(self) -> float:
        """Percentage of tokens processed."""
        if self.tokens_total == 0:
            return 0.0
        return (self.tokens_processed / self.tokens_total) * 100

    @property
    def overall_progress_percentage(self) -> float:
        """Overall progress percentage (weighted average)."""
        # Weight records more heavily than files for better accuracy
        if self.records_total > 0:
            return self.records_progress_percentage
        elif self.files_total > 0:
            return self.files_progress_percentage
        else:
            return 0.0

    @property
    def eta_seconds(self) -> Optional[float]:
        """Estimated seconds until completion."""
        if self.estimated_completion_time:
            return (self.estimated_completion_time - datetime.now()).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if migration is complete."""
        return (self.files_completed + self.files_failed + self.files_skipped) >= self.files_total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            "start_time": self.start_time.isoformat(),
            "last_update_time": self.last_update_time.isoformat(),
            "estimated_completion_time": (
                self.estimated_completion_time.isoformat() if self.estimated_completion_time else None
            ),
            "elapsed_time_seconds": self.elapsed_time_seconds,
            "files_progress_percentage": self.files_progress_percentage,
            "records_progress_percentage": self.records_progress_percentage,
            "tokens_progress_percentage": self.tokens_progress_percentage,
            "overall_progress_percentage": self.overall_progress_percentage,
            "eta_seconds": self.eta_seconds,
            "is_complete": self.is_complete,
        }


@dataclass
class MigrationCheckpoint:
    """Migration checkpoint for resumable operations."""

    checkpoint_id: str
    migration_id: str
    timestamp: datetime

    # State information
    completed_files: List[str] = field(default_factory=list)
    failed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    current_file_index: int = 0

    # Progress snapshot
    progress_snapshot: Optional[Dict[str, Any]] = None

    # Metadata
    checkpoint_reason: str = "periodic"  # periodic, error, manual
    recovery_instructions: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "progress_snapshot": self.progress_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationCheckpoint":
        """Create checkpoint from dictionary."""
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ProgressTracker:
    """
    Real-time progress tracker for migration operations.

    Provides comprehensive progress monitoring, performance metrics,
    checkpoint management, and ETA calculations for large-scale
    migration operations.
    """

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        checkpoint_interval_seconds: int = 300,  # 5 minutes
        performance_window_size: int = 100,  # Number of samples for moving average
        enable_system_monitoring: bool = True,
    ):
        self.checkpoint_dir = Path(checkpoint_dir or Path.home() / ".claude" / "migration_checkpoints")
        self.checkpoint_interval_seconds = checkpoint_interval_seconds
        self.performance_window_size = performance_window_size
        self.enable_system_monitoring = enable_system_monitoring

        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.current_progress: Optional[MigrationProgress] = None
        self.progress_callbacks: List[Callable[[MigrationProgress], None]] = []

        # Performance tracking
        self.performance_history: Dict[str, deque] = {
            "records_per_second": deque(maxlen=performance_window_size),
            "tokens_per_second": deque(maxlen=performance_window_size),
            "processing_times": deque(maxlen=performance_window_size),
        }

        # Checkpoint management
        self.last_checkpoint_time = datetime.now()
        self.auto_checkpoint_enabled = True

        logger.info("Progress tracker initialized")

    def start_migration(
        self,
        migration_id: str,
        migration_type: str,
        total_files: int = 0,
        total_records: int = 0,
        total_tokens: int = 0,
    ) -> MigrationProgress:
        """
        Start tracking a new migration.

        Args:
            migration_id: Unique migration identifier
            migration_type: Type of migration (historical, incremental, etc.)
            total_files: Total number of files to process
            total_records: Total number of records expected
            total_tokens: Total number of tokens expected

        Returns:
            MigrationProgress object for tracking
        """
        self.current_progress = MigrationProgress(
            migration_id=migration_id,
            migration_type=migration_type,
            current_phase="starting",
            files_total=total_files,
            files_remaining=total_files,
            records_total=total_records,
            tokens_total=total_tokens,
        )

        logger.info(
            f"Started tracking migration {migration_id}: "
            f"{total_files} files, {total_records:,} records, {total_tokens:,} tokens"
        )

        self._notify_callbacks()
        return self.current_progress

    def update_phase(self, phase: str, details: Optional[str] = None):
        """Update current migration phase."""
        if not self.current_progress:
            return

        self.current_progress.current_phase = phase
        self.current_progress.last_update_time = datetime.now()

        if details:
            logger.info(f"Phase update: {phase} - {details}")
        else:
            logger.info(f"Phase update: {phase}")

        self._notify_callbacks()
        self._auto_checkpoint_if_needed()

    def update_file_progress(
        self,
        current_file: Optional[str] = None,
        files_completed: Optional[int] = None,
        files_failed: Optional[int] = None,
        files_skipped: Optional[int] = None,
    ):
        """Update file processing progress."""
        if not self.current_progress:
            return

        if current_file is not None:
            self.current_progress.current_file = current_file

        if files_completed is not None:
            self.current_progress.files_completed = files_completed

        if files_failed is not None:
            self.current_progress.files_failed = files_failed

        if files_skipped is not None:
            self.current_progress.files_skipped = files_skipped

        # Update remaining files
        self.current_progress.files_remaining = max(
            0,
            self.current_progress.files_total
            - self.current_progress.files_completed
            - self.current_progress.files_failed
            - self.current_progress.files_skipped,
        )

        self.current_progress.last_update_time = datetime.now()
        self._update_eta()
        self._notify_callbacks()
        self._auto_checkpoint_if_needed()

    def update_record_progress(
        self,
        records_processed: Optional[int] = None,
        records_stored: Optional[int] = None,
        records_failed: Optional[int] = None,
        batch_size: Optional[int] = None,
    ):
        """Update record processing progress."""
        if not self.current_progress:
            return

        old_processed = self.current_progress.records_processed

        if records_processed is not None:
            self.current_progress.records_processed = records_processed

        if records_stored is not None:
            self.current_progress.records_stored = records_stored

        if records_failed is not None:
            self.current_progress.records_failed = records_failed

        if batch_size is not None:
            self.current_progress.current_batch += 1

        # Update processing rates
        new_processed = self.current_progress.records_processed
        if new_processed > old_processed:
            self._update_processing_rates(new_processed - old_processed)

        self.current_progress.last_update_time = datetime.now()
        self._update_eta()
        self._notify_callbacks()

    def update_token_progress(
        self,
        tokens_processed: Optional[int] = None,
        tokens_stored: Optional[int] = None,
    ):
        """Update token processing progress."""
        if not self.current_progress:
            return

        old_tokens = self.current_progress.tokens_processed

        if tokens_processed is not None:
            self.current_progress.tokens_processed = tokens_processed

        if tokens_stored is not None:
            self.current_progress.tokens_stored = tokens_stored

        # Update token processing rates
        new_tokens = self.current_progress.tokens_processed
        if new_tokens > old_tokens:
            self._update_token_rates(new_tokens - old_tokens)

        self.current_progress.last_update_time = datetime.now()
        self._update_eta()
        self._notify_callbacks()

    def add_error(self, error: str):
        """Record an error during migration."""
        if not self.current_progress:
            return

        self.current_progress.errors_count += 1
        self.current_progress.last_error = error
        self.current_progress.last_update_time = datetime.now()

        logger.error(f"Migration error: {error}")
        self._notify_callbacks()

    def add_warning(self, warning: str):
        """Record a warning during migration."""
        if not self.current_progress:
            return

        self.current_progress.warnings_count += 1
        self.current_progress.last_warning = warning
        self.current_progress.last_update_time = datetime.now()

        logger.warning(f"Migration warning: {warning}")
        self._notify_callbacks()

    def add_progress_callback(self, callback: Callable[[MigrationProgress], None]):
        """Add a callback for progress updates."""
        self.progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[MigrationProgress], None]):
        """Remove a progress callback."""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)

    async def create_checkpoint(
        self,
        checkpoint_reason: str = "manual",
        recovery_instructions: Optional[str] = None,
        completed_files: Optional[List[str]] = None,
        failed_files: Optional[List[str]] = None,
    ) -> MigrationCheckpoint:
        """
        Create a migration checkpoint for resumability.

        Args:
            checkpoint_reason: Reason for checkpoint creation
            recovery_instructions: Optional recovery instructions
            completed_files: List of completed files
            failed_files: List of failed files

        Returns:
            Created MigrationCheckpoint
        """
        if not self.current_progress:
            raise ValueError("No active migration to checkpoint")

        checkpoint_id = f"checkpoint_{self.current_progress.migration_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        checkpoint = MigrationCheckpoint(
            checkpoint_id=checkpoint_id,
            migration_id=self.current_progress.migration_id,
            timestamp=datetime.now(),
            completed_files=completed_files or [],
            failed_files=failed_files or [],
            progress_snapshot=self.current_progress.to_dict(),
            checkpoint_reason=checkpoint_reason,
            recovery_instructions=recovery_instructions,
        )

        # Save checkpoint to disk
        await self._save_checkpoint(checkpoint)

        logger.info(f"Created checkpoint: {checkpoint_id}")
        return checkpoint

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[MigrationCheckpoint]:
        """Load a migration checkpoint."""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            async with aiofiles.open(checkpoint_file, "r", encoding="utf-8") as file:
                data = json.loads(await file.read())

            return MigrationCheckpoint.from_dict(data)

        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    async def resume_from_checkpoint(self, checkpoint: MigrationCheckpoint) -> bool:
        """Resume migration from checkpoint."""
        try:
            if checkpoint.progress_snapshot:
                # Restore progress state
                progress_data = checkpoint.progress_snapshot

                self.current_progress = MigrationProgress(
                    migration_id=progress_data["migration_id"],
                    migration_type=progress_data["migration_type"],
                    current_phase="resumed",
                    current_file=progress_data.get("current_file"),
                    current_batch=progress_data.get("current_batch", 0),
                    files_total=progress_data["files_total"],
                    files_completed=progress_data["files_completed"],
                    files_failed=progress_data["files_failed"],
                    files_skipped=progress_data["files_skipped"],
                    records_total=progress_data["records_total"],
                    records_processed=progress_data["records_processed"],
                    records_stored=progress_data["records_stored"],
                    records_failed=progress_data["records_failed"],
                    tokens_total=progress_data["tokens_total"],
                    tokens_processed=progress_data["tokens_processed"],
                    tokens_stored=progress_data["tokens_stored"],
                    start_time=datetime.fromisoformat(progress_data["start_time"]),
                    errors_count=progress_data["errors_count"],
                    warnings_count=progress_data["warnings_count"],
                )

                # Update remaining files
                self.current_progress.files_remaining = max(
                    0,
                    self.current_progress.files_total
                    - self.current_progress.files_completed
                    - self.current_progress.files_failed
                    - self.current_progress.files_skipped,
                )

            logger.info(f"Resumed migration from checkpoint: {checkpoint.checkpoint_id}")
            self._notify_callbacks()
            return True

        except Exception as e:
            logger.error(f"Failed to resume from checkpoint: {e}")
            return False

    async def list_checkpoints(self, migration_id: Optional[str] = None) -> List[MigrationCheckpoint]:
        """List available checkpoints."""
        checkpoints = []

        try:
            for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
                try:
                    async with aiofiles.open(checkpoint_file, "r", encoding="utf-8") as file:
                        data = json.loads(await file.read())

                    checkpoint = MigrationCheckpoint.from_dict(data)

                    # Filter by migration ID if specified
                    if migration_id is None or checkpoint.migration_id == migration_id:
                        checkpoints.append(checkpoint)

                except Exception as e:
                    logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")

        # Sort by timestamp (newest first)
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)
        return checkpoints

    def get_current_progress(self) -> Optional[MigrationProgress]:
        """Get current migration progress."""
        return self.current_progress

    def _update_processing_rates(self, records_delta: int):
        """Update processing rate metrics."""
        if not self.current_progress:
            return

        now = datetime.now()
        elapsed = (now - self.current_progress.last_update_time).total_seconds()

        if elapsed > 0:
            current_rate = records_delta / elapsed
            self.current_progress.current_processing_rate_records_per_second = current_rate
            self.performance_history["records_per_second"].append(current_rate)

            # Calculate moving average
            if self.performance_history["records_per_second"]:
                avg_rate = sum(self.performance_history["records_per_second"]) / len(
                    self.performance_history["records_per_second"]
                )
                self.current_progress.average_processing_rate_records_per_second = avg_rate

    def _update_token_rates(self, tokens_delta: int):
        """Update token processing rate metrics."""
        if not self.current_progress:
            return

        now = datetime.now()
        elapsed = (now - self.current_progress.last_update_time).total_seconds()

        if elapsed > 0:
            current_rate = tokens_delta / elapsed
            self.current_progress.current_processing_rate_tokens_per_second = current_rate
            self.performance_history["tokens_per_second"].append(current_rate)

            # Calculate moving average
            if self.performance_history["tokens_per_second"]:
                avg_rate = sum(self.performance_history["tokens_per_second"]) / len(
                    self.performance_history["tokens_per_second"]
                )
                self.current_progress.average_processing_rate_tokens_per_second = avg_rate

    def _update_eta(self):
        """Update estimated time to completion."""
        if not self.current_progress:
            return

        # Use records-based ETA if available, otherwise use files
        if (
            self.current_progress.records_total > 0
            and self.current_progress.average_processing_rate_records_per_second > 0
        ):

            remaining_records = self.current_progress.records_total - self.current_progress.records_processed
            eta_seconds = remaining_records / self.current_progress.average_processing_rate_records_per_second

        elif self.current_progress.files_remaining > 0 and self.current_progress.files_completed > 0:

            elapsed = self.current_progress.elapsed_time_seconds
            files_per_second = self.current_progress.files_completed / elapsed if elapsed > 0 else 0

            if files_per_second > 0:
                eta_seconds = self.current_progress.files_remaining / files_per_second
            else:
                eta_seconds = None
        else:
            eta_seconds = None

        if eta_seconds is not None:
            self.current_progress.estimated_completion_time = datetime.now() + timedelta(seconds=eta_seconds)
        else:
            self.current_progress.estimated_completion_time = None

    def _notify_callbacks(self):
        """Notify all registered progress callbacks."""
        if self.current_progress:
            for callback in self.progress_callbacks:
                try:
                    callback(self.current_progress)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")

    def _auto_checkpoint_if_needed(self):
        """Create automatic checkpoint if interval has passed."""
        if not self.auto_checkpoint_enabled or not self.current_progress:
            return

        now = datetime.now()
        if (now - self.last_checkpoint_time).seconds >= self.checkpoint_interval_seconds:
            asyncio.create_task(self._create_auto_checkpoint())

    async def _create_auto_checkpoint(self):
        """Create automatic checkpoint."""
        try:
            await self.create_checkpoint("automatic")
            self.last_checkpoint_time = datetime.now()
        except Exception as e:
            logger.error(f"Auto-checkpoint failed: {e}")

    async def _save_checkpoint(self, checkpoint: MigrationCheckpoint):
        """Save checkpoint to disk."""
        checkpoint_file = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.json"

        async with aiofiles.open(checkpoint_file, "w", encoding="utf-8") as file:
            await file.write(json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False))

    def enable_auto_checkpoint(self, enabled: bool = True):
        """Enable or disable automatic checkpointing."""
        self.auto_checkpoint_enabled = enabled
        logger.info(f"Auto-checkpoint {'enabled' if enabled else 'disabled'}")

    async def cleanup_old_checkpoints(self, max_age_days: int = 30):
        """Clean up old checkpoint files."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        cleaned_count = 0

        try:
            for checkpoint_file in self.checkpoint_dir.glob("checkpoint_*.json"):
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)

                    if file_mtime < cutoff_date:
                        checkpoint_file.unlink()
                        cleaned_count += 1

                except Exception as e:
                    logger.warning(f"Failed to cleanup checkpoint {checkpoint_file}: {e}")

        except Exception as e:
            logger.error(f"Checkpoint cleanup failed: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old checkpoints")

        return cleaned_count
