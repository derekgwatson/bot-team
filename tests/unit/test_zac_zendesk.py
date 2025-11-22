"""
Unit tests for Zac's Zendesk service.

Tests cover user CRUD operations without hitting the real Zendesk API.
Uses mocked Zenpy client to simulate API responses.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add Zac to path
project_root = Path(__file__).parent.parent.parent
zac_path = project_root / 'zac'
if str(zac_path) not in sys.path:
    sys.path.insert(0, str(zac_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_zenpy_client():
    """Create a mock Zenpy client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_zac_config():
    """Mock Zac config with Zendesk credentials."""
    config = Mock()
    config.zendesk_subdomain = 'testcompany'
    config.zendesk_email = 'admin@company.com'
    config.zendesk_api_token = 'test_api_token'
    return config


@pytest.fixture
def mock_zendesk_user():
    """Create a mock Zendesk user object."""
    user = Mock()
    user.id = 12345
    user.name = 'Test User'
    user.email = 'test@example.com'
    user.role = 'agent'
    user.verified = True
    user.active = True
    user.suspended = False
    user.created_at = '2025-01-15T10:00:00Z'
    user.last_login_at = '2025-01-20T14:30:00Z'
    user.phone = '555-0100'
    user.organization_id = None
    user.locale = 'en-US'
    user.time_zone = 'Australia/Sydney'
    user.notes = 'Test notes'
    return user


# ==============================================================================
# User Creation Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_create_user_success(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test successful user creation."""
    # Setup mock
    mock_zenpy_client.users.create.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.create_user(
                name='Test User',
                email='test@example.com',
                role='agent'
            )

    assert result['id'] == 12345
    assert result['name'] == 'Test User'
    assert result['email'] == 'test@example.com'
    assert result['role'] == 'agent'
    mock_zenpy_client.users.create.assert_called_once()


