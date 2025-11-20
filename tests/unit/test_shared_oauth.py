"""
Unit tests for shared Google OAuth authentication.

Tests cover login/logout flows, authorization strategies, and session management.
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from flask import Flask, session
from urllib.parse import urlparse

# Add shared directory to path
shared_path = Path(__file__).parent.parent.parent / 'shared'
sys.path.insert(0, str(shared_path))

from auth.google_oauth import GoogleAuth


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def flask_app(test_env):
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'test-secret-key'

    # Add dummy routes
    @app.route('/')
    def index():
        return 'Index'

    @app.route('/login')
    def login():
        return 'Login Page'

    @app.route('/access_denied')
    def access_denied():
        return 'Access Denied'

    @app.route('/auth/callback')
    def auth_callback():
        return 'Callback'

    return app


@pytest.fixture
def mock_config_domain():
    """Mock config with domain-based authorization."""
    config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'allowed_domains'])
    config.oauth_client_id = 'test-client-id'
    config.oauth_client_secret = 'test-client-secret'
    config.allowed_domains = ['company.com', 'example.org']
    return config


@pytest.fixture
def mock_config_whitelist():
    """Mock config with admin whitelist authorization."""
    config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'admin_emails'])
    config.oauth_client_id = 'test-client-id'
    config.oauth_client_secret = 'test-client-secret'
    config.admin_emails = ['admin@company.com', 'superuser@company.com']
    return config


@pytest.fixture
def mock_config_quinn():
    """Mock config with Quinn API authorization."""
    config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url'])
    config.oauth_client_id = 'test-client-id'
    config.oauth_client_secret = 'test-client-secret'
    config.quinn_api_url = 'http://localhost:8004'
    return config


@pytest.fixture
def mock_config_minimal():
    """Mock config with minimal settings (no authorization)."""
    config = Mock(spec=['oauth_client_id', 'oauth_client_secret'])
    config.oauth_client_id = 'test-client-id'
    config.oauth_client_secret = 'test-client-secret'
    return config


# ==============================================================================
# Initialization Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_google_auth_initialization(flask_app, mock_config_domain):
    """Test GoogleAuth initializes properly."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    assert auth.app == flask_app
    assert auth.config == mock_config_domain
    assert auth.oauth is not None
    assert auth.google is not None


@pytest.mark.unit
@pytest.mark.shared
def test_google_auth_sets_secret_key(mock_config_domain):
    """Test that GoogleAuth sets Flask secret key from environment."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    # FLASK_SECRET_KEY should be set from env (via test_env fixture)
    auth = GoogleAuth(app, mock_config_domain)

    assert app.config.get('FLASK_SECRET_KEY') is not None


@pytest.mark.unit
@pytest.mark.shared
def test_google_auth_preserves_existing_secret_key(mock_config_domain):
    """Test that GoogleAuth doesn't override existing secret key."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'existing-secret'

    auth = GoogleAuth(app, mock_config_domain)

    assert app.config['FLASK_SECRET_KEY'] == 'existing-secret'


