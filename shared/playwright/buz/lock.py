"""
Buz Playwright concurrency lock.

Ensures only one bot can use Playwright to access Buz at a time.
This prevents login conflicts and session corruption when multiple bots
try to interact with the same Buz organization simultaneously.
"""
import asyncio
import json
import logging
import os
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from filelock import FileLock, Timeout

# Max lock age before considering it stale (30 minutes)
MAX_LOCK_AGE_SECONDS = 1800

logger = logging.getLogger(__name__)

# Default lock location
DEFAULT_LOCK_PATH = Path(__file__).parent.parent.parent.parent / '.secrets' / 'buz_playwright.lock'
# Info file tracks who holds the lock (for better error messages)
DEFAULT_LOCK_INFO_PATH = DEFAULT_LOCK_PATH.with_suffix('.info')


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
        timeout: int = 600  # 10 minutes default
    ):
        """
        Initialize the lock.

        Args:
            lock_path: Path to the lock file. Defaults to .secrets/buz_playwright.lock
            timeout: Seconds to wait for lock acquisition before timing out.
                     Set to -1 for infinite wait. Default: 600 (10 minutes)
        """
        self.lock_path = lock_path or DEFAULT_LOCK_PATH
        self.lock_info_path = self.lock_path.with_suffix('.info')
        self.timeout = timeout
        self._file_lock = FileLock(str(self.lock_path))
        self._holder: Optional[str] = None
        self._acquired_at: Optional[datetime] = None

    def _write_holder_info(self, bot_name: str) -> None:
        """Write holder info to the info file."""
        try:
            info = {
                'bot': bot_name,
                'acquired_at': datetime.now(timezone.utc).isoformat(),
                'pid': __import__('os').getpid()
            }
            self.lock_info_path.write_text(json.dumps(info))
        except Exception as e:
            logger.warning(f"Could not write lock info: {e}")

    def _clear_holder_info(self) -> None:
        """Clear the holder info file."""
        try:
            if self.lock_info_path.exists():
                self.lock_info_path.unlink()
        except Exception as e:
            logger.warning(f"Could not clear lock info: {e}")

    def _get_holder_info(self) -> Optional[dict]:
        """Read holder info from the info file."""
        try:
            if self.lock_info_path.exists():
                return json.loads(self.lock_info_path.read_text())
        except Exception as e:
            logger.warning(f"Could not read lock info: {e}")
        return None

    @contextmanager
    def acquire(self, bot_name: str):
        """
        Sync context manager to acquire the Buz Playwright lock.

        Args:
            bot_name: Name of the bot acquiring the lock (for logging)

        Raises:
            Timeout: If the lock cannot be acquired within the timeout period
        """
        acquired = False
        try:
            logger.info(f"[{bot_name}] Acquiring Buz Playwright lock...")
            self._file_lock.acquire(timeout=self.timeout)
            acquired = True
            self._holder = bot_name
            self._acquired_at = datetime.now(timezone.utc)
            self._write_holder_info(bot_name)
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
            yield
        except Timeout:
            holder_info = self._get_holder_info()
            if holder_info:
                holder_bot = holder_info.get('bot', 'unknown')
                acquired_at = holder_info.get('acquired_at', 'unknown time')
                logger.error(
                    f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                    f"Lock held by '{holder_bot}' since {acquired_at}"
                )
            else:
                logger.error(
                    f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                    f"Another bot may be using Buz."
                )
            raise
        finally:
            if acquired:
                try:
                    self._file_lock.release()
                    self._clear_holder_info()
                    logger.info(f"[{bot_name}] Buz Playwright lock released")
                except Exception as e:
                    logger.warning(f"[{bot_name}] Error releasing lock: {e}")
                self._holder = None
                self._acquired_at = None

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
        acquired = False
        try:
            logger.info(f"[{bot_name}] Acquiring Buz Playwright lock (async)...")
            # Run blocking lock acquisition in executor
            await loop.run_in_executor(
                None,
                lambda: self._file_lock.acquire(timeout=self.timeout)
            )
            acquired = True
            self._holder = bot_name
            self._acquired_at = datetime.now(timezone.utc)
            self._write_holder_info(bot_name)
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
            yield
        except Timeout:
            holder_info = self._get_holder_info()
            if holder_info:
                holder_bot = holder_info.get('bot', 'unknown')
                acquired_at = holder_info.get('acquired_at', 'unknown time')
                logger.error(
                    f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                    f"Lock held by '{holder_bot}' since {acquired_at}"
                )
            else:
                logger.error(
                    f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                    f"Another bot may be using Buz."
                )
            raise
        finally:
            if acquired:
                try:
                    self._file_lock.release()
                    self._clear_holder_info()
                    logger.info(f"[{bot_name}] Buz Playwright lock released")
                except Exception as e:
                    logger.warning(f"[{bot_name}] Error releasing lock: {e}")
                self._holder = None
                self._acquired_at = None

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
            self._acquired_at = datetime.now(timezone.utc)
            self._write_holder_info(bot_name)
            logger.info(f"[{bot_name}] Buz Playwright lock acquired")
        except Timeout:
            holder_info = self._get_holder_info()
            if holder_info:
                holder_bot = holder_info.get('bot', 'unknown')
                acquired_at = holder_info.get('acquired_at', 'unknown time')
                logger.error(
                    f"[{bot_name}] Failed to acquire Buz Playwright lock after {self.timeout}s. "
                    f"Lock held by '{holder_bot}' since {acquired_at}"
                )
            else:
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
            self._clear_holder_info()
            logger.info(f"[{bot_name}] Buz Playwright lock released")
            self._holder = None
            self._acquired_at = None

    @property
    def is_locked(self) -> bool:
        """Check if the lock is currently held (by this instance)."""
        return self._file_lock.is_locked

    @property
    def holder(self) -> Optional[str]:
        """Get the name of the bot currently holding the lock (this instance only)."""
        return self._holder

    def get_lock_status(self) -> dict:
        """
        Get current lock status information.

        Returns:
            Dict with lock status, holder info if available
        """
        holder_info = self._get_holder_info()
        return {
            'is_locked_by_us': self._file_lock.is_locked,
            'our_holder': self._holder,
            'holder_info': holder_info,
            'lock_file_exists': self.lock_path.exists(),
            'info_file_exists': self.lock_info_path.exists()
        }


