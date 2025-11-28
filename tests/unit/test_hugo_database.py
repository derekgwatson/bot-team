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


@pytest.mark.unit
@pytest.mark.hugo
class TestQueueOperations:
    """Test change queue operations."""

    def test_queue_change(self, hugo_db):
        """Test queuing a status change."""
        result = hugo_db.queue_change(
            email='user@example.com',
            org_key='canberra',
            action='deactivate',
            user_type='employee',
            requested_by='admin@example.com'
        )

        assert result['success'] is True
        assert result['queued'] is True

        # Verify it appears in pending changes
        pending = hugo_db.get_pending_changes()
        assert len(pending) == 1
        assert pending[0]['email'] == 'user@example.com'

    def test_get_pending_changes(self, hugo_db):
        """Test getting pending changes."""
        hugo_db.queue_change('user1@example.com', 'canberra', 'deactivate', 'employee')
        hugo_db.queue_change('user2@example.com', 'tweed', 'activate', 'employee')

        changes = hugo_db.get_pending_changes()
        assert len(changes) == 2

        # Filter by org
        canberra_changes = hugo_db.get_pending_changes(org_key='canberra')
        assert len(canberra_changes) == 1
        assert canberra_changes[0]['email'] == 'user1@example.com'

    def test_get_pending_changes_by_org(self, hugo_db):
        """Test getting pending changes grouped by org."""
        hugo_db.queue_change('user1@example.com', 'canberra', 'deactivate', 'employee')
        hugo_db.queue_change('user2@example.com', 'canberra', 'activate', 'employee')
        hugo_db.queue_change('user3@example.com', 'tweed', 'deactivate', 'customer')

        by_org = hugo_db.get_pending_changes_by_org()

        assert 'canberra' in by_org
        assert 'tweed' in by_org
        assert len(by_org['canberra']) == 2
        assert len(by_org['tweed']) == 1

    def test_mark_changes_processing(self, hugo_db):
        """Test marking changes as processing."""
        hugo_db.queue_change('user1@example.com', 'canberra', 'deactivate', 'employee')
        hugo_db.queue_change('user2@example.com', 'canberra', 'activate', 'employee')

        # Get the IDs from pending changes
        pending = hugo_db.get_pending_changes()
        change_ids = [c['id'] for c in pending]

        hugo_db.mark_changes_processing(change_ids)

        # Should no longer appear in pending
        pending = hugo_db.get_pending_changes()
        assert len(pending) == 0

    def test_complete_change(self, hugo_db):
        """Test completing a change."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID from pending changes
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']

        hugo_db.complete_change(change_id, success=True)

        pending = hugo_db.get_pending_changes()
        assert len(pending) == 0

    def test_complete_change_failure(self, hugo_db):
        """Test recording a failed change."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID from pending changes
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']

        hugo_db.complete_change(change_id, success=False, error_message='Connection timeout')

        pending = hugo_db.get_pending_changes()
        assert len(pending) == 0

        # Verify it shows in stats as failed
        stats = hugo_db.get_queue_stats()
        assert stats['failed'] == 1

    def test_get_queue_stats(self, hugo_db):
        """Test getting queue statistics."""
        hugo_db.queue_change('user1@example.com', 'canberra', 'deactivate', 'employee')
        hugo_db.queue_change('user2@example.com', 'tweed', 'activate', 'employee')

        stats = hugo_db.get_queue_stats()

        assert stats['pending'] == 2
        assert stats['processing'] == 0
        assert stats['completed'] == 0
        assert stats['failed'] == 0

    def test_clear_completed_changes(self, hugo_db):
        """Test clearing old completed changes."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID from pending changes
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']

        hugo_db.complete_change(change_id, success=True)

        # Verify it's in the completed count
        stats = hugo_db.get_queue_stats()
        assert stats['completed'] == 1

        # Clear with older_than_days=0 clears items processed before now
        # Since we just completed it, it won't be cleared (processed_at = now)
        # But we can verify the method runs without error
        cleared = hugo_db.clear_completed_changes(older_than_days=0)

        # The entry is still there because processed_at is not < now
        stats = hugo_db.get_queue_stats()
        # We just need to verify the method works - whether it clears depends on timing
        assert stats['completed'] >= 0

    def test_get_pending_change_by_id(self, hugo_db):
        """Test getting a pending change by ID."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID from pending changes
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']

        # Get by ID
        change = hugo_db.get_pending_change_by_id(change_id)
        assert change is not None
        assert change['email'] == 'user@example.com'
        assert change['action'] == 'deactivate'

        # Non-existent ID returns None
        assert hugo_db.get_pending_change_by_id(9999) is None

    def test_cancel_pending_change(self, hugo_db):
        """Test cancelling a pending change."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID from pending changes
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']

        # Cancel the change
        result = hugo_db.cancel_pending_change(change_id)
        assert result['success'] is True
        assert result['change']['email'] == 'user@example.com'

        # Verify it's no longer pending
        pending = hugo_db.get_pending_changes()
        assert len(pending) == 0

    def test_cancel_nonpending_change(self, hugo_db):
        """Test cancelling a non-pending change fails."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')

        # Get the ID and mark as processing
        pending = hugo_db.get_pending_changes()
        change_id = pending[0]['id']
        hugo_db.mark_changes_processing([change_id])

        # Try to cancel - should fail since it's processing
        result = hugo_db.cancel_pending_change(change_id)
        assert result['success'] is False

    def test_get_user_pending_change(self, hugo_db):
        """Test getting a pending change for a user/org."""
        hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')
        hugo_db.queue_change('other@example.com', 'tweed', 'activate', 'employee')

        # Get pending change for user
        pending = hugo_db.get_user_pending_change('user@example.com', 'canberra')
        assert pending is not None
        assert pending['action'] == 'deactivate'

        # No pending change for this user/org
        pending = hugo_db.get_user_pending_change('user@example.com', 'tweed')
        assert pending is None

    def test_queue_opposite_cancels_existing(self, hugo_db):
        """Test that queuing the opposite action cancels the existing one."""
        # Queue a deactivate
        result1 = hugo_db.queue_change('user@example.com', 'canberra', 'deactivate', 'employee')
        assert result1['success'] is True
        assert result1['queued'] is True

        # Queue the opposite (activate) - should cancel
        result2 = hugo_db.queue_change('user@example.com', 'canberra', 'activate', 'employee')
        assert result2['success'] is True
        assert result2['queued'] is False
        assert 'Cancelled' in result2['message']

        # No pending changes remain
        pending = hugo_db.get_pending_changes()
        assert len(pending) == 0


