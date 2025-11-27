"""
Unit tests for Hugo database operations.
"""

import os
import sys
import pytest
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['BUZ_ORGS'] = ''  # Empty for tests - no actual Buz auth needed

# Add hugo to path before importing its modules
sys.path.insert(0, str(project_root / 'hugo'))

# Clear any cached config module
if 'config' in sys.modules:
    del sys.modules['config']

# Import Database directly using importlib to avoid sys.modules caching issues
module_path = project_root / 'hugo' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('hugo_database_db', module_path)
hugo_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hugo_db_module)
UserDatabase = hugo_db_module.UserDatabase


@pytest.fixture
def hugo_db(tmp_path):
    """Create an isolated Hugo database for testing."""
    db_path = tmp_path / "hugo_test.db"
    return UserDatabase(str(db_path))


@pytest.mark.unit
@pytest.mark.hugo
class TestUserOperations:
    """Test user CRUD operations."""

    def test_upsert_user_new(self, hugo_db):
        """Test inserting a new user."""
        result = hugo_db.upsert_user(
            email='user@example.com',
            org_key='canberra',
            full_name='Test User',
            user_type='employee',
            is_active=True,
            mfa_enabled=False,
            user_group='Sales',
            last_session='2025-01-01 10:00:00'
        )

        assert result['success'] is True
        assert result['action'] == 'created'

        # Verify user exists
        user = hugo_db.get_user_by_email('user@example.com', 'canberra')
        assert user is not None
        assert user['full_name'] == 'Test User'
        assert user['user_type'] == 'employee'
        assert user['is_active'] == 1

    def test_upsert_user_update(self, hugo_db):
        """Test updating an existing user."""
        # Create user first
        hugo_db.upsert_user(
            email='user@example.com',
            org_key='canberra',
            full_name='Old Name',
            is_active=True
        )

        # Update user
        result = hugo_db.upsert_user(
            email='user@example.com',
            org_key='canberra',
            full_name='New Name',
            is_active=False
        )

        assert result['success'] is True
        assert result['action'] == 'updated'

        # Verify update
        user = hugo_db.get_user_by_email('user@example.com', 'canberra')
        assert user['full_name'] == 'New Name'
        assert user['is_active'] == 0

    def test_user_multi_org(self, hugo_db):
        """Test user can exist in multiple orgs."""
        hugo_db.upsert_user(
            email='user@example.com',
            org_key='canberra',
            full_name='User Canberra',
            is_active=True
        )
        hugo_db.upsert_user(
            email='user@example.com',
            org_key='tweed',
            full_name='User Tweed',
            is_active=False
        )

        # Get orgs for user
        orgs = hugo_db.get_user_orgs('user@example.com')
        assert 'canberra' in orgs
        assert 'tweed' not in orgs  # Only active orgs

    def test_update_user_status(self, hugo_db):
        """Test updating user active status."""
        hugo_db.upsert_user(
            email='user@example.com',
            org_key='canberra',
            is_active=True
        )

        result = hugo_db.update_user_status('user@example.com', 'canberra', False)

        assert result['success'] is True
        assert result['old_status'] is True
        assert result['new_status'] is False

        user = hugo_db.get_user_by_email('user@example.com', 'canberra')
        assert user['is_active'] == 0

    def test_update_nonexistent_user_status(self, hugo_db):
        """Test updating status of nonexistent user."""
        result = hugo_db.update_user_status('nobody@example.com', 'canberra', False)

        assert result['success'] is False
        assert 'not found' in result['error']


@pytest.mark.unit
@pytest.mark.hugo
class TestUserQueries:
    """Test user query operations."""

    def test_get_users_all(self, hugo_db):
        """Test getting all users."""
        hugo_db.upsert_user(email='user1@example.com', org_key='canberra', is_active=True)
        hugo_db.upsert_user(email='user2@example.com', org_key='canberra', is_active=False)
        hugo_db.upsert_user(email='user3@example.com', org_key='tweed', is_active=True)

        users = hugo_db.get_users()
        assert len(users) == 3

    def test_get_users_by_org(self, hugo_db):
        """Test filtering users by org."""
        hugo_db.upsert_user(email='user1@example.com', org_key='canberra', is_active=True)
        hugo_db.upsert_user(email='user2@example.com', org_key='tweed', is_active=True)

        users = hugo_db.get_users(org_key='canberra')
        assert len(users) == 1
        assert users[0]['email'] == 'user1@example.com'

    def test_get_users_by_status(self, hugo_db):
        """Test filtering users by active status."""
        hugo_db.upsert_user(email='active@example.com', org_key='canberra', is_active=True)
        hugo_db.upsert_user(email='inactive@example.com', org_key='canberra', is_active=False)

        active_users = hugo_db.get_users(is_active=True)
        assert len(active_users) == 1
        assert active_users[0]['email'] == 'active@example.com'

        inactive_users = hugo_db.get_users(is_active=False)
        assert len(inactive_users) == 1
        assert inactive_users[0]['email'] == 'inactive@example.com'

    def test_get_users_by_type(self, hugo_db):
        """Test filtering users by type."""
        hugo_db.upsert_user(email='emp@example.com', org_key='canberra', user_type='employee')
        hugo_db.upsert_user(email='cust@example.com', org_key='canberra', user_type='customer')

        employees = hugo_db.get_users(user_type='employee')
        assert len(employees) == 1
        assert employees[0]['email'] == 'emp@example.com'