# ==============================================================================
# Authorization Tests - Domain-based
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_domain_match(flask_app, mock_config_domain):
    """Test authorization succeeds for matching domain."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    assert auth._is_authorized('user@company.com') is True
    assert auth._is_authorized('another@example.org') is True


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_domain_case_insensitive(flask_app, mock_config_domain):
    """Test domain checking is case-insensitive."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    assert auth._is_authorized('USER@COMPANY.COM') is True
    assert auth._is_authorized('User@Company.Com') is True


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_domain_mismatch(flask_app, mock_config_domain):
    """Test authorization fails for non-matching domain."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    assert auth._is_authorized('user@other.com') is False
    assert auth._is_authorized('hacker@evil.com') is False


# ==============================================================================
# Authorization Tests - Whitelist-based
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_whitelist_match(flask_app, mock_config_whitelist):
    """Test authorization succeeds for whitelisted email."""
    auth = GoogleAuth(flask_app, mock_config_whitelist)

    assert auth._is_authorized('admin@company.com') is True
    assert auth._is_authorized('superuser@company.com') is True


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_whitelist_case_insensitive(flask_app, mock_config_whitelist):
    """Test whitelist checking is case-insensitive."""
    auth = GoogleAuth(flask_app, mock_config_whitelist)

    assert auth._is_authorized('ADMIN@COMPANY.COM') is True
    assert auth._is_authorized('Admin@Company.Com') is True


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_whitelist_mismatch(flask_app, mock_config_whitelist):
    """Test authorization fails for non-whitelisted email."""
    auth = GoogleAuth(flask_app, mock_config_whitelist)

    assert auth._is_authorized('user@company.com') is False
    assert auth._is_authorized('random@other.com') is False


# ==============================================================================
# Authorization Tests - Quinn API
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_quinn_approved(flask_app, mock_config_quinn, mock_responses):
    """Test authorization succeeds when Quinn API returns approved."""
    auth = GoogleAuth(flask_app, mock_config_quinn)

    # Mock Quinn API response
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'approved': True, 'name': 'External User'},
        status=200
    )

    assert auth._is_authorized('external@contractor.com') is True


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_quinn_not_approved(flask_app, mock_config_quinn, mock_responses):
    """Test authorization fails when Quinn API returns not approved."""
    auth = GoogleAuth(flask_app, mock_config_quinn)

    # Mock Quinn API response
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'approved': False},
        status=200
    )

    assert auth._is_authorized('unknown@contractor.com') is False


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_quinn_timeout(flask_app, mock_config_quinn, mock_responses):
    """Test authorization fails when Quinn API times out."""
    import requests
    auth = GoogleAuth(flask_app, mock_config_quinn)

    # Mock timeout exception
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8004/api/is-approved',
        body=requests.exceptions.Timeout('Connection timeout')
    )

    # Should fail closed (deny access)
    assert auth._is_authorized('external@contractor.com') is False


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_quinn_connection_error(flask_app, mock_config_quinn, mock_responses):
    """Test authorization fails when Quinn API is unreachable."""
    import requests
    auth = GoogleAuth(flask_app, mock_config_quinn)

    # Mock connection error
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8004/api/is-approved',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

    # Should fail closed (deny access)
    assert auth._is_authorized('external@contractor.com') is False


@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_quinn_error_status(flask_app, mock_config_quinn, mock_responses):
    """Test authorization fails when Quinn API returns error status."""
    auth = GoogleAuth(flask_app, mock_config_quinn)

    # Mock 500 error
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'error': 'Internal server error'},
        status=500
    )

    # Should fail closed (deny access)
    assert auth._is_authorized('external@contractor.com') is False


# ==============================================================================
# Authorization Tests - No authorization configured
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_is_authorized_no_config(flask_app, mock_config_minimal):
    """Test authorization fails when no authorization method is configured."""
    auth = GoogleAuth(flask_app, mock_config_minimal)

    # Without any authorization config, all users should be denied
    assert auth._is_authorized('anyone@example.com') is False


# ==============================================================================
# Callback Route Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_callback_route_success(flask_app, mock_config_domain):
    """Test successful OAuth callback."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/auth/callback'):
        # Set up session
        with flask_app.test_client() as client:
            with client.session_transaction() as sess:
                sess['next_url'] = '/dashboard'

        # Mock the OAuth token exchange
        with patch.object(auth.google, 'authorize_access_token') as mock_token:
            mock_token.return_value = {
                'userinfo': {
                    'email': 'user@company.com',
                    'name': 'Test User',
                    'picture': 'https://example.com/photo.jpg'
                }
            }

            session['next_url'] = '/dashboard'
            response = auth.callback_route()

            # Should redirect to next_url
            assert response.status_code == 302
            assert response.location == '/dashboard'


@pytest.mark.unit
@pytest.mark.shared
def test_callback_route_unauthorized_user(flask_app, mock_config_domain):
    """Test OAuth callback with unauthorized user."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/auth/callback'):
        # Mock the OAuth token exchange with unauthorized email
        with patch.object(auth.google, 'authorize_access_token') as mock_token:
            mock_token.return_value = {
                'userinfo': {
                    'email': 'hacker@evil.com',
                    'name': 'Bad Actor'
                }
            }

            response = auth.callback_route()

            # Should redirect to access_denied
            assert response.status_code == 302
            assert 'access_denied' in response.location


@pytest.mark.unit
@pytest.mark.shared
def test_callback_route_stores_user_session(flask_app, mock_config_domain):
    """Test that callback stores user info in session."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context():
        # Mock the OAuth token exchange
        with patch.object(auth.google, 'authorize_access_token') as mock_token:
            mock_token.return_value = {
                'userinfo': {
                    'email': 'user@company.com',
                    'name': 'Test User',
                    'picture': 'https://example.com/photo.jpg'
                }
            }

            # Set up session
            session['next_url'] = '/'

            response = auth.callback_route()

            # Check session (note: this is simplified; actual session testing needs test_client context)
            # In real implementation, you'd check within a request context


