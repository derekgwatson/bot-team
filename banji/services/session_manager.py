"""Session manager for maintaining browser state across API calls."""
import uuid
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from .browser import BrowserManager
from .quotes.login_page import LoginPage
from .quotes.quote_page import QuotePage

logger = logging.getLogger(__name__)


class BrowserSession:
    """Represents an active browser session."""

    def __init__(self, session_id: str, org_name: str, org_config: dict, config, browser_manager: BrowserManager):
        self.session_id = session_id
        self.org_name = org_name
        self.org_config = org_config
        self.config = config
        self.browser_manager = browser_manager
        self.quote_page = QuotePage(browser_manager.page, config, org_config)
        self.last_activity = datetime.now()
        self.created_at = datetime.now()
        self.current_quote_id = None
        self.current_order_pk_id = None

    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if session has expired due to inactivity."""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)

    def close(self):
        """Close the browser session."""
        try:
            logger.info(f"Closing browser session {self.session_id}")
            self.browser_manager.close()
        except Exception as e:
            logger.error(f"Error closing session {self.session_id}: {e}")


class SessionManager:
    """
    Manages browser sessions for API requests.

    Thread-safe session store that maintains browser instances across multiple API calls.
    Automatically cleans up expired sessions.
    """

    def __init__(self, config, session_timeout_minutes: int = 30):
        """
        Initialize session manager.

        Args:
            config: Banji config object
            session_timeout_minutes: Minutes of inactivity before session expires
        """
        self.config = config
        self.session_timeout_minutes = session_timeout_minutes
        self.sessions: Dict[str, BrowserSession] = {}
        self.lock = threading.RLock()
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background thread to clean up expired sessions."""
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                try:
                    self.cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
                # Check every 5 minutes
                self._stop_cleanup.wait(300)

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Session cleanup thread started")

    def create_session(self, org_name: str) -> BrowserSession:
        """
        Create a new browser session for an organization.

        Args:
            org_name: Name of the organization (e.g., 'designer_drapes')

        Returns:
            BrowserSession: The created session

        Raises:
            ValueError: If org_name is invalid
        """
        logger.info(f"Creating new browser session for org: {org_name}")

        # Get org config
        org_config = self.config.get_org_config(org_name)

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Start browser
        browser_manager = BrowserManager(self.config, org_config)
        browser_manager.start()

        # Verify authentication
        login_page = LoginPage(browser_manager.page, self.config, org_config)
        login_page.login()

        # Create session
        session = BrowserSession(
            session_id=session_id,
            org_name=org_name,
            org_config=org_config,
            config=self.config,
            browser_manager=browser_manager
        )

        # Store session
        with self.lock:
            self.sessions[session_id] = session

        logger.info(f"Browser session created: {session_id} for org: {org_name}")
        logger.info(f"Active sessions: {len(self.sessions)}")

        return session

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """
        Get an existing session by ID.

        Args:
            session_id: The session ID

        Returns:
            BrowserSession or None if not found

        Raises:
            ValueError: If session expired or not found
        """
        with self.lock:
            session = self.sessions.get(session_id)

            if not session:
                raise ValueError(f"Session not found: {session_id}")

            if session.is_expired(self.session_timeout_minutes):
                # Clean up expired session
                logger.warning(f"Session {session_id} expired, removing")
                self.close_session(session_id)
                raise ValueError(f"Session expired: {session_id}")

            # Update activity timestamp
            session.touch()
            return session

    def close_session(self, session_id: str) -> bool:
        """
        Close and remove a session.

        Args:
            session_id: The session ID to close

        Returns:
            bool: True if session was closed, False if not found
        """
        with self.lock:
            session = self.sessions.pop(session_id, None)

            if session:
                session.close()
                logger.info(f"Session closed: {session_id}")
                logger.info(f"Active sessions: {len(self.sessions)}")
                return True

            return False

    def cleanup_expired_sessions(self):
        """Remove all expired sessions."""
        with self.lock:
            expired = [
                sid for sid, session in self.sessions.items()
                if session.is_expired(self.session_timeout_minutes)
            ]

            for session_id in expired:
                logger.info(f"Cleaning up expired session: {session_id}")
                self.close_session(session_id)

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")

    def close_all_sessions(self):
        """Close all active sessions (for shutdown)."""
        with self.lock:
            session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                self.close_session(session_id)

            logger.info("All sessions closed")

    def get_session_count(self) -> int:
        """Get count of active sessions."""
        with self.lock:
            return len(self.sessions)

    def shutdown(self):
        """Shutdown the session manager."""
        logger.info("Shutting down session manager")
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self.close_all_sessions()


# Global session manager instance (initialized in app.py)
session_manager: Optional[SessionManager] = None


def init_session_manager(config, session_timeout_minutes: int = 30):
    """Initialize the global session manager."""
    global session_manager
    session_manager = SessionManager(config, session_timeout_minutes)
    logger.info("Session manager initialized")
    return session_manager


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    if session_manager is None:
        raise RuntimeError("Session manager not initialized")
    return session_manager