@pytest.mark.unit
@pytest.mark.hugo
class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_upsert_users(self, hugo_db):
        """Test bulk upserting users."""
        users = [
            {'email': 'user1@example.com', 'full_name': 'User 1', 'is_active': True, 'user_type': 'employee'},
            {'email': 'user2@example.com', 'full_name': 'User 2', 'is_active': False, 'user_type': 'employee'},
            {'email': 'user3@example.com', 'full_name': 'User 3', 'is_active': True, 'user_type': 'customer'},
        ]

        result = hugo_db.bulk_upsert_users(users, 'canberra')

        assert result['success'] is True
        assert result['created'] == 3
        assert result['updated'] == 0
        assert result['total'] == 3

        # Verify all users exist
        all_users = hugo_db.get_users(org_key='canberra')
        assert len(all_users) == 3

    def test_bulk_upsert_mixed(self, hugo_db):
        """Test bulk upsert with existing users."""
        # Create one user first
        hugo_db.upsert_user(email='existing@example.com', org_key='canberra', full_name='Old Name')

        users = [
            {'email': 'existing@example.com', 'full_name': 'New Name', 'is_active': True},
            {'email': 'new@example.com', 'full_name': 'New User', 'is_active': True},
        ]

        result = hugo_db.bulk_upsert_users(users, 'canberra')

        assert result['created'] == 1
        assert result['updated'] == 1

        # Verify existing user was updated
        user = hugo_db.get_user_by_email('existing@example.com', 'canberra')
        assert user['full_name'] == 'New Name'


@pytest.mark.unit
@pytest.mark.hugo
class TestSyncLog:
    """Test sync log operations."""

    def test_log_sync_success(self, hugo_db):
        """Test logging a successful sync."""
        log_id = hugo_db.log_sync(
            org_key='canberra',
            user_count=50,
            status='success',
            duration_seconds=15.5
        )

        assert log_id is not None

        last_sync = hugo_db.get_last_sync('canberra')
        assert last_sync is not None
        assert last_sync['user_count'] == 50
        assert last_sync['status'] == 'success'
        assert last_sync['duration_seconds'] == 15.5

    def test_log_sync_error(self, hugo_db):
        """Test logging a failed sync."""
        hugo_db.log_sync(
            org_key='canberra',
            user_count=0,
            status='error',
            error_message='Connection timeout'
        )

        last_sync = hugo_db.get_last_sync('canberra')
        assert last_sync['status'] == 'error'
        assert last_sync['error_message'] == 'Connection timeout'

    def test_get_sync_history(self, hugo_db):
        """Test getting sync history."""
        hugo_db.log_sync(org_key='canberra', user_count=10, status='success')
        hugo_db.log_sync(org_key='tweed', user_count=5, status='success')
        hugo_db.log_sync(org_key='canberra', user_count=12, status='success')

        # All history
        history = hugo_db.get_sync_history()
        assert len(history) == 3

        # Filtered by org
        canberra_history = hugo_db.get_sync_history(org_key='canberra')
        assert len(canberra_history) == 2


@pytest.mark.unit
@pytest.mark.hugo
class TestActivityLog:
    """Test activity log operations."""

    def test_log_activity(self, hugo_db):
        """Test logging an activity."""
        log_id = hugo_db.log_activity(
            action='activate',
            email='user@example.com',
            org_key='canberra',
            old_value='False',
            new_value='True',
            performed_by='admin@example.com'
        )

        assert log_id is not None

        activity = hugo_db.get_activity_log(email='user@example.com')
        assert len(activity) == 1
        assert activity[0]['action'] == 'activate'
        assert activity[0]['performed_by'] == 'admin@example.com'

    def test_log_failed_activity(self, hugo_db):
        """Test logging a failed activity."""
        hugo_db.log_activity(
            action='deactivate',
            email='user@example.com',
            org_key='canberra',
            success=False,
            error_message='User not found'
        )

        activity = hugo_db.get_activity_log(email='user@example.com')
        assert activity[0]['success'] == 0
        assert activity[0]['error_message'] == 'User not found'


@pytest.mark.unit
@pytest.mark.hugo
class TestStats:
    """Test statistics operations."""

    def test_get_stats(self, hugo_db):
        """Test getting user statistics."""
        hugo_db.upsert_user(email='active1@example.com', org_key='canberra', is_active=True)
        hugo_db.upsert_user(email='active2@example.com', org_key='canberra', is_active=True)
        hugo_db.upsert_user(email='inactive@example.com', org_key='canberra', is_active=False)
        hugo_db.upsert_user(email='tweed@example.com', org_key='tweed', is_active=True)

        stats = hugo_db.get_stats()

        assert stats['total_users'] == 4
        assert stats['active_users'] == 3
        assert stats['inactive_users'] == 1
        assert 'canberra' in stats['by_org']
        assert stats['by_org']['canberra']['active'] == 2
        assert stats['by_org']['canberra']['inactive'] == 1
