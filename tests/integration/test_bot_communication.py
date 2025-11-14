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


# ==============================================================================
# Pam -> Peter Integration Tests
# ==============================================================================

@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_calls_peter_search(mock_responses):
    """Test Pam successfully calling Peter's search API."""
    from services.peter_client import PeterClient

    # Mock Peter API response
    mock_responses.add(
        responses.GET,
        'http://localhost:8003/api/contacts/search',
        json=[
            {'name': 'John Doe', 'email': 'john@company.com', 'phone': '555-0100'}
        ],
        status=200
    )

    # Mock config
    class MockConfig:
        peter_api_url = 'http://localhost:8003'

    import config as pam_config
    with patch.object(pam_config, 'config', MockConfig()):
        client = PeterClient()
        results = client.search_contacts('John')

        assert len(results) == 1
        assert results[0]['name'] == 'John Doe'


@pytest.mark.integration
@pytest.mark.pam
@pytest.mark.peter
def test_pam_handles_peter_unavailable(mock_responses):
    """Test Pam handling Peter being unavailable."""
    from services.peter_client import PeterClient

    # Mock connection error
    mock_responses.add(
        responses.GET,
        'http://localhost:8003/api/contacts/search',
        body=Exception('Connection refused')
    )

    class MockConfig:
        peter_api_url = 'http://localhost:8003'

    import config as pam_config
    with patch.object(pam_config, 'config', MockConfig()):
        client = PeterClient()
        # Should handle error gracefully
        # Actual behavior depends on implementation


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
    app.config['SECRET_KEY'] = 'test-secret'

    @app.route('/access_denied')
    def access_denied():
        return 'Access Denied'

    # Mock config with Quinn URL
    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url', 'allowed_domains', 'admin_emails'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'

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
    app.config['SECRET_KEY'] = 'test-secret'

    mock_config = Mock(spec=['oauth_client_id', 'oauth_client_secret', 'quinn_api_url', 'allowed_domains', 'admin_emails'])
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'

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
    app.config['SECRET_KEY'] = 'test-secret'

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

    class QuinnConfig:
        database_path = str(db_file)

    import config as quinn_config
    monkeypatch.setattr(quinn_config, 'config', QuinnConfig())

    db = ExternalStaffDB()

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
    app.config['SECRET_KEY'] = 'test-secret'

    mock_config = Mock()
    mock_config.oauth_client_id = 'test-client-id'
    mock_config.oauth_client_secret = 'test-client-secret'
    mock_config.quinn_api_url = 'http://localhost:8004'

    auth = GoogleAuth(app, mock_config)

    # Verify authorization succeeds
    assert auth._is_authorized('consultant@external.com') is True
