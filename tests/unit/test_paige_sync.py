"""
Tests for Paige sync service.

These tests verify the login generation, email selection, and sync logic
for keeping DokuWiki users in sync with Peter staff directory.

Note: Tests are skipped if requests module is unavailable (CI environment).
"""
import pytest
from unittest.mock import MagicMock
import sys
from pathlib import Path
import re

# Set environment variables before importing modules
import os
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['BOT_API_KEY'] = 'test-api-key'

project_root = Path(__file__).parent.parent.parent
paige_path = project_root / 'paige'

# Check if required dependencies are available
try:
    import requests
    import yaml
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False

# Skip all tests in this module if deps not available
pytestmark = pytest.mark.skipif(
    not DEPS_AVAILABLE,
    reason="Required dependencies (requests, yaml) not available"
)


# Create a simple WikiUser class for testing
class WikiUser:
    """Test version of WikiUser."""
    def __init__(self, login, name, email, groups):
        self.login = login
        self.name = name
        self.email = email
        self.groups = groups

    def to_dict(self):
        return {
            'login': self.login,
            'name': self.name,
            'email': self.email,
            'groups': self.groups,
        }


# Lazy loading of sync service
_sync_service_class = None


def get_sync_service_class():
    """Get the SyncService class, loading if needed."""
    global _sync_service_class
    if _sync_service_class is None:
        # Setup paths
        paige_str = str(paige_path)
        project_str = str(project_root)
        if paige_str not in sys.path:
            sys.path.insert(0, paige_str)
        if project_str not in sys.path:
            sys.path.insert(0, project_str)

        # Import the module
        from paige.services.sync_service import SyncService
        _sync_service_class = SyncService
    return _sync_service_class


class TestSyncServiceLoginGeneration:
    """Tests for login generation from names."""

    def test_simple_name(self):
        """Test simple two-part name."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        assert service._generate_login("John Smith") == "john.smith"

    def test_three_part_name(self):
        """Test three-part name."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        assert service._generate_login("John van Smith") == "john.van.smith"

    def test_name_with_special_chars(self):
        """Test name with special characters."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        assert service._generate_login("John O'Smith") == "john.osmith"

    def test_single_name(self):
        """Test single name."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        assert service._generate_login("John") == "john"

    def test_empty_name(self):
        """Test empty name returns empty string."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        assert service._generate_login("") == ""

    def test_name_with_hyphen(self):
        """Test name with hyphen."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)
        # Hyphens are removed within name parts
        assert service._generate_login("Mary-Jane Watson") == "maryjane.watson"


