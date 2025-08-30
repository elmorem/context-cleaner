"""
Session Observer

Automatic detection and tracking of development session events
through file system monitoring and process observation.
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

from ..config.settings import ContextCleanerConfig
from ..tracking.models import EventType
from .real_time_monitor import RealTimeMonitor

logger = logging.getLogger(__name__)


class ProjectFileHandler(FileSystemEventHandler):
    """File system event handler for project monitoring."""

    def __init__(self, observer: "SessionObserver"):
        self.observer = observer
        self.last_event_time = time.time()

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        # Throttle events to avoid spam
        current_time = time.time()
        if current_time - self.last_event_time < 2.0:  # 2 second throttle
            return

        self.last_event_time = current_time

        # Trigger context change event
        asyncio.create_task(self.observer._handle_file_change(event.src_path))

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        asyncio.create_task(self.observer._handle_file_creation(event.src_path))


class SessionObserver:
    """
    Automatic session observation and event detection.

    Features:
    - File system monitoring for development activity
    - Automatic session start/end detection
    - Context change detection based on activity patterns
    - Integration with RealTimeMonitor for live updates
    """

    def __init__(
        self,
        config: Optional[ContextCleanerConfig] = None,
        real_time_monitor: Optional[RealTimeMonitor] = None,
    ):
        """
        Initialize session observer.

        Args:
            config: Context Cleaner configuration
            real_time_monitor: Optional real-time monitor for integration
        """
        self.config = config or ContextCleanerConfig.from_env()
        self.monitor = real_time_monitor

        # Observation state
        self.is_observing = False
        self.file_observer: Optional[Observer] = None

        # Activity tracking
        self.last_activity_time = time.time()
        self.activity_threshold = 300  # 5 minutes of inactivity before session pause

        # File monitoring
        self.watched_directories: Set[Path] = set()
        self.file_handler = ProjectFileHandler(self)

        # Session state
        self.auto_session_started = False
        self.session_start_time: Optional[datetime] = None

    def start_observing(self, project_paths: Optional[list] = None):
        """
        Start automatic session observation.

        Args:
            project_paths: List of project directories to monitor
        """
        if self.is_observing:
            logger.warning("Session observer already running")
            return

        try:
            # Setup file system monitoring
            self.file_observer = Observer()

            # Add project paths to watch
            if project_paths:
                for path_str in project_paths:
                    path = Path(path_str)
                    if path.exists() and path.is_dir():
                        self.file_observer.schedule(
                            self.file_handler, str(path), recursive=True
                        )
                        self.watched_directories.add(path)
                        logger.info(f"Watching directory: {path}")

            # Start file system observer
            self.file_observer.start()
            self.is_observing = True

            logger.info("Started automatic session observation")

            # Start activity monitoring loop
            asyncio.create_task(self._activity_monitoring_loop())

        except Exception as e:
            logger.error(f"Failed to start session observer: {e}")
            self.stop_observing()

    def stop_observing(self):
        """Stop automatic session observation."""
        if not self.is_observing:
            return

        try:
            self.is_observing = False

            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join(timeout=5.0)
                self.file_observer = None

            # End auto-started session if active
            if self.auto_session_started and self.monitor:
                asyncio.create_task(self._auto_end_session())

            self.watched_directories.clear()
            logger.info("Stopped automatic session observation")

        except Exception as e:
            logger.error(f"Error stopping session observer: {e}")

    async def _activity_monitoring_loop(self):
        """Monitor activity patterns for automatic session management."""
        try:
            while self.is_observing:
                current_time = time.time()
                time_since_activity = current_time - self.last_activity_time

                # Check if we should start a session
                if (
                    not self.auto_session_started and time_since_activity < 30
                ):  # Recent activity
                    await self._auto_start_session()

                # Check if we should pause/end a session due to inactivity
                elif (
                    self.auto_session_started
                    and time_since_activity > self.activity_threshold
                ):
                    await self._auto_end_session()

                # Sleep for monitoring interval
                await asyncio.sleep(60)  # Check every minute

        except asyncio.CancelledError:
            logger.debug("Activity monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Activity monitoring error: {e}")

    async def _handle_file_change(self, file_path: str):
        """Handle file modification event."""
        try:
            self.last_activity_time = time.time()

            # Filter out irrelevant files
            path = Path(file_path)
            if self._should_ignore_file(path):
                return

            logger.debug(f"File changed: {file_path}")

            # Trigger context change event if monitoring
            if self.monitor:
                await self.monitor.trigger_context_event(
                    event_type=EventType.CONTEXT_CHANGE,
                    metadata={
                        "trigger": "file_change",
                        "file_path": str(path.name),  # Only filename for privacy
                        "file_extension": path.suffix,
                        "directory_name": path.parent.name,
                    },
                )

        except Exception as e:
            logger.error(f"File change handling error: {e}")

    async def _handle_file_creation(self, file_path: str):
        """Handle file creation event."""
        try:
            self.last_activity_time = time.time()

            path = Path(file_path)
            if self._should_ignore_file(path):
                return

            logger.debug(f"File created: {file_path}")

            # Trigger context change event
            if self.monitor:
                await self.monitor.trigger_context_event(
                    event_type=EventType.CONTEXT_CHANGE,
                    metadata={
                        "trigger": "file_creation",
                        "file_name": str(path.name),
                        "file_extension": path.suffix,
                        "directory_name": path.parent.name,
                    },
                )

        except Exception as e:
            logger.error(f"File creation handling error: {e}")

    def _should_ignore_file(self, path: Path) -> bool:
        """Check if file should be ignored for monitoring."""
        # Ignore list
        ignore_patterns = {
            # Temporary files
            "*.tmp",
            "*.temp",
            "*~",
            "*.swp",
            "*.swo",
            # Log files
            "*.log",
            "*.logs",
            # Build artifacts
            "*.pyc",
            "*.pyo",
            "*.o",
            "*.so",
            "*.dylib",
            "*.dll",
            # IDE files
            ".DS_Store",
            "Thumbs.db",
            "*.iml",
            # Lock files
            "*.lock",
            "package-lock.json",
            "poetry.lock",
        }

        ignore_directories = {
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            ".venv",
            "venv",
            ".idea",
            ".vscode",
            ".vs",
            "build",
            "dist",
            "target",
            "out",
        }

        # Check if in ignored directory
        for part in path.parts:
            if part in ignore_directories:
                return True

        # Check file patterns
        for pattern in ignore_patterns:
            if path.match(pattern):
                return True

        return False

    async def _auto_start_session(self):
        """Automatically start a session when activity is detected."""
        try:
            if self.monitor:
                from ..tracking.session_tracker import SessionTracker

                tracker = SessionTracker(self.config)

                # Get current working directory as project path
                import os

                project_path = os.getcwd()

                session = tracker.start_session(
                    project_path=project_path,
                    model_name="auto_detected",
                    claude_version="observer",
                )

                self.auto_session_started = True
                self.session_start_time = datetime.now()

                logger.info(f"Auto-started session: {session.session_id}")

                # Trigger session start event in monitor
                await self.monitor.trigger_context_event(
                    event_type=EventType.SESSION_START,
                    metadata={
                        "trigger": "auto_detection",
                        "project_path": str(Path(project_path).name),
                        "session_id": session.session_id,
                    },
                )

        except Exception as e:
            logger.error(f"Auto session start failed: {e}")

    async def _auto_end_session(self):
        """Automatically end the current session due to inactivity."""
        try:
            if self.monitor and self.auto_session_started:
                from ..tracking.session_tracker import SessionTracker

                tracker = SessionTracker(self.config)

                success = tracker.end_session()

                if success:
                    duration = (
                        (datetime.now() - self.session_start_time).total_seconds()
                        if self.session_start_time
                        else 0
                    )
                    logger.info(
                        f"Auto-ended session after {duration:.1f}s of inactivity"
                    )

                    # Trigger session end event
                    await self.monitor.trigger_context_event(
                        event_type=EventType.SESSION_END,
                        metadata={
                            "trigger": "auto_inactivity",
                            "duration_seconds": duration,
                            "inactivity_threshold": self.activity_threshold,
                        },
                    )

                self.auto_session_started = False
                self.session_start_time = None

        except Exception as e:
            logger.error(f"Auto session end failed: {e}")

    def get_observer_status(self) -> Dict[str, Any]:
        """Get current observer status and statistics."""
        return {
            "observer": {
                "is_observing": self.is_observing,
                "watched_directories": [str(d) for d in self.watched_directories],
                "auto_session_active": self.auto_session_started,
                "last_activity_time": datetime.fromtimestamp(
                    self.last_activity_time
                ).isoformat(),
                "activity_threshold_s": self.activity_threshold,
            },
            "file_monitoring": {
                "observer_running": (
                    self.file_observer is not None and self.file_observer.is_alive()
                    if self.file_observer
                    else False
                ),
                "directories_count": len(self.watched_directories),
            },
            "session_management": {
                "auto_start_enabled": True,
                "auto_end_enabled": True,
                "session_start_time": (
                    self.session_start_time.isoformat()
                    if self.session_start_time
                    else None
                ),
            },
        }
