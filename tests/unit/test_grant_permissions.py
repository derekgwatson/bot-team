"""
Unit tests for Grant permission service.
"""

import os
import sys
import pytest
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment BEFORE any imports
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['GRANT_SUPERADMINS'] = 'superadmin@example.com,another-superadmin@example.com'

# Add grant to path
sys.path.insert(0, str(project_root / 'grant'))

# Clear any cached modules
for mod in ['config', 'database', 'database.db', 'services', 'services.permissions']:
    if mod in sys.modules:
        del sys.modules[mod]


@pytest.fixture
def permission_service(tmp_path):
    """Create a permission service with isolated database."""
    # Import fresh
    module_path = project_root / 'grant' / 'database' / 'db.py'
    spec = importlib.util.spec_from_file_location('grant_db', module_path)
    db_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(db_module)

    # Create test database
    db_path = tmp_path / "grant_test.db"
    test_db = db_module.Database(str(db_path))

    # Import service module
    service_path = project_root / 'grant' / 'services' / 'permissions.py'
    spec = importlib.util.spec_from_file_location('grant_permissions', service_path)
    service_module = importlib.util.module_from_spec(spec)

    # Mock the get_db function to return our test database
    with patch.dict(sys.modules, {'database.db': db_module}):
        db_module.db = test_db
        spec.loader.exec_module(service_module)

    # Create service with mocked db
    service = service_module.PermissionService()

    # Override _get_db to return test database
    service._get_db = lambda: test_db

    return service


@pytest.mark.unit
@pytest.mark.grant
class TestSuperadminAccess:
    """Test superadmin access handling."""

    def test_superadmin_always_has_access(self, permission_service):
        """Test that superadmins always have admin access."""
        result = permission_service.check_access('superadmin@example.com', 'fiona')

        assert result['allowed'] is True
        assert result['role'] == 'admin'
        assert result['is_admin'] is True
        assert result['source'] == 'superadmin'

    def test_superadmin_access_to_any_bot(self, permission_service):
        """Test that superadmins have access to any bot."""
        for bot in ['fiona', 'skye', 'chester', 'grant', 'nonexistent']:
            result = permission_service.check_access('superadmin@example.com', bot)
            assert result['allowed'] is True
            assert result['is_admin'] is True

    def test_is_superadmin(self, permission_service):
        """Test superadmin check."""
        assert permission_service.is_superadmin('superadmin@example.com') is True
        assert permission_service.is_superadmin('SUPERADMIN@EXAMPLE.COM') is True  # Case insensitive
        assert permission_service.is_superadmin('another-superadmin@example.com') is True
        assert permission_service.is_superadmin('regular@example.com') is False


@pytest.mark.unit
@pytest.mark.grant
class TestRegularUserAccess:
    """Test regular user access handling."""

    def test_user_without_permission_denied(self, permission_service):
        """Test that users without permission are denied."""
        result = permission_service.check_access('nobody@example.com', 'fiona')

        assert result['allowed'] is False
        assert result['role'] is None
        assert result['is_admin'] is False

    def test_user_with_permission_allowed(self, permission_service):
        """Test that users with permission are allowed."""
        permission_service.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='user',
            granted_by='admin@example.com'
        )

        result = permission_service.check_access('user@example.com', 'fiona')

        assert result['allowed'] is True
        assert result['role'] == 'user'
        assert result['is_admin'] is False
        assert result['source'] == 'database'

    def test_admin_user_has_admin_flag(self, permission_service):
        """Test that admin users have is_admin flag."""
        permission_service.grant_permission(
            email='admin@example.com',
            bot_name='fiona',
            role='admin',
            granted_by='superadmin@example.com'
        )

        result = permission_service.check_access('admin@example.com', 'fiona')

        assert result['allowed'] is True
        assert result['role'] == 'admin'
        assert result['is_admin'] is True


@pytest.mark.unit
@pytest.mark.grant
class TestPermissionManagement:
    """Test permission management operations."""

    def test_grant_and_revoke(self, permission_service):
        """Test granting and revoking permissions."""
        # Grant
        perm = permission_service.grant_permission(
            email='user@example.com',
            bot_name='fiona',
            role='user',
            granted_by='admin@example.com'
        )
        assert perm['email'] == 'user@example.com'

        # Verify access
        result = permission_service.check_access('user@example.com', 'fiona')
        assert result['allowed'] is True

        # Revoke
        revoked = permission_service.revoke_permission(
            email='user@example.com',
            bot_name='fiona',
            revoked_by='admin@example.com'
        )
        assert revoked is True

        # Verify no access
        result = permission_service.check_access('user@example.com', 'fiona')
        assert result['allowed'] is False

    def test_get_user_permissions(self, permission_service):
        """Test getting all permissions for a user."""
        permission_service.grant_permission('user@example.com', 'fiona', 'admin', 'admin@example.com')
        permission_service.grant_permission('user@example.com', 'skye', 'user', 'admin@example.com')

        perms = permission_service.get_user_permissions('user@example.com')
        assert len(perms) == 2

    def test_get_bot_permissions(self, permission_service):
        """Test getting all permissions for a bot."""
        permission_service.grant_permission('user1@example.com', 'fiona', 'admin', 'admin@example.com')
        permission_service.grant_permission('user2@example.com', 'fiona', 'user', 'admin@example.com')

        perms = permission_service.get_bot_permissions('fiona')
        assert len(perms) == 2


@pytest.mark.unit
@pytest.mark.grant
class TestAuditLog:
    """Test audit log functionality."""

    def test_audit_log_records_changes(self, permission_service):
        """Test that audit log records permission changes."""
        permission_service.grant_permission('user@example.com', 'fiona', 'user', 'admin@example.com')
        permission_service.grant_permission('user@example.com', 'fiona', 'admin', 'superadmin@example.com')
        permission_service.revoke_permission('user@example.com', 'fiona', 'admin@example.com')

        audit = permission_service.get_audit_log()
        assert len(audit) == 3

        # Check actions (most recent first)
        assert audit[0]['action'] == 'revoke'
        assert audit[1]['action'] == 'modify'
        assert audit[2]['action'] == 'grant'
