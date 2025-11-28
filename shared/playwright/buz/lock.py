"""
Buz Playwright concurrency lock.

Ensures only one bot can use Playwright to access Buz at a time.
This prevents login conflicts and session corruption when multiple bots
try to interact with the same Buz organization simultaneously.
"""
import asyncio
import logging
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from typing import Optional

from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

# Default lock location
DEFAULT_LOCK_PATH = Path(__file__).parent.parent.parent.parent / '.secrets' / 'buz_playwright.lock'


class BuzPlaywrightLock:
    """
    File-based lock for Buz Playwright access.

    Usage (sync context manager):
        lock = BuzPlaywrightLock()
        with lock.acquire('hugo'):
            # Do Playwright work
            pass

    Usage (async context manager):
        lock = BuzPlaywrightLock()
        async with lock.acquire_async('ivy'):
            # Do async Playwright work
            pass

    Usage (manual):
        lock = BuzPlaywrightLock()
        lock.lock('hugo')
        try:
            # Do Playwright work
        finally:
            lock.unlock()
    """

    def __init__(
        self,
        lock_path: Optional[Path] = None,
        timeout: int = 300  # 5 minutes default
    ):
        """
        Initialize the lock.

        Args:
            lock_path: Path to the lock file. Defaults to .secrets/buz_playwright.lock
            timeout: Seconds to wait for lock acquisition before timing out.
                     Set to -1 for infinite wait. Default: 300 (5 minutes)
        """
        self.lock_path = lock_path or DEFAULT_LOCK_PATH
        self.timeout = timeout
        self._file_lock = FileLock(str(self.lock_path))
        self._holder: Optional[str] = None

    @contextmanager
    def acquire(self, bot_name: str):
        """
        Sync context manager to acquire the Buz Playwright lock.

        Args:
            bot_name: Name of the bot acquiring the lock (for logging)

        Raises:
            Timeout: If the lock cannot be acquired within the timeout period
        """
        try:
            logger.info(f"[{bot_name}] Acquiring Buz Playwright lock...")
            self._file_lock.acquire(timeout=self.timeout)
            self._holder = bot_name
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
            yield
        except Timeout:
            logger.error(
                f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                f"Another bot may be using Buz."
            )
            raise
        finally:
            if self._file_lock.is_locked:
                self._file_lock.release()
                logger.info(f"[{bot_name}] Buz Playwright lock released")
                self._holder = None

    @asynccontextmanager
    async def acquire_async(self, bot_name: str):
        """
        Async context manager to acquire the Buz Playwright lock.

        Uses run_in_executor to avoid blocking the event loop while waiting.

        Args:
            bot_name: Name of the bot acquiring the lock (for logging)

        Raises:
            Timeout: If the lock cannot be acquired within the timeout period
        """
        loop = asyncio.get_event_loop()
        try:
            logger.info(f"[{bot_name}] Acquiring Buz Playwright lock (async)...")
            # Run blocking lock acquisition in executor
            await loop.run_in_executor(
                None,
                lambda: self._file_lock.acquire(timeout=self.timeout)
            )
            self._holder = bot_name
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
            yield
        except Timeout:
            logger.error(
                f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                f"Another bot may be using Buz."
            )
            raise
        finally:
            if self._file_lock.is_locked:
                self._file_lock.release()
                logger.info(f"[{bot_name}] Buz Playwright lock released")
                self._holder = None

    def lock(self, bot_name: str) -> None:
        """
        Manually acquire the lock (non-context-manager usage).

        Args:
            bot_name: Name of the bot acquiring the lock

        Raises:
            Timeout: If the lock cannot be acquired within the timeout period
        """
        logger.info(f"[{bot_name}] Acquiring Buz Playwright lock...")
        try:
            self._file_lock.acquire(timeout=self.timeout)
            self._holder = bot_name
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
        except Timeout:
            logger.error(
                f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                f"Another bot may be using Buz."
            )
            raise

    def unlock(self) -> None:
        """Release the lock if held."""
        if self._file_lock.is_locked:
            bot_name = self._holder or "unknown"
            self._file_lock.release()
            logger.info(f"[{bot_name}] Buz Playwright lock released")
            self._holder = None

    @property
    def is_locked(self) -> bool:
        """Check if the lock is currently held (by this instance)."""
        return self._file_lock.is_locked

    @property
    def holder(self) -> Optional[str]:
        """Get the name of the bot currently holding the lock."""
        return self._holder


# Module-level singleton for convenience
_default_lock: Optional[BuzPlaywrightLock] = None


def get_buz_lock(timeout: int = 300) -> BuzPlaywrightLock:
    """
    Get the default Buz Playwright lock instance.

    Args:
        timeout: Lock timeout in seconds (only used on first call)

    Returns:
        The singleton BuzPlaywrightLock instance
    """
    global _default_lock
    if _default_lock is None:
        _default_lock = BuzPlaywrightLock(timeout=timeout)
    return _default_lock