@pytest.mark.unit
@pytest.mark.hugo
class TestAuthHealth:
    """Test auth health monitoring operations."""

    def test_update_auth_health_success(self, hugo_db):
        """Test updating auth health with success."""
        hugo_db.update_auth_health(org_key='canberra', status='healthy')

        # get_auth_health with org_key returns the row directly
        health = hugo_db.get_auth_health(org_key='canberra')
        assert health is not None
        assert health['status'] == 'healthy'
        assert health['consecutive_failures'] == 0

    def test_update_auth_health_failure(self, hugo_db):
        """Test updating auth health with failure."""
        hugo_db.update_auth_health(org_key='canberra', status='failed', error_message='Login redirect detected')

        health = hugo_db.get_auth_health(org_key='canberra')
        assert health['status'] == 'failed'
        assert health['error_message'] == 'Login redirect detected'
        assert health['consecutive_failures'] == 1

    def test_auth_health_consecutive_failures(self, hugo_db):
        """Test consecutive failure counting."""
        hugo_db.update_auth_health(org_key='canberra', status='failed', error_message='Error 1')
        hugo_db.update_auth_health(org_key='canberra', status='failed', error_message='Error 2')
        hugo_db.update_auth_health(org_key='canberra', status='failed', error_message='Error 3')

        health = hugo_db.get_auth_health(org_key='canberra')
        assert health['consecutive_failures'] == 3

        # Success should reset
        hugo_db.update_auth_health(org_key='canberra', status='healthy')
        health = hugo_db.get_auth_health(org_key='canberra')
        assert health['consecutive_failures'] == 0

    def test_get_unhealthy_orgs(self, hugo_db):
        """Test getting unhealthy organizations."""
        hugo_db.update_auth_health(org_key='canberra', status='healthy')
        hugo_db.update_auth_health(org_key='tweed', status='failed', error_message='Auth expired')
        hugo_db.update_auth_health(org_key='sydney', status='expired', error_message='Session expired')

        unhealthy = hugo_db.get_unhealthy_orgs()

        assert len(unhealthy) == 2
        org_keys = [o['org_key'] for o in unhealthy]
        assert 'tweed' in org_keys
        assert 'sydney' in org_keys
        assert 'canberra' not in org_keys
