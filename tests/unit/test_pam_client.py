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

# Add pam directory to path
pam_path = Path(__file__).parent.parent.parent / 'pam'
sys.path.insert(0, str(pam_path))

from services.peter_client import PeterClient


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_config(monkeypatch):
    """Mock Pam's config."""
    class MockConfig:
        peter_api_url = 'http://localhost:8003'

    import config as pam_config
    monkeypatch.setattr(pam_config, 'config', MockConfig())

    return MockConfig()


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
        json=[
            {'name': 'John Doe', 'email': 'john@example.com', 'phone': '555-0100'},
            {'name': 'Jane Doe', 'email': 'jane@example.com', 'phone': '555-0101'}
        ],
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
        json=[
            {'name': 'Contact 1', 'email': 'c1@example.com'},
            {'name': 'Contact 2', 'email': 'c2@example.com'}
        ],
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
        json=[],
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
