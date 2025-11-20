"""Unit tests for Banji session manager."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def mock_config():
    """Mock Banji config."""
    config = Mock()
    config.browser_headless = True
    config.browser_default_timeout = 30000
    config.browser_screenshot_on_failure = True
    config.browser_screenshot_dir = "screenshots"
    config.buz_login_timeout = 10000
    config.buz_orgs = {
        'test_org': {
            'name': 'test_org',
            'storage_state_path': '/fake/path/storage_state_test_org.json'
        }
    }
    return config


@pytest.fixture
def mock_org_config():
    """Mock organization config."""
    return {
        'name': 'test_org',
        'storage_state_path': '/fake/path/storage_state_test_org.json'
    }


class TestSessionManager:
    """Test SessionManager class."""

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_create_session(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test creating a new session."""
        from banji.services.session_manager import SessionManager

        # Setup mocks
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value = mock_browser
        mock_login = MagicMock()
        mock_login_page_class.return_value = mock_login

        # Create session manager
        session_mgr = SessionManager(mock_config, session_timeout_minutes=30)

        # Create session
        session = session_mgr.create_session('test_org')

        # Verify
        assert session.session_id is not None
        assert session.org_name == 'test_org'
        assert session_mgr.get_session_count() == 1
        mock_browser.start.assert_called_once()
        mock_login.login.assert_called_once()

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_get_session(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test getting an existing session."""
        from banji.services.session_manager import SessionManager

        # Setup mocks
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value = mock_browser
        mock_login = MagicMock()
        mock_login_page_class.return_value = mock_login

        session_mgr = SessionManager(mock_config)
        session = session_mgr.create_session('test_org')

        # Get the session
        retrieved = session_mgr.get_session(session.session_id)

        assert retrieved.session_id == session.session_id
        assert retrieved.org_name == 'test_org'

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_get_nonexistent_session(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test getting a session that doesn't exist."""
        from banji.services.session_manager import SessionManager

        session_mgr = SessionManager(mock_config)

        with pytest.raises(ValueError, match="Session not found"):
            session_mgr.get_session('nonexistent-id')

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_close_session(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test closing a session."""
        from banji.services.session_manager import SessionManager

        # Setup mocks
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value = mock_browser
        mock_login = MagicMock()
        mock_login_page_class.return_value = mock_login

        session_mgr = SessionManager(mock_config)
        session = session_mgr.create_session('test_org')
        session_id = session.session_id

        # Close the session
        result = session_mgr.close_session(session_id)

        assert result is True
        assert session_mgr.get_session_count() == 0
        mock_browser.close.assert_called_once()

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_session_expiration(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test that expired sessions are detected."""
        from banji.services.session_manager import SessionManager

        # Setup mocks
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value = mock_browser
        mock_login = MagicMock()
        mock_login_page_class.return_value = mock_login

        session_mgr = SessionManager(mock_config, session_timeout_minutes=1)
        session = session_mgr.create_session('test_org')

        # Artificially age the session
        session.last_activity = datetime.now() - timedelta(minutes=2)

        # Try to get it - should raise error
        with pytest.raises(ValueError, match="Session expired"):
            session_mgr.get_session(session.session_id)

    @patch('banji.services.session_manager.LoginPage')
    @patch('banji.services.session_manager.BrowserManager')
    def test_session_touch(self, mock_browser_manager_class, mock_login_page_class, mock_config):
        """Test that getting a session updates its activity timestamp."""
        from banji.services.session_manager import SessionManager

        # Setup mocks
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value = mock_browser
        mock_login = MagicMock()
        mock_login_page_class.return_value = mock_login

        session_mgr = SessionManager(mock_config)
        session = session_mgr.create_session('test_org')

        original_time = session.last_activity

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        # Get the session (should touch it)
        session_mgr.get_session(session.session_id)

        # Timestamp should be updated
        assert session.last_activity > original_time


class TestBrowserSession:
    """Test BrowserSession class."""

    def test_browser_session_creation(self, mock_config, mock_org_config):
        """Test creating a BrowserSession."""
        from banji.services.session_manager import BrowserSession

        mock_browser = Mock()
        mock_browser.page = Mock()

        session = BrowserSession(
            session_id="test-123",
            org_name="test_org",
            org_config=mock_org_config,
            config=mock_config,
            browser_manager=mock_browser
        )

        assert session.session_id == "test-123"
        assert session.org_name == "test_org"
        assert session.current_quote_id is None
        assert session.current_order_pk_id is None

    def test_browser_session_touch(self, mock_config, mock_org_config):
        """Test touching a session updates timestamp."""
        from banji.services.session_manager import BrowserSession

        mock_browser = Mock()
        mock_browser.page = Mock()

        session = BrowserSession(
            session_id="test-123",
            org_name="test_org",
            org_config=mock_org_config,
            config=mock_config,
            browser_manager=mock_browser
        )

        original_time = session.last_activity

        import time
        time.sleep(0.01)

        session.touch()

        assert session.last_activity > original_time

    def test_browser_session_is_expired(self, mock_config, mock_org_config):
        """Test session expiration detection."""
        from banji.services.session_manager import BrowserSession

        mock_browser = Mock()
        mock_browser.page = Mock()

        session = BrowserSession(
            session_id="test-123",
            org_name="test_org",
            org_config=mock_org_config,
            config=mock_config,
            browser_manager=mock_browser
        )

        # Fresh session should not be expired
        assert not session.is_expired(timeout_minutes=30)

        # Age the session
        session.last_activity = datetime.now() - timedelta(minutes=31)

        # Now it should be expired
        assert session.is_expired(timeout_minutes=30)
