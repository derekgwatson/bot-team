"""
Unit tests for Pam's Peter API client.

Tests cover bot-to-bot communication and error handling.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import requests
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent.parent
pam_path = project_root / 'pam'

# Set environment variables before any imports
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['BOT_API_KEY'] = 'test-api-key'
os.environ['CHESTER_API_URL'] = 'http://localhost:8008'

# Clear any cached config and set up pam's path BEFORE loading the module
if 'config' in sys.modules:
    del sys.modules['config']
sys.path.insert(0, str(pam_path))
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
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_config(monkeypatch):
    """Mock Pam's config - patch the config that peter_client_module already imported."""
    # Get the config object that peter_client_module is using
    # (it imported config when exec_module ran)
    config_obj = peter_client_module.config

    # Pre-populate Chester's bot URL cache to avoid hitting Chester API
    config_obj._bot_url_cache['peter'] = 'http://localhost:8003'

    # Patch the endpoints
    monkeypatch.setattr(config_obj, 'peter_contacts_endpoint', '/api/contacts')
    monkeypatch.setattr(config_obj, 'peter_search_endpoint', '/api/contacts/search')

    yield config_obj


@pytest.fixture
def peter_client(mock_config):
    """Create a PeterClient instance."""
    return PeterClient()


# ==============================================================================
# Search Contacts Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.pam
def test_search_contacts_success(peter_client, mock_responses):
    """Test successfully searching contacts via Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts/search',
        json={
            'results': [
                {'name': 'John Doe', 'email': 'john@example.com', 'phone': '555-0100'},
                {'name': 'Jane Doe', 'email': 'jane@example.com', 'phone': '555-0101'}
            ],
            'count': 2,
            'query': 'Doe'
        },
        status=200
    )

    results = peter_client.search_contacts('Doe')

    assert len(results) == 2
    assert results[0]['name'] == 'John Doe'


@pytest.mark.unit
@pytest.mark.pam
def test_search_contacts_connection_error(peter_client, mock_responses):
    """Test handling connection errors when calling Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts/search',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

    result = peter_client.search_contacts('test')

    assert 'error' in result or result == []


@pytest.mark.unit
@pytest.mark.pam
def test_search_contacts_timeout(peter_client, mock_responses):
    """Test handling timeout when calling Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts/search',
        body=requests.exceptions.Timeout('Request timeout')
    )

    result = peter_client.search_contacts('test')

    assert 'error' in result or result == []


@pytest.mark.unit
@pytest.mark.pam
def test_search_contacts_error_status(peter_client, mock_responses):
    """Test handling error status codes from Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts/search',
        json={'error': 'Internal server error'},
        status=500
    )

    result = peter_client.search_contacts('test')

    assert 'error' in result or result == []


# ==============================================================================
# Get All Contacts Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.pam
def test_get_all_contacts_success(peter_client, mock_responses):
    """Test successfully getting all contacts via Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts',
        json={
            'contacts': [
                {'name': 'Contact 1', 'email': 'c1@example.com'},
                {'name': 'Contact 2', 'email': 'c2@example.com'}
            ],
            'count': 2
        },
        status=200
    )

    contacts = peter_client.get_all_contacts()

    assert len(contacts) == 2


@pytest.mark.unit
@pytest.mark.pam
def test_get_all_contacts_empty(peter_client, mock_responses):
    """Test getting empty contact list from Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts',
        json={
            'contacts': [],
            'count': 0
        },
        status=200
    )

    contacts = peter_client.get_all_contacts()

    assert contacts == []


# ==============================================================================
# Error Handling Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.pam
def test_handles_malformed_json(peter_client, mock_responses):
    """Test handling malformed JSON responses from Peter API."""
    mock_responses.add(
        mock_responses.GET,
        'http://localhost:8003/api/contacts',
        body='invalid json{',
        status=200
    )

    result = peter_client.get_all_contacts()

    # Should handle gracefully
    assert 'error' in result or result == []


@pytest.mark.unit
@pytest.mark.pam
def test_handles_network_issues(peter_client):
    """Test handling various network issues."""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError('Network unreachable')

        result = peter_client.search_contacts('test')

        # Should fail gracefully
        assert 'error' in result or result == []