# Module-level singleton for convenience
_default_lock: Optional[BuzPlaywrightLock] = None


def get_buz_lock(timeout: int = 600) -> BuzPlaywrightLock:
    """
    Get the default Buz Playwright lock instance.

    Args:
        timeout: Lock timeout in seconds (only used on first call).
                 Default: 600 (10 minutes)

    Returns:
        The singleton BuzPlaywrightLock instance
    """
    global _default_lock
    if _default_lock is None:
        _default_lock = BuzPlaywrightLock(timeout=timeout)
    return _default_lock


def get_lock_holder_info() -> Optional[dict]:
    """
    Get info about who currently holds the Buz Playwright lock.

    Useful for checking lock status without creating a lock instance.

    Returns:
        Dict with 'bot', 'acquired_at', 'pid' if lock is held, None otherwise
    """
    try:
        if DEFAULT_LOCK_INFO_PATH.exists():
            return json.loads(DEFAULT_LOCK_INFO_PATH.read_text())
    except Exception:
        pass
    return None


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except OSError:
        return False


def _is_lock_stale(holder_info: dict) -> bool:
    """
    Check if a lock is stale (process dead, or process unknown and too old).

    A lock is stale if:
    - The holding process is no longer running, OR
    - We can't check the PID AND the lock is older than MAX_LOCK_AGE_SECONDS

    If the process IS running, the lock is NEVER stale (even if old).
    """
    pid = holder_info.get('pid')

    # If we have a PID, check if it's running
    if pid:
        if _is_process_running(pid):
            # Process is alive - lock is NOT stale, regardless of age
            return False
        else:
            # Process is dead - lock IS stale
            logger.info(f"Lock held by dead process (PID {pid}) - stale")
            return True

    # No PID available - fall back to age check
    acquired_at_str = holder_info.get('acquired_at')
    if acquired_at_str:
        try:
            acquired_at = datetime.fromisoformat(acquired_at_str)
            age = (datetime.now(timezone.utc) - acquired_at).total_seconds()
            if age > MAX_LOCK_AGE_SECONDS:
                logger.info(f"Lock is {age:.0f}s old (max {MAX_LOCK_AGE_SECONDS}s) with no PID - stale")
                return True
        except (ValueError, TypeError):
            pass

    return False


def _cleanup_stale_lock() -> bool:
    """
    Clean up stale lock files if the lock is stale.

    Returns:
        True if stale lock was cleaned up, False otherwise
    """
    holder_info = get_lock_holder_info()
    if holder_info and _is_lock_stale(holder_info):
        bot = holder_info.get('bot', 'unknown')
        logger.warning(f"Cleaning up stale lock from '{bot}'")
        try:
            if DEFAULT_LOCK_INFO_PATH.exists():
                DEFAULT_LOCK_INFO_PATH.unlink()
            if DEFAULT_LOCK_PATH.exists():
                DEFAULT_LOCK_PATH.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to clean up stale lock: {e}")
    return False


def is_lock_available() -> bool:
    """
    Quick check if the Buz Playwright lock is available.

    This is a non-blocking check - useful for determining whether to
    wait or fail immediately. Automatically cleans up stale locks.

    Returns:
        True if lock appears to be available, False if held
    """
    # Try to clean up stale locks first
    _cleanup_stale_lock()

    # Check if info file exists (indicates lock is held)
    if DEFAULT_LOCK_INFO_PATH.exists():
        return False
    # Also check the actual lock file
    if DEFAULT_LOCK_PATH.exists():
        # Try to acquire with timeout=0 to check availability
        try:
            lock = FileLock(str(DEFAULT_LOCK_PATH))
            lock.acquire(timeout=0)
            lock.release()
            return True
        except Timeout:
            return False
    return True
