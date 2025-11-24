"""
Scheduler service for Scout

Manages periodic execution of system checks.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Callable

from config import config

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service that manages scheduled check runs"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._check_callback: Optional[Callable] = None
        self._last_run_time: Optional[datetime] = None
        self._next_run_time: Optional[datetime] = None

    def start(self, check_callback: Callable):
        """
        Start the scheduler.

        Args:
            check_callback: Function to call when running checks
        """
        if self._running:
            logger.warning("Scheduler is already running")
            return

        if not config.scheduler_enabled:
            logger.info("Scheduler is disabled in configuration")
            return

        self._check_callback = check_callback
        self._stop_event.clear()
        self._running = True

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"Scheduler started with interval of {config.check_interval_minutes} minutes"
        )

    def stop(self):
        """Stop the scheduler"""
        if not self._running:
            return

        logger.info("Stopping scheduler...")
        self._stop_event.set()
        self._running = False

        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        logger.info("Scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop"""
        interval_seconds = config.check_interval_minutes * 60

        # Run on startup if configured
        if config.run_on_startup:
            logger.info("Running checks on startup")
            self._execute_checks()

        while not self._stop_event.is_set():
            # Calculate next run time
            self._next_run_time = datetime.now(timezone.utc)

            # Wait for the interval, checking for stop event periodically
            wait_time = interval_seconds
            while wait_time > 0 and not self._stop_event.is_set():
                sleep_time = min(wait_time, 10)  # Check every 10 seconds
                time.sleep(sleep_time)
                wait_time -= sleep_time

            if not self._stop_event.is_set():
                self._execute_checks()

    def _execute_checks(self):
        """Execute the check callback"""
        if not self._check_callback:
            logger.error("No check callback configured")
            return

        try:
            self._last_run_time = datetime.now(timezone.utc)
            logger.info("Scheduler executing checks")
            self._check_callback()
        except Exception as e:
            logger.exception(f"Error executing scheduled checks: {e}")

    def trigger_manual_run(self) -> bool:
        """
        Trigger a manual check run.

        Returns:
            True if checks were triggered, False if no callback configured
        """
        if not self._check_callback:
            logger.error("No check callback configured")
            return False

        logger.info("Manual check run triggered")
        self._execute_checks()
        return True

    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'enabled': config.scheduler_enabled,
            'running': self._running,
            'interval_minutes': config.check_interval_minutes,
            'run_on_startup': config.run_on_startup,
            'last_run_time': self._last_run_time.isoformat() if self._last_run_time else None,
            'next_run_time': self._next_run_time.isoformat() if self._next_run_time else None
        }

    @property
    def is_running(self) -> bool:
        return self._running


# Singleton instance
scheduler = SchedulerService()
