"""
Unit tests for Fred's Google Workspace service.

Tests cover user CRUD operations and error handling with mocked Google API.
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from googleapiclient.errors import HttpError
import importlib.util

# Add fred directory to path
project_root = Path(__file__).parent.parent.parent
fred_path = project_root / 'fred'

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'

# Clear any cached config and set up fred's path BEFORE loading the module
if 'config' in sys.modules:
    del sys.modules['config']
sys.path.insert(0, str(fred_path))
sys.path.insert(0, str(project_root))

# Load the service using importlib
spec = importlib.util.spec_from_file_location(
    "fred_google_workspace",
    fred_path / "services" / "google_workspace.py"
)
google_workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(google_workspace)
GoogleWorkspaceService = google_workspace.GoogleWorkspaceService


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_config(monkeypatch, tmp_path):
    """Mock Fred's config with test credentials."""
    # Create a dummy credentials file
    creds_file = tmp_path / 'service_account.json'
    creds_file.write_text('{"type": "service_account"}')

    class MockConfig:
        google_credentials_file = str(creds_file)
        google_admin_email = 'admin@company.com'
        google_domain = 'example.com'

    mock_config_obj = MockConfig()

    # Patch where the config is USED (using already-imported module)
    monkeypatch.setattr(google_workspace, 'config', mock_config_obj)

    return mock_config_obj


@pytest.fixture
def workspace_service_with_mock(mock_config, mock_google_workspace_service):
    """Create a GoogleWorkspaceService instance with mocked Google API."""
    with patch.object(google_workspace, 'service_account'), \
         patch.object(google_workspace, 'build', return_value=mock_google_workspace_service):
        service = GoogleWorkspaceService()
        return service


@pytest.fixture
def workspace_service_uninitialized(monkeypatch):
    """Create a GoogleWorkspaceService instance that fails to initialize."""
    # Mock config with non-existent credentials file
    class MockConfig:
        google_credentials_file = '/nonexistent/credentials.json'
        google_admin_email = 'admin@company.com'
        google_domain = 'example.com'

    # Patch where the config is USED (using already-imported module)
    monkeypatch.setattr(google_workspace, 'config', MockConfig())

    service = GoogleWorkspaceService()
    return service


# ==============================================================================
# Initialization Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_initialization_success(mock_config, mock_google_workspace_service):
    """Test successful service initialization."""
    # Use the already-loaded google_workspace module
    with patch.object(google_workspace, 'service_account') as mock_sa, \
         patch.object(google_workspace, 'build', return_value=mock_google_workspace_service):
        mock_creds = Mock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds
        mock_creds.with_subject.return_value = mock_creds

        service = GoogleWorkspaceService()

        assert service.service is not None
        assert service.credentials is not None


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_initialization_missing_credentials(workspace_service_uninitialized):
    """Test initialization with missing credentials file."""
    service = workspace_service_uninitialized

    # Service should not be initialized
    assert service.service is None


# ==============================================================================
# list_users() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_list_users_success(workspace_service_with_mock):
    """Test listing users successfully."""
    users = workspace_service_with_mock.list_users()

    assert isinstance(users, list)
    assert len(users) > 0
    assert users[0]['email'] == 'test@example.com'
    assert 'full_name' in users[0]


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_list_users_archived_filter(workspace_service_with_mock, mock_google_workspace_service):
    """Test listing only archived users."""
    # Set up mock for archived users
    mock_google_workspace_service.users().list().execute.return_value = {
        'users': [
            {
                'primaryEmail': 'archived@example.com',
                'name': {'fullName': 'Archived User', 'givenName': 'Archived', 'familyName': 'User'},
                'archived': True,
                'suspended': True
            }
        ]
    }

    users = workspace_service_with_mock.list_users(archived=True)

    assert isinstance(users, list)
    assert len(users) == 1
    assert users[0]['archived'] is True


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_list_users_empty_result(workspace_service_with_mock, mock_google_workspace_service):
    """Test listing users when no users exist."""
    mock_google_workspace_service.users().list().execute.return_value = {'users': []}

    users = workspace_service_with_mock.list_users()

    assert users == []


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_list_users_service_not_initialized(workspace_service_uninitialized):
    """Test listing users when service is not initialized."""
    result = workspace_service_uninitialized.list_users()

    assert 'error' in result
    assert 'not initialized' in result['error']


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_list_users_api_error(workspace_service_with_mock, mock_google_workspace_service):
    """Test handling API errors when listing users."""
    # Mock HttpError
    mock_response = Mock()
    mock_response.status = 500
    error = HttpError(resp=mock_response, content=b'Server Error')
    mock_google_workspace_service.users().list().execute.side_effect = error

    result = workspace_service_with_mock.list_users()

    assert 'error' in result
    assert 'API error' in result['error']