@pytest.mark.unit
@pytest.mark.zac
def test_create_user_with_additional_properties(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test user creation with additional properties."""
    mock_zenpy_client.users.create.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.create_user(
                name='Test User',
                email='test@example.com',
                role='agent',
                phone='555-0100',
                verified=True
            )

    assert result is not None
    mock_zenpy_client.users.create.assert_called_once()


@pytest.mark.unit
@pytest.mark.zac
def test_create_user_api_error(mock_zenpy_client, mock_zac_config):
    """Test handling of API errors during user creation."""
    mock_zenpy_client.users.create.side_effect = Exception('API Error: Email already exists')

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()

            with pytest.raises(Exception) as exc_info:
                service.create_user(
                    name='Test User',
                    email='existing@example.com',
                    role='agent'
                )

            assert 'Email already exists' in str(exc_info.value)


# ==============================================================================
# User Retrieval Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_get_user_success(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test successful user retrieval."""
    mock_zenpy_client.users.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.get_user(12345)

    assert result['id'] == 12345
    assert result['name'] == 'Test User'
    assert result['email'] == 'test@example.com'


@pytest.mark.unit
@pytest.mark.zac
def test_get_user_not_found(mock_zenpy_client, mock_zac_config):
    """Test handling of user not found."""
    mock_zenpy_client.users.side_effect = Exception('User not found')

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.get_user(99999)

    assert result is None


# ==============================================================================
# User List Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_list_users_success(mock_zenpy_client, mock_zac_config):
    """Test listing users without role filter."""
    # Create mock users
    mock_user1 = Mock()
    mock_user1.id = 1
    mock_user1.name = 'User One'
    mock_user1.email = 'user1@example.com'
    mock_user1.role = 'agent'
    mock_user1.verified = True
    mock_user1.active = True
    mock_user1.suspended = False
    mock_user1.created_at = '2025-01-01'
    mock_user1.last_login_at = None
    mock_user1.phone = None
    mock_user1.organization_id = None

    mock_user2 = Mock()
    mock_user2.id = 2
    mock_user2.name = 'User Two'
    mock_user2.email = 'user2@example.com'
    mock_user2.role = 'end-user'
    mock_user2.verified = False
    mock_user2.active = True
    mock_user2.suspended = False
    mock_user2.created_at = '2025-01-02'
    mock_user2.last_login_at = None
    mock_user2.phone = None
    mock_user2.organization_id = None

    mock_zenpy_client.users.return_value = iter([mock_user1, mock_user2])

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.list_users()

    assert len(result['users']) == 2
    assert result['users'][0]['name'] == 'User One'
    assert result['users'][1]['name'] == 'User Two'


@pytest.mark.unit
@pytest.mark.zac
def test_list_users_with_role_filter(mock_zenpy_client, mock_zac_config):
    """Test listing users with role filter."""
    mock_agent = Mock()
    mock_agent.id = 1
    mock_agent.name = 'Agent User'
    mock_agent.email = 'agent@example.com'
    mock_agent.role = 'agent'
    mock_agent.verified = True
    mock_agent.active = True
    mock_agent.suspended = False
    mock_agent.created_at = '2025-01-01'
    mock_agent.last_login_at = None
    mock_agent.phone = None
    mock_agent.organization_id = None

    mock_zenpy_client.search.return_value = iter([mock_agent])

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.list_users(role='agent')

    assert len(result['users']) == 1
    assert result['users'][0]['role'] == 'agent'
    mock_zenpy_client.search.assert_called_once()


# ==============================================================================
# User Search Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_search_users_success(mock_zenpy_client, mock_zac_config):
    """Test user search by query."""
    mock_user = Mock()
    mock_user.id = 1
    mock_user.name = 'John Smith'
    mock_user.email = 'john@example.com'
    mock_user.role = 'agent'
    mock_user.verified = True
    mock_user.active = True
    mock_user.suspended = False

    mock_zenpy_client.search.return_value = iter([mock_user])

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            results = service.search_users('John')

    assert len(results) == 1
    assert results[0]['name'] == 'John Smith'


@pytest.mark.unit
@pytest.mark.zac
def test_search_users_no_results(mock_zenpy_client, mock_zac_config):
    """Test user search with no results."""
    mock_zenpy_client.search.return_value = iter([])

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            results = service.search_users('NonexistentUser')

    assert len(results) == 0


# ==============================================================================
# User Update Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_update_user_success(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test successful user update."""
    mock_zenpy_client.users.return_value = mock_zendesk_user
    mock_zenpy_client.users.update.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.update_user(12345, name='Updated Name')

    assert result is not None
    mock_zenpy_client.users.update.assert_called_once()


# ==============================================================================
# User Suspend/Unsuspend Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_suspend_user_success(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test successful user suspension."""
    mock_zenpy_client.users.return_value = mock_zendesk_user
    mock_zendesk_user.suspended = True
    mock_zenpy_client.users.update.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.suspend_user(12345)

    assert result['suspended'] is True


@pytest.mark.unit
@pytest.mark.zac
def test_unsuspend_user_success(mock_zenpy_client, mock_zac_config, mock_zendesk_user):
    """Test successful user unsuspension."""
    mock_zenpy_client.users.return_value = mock_zendesk_user
    mock_zendesk_user.suspended = False
    mock_zenpy_client.users.update.return_value = mock_zendesk_user

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.unsuspend_user(12345)

    assert result['suspended'] is False


# ==============================================================================
# User Delete Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_delete_user_success(mock_zenpy_client, mock_zac_config):
    """Test successful user deletion."""
    mock_zenpy_client.users.delete.return_value = None

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()
            result = service.delete_user(12345)

    assert result is True
    mock_zenpy_client.users.delete.assert_called_once_with(12345)


@pytest.mark.unit
@pytest.mark.zac
def test_delete_user_error(mock_zenpy_client, mock_zac_config):
    """Test handling of delete error."""
    mock_zenpy_client.users.delete.side_effect = Exception('Cannot delete user')

    with patch('services.zendesk.config', mock_zac_config):
        with patch('services.zendesk.Zenpy', return_value=mock_zenpy_client):
            from services.zendesk import ZendeskService

            service = ZendeskService()

            with pytest.raises(Exception) as exc_info:
                service.delete_user(12345)

            assert 'Cannot delete user' in str(exc_info.value)


# ==============================================================================
# Configuration Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.zac
def test_missing_credentials_raises_error():
    """Test that missing credentials raises ValueError."""
    mock_config = Mock()
    mock_config.zendesk_subdomain = None
    mock_config.zendesk_email = None
    mock_config.zendesk_api_token = None

    with patch('services.zendesk.config', mock_config):
        # Need to reload the module to trigger the error
        from services.zendesk import ZendeskService

        with pytest.raises(ValueError) as exc_info:
            ZendeskService()

        assert 'Zendesk credentials not configured' in str(exc_info.value)