class TestSyncServiceEmailSelection:
    """Tests for email selection logic."""

    def test_google_user_gets_primary_email(self):
        """Staff with Google access should use google_primary_email."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)

        staff = {
            'google_access': 1,
            'google_primary_email': 'john.smith@watson.com',
            'work_email': 'john@watson.com',
            'personal_email': 'john@gmail.com'
        }

        assert service._get_email_for_staff(staff) == 'john.smith@watson.com'

    def test_non_google_user_gets_work_email(self):
        """Staff without Google access should use work_email first."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)

        staff = {
            'google_access': 0,
            'google_primary_email': '',
            'work_email': 'john@watson.com',
            'personal_email': 'john@gmail.com'
        }

        assert service._get_email_for_staff(staff) == 'john@watson.com'

    def test_non_google_user_falls_back_to_personal_email(self):
        """Staff without Google or work email should use personal_email."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)

        staff = {
            'google_access': 0,
            'google_primary_email': '',
            'work_email': '',
            'personal_email': 'john@gmail.com'
        }

        assert service._get_email_for_staff(staff) == 'john@gmail.com'

    def test_missing_email_returns_empty(self):
        """Missing email fields should return empty string."""
        SyncService = get_sync_service_class()
        mock_wiki = MagicMock()
        service = SyncService(mock_wiki)

        staff = {
            'google_access': 0,
            'google_primary_email': None,
            'work_email': None,
            'personal_email': None
        }

        assert service._get_email_for_staff(staff) == ''


class TestSyncServiceSync:
    """Tests for the main sync logic."""

    def test_adds_missing_users(self):
        """Test that users in Peter but not wiki are added."""
        SyncService = get_sync_service_class()

        # Mock wiki service
        mock_wiki = MagicMock()
        mock_wiki.get_all_users.return_value = []  # No existing users
        mock_wiki.add_user.return_value = {
            'success': True,
            'user': {'login': 'john.smith', 'name': 'John Smith', 'email': 'john.smith@watson.com'}
        }

        service = SyncService(mock_wiki)

        # Mock the peter client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'staff': [
                {
                    'name': 'John Smith',
                    'google_access': 1,
                    'google_primary_email': 'john.smith@watson.com',
                    'wiki_access': 1
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.sync()

        assert result['success'] is True
        assert len(result['added']) == 1
        assert result['added'][0]['login'] == 'john.smith'
        mock_wiki.add_user.assert_called_once_with(
            login='john.smith',
            name='John Smith',
            email='john.smith@watson.com'
        )

    def test_removes_departed_users(self):
        """Test that users in wiki but not Peter are removed."""
        SyncService = get_sync_service_class()

        # Mock wiki service - has one user
        mock_wiki = MagicMock()
        existing_user = WikiUser(
            login='john.smith',
            name='John Smith',
            email='john.smith@watson.com',
            groups=['user', 'google']
        )
        mock_wiki.get_all_users.return_value = [existing_user]
        mock_wiki.remove_user.return_value = {
            'success': True,
            'removed_user': existing_user.to_dict()
        }

        service = SyncService(mock_wiki)

        # Mock Peter response - no staff
        mock_response = MagicMock()
        mock_response.json.return_value = {'staff': []}
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.sync()

        assert result['success'] is True
        assert len(result['removed']) == 1
        assert result['removed'][0]['login'] == 'john.smith'
        mock_wiki.remove_user.assert_called_once_with('john.smith')

    def test_skips_admin_users(self):
        """Test that admin users are never removed."""
        SyncService = get_sync_service_class()

        # Mock wiki service - has one admin user
        mock_wiki = MagicMock()
        admin_user = WikiUser(
            login='admin.user',
            name='Admin User',
            email='admin@watson.com',
            groups=['user', 'google', 'admin']
        )
        mock_wiki.get_all_users.return_value = [admin_user]

        service = SyncService(mock_wiki)

        # Mock Peter response - no staff
        mock_response = MagicMock()
        mock_response.json.return_value = {'staff': []}
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.sync()

        assert result['success'] is True
        assert len(result['removed']) == 0
        assert len(result['skipped_admins']) == 1
        assert 'admin.user' in result['skipped_admins']
        mock_wiki.remove_user.assert_not_called()

    def test_skips_existing_users(self):
        """Test that existing users are not re-added."""
        SyncService = get_sync_service_class()

        # Mock wiki service - user already exists
        mock_wiki = MagicMock()
        existing_user = WikiUser(
            login='john.smith',
            name='John Smith',
            email='john.smith@watson.com',
            groups=['user', 'google']
        )
        mock_wiki.get_all_users.return_value = [existing_user]

        service = SyncService(mock_wiki)

        # Mock Peter response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'staff': [
                {
                    'name': 'John Smith',
                    'google_access': 1,
                    'google_primary_email': 'john.smith@watson.com',
                    'wiki_access': 1
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.sync()

        assert result['success'] is True
        assert len(result['added']) == 0
        assert len(result['removed']) == 0
        mock_wiki.add_user.assert_not_called()
        mock_wiki.remove_user.assert_not_called()

    def test_handles_staff_without_email(self):
        """Test that staff without valid email are reported as errors."""
        SyncService = get_sync_service_class()

        mock_wiki = MagicMock()
        mock_wiki.get_all_users.return_value = []

        service = SyncService(mock_wiki)

        # Mock Peter response - staff with no email
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'staff': [
                {
                    'name': 'John Smith',
                    'google_access': 0,
                    'google_primary_email': '',
                    'personal_email': '',
                    'wiki_access': 1
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.sync()

        assert len(result['errors']) == 1
        assert 'No email' in result['errors'][0]


class TestSyncServicePreview:
    """Tests for the preview functionality."""

    def test_preview_shows_additions(self):
        """Test that preview shows what would be added."""
        SyncService = get_sync_service_class()

        mock_wiki = MagicMock()
        mock_wiki.get_all_users.return_value = []

        service = SyncService(mock_wiki)

        # Mock Peter response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'staff': [
                {
                    'name': 'John Smith',
                    'google_access': 1,
                    'google_primary_email': 'john.smith@watson.com',
                    'wiki_access': 1
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.preview()

        assert len(result['would_add']) == 1
        assert result['would_add'][0]['login'] == 'john.smith'
        # Preview should not call add_user
        mock_wiki.add_user.assert_not_called()

    def test_preview_shows_removals(self):
        """Test that preview shows what would be removed."""
        SyncService = get_sync_service_class()

        mock_wiki = MagicMock()
        existing_user = WikiUser(
            login='john.smith',
            name='John Smith',
            email='john.smith@watson.com',
            groups=['user', 'google']
        )
        mock_wiki.get_all_users.return_value = [existing_user]

        service = SyncService(mock_wiki)

        mock_response = MagicMock()
        mock_response.json.return_value = {'staff': []}
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.preview()

        assert len(result['would_remove']) == 1
        assert result['would_remove'][0]['login'] == 'john.smith'
        # Preview should not call remove_user
        mock_wiki.remove_user.assert_not_called()

    def test_preview_shows_skipped_admins(self):
        """Test that preview shows admins that would be skipped."""
        SyncService = get_sync_service_class()

        mock_wiki = MagicMock()
        admin_user = WikiUser(
            login='admin.user',
            name='Admin User',
            email='admin@watson.com',
            groups=['user', 'google', 'admin']
        )
        mock_wiki.get_all_users.return_value = [admin_user]

        service = SyncService(mock_wiki)

        mock_response = MagicMock()
        mock_response.json.return_value = {'staff': []}
        mock_response.raise_for_status = MagicMock()
        service._peter_client = MagicMock()
        service._peter_client.get.return_value = mock_response

        result = service.preview()

        assert len(result['would_remove']) == 0
        assert len(result['would_skip_admins']) == 1
        assert 'admin.user' in result['would_skip_admins']