# ==============================================================================
# get_user() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_get_user_success(workspace_service_with_mock):
    """Test getting a specific user successfully."""
    user = workspace_service_with_mock.get_user('test@example.com')

    assert 'error' not in user
    assert user['email'] == 'test@example.com'
    assert user['full_name'] == 'Test User'


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_get_user_not_found(workspace_service_with_mock, mock_google_workspace_service):
    """Test getting a non-existent user."""
    # Mock 404 error
    mock_response = Mock()
    mock_response.status = 404
    error = HttpError(resp=mock_response, content=b'Not Found')
    mock_google_workspace_service.users().get().execute.side_effect = error

    result = workspace_service_with_mock.get_user('nonexistent@example.com')

    assert 'error' in result
    assert 'not found' in result['error'].lower()


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_get_user_service_not_initialized(workspace_service_uninitialized):
    """Test getting user when service is not initialized."""
    result = workspace_service_uninitialized.get_user('test@example.com')

    assert 'error' in result
    assert 'not initialized' in result['error']


# ==============================================================================
# create_user() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_create_user_success(workspace_service_with_mock, mock_google_workspace_service):
    """Test creating a new user successfully."""
    # Mock the insert response
    mock_google_workspace_service.users().insert().execute.return_value = {
        'primaryEmail': 'newuser@example.com',
        'name': {
            'givenName': 'New',
            'familyName': 'User',
            'fullName': 'New User'
        },
        'suspended': False,
        'archived': False
    }

    result = workspace_service_with_mock.create_user(
        email='newuser@example.com',
        first_name='New',
        last_name='User',
        password='TempPass123!'
    )

    assert 'error' not in result
    assert result['email'] == 'newuser@example.com'
    assert result['first_name'] == 'New'
    assert result['last_name'] == 'User'


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_create_user_duplicate_email(workspace_service_with_mock, mock_google_workspace_service):
    """Test creating a user with duplicate email."""
    # Mock conflict error
    mock_response = Mock()
    mock_response.status = 409
    error = HttpError(resp=mock_response, content=b'Entity already exists')
    mock_google_workspace_service.users().insert().execute.side_effect = error

    result = workspace_service_with_mock.create_user(
        email='duplicate@example.com',
        first_name='Duplicate',
        last_name='User',
        password='Pass123!'
    )

    assert 'error' in result
    assert 'API error' in result['error']


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_create_user_service_not_initialized(workspace_service_uninitialized):
    """Test creating user when service is not initialized."""
    result = workspace_service_uninitialized.create_user(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        password='Pass123!'
    )

    assert 'error' in result
    assert 'not initialized' in result['error']


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_create_user_sets_change_password(workspace_service_with_mock, mock_google_workspace_service):
    """Test that create_user sets changePasswordAtNextLogin flag."""
    mock_insert = mock_google_workspace_service.users().insert
    mock_insert().execute.return_value = {
        'primaryEmail': 'test@example.com',
        'name': {'givenName': 'Test', 'familyName': 'User', 'fullName': 'Test User'}
    }

    workspace_service_with_mock.create_user(
        email='test@example.com',
        first_name='Test',
        last_name='User',
        password='Pass123!'
    )

    # Verify the body passed to insert includes changePasswordAtNextLogin
    call_args = mock_insert.call_args
    assert call_args[1]['body']['changePasswordAtNextLogin'] is True


# ==============================================================================
# archive_user() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_archive_user_success(workspace_service_with_mock, mock_google_workspace_service):
    """Test archiving a user successfully."""
    mock_google_workspace_service.users().update().execute.return_value = {}

    result = workspace_service_with_mock.archive_user('test@example.com')

    assert result['success'] is True
    assert 'archived successfully' in result['message']


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_archive_user_not_found(workspace_service_with_mock, mock_google_workspace_service):
    """Test archiving a non-existent user."""
    # Mock 404 error
    mock_response = Mock()
    mock_response.status = 404
    error = HttpError(resp=mock_response, content=b'Not Found')
    mock_google_workspace_service.users().update().execute.side_effect = error

    result = workspace_service_with_mock.archive_user('nonexistent@example.com')

    assert 'error' in result
    assert 'not found' in result['error'].lower()


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_archive_user_sets_suspended_and_archived(workspace_service_with_mock, mock_google_workspace_service):
    """Test that archive_user sets both suspended and archived flags."""
    mock_update = mock_google_workspace_service.users().update
    mock_update().execute.return_value = {}

    workspace_service_with_mock.archive_user('test@example.com')

    # Verify the body includes both flags
    call_args = mock_update.call_args
    assert call_args[1]['body']['suspended'] is True
    assert call_args[1]['body']['archived'] is True


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_archive_user_service_not_initialized(workspace_service_uninitialized):
    """Test archiving user when service is not initialized."""
    result = workspace_service_uninitialized.archive_user('test@example.com')

    assert 'error' in result
    assert 'not initialized' in result['error']


