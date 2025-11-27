"""
Unit tests for Grant database operations.
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
os.environ['GRANT_SUPERADMINS'] = 'superadmin@example.com'

# Add grant to path before importing its modules
sys.path.insert(0, str(project_root / 'grant'))

# Clear any cached config module
if 'config' in sys.modules:
    del sys.modules['config']

# Import Database directly using importlib to avoid sys.modules caching issues
module_path = project_root / 'grant' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('grant_database_db', module_path)
grant_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grant_db_module)
Database = grant_db_module.Database


@pytest.fixture
def grant_db(tmp_path):
    """Create an isolated Grant database for testing."""
    db_path = tmp_path / "grant_test.db"
    return Database(str(db_path))


@pytest.mark.unit
@pytest.mark.grant
class TestPermissionOperations:
    """Test permission CRUD operations."""

    def test_grant_permission_new(self, grant_db):
        """Test granting a new permission."""
        perm = grant_db.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='user',
            granted_by='admin@example.com'
        )

        assert perm is not None
        assert perm['email'] == 'user@example.com'
        assert perm['bot_name'] == 'fiona'
        assert perm['role'] == 'user'
        assert perm['granted_by'] == 'admin@example.com'

    def test_grant_permission_update_existing(self, grant_db):
        """Test updating an existing permission."""
        # Grant initial permission
        grant_db.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='user',
            granted_by='admin@example.com'
        )

        # Update to admin
        perm = grant_db.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='admin',
            granted_by='superadmin@example.com'
        )

        assert perm['role'] == 'admin'
        assert perm['granted_by'] == 'superadmin@example.com'

    def test_revoke_permission(self, grant_db):
        """Test revoking a permission."""
        # Grant permission first
        grant_db.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='user',
            granted_by='admin@example.com'
        )

        # Verify it exists
        perm = grant_db.get_permission('user@example.com', 'fiona')
        assert perm is not None

        # Revoke it
        result = grant_db.revoke_permission(
            email='user@example.com',
            bot_name='fiona',
            revoked_by='admin@example.com'
        )
        assert result is True

        # Verify it's gone
        perm = grant_db.get_permission('user@example.com', 'fiona')
        assert perm is None

    def test_revoke_nonexistent_permission(self, grant_db):
        """Test revoking a permission that doesn't exist."""
        result = grant_db.revoke_permission(
            email='nobody@example.com',
            bot_name='fiona',
            revoked_by='admin@example.com'
        )
        assert result is False

    def test_check_access_with_permission(self, grant_db):
        """Test checking access when user has permission."""
        grant_db.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='admin',
            granted_by='admin@example.com'
        )

        result = grant_db.check_access('user@example.com', 'fiona')
        assert result['allowed'] is True
        assert result['role'] == 'admin'
        assert result['is_admin'] is True

    def test_check_access_without_permission(self, grant_db):
        """Test checking access when user has no permission."""
        result = grant_db.check_access('nobody@example.com', 'fiona')
        assert result['allowed'] is False
        assert result['role'] is None
        assert result['is_admin'] is False

    def test_check_access_wildcard(self, grant_db):
        """Test checking access with wildcard permission."""
        # Grant access to all bots
        grant_db.grant_permission(
            email='itadmin@example.com',
            bot_name='*',
            role='admin',
            granted_by='superadmin@example.com'
        )

        # Should have access to any bot
        result = grant_db.check_access('itadmin@example.com', 'fiona')
        assert result['allowed'] is True
        assert result['role'] == 'admin'

        result = grant_db.check_access('itadmin@example.com', 'skye')
        assert result['allowed'] is True


@pytest.mark.unit
@pytest.mark.grant
class TestPermissionQueries:
    """Test permission query operations."""

    def test_get_permissions_for_user(self, grant_db):
        """Test getting all permissions for a user."""
        grant_db.grant_permission('user@example.com', 'fiona', 'admin', 'admin@example.com')
        grant_db.grant_permission('user@example.com', 'skye', 'user', 'admin@example.com')
        grant_db.grant_permission('other@example.com', 'fiona', 'user', 'admin@example.com')

        perms = grant_db.get_permissions_for_user('user@example.com')
        assert len(perms) == 2
        bot_names = [p['bot_name'] for p in perms]
        assert 'fiona' in bot_names
        assert 'skye' in bot_names

    def test_get_permissions_for_bot(self, grant_db):
        """Test getting all permissions for a bot."""
        grant_db.grant_permission('user1@example.com', 'fiona', 'admin', 'admin@example.com')
        grant_db.grant_permission('user2@example.com', 'fiona', 'user', 'admin@example.com')
        grant_db.grant_permission('user1@example.com', 'skye', 'user', 'admin@example.com')

        perms = grant_db.get_permissions_for_bot('fiona')
        assert len(perms) == 2
        emails = [p['email'] for p in perms]
        assert 'user1@example.com' in emails
        assert 'user2@example.com' in emails

    def test_get_unique_users(self, grant_db):
        """Test getting unique users."""
        grant_db.grant_permission('user1@example.com', 'fiona', 'admin', 'admin@example.com')
        grant_db.grant_permission('user2@example.com', 'fiona', 'user', 'admin@example.com')
        grant_db.grant_permission('user1@example.com', 'skye', 'user', 'admin@example.com')

        users = grant_db.get_unique_users()
        assert len(users) == 2
        assert 'user1@example.com' in users
        assert 'user2@example.com' in users


