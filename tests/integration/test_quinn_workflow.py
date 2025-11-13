"""
Integration tests for Quinn's approval workflow.

Tests cover end-to-end access request and approval processes.
"""
import os
import sys
import pytest
import tempfile
from pathlib import Path

# Add quinn directory to path
project_root = Path(__file__).parent.parent.parent
quinn_path = project_root / 'quinn'

if str(quinn_path) not in sys.path:
    sys.path.insert(0, str(quinn_path))

# Add project root for imports
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Need to handle module-level database instantiation
from unittest.mock import Mock
import config as quinn_config

# Create a temporary mock config to prevent errors during module import
original_config = quinn_config.config
temp_mock = Mock()
temp_mock.database_path = ':memory:'
quinn_config.config = temp_mock

# Now safe to import database module
from database.db import ExternalStaffDB

# Restore original (will be mocked properly in fixtures)
quinn_config.config = original_config


@pytest.fixture
def db(monkeypatch, tmp_path):
    """Create a test database instance."""
    db_file = tmp_path / 'test_quinn_integration.db'

    class MockConfig:
        database_path = str(db_file)

    import config as quinn_config
    monkeypatch.setattr(quinn_config, 'config', MockConfig())

    return ExternalStaffDB()


# ==============================================================================
# End-to-End Approval Workflow Tests
# ==============================================================================

@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_complete_approval_workflow(db):
    """Test complete workflow: submit request -> approve -> verify access."""
    # Step 1: External user submits access request
    request_result = db.submit_request(
        name='External Contractor',
        email='contractor@external.com',
        phone='555-1234',
        reason='Need access for Q1 project'
    )

    assert request_result['success'] is True
    request_id = request_result['id']

    # Step 2: Verify request appears in pending list
    pending = db.get_pending_requests(status='pending')
    assert len(pending) == 1
    assert pending[0]['email'] == 'contractor@external.com'
    assert pending[0]['status'] == 'pending'

    # Step 3: User should NOT be approved yet
    approval_check = db.is_approved('contractor@external.com')
    assert approval_check['approved'] is False

    # Step 4: Admin approves the request
    approve_result = db.approve_request(request_id, reviewed_by='admin@company.com')
    assert approve_result['success'] is True

    # Step 5: Request should be marked as approved
    request = db.get_request_by_id(request_id)
    assert request['status'] == 'approved'
    assert request['reviewed_by'] == 'admin@company.com'

    # Step 6: User should now be approved
    approval_check = db.is_approved('contractor@external.com')
    assert approval_check['approved'] is True
    assert approval_check['name'] == 'External Contractor'

    # Step 7: User should appear in staff list
    all_staff = db.get_all_staff(status='active')
    assert len(all_staff) == 1
    assert all_staff[0]['email'] == 'contractor@external.com'

    # Step 8: No more pending requests
    pending = db.get_pending_requests(status='pending')
    assert len(pending) == 0


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_complete_denial_workflow(db):
    """Test complete workflow: submit request -> deny -> verify no access."""
    # Step 1: Submit request
    request_result = db.submit_request(
        name='Denied User',
        email='denied@external.com',
        phone='555-5678',
        reason='Insufficient justification'
    )

    assert request_result['success'] is True
    request_id = request_result['id']

    # Step 2: Admin denies the request
    deny_result = db.deny_request(
        request_id,
        reviewed_by='admin@company.com',
        notes='Does not meet criteria'
    )

    assert deny_result['success'] is True

    # Step 3: Request should be marked as denied
    request = db.get_request_by_id(request_id)
    assert request['status'] == 'denied'
    assert request['notes'] == 'Does not meet criteria'

    # Step 4: User should NOT be approved
    approval_check = db.is_approved('denied@external.com')
    assert approval_check['approved'] is False

    # Step 5: User should NOT appear in active staff
    all_staff = db.get_all_staff(status='active')
    assert len(all_staff) == 0


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_multiple_requests_workflow(db):
    """Test handling multiple concurrent requests."""
    # Submit multiple requests
    req1 = db.submit_request(name='User 1', email='user1@external.com')['id']
    req2 = db.submit_request(name='User 2', email='user2@external.com')['id']
    req3 = db.submit_request(name='User 3', email='user3@external.com')['id']

    # All should be pending
    pending = db.get_pending_requests(status='pending')
    assert len(pending) == 3

    # Approve first, deny second, leave third pending
    db.approve_request(req1, reviewed_by='admin@company.com')
    db.deny_request(req2, reviewed_by='admin@company.com')

    # Check counts
    assert len(db.get_pending_requests(status='pending')) == 1
    assert len(db.get_pending_requests(status='approved')) == 1
    assert len(db.get_pending_requests(status='denied')) == 1

    # Only user1 should be approved
    assert db.is_approved('user1@external.com')['approved'] is True
    assert db.is_approved('user2@external.com')['approved'] is False
    assert db.is_approved('user3@external.com')['approved'] is False


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_deactivate_approved_user(db):
    """Test workflow: approve user -> deactivate -> verify no longer approved."""
    # Approve user
    req_id = db.submit_request(name='Temp User', email='temp@external.com')['id']
    db.approve_request(req_id, reviewed_by='admin@company.com')

    # Verify approved
    assert db.is_approved('temp@external.com')['approved'] is True

    # Get staff ID and deactivate
    staff = db.get_all_staff(status='active')
    staff_id = staff[0]['id']

    db.delete_staff(staff_id)  # Soft delete (deactivate)

    # Should no longer be approved
    assert db.is_approved('temp@external.com')['approved'] is False

    # Should appear in inactive staff
    inactive = db.get_all_staff(status='inactive')
    assert len(inactive) == 1


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_cannot_submit_duplicate_pending_request(db):
    """Test that duplicate pending requests are prevented."""
    # Submit first request
    result1 = db.submit_request(name='User', email='duplicate@external.com')
    assert result1['success'] is True

    # Try to submit another for same email while first is pending
    result2 = db.submit_request(name='User', email='duplicate@external.com')

    assert 'error' in result2
    assert result2.get('already_pending') is True


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_cannot_request_if_already_approved(db):
    """Test that already approved users cannot submit new requests."""
    # Add staff directly
    db.add_staff(name='Approved User', email='approved@external.com')

    # Try to submit request
    result = db.submit_request(name='Approved User', email='approved@external.com')

    assert 'error' in result
    assert result.get('already_approved') is True


@pytest.mark.integration
@pytest.mark.quinn
@pytest.mark.database
def test_update_approved_staff_info(db):
    """Test workflow: approve user -> update their information."""
    # Approve user
    req_id = db.submit_request(
        name='John Contractor',
        email='john@external.com',
        phone='555-0001'
    )['id']

    db.approve_request(req_id, reviewed_by='admin@company.com')

    # Get staff ID
    staff = db.get_all_staff()[0]
    staff_id = staff['id']

    # Update staff information
    update_result = db.update_staff(
        staff_id,
        phone='555-0002',
        role='Senior Consultant',
        notes='Updated contact info'
    )

    assert update_result['success'] is True

    # Verify changes
    updated_staff = db.get_staff_by_id(staff_id)
    assert updated_staff['phone'] == '555-0002'
    assert updated_staff['role'] == 'Senior Consultant'
    assert updated_staff['notes'] == 'Updated contact info'

    # Should still be approved
    assert db.is_approved('john@external.com')['approved'] is True