# ==============================================================================
# delete_user() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_delete_user_success(workspace_service_with_mock, mock_google_workspace_service):
    """Test deleting a user successfully."""
    mock_google_workspace_service.users().delete().execute.return_value = {}

    result = workspace_service_with_mock.delete_user('test@example.com')

    assert result['success'] is True
    assert 'deleted successfully' in result['message']


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_delete_user_not_found(workspace_service_with_mock, mock_google_workspace_service):
    """Test deleting a non-existent user."""
    # Mock 404 error
    mock_response = Mock()
    mock_response.status = 404
    error = HttpError(resp=mock_response, content=b'Not Found')
    mock_google_workspace_service.users().delete().execute.side_effect = error

    result = workspace_service_with_mock.delete_user('nonexistent@example.com')

    assert 'error' in result
    assert 'not found' in result['error'].lower()


@pytest.mark.unit
@pytest.mark.fred
@pytest.mark.google_api
def test_delete_user_service_not_initialized(workspace_service_uninitialized):
    """Test deleting user when service is not initialized."""
    result = workspace_service_uninitialized.delete_user('test@example.com')

    assert 'error' in result
    assert 'not initialized' in result['error']


# ==============================================================================
# _format_user() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.fred
def test_format_user_complete_data(workspace_service_with_mock):
    """Test formatting user with complete data."""
    raw_user = {
        'primaryEmail': 'test@example.com',
        'name': {
            'givenName': 'John',
            'familyName': 'Doe',
            'fullName': 'John Doe'
        },
        'suspended': False,
        'archived': False,
        'creationTime': '2024-01-01T00:00:00Z',
        'lastLoginTime': '2024-06-01T12:00:00Z'
    }

    formatted = workspace_service_with_mock._format_user(raw_user)

    assert formatted['email'] == 'test@example.com'
    assert formatted['first_name'] == 'John'
    assert formatted['last_name'] == 'Doe'
    assert formatted['full_name'] == 'John Doe'
    assert formatted['suspended'] is False
    assert formatted['archived'] is False
    assert formatted['created_time'] == '2024-01-01T00:00:00Z'
    assert formatted['last_login'] == '2024-06-01T12:00:00Z'


@pytest.mark.unit
@pytest.mark.fred
def test_format_user_minimal_data(workspace_service_with_mock):
    """Test formatting user with minimal data."""
    raw_user = {
        'primaryEmail': 'minimal@example.com'
    }

    formatted = workspace_service_with_mock._format_user(raw_user)

    assert formatted['email'] == 'minimal@example.com'
    assert formatted['first_name'] == ''
    assert formatted['last_name'] == ''
    assert formatted['full_name'] == ''
    assert formatted['suspended'] is False
    assert formatted['archived'] is False
    assert formatted['created_time'] == ''
    assert formatted['last_login'] == ''


@pytest.mark.unit
@pytest.mark.fred
def test_format_user_suspended(workspace_service_with_mock):
    """Test formatting suspended user."""
    raw_user = {
        'primaryEmail': 'suspended@example.com',
        'name': {'fullName': 'Suspended User'},
        'suspended': True,
        'archived': True
    }

    formatted = workspace_service_with_mock._format_user(raw_user)

    assert formatted['suspended'] is True
    assert formatted['archived'] is True


@pytest.mark.unit
@pytest.mark.fred
def test_format_user_with_aliases(workspace_service_with_mock):
    """Test formatting user with email aliases."""
    raw_user = {
        'primaryEmail': 'user@example.com',
        'aliases': ['user.alias@example.com', 'useralias@example.com'],
        'name': {'fullName': 'User With Aliases'},
        'suspended': False,
        'archived': False
    }

    formatted = workspace_service_with_mock._format_user(raw_user)

    assert formatted['email'] == 'user@example.com'
    assert formatted['aliases'] == ['user.alias@example.com', 'useralias@example.com']
    assert len(formatted['aliases']) == 2


@pytest.mark.unit
@pytest.mark.fred
def test_format_user_without_aliases(workspace_service_with_mock):
    """Test formatting user without email aliases returns empty list."""
    raw_user = {
        'primaryEmail': 'noaliases@example.com',
        'name': {'fullName': 'User Without Aliases'},
        'suspended': False,
        'archived': False
    }

    formatted = workspace_service_with_mock._format_user(raw_user)

    assert formatted['email'] == 'noaliases@example.com'
    assert formatted['aliases'] == []