@pytest.mark.unit
@pytest.mark.grant
class TestAuditLog:
    """Test audit log operations."""

    def test_audit_log_on_grant(self, grant_db):
        """Test that audit log records grants."""
        grant_db.grant_permission('user@example.com', 'fiona', 'user', 'admin@example.com')

        audit = grant_db.get_audit_log()
        assert len(audit) == 1
        assert audit[0]['email'] == 'user@example.com'
        assert audit[0]['bot_name'] == 'fiona'
        assert audit[0]['action'] == 'grant'
        assert audit[0]['new_role'] == 'user'

    def test_audit_log_on_modify(self, grant_db):
        """Test that audit log records modifications."""
        grant_db.grant_permission('user@example.com', 'fiona', 'user', 'admin@example.com')
        grant_db.grant_permission('user@example.com', 'fiona', 'admin', 'superadmin@example.com')

        audit = grant_db.get_audit_log()
        assert len(audit) == 2

        # Most recent first
        assert audit[0]['action'] == 'modify'
        assert audit[0]['old_role'] == 'user'
        assert audit[0]['new_role'] == 'admin'

    def test_audit_log_on_revoke(self, grant_db):
        """Test that audit log records revocations."""
        grant_db.grant_permission('user@example.com', 'fiona', 'admin', 'admin@example.com')
        grant_db.revoke_permission('user@example.com', 'fiona', 'admin@example.com')

        audit = grant_db.get_audit_log()
        assert len(audit) == 2

        # Most recent first
        assert audit[0]['action'] == 'revoke'
        assert audit[0]['old_role'] == 'admin'
        assert audit[0]['new_role'] is None

    def test_audit_log_filter_by_email(self, grant_db):
        """Test filtering audit log by email."""
        grant_db.grant_permission('user1@example.com', 'fiona', 'user', 'admin@example.com')
        grant_db.grant_permission('user2@example.com', 'fiona', 'user', 'admin@example.com')

        audit = grant_db.get_audit_log(email='user1@example.com')
        assert len(audit) == 1
        assert audit[0]['email'] == 'user1@example.com'


@pytest.mark.unit
@pytest.mark.grant
class TestBotRegistry:
    """Test bot registry operations."""

    def test_sync_bots(self, grant_db):
        """Test syncing bot registry."""
        bots = [
            {'name': 'fiona', 'description': 'Fabric manager', 'port': 8018},
            {'name': 'skye', 'description': 'Scheduler', 'port': 8020},
        ]

        result = grant_db.sync_bots(bots)
        assert result['synced'] == 2

        # Verify bots are stored
        stored_bots = grant_db.get_bots()
        assert len(stored_bots) == 2

        fiona = grant_db.get_bot('fiona')
        assert fiona is not None
        assert fiona['description'] == 'Fabric manager'
        assert fiona['port'] == 8018

    def test_sync_bots_replaces_existing(self, grant_db):
        """Test that sync replaces existing bots."""
        # Initial sync
        grant_db.sync_bots([
            {'name': 'fiona', 'description': 'Old description', 'port': 8018},
        ])

        # New sync
        grant_db.sync_bots([
            {'name': 'fiona', 'description': 'New description', 'port': 8018},
            {'name': 'skye', 'description': 'Scheduler', 'port': 8020},
        ])

        bots = grant_db.get_bots()
        assert len(bots) == 2

        fiona = grant_db.get_bot('fiona')
        assert fiona['description'] == 'New description'


@pytest.mark.unit
@pytest.mark.grant
class TestStats:
    """Test statistics operations."""

    def test_get_stats(self, grant_db):
        """Test getting permission statistics."""
        grant_db.grant_permission('user1@example.com', 'fiona', 'admin', 'admin@example.com')
        grant_db.grant_permission('user2@example.com', 'fiona', 'user', 'admin@example.com')
        grant_db.grant_permission('user1@example.com', 'skye', 'user', 'admin@example.com')
        grant_db.sync_bots([
            {'name': 'fiona', 'description': 'Fabric', 'port': 8018},
            {'name': 'skye', 'description': 'Scheduler', 'port': 8020},
        ])

        stats = grant_db.get_stats()
        assert stats['unique_users'] == 2
        assert stats['total_permissions'] == 3
        assert stats['admin_permissions'] == 1
        assert stats['registered_bots'] == 2
