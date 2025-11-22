"""
Integration tests for bot-to-bot communication.

Tests cover inter-service API calls and authorization checks.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from flask import Flask
import responses
import importlib.util

# Add paths for multiple bots
project_root = Path(__file__).parent.parent.parent
quinn_path = project_root / 'quinn'
pam_path = project_root / 'pam'
shared_path = project_root / 'shared'

# Add bot directories
if str(quinn_path) not in sys.path:
    sys.path.insert(0, str(quinn_path))
if str(pam_path) not in sys.path:
    sys.path.insert(0, str(pam_path))
if str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

# Add project root for imports
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import Pam's peter_client using importlib for Windows compatibility
try:
    from services.peter_client import PeterClient
except (ImportError, AttributeError) as e:
    # Fallback for Windows: use importlib to load module directly
    spec = importlib.util.spec_from_file_location(
        "peter_client",
        pam_path / "services" / "peter_client.py"
    )
    if spec and spec.loader:
        peter_client_module = importlib.util.module_from_spec(spec)
        sys.modules['peter_client'] = peter_client_module
        spec.loader.exec_module(peter_client_module)
        PeterClient = peter_client_module.PeterClient
    else:
        raise ImportError(f"Could not import PeterClient: {e}")


# ==============================================================================
# Pam -> Peter Integration Tests
# ==============================================================================

@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_calls_peter_search(mock_responses):
    """Test Pam successfully calling Peter's search API."""
    # Mock Peter API response (proper format with 'results' key)
    mock_responses.add(
        responses.GET,
        'http://localhost:8003/api/contacts/search',
        json={
            'results': [
                {'name': 'John Doe', 'email': 'john@company.com', 'phone': '555-0100'}
            ],
            'count': 1,
            'query': 'John'
        },
        status=200
    )

    # Pre-populate Chester's cache to avoid calling Chester API
    import config as pam_config
    pam_config.config._bot_url_cache['peter'] = 'http://localhost:8003'

    client = PeterClient()
    results = client.search_contacts('John')

    assert len(results) == 1
    assert results[0]['name'] == 'John Doe'


@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_handles_peter_unavailable(mock_responses):
    """Test Pam handling Peter being unavailable."""
    # Mock connection error by raising ConnectionError
    import requests.exceptions
    mock_responses.add(
        responses.GET,
        'http://localhost:8003/api/contacts/search',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

    # Pre-populate Chester's cache to avoid calling Chester API
    import config as pam_config
    pam_config.config._bot_url_cache['peter'] = 'http://localhost:8003'

    client = PeterClient()
    # Should handle error gracefully and return error dict
    result = client.search_contacts('test')
    assert 'error' in result
    assert 'Could not connect to Peter' in result['error']


# ==============================================================================
# Shared Auth -> Quinn Integration Tests
# ==============================================================================

@pytest.mark.integration
@pytest.mark.shared
@pytest.mark.quinn
def test_oauth_checks_quinn_for_external_approval(mock_responses, test_env):
    """Test that shared OAuth checks Quinn for external staff approval."""
    from auth.google_oauth import GoogleAuth

    # Create Flask app
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'test-secret'
    app.secret_key = 'test-secret'

    @app.route('/access_denied')
    def access_denied():
        return 'Access Denied'

    # Mock config with Quinn URL
    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url', 'allowed_domains', 'admin_emails'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'
    mock_config.allowed_domains = []
    mock_config.admin_emails = []

    # Mock Quinn API response - approved
    mock_responses.add(
        responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'approved': True, 'name': 'External User'},
        status=200
    )

    auth = GoogleAuth(app, mock_config)

    # Should authorize external user approved by Quinn
    assert auth._is_authorized('external@contractor.com') is True


@pytest.mark.integration
@pytest.mark.shared
@pytest.mark.quinn
def test_oauth_handles_quinn_unavailable(mock_responses, test_env):
    """Test that shared OAuth fails closed when Quinn is unavailable."""
    from auth.google_oauth import GoogleAuth

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'test-secret'
    app.secret_key = 'test-secret'

    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url', 'allowed_domains', 'admin_emails'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'
    mock_config.allowed_domains = []
    mock_config.admin_emails = []

    # Mock Quinn being unavailable
    import requests
    mock_responses.add(
        responses.GET,
        'http://localhost:8004/api/is-approved',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

    auth = GoogleAuth(app, mock_config)

    # Should fail closed (deny access) when Quinn is unreachable
    assert auth._is_authorized('external@contractor.com') is False


@pytest.mark.integration
@pytest.mark.shared
@pytest.mark.quinn
def test_oauth_combines_domain_and_quinn_checks(mock_responses, test_env):
    """Test that OAuth can authorize via either domain OR Quinn approval."""
    from auth.google_oauth import GoogleAuth

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'test-secret'
    app.secret_key = 'test-secret'

    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'allowed_domains', 'admin_emails', 'quinn_api_url'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.allowed_domains = ['company.com']
    mock_config.admin_emails = []
    mock_config.quinn_api_url = 'http://localhost:8004'

    # Mock Quinn response for external user
    mock_responses.add(
        responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'approved': True},
        status=200
    )

    auth = GoogleAuth(app, mock_config)

    # Domain user should be authorized (without calling Quinn)
    assert auth._is_authorized('employee@company.com') is True

    # External user should be authorized via Quinn
    assert auth._is_authorized('contractor@external.com') is True


# ==============================================================================
# Multi-Bot Authorization Flow
# ==============================================================================

@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.slow
def test_end_to_end_external_access_flow(mock_responses, tmp_path, monkeypatch, test_env):
    """Test complete flow: request -> approve in Quinn -> access granted via OAuth."""
    # Set up Quinn database
    from database.db import ExternalStaffDB

    db_file = tmp_path / 'test_e2e.db'

    # Create database with explicit path (no need to mock config)
    db = ExternalStaffDB(db_path=str(db_file))

    # Step 1: External user submits request
    req_id = db.submit_request(
        name='External Consultant',
        email='consultant@external.com',
        phone='555-9999'
    )['id']

    # Step 2: Admin approves in Quinn
    db.approve_request(req_id, reviewed_by='admin@company.com')

    # Step 3: Mock Quinn API endpoint
    mock_responses.add(
        responses.GET,
        'http://localhost:8004/api/is-approved',
        json={'approved': True, 'name': 'External Consultant'},
        status=200
    )

    # Step 4: Shared auth checks Quinn and authorizes
    from auth.google_oauth import GoogleAuth

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['FLASK_SECRET_KEY'] = 'test-secret'
    app.secret_key = 'test-secret'

    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url', 'allowed_domains', 'admin_emails'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'
    mock_config.allowed_domains = []
    mock_config.admin_emails = []

    auth = GoogleAuth(app, mock_config)

    # Verify authorization succeeds
    assert auth._is_authorized('consultant@external.com') is True
