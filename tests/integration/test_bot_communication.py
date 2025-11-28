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

# Add project root to path
project_root = Path(__file__).parent.parent.parent
quinn_path = project_root / 'quinn'
pam_path = project_root / 'pam'
shared_path = project_root / 'shared'

# Set environment variables before any imports
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['BOT_API_KEY'] = 'test-api-key'
os.environ['CHESTER_API_URL'] = 'http://localhost:8008'

# Clear any cached config and set up pam's path BEFORE loading the module
if 'config' in sys.modules:
    del sys.modules['config']
sys.path.insert(0, str(pam_path))
sys.path.insert(0, str(shared_path))
sys.path.insert(0, str(project_root))

# Load PeterClient using importlib to avoid conflicts
spec = importlib.util.spec_from_file_location(
    "pam_peter_client",
    pam_path / "services" / "peter_client.py"
)
peter_client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peter_client_module)
PeterClient = peter_client_module.PeterClient


# ==============================================================================
# Pam -> Peter Integration Tests
# ==============================================================================

@pytest.fixture
def pam_config_for_test():
    """Set up Pam's config with proper module isolation.

    Note: PeterClient was loaded via importlib at module level, so it already
    has a reference to 'config' from that load. We need to patch the config
    that peter_client_module is actually using.
    """
    # Get the config object that peter_client_module is using
    # (it imported config when exec_module ran)
    config_obj = peter_client_module.config

    # Pre-populate Chester's bot URL cache to avoid hitting Chester API
    config_obj._bot_url_cache['peter'] = 'http://localhost:8003'

    yield config_obj

    # Clean up cache after test
    config_obj._bot_url_cache.clear()


@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_calls_peter_search(mock_responses, pam_config_for_test):
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

    client = PeterClient()
    results = client.search_contacts('John')

    assert len(results) == 1
    assert results[0]['name'] == 'John Doe'


@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_handles_peter_unavailable(mock_responses, pam_config_for_test):
    """Test Pam handling Peter being unavailable."""
    # Mock connection error by raising ConnectionError
    import requests.exceptions
    mock_responses.add(
        responses.GET,
        'http://localhost:8003/api/contacts/search',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

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
    # Load Quinn's database module using importlib to avoid path conflicts
    quinn_db_path = project_root / 'quinn' / 'database' / 'db.py'
    spec = importlib.util.spec_from_file_location('quinn_db_module', quinn_db_path)
    quinn_db_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quinn_db_module)
    ExternalStaffDB = quinn_db_module.ExternalStaffDB

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