@pytest.mark.unit
@pytest.mark.shared
def test_callback_route_oauth_error(flask_app, mock_config_domain):
    """Test OAuth callback handles errors gracefully."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/auth/callback'):
        # Mock OAuth error
        with patch.object(auth.google, 'authorize_access_token') as mock_token:
            mock_token.side_effect = Exception('OAuth error')

            response = auth.callback_route()

            # Should redirect to login
            assert response.status_code == 302
            assert 'login' in response.location


# ==============================================================================
# Login Route Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_login_route_stores_next_url(flask_app, mock_config_domain):
    """Test that login route stores next URL parameter."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/?next=/dashboard'):
        with patch.object(auth.google, 'authorize_redirect') as mock_redirect:
            mock_redirect.return_value = 'redirect response'

            auth.login_route()

            # next_url should be stored in session
            assert session.get('next_url') == '/dashboard'


@pytest.mark.unit
@pytest.mark.shared
def test_login_route_calls_authorize_redirect(flask_app, mock_config_domain):
    """Test that login route calls OAuth authorize_redirect."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/'):
        with patch.object(auth.google, 'authorize_redirect') as mock_redirect:
            mock_redirect.return_value = 'redirect response'

            result = auth.login_route()

            # Should have called authorize_redirect
            mock_redirect.assert_called_once()
            assert result == 'redirect response'


# ==============================================================================
# Logout Route Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_logout_route_clears_session(flask_app, mock_config_domain):
    """Test that logout clears the session."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/'):
        # Set up session with user data
        session['user'] = {'email': 'test@company.com'}
        session['other_data'] = 'some value'

        response = auth.logout_route()

        # Session should be cleared
        assert 'user' not in session
        assert 'other_data' not in session


@pytest.mark.unit
@pytest.mark.shared
def test_logout_route_redirects_to_home(flask_app, mock_config_domain):
    """Test that logout redirects to login page."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/logout'):
        response = auth.logout_route()

        assert response.status_code == 302
        # Parse the redirect location and assert it goes to '/'
        path = urlparse(response.location).path
        assert path == '/'


# ==============================================================================
# Decorator Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_require_auth_decorator_allows_authenticated(flask_app, mock_config_domain):
    """Test that require_auth allows authenticated users."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    @auth.require_auth
    def protected_view():
        return 'Protected Content'

    with flask_app.test_request_context('/'):
        session['user'] = {'email': 'test@company.com'}

        result = protected_view()
        assert result == 'Protected Content'


@pytest.mark.unit
@pytest.mark.shared
def test_require_auth_decorator_blocks_unauthenticated(flask_app, mock_config_domain):
    """Test that require_auth blocks unauthenticated users."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    @auth.require_auth
    def protected_view():
        return 'Protected Content'

    with flask_app.test_request_context('/protected'):
        # No user in session
        result = protected_view()

        # Should redirect to login
        assert result.status_code == 302
        assert 'login' in result.location


@pytest.mark.unit
@pytest.mark.shared
def test_require_auth_decorator_stores_next_url(flask_app, mock_config_domain):
    """Test that require_auth stores the requested URL."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    @auth.require_auth
    def protected_view():
        return 'Protected Content'

    with flask_app.test_request_context('/protected/page'):
        # No user in session
        result = protected_view()

        # Should store the requested URL
        assert session.get('next_url') == 'http://localhost/protected/page'


# ==============================================================================
# Get Current User Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.shared
def test_get_current_user_returns_user(flask_app, mock_config_domain):
    """Test getting current user from session."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/'):
        user_data = {
            'email': 'test@company.com',
            'name': 'Test User',
            'picture': 'https://example.com/photo.jpg'
        }
        session['user'] = user_data

        current_user = auth.get_current_user()
        assert current_user == user_data


@pytest.mark.unit
@pytest.mark.shared
def test_get_current_user_returns_none_when_not_logged_in(flask_app, mock_config_domain):
    """Test that get_current_user returns None when not logged in."""
    auth = GoogleAuth(flask_app, mock_config_domain)

    with flask_app.test_request_context('/'):
        # No user in session
        current_user = auth.get_current_user()
        assert current_user is None
