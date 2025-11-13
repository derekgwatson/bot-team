"""
Shared pytest fixtures for bot-team tests.

This module provides common fixtures used across all test modules including
Flask app instances, database connections, mocked Google API responses, and
test data factories.
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, Mock
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ==============================================================================
# Environment Setup Fixtures
# ==============================================================================

@pytest.fixture(scope='session')
def test_env():
    """Set up test environment variables."""
    os.environ['TESTING'] = '1'
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-testing-only'
    os.environ['GOOGLE_OAUTH_CLIENT_ID'] = 'test-client-id'
    os.environ['GOOGLE_OAUTH_CLIENT_SECRET'] = 'test-client-secret'
    yield
    # Cleanup
    os.environ.pop('TESTING', None)
    os.environ.pop('FLASK_SECRET_KEY', None)
    os.environ.pop('GOOGLE_OAUTH_CLIENT_ID', None)
    os.environ.pop('GOOGLE_OAUTH_CLIENT_SECRET', None)


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


# ==============================================================================
# Google API Mock Fixtures
# ==============================================================================

@pytest.fixture
def mock_google_credentials():
    """Mock Google API credentials."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.refresh_token = 'mock-refresh-token'
    mock_creds.token = 'mock-access-token'
    return mock_creds


@pytest.fixture
def mock_google_workspace_service():
    """Mock Google Workspace Admin SDK service."""
    mock_service = MagicMock()

    # Mock users().list() response
    mock_service.users().list().execute.return_value = {
        'users': [
            {
                'primaryEmail': 'test@example.com',
                'name': {'fullName': 'Test User'},
                'suspended': False,
                'archived': False
            }
        ]
    }

    # Mock users().get() response
    mock_service.users().get().execute.return_value = {
        'primaryEmail': 'test@example.com',
        'name': {'fullName': 'Test User'},
        'suspended': False,
        'archived': False
    }

    # Mock users().insert() response
    mock_service.users().insert().execute.return_value = {
        'primaryEmail': 'newuser@example.com',
        'name': {'fullName': 'New User'}
    }

    return mock_service


@pytest.fixture
def mock_google_reports_service():
    """Mock Google Reports API service."""
    mock_service = MagicMock()

    mock_service.userUsageReport().get().execute.return_value = {
        'usageReports': [
            {
                'entity': {'userEmail': 'test@example.com'},
                'parameters': [
                    {'name': 'accounts:used_quota_in_mb', 'intValue': '1024'}
                ]
            }
        ]
    }

    return mock_service


@pytest.fixture
def mock_google_sheets_service():
    """Mock Google Sheets API service."""
    mock_service = MagicMock()

    # Mock spreadsheets().values().get() response
    mock_service.spreadsheets().values().get().execute.return_value = {
        'values': [
            ['Name', 'Email', 'Phone', 'Department'],
            ['John Doe', 'john@example.com', '555-0100', 'Engineering'],
            ['Jane Smith', 'jane@example.com', '555-0101', 'Marketing']
        ]
    }

    # Mock spreadsheets().values().append() response
    mock_service.spreadsheets().values().append().execute.return_value = {
        'updates': {'updatedRows': 1}
    }

    return mock_service


@pytest.fixture
def mock_google_groups_service():
    """Mock Google Groups API service."""
    mock_service = MagicMock()

    # Mock members().list() response
    mock_service.members().list().execute.return_value = {
        'members': [
            {
                'email': 'test@example.com',
                'role': 'MEMBER',
                'status': 'ACTIVE'
            }
        ]
    }

    # Mock members().insert() response
    mock_service.members().insert().execute.return_value = {
        'email': 'newmember@example.com',
        'role': 'MEMBER'
    }

    return mock_service


# ==============================================================================
# Test Data Factories
# ==============================================================================

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'email': 'testuser@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password': 'TempPassword123!',
        'org_unit_path': '/',
        'suspended': False
    }


@pytest.fixture
def sample_contact_data():
    """Sample contact data for testing."""
    return {
        'name': 'John Doe',
        'email': 'john.doe@example.com',
        'phone': '555-0100',
        'department': 'Engineering',
        'title': 'Software Engineer'
    }


@pytest.fixture
def sample_external_staff_data():
    """Sample external staff data for testing."""
    return {
        'name': 'External Contractor',
        'email': 'contractor@external.com',
        'phone': '555-0200',
        'role': 'Consultant',
        'status': 'active'
    }


@pytest.fixture
def sample_pending_request_data():
    """Sample pending request data for testing."""
    return {
        'name': 'New External',
        'email': 'new.external@company.com',
        'phone': '555-0300',
        'reason': 'Need access for project work'
    }


# ==============================================================================
# HTTP Mock Fixtures
# ==============================================================================

@pytest.fixture
def mock_responses():
    """Fixture to mock HTTP responses using responses library."""
    import responses as responses_lib
    with responses_lib.RequestsMock() as rsps:
        yield rsps


# ==============================================================================
# Time-related Fixtures
# ==============================================================================

@pytest.fixture
def frozen_time():
    """Fixture to freeze time for testing."""
    from freezegun import freeze_time
    with freeze_time('2025-01-15 10:00:00'):
        yield
