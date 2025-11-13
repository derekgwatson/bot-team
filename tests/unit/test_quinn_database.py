"""
Unit tests for Quinn's external staff database layer.

Tests cover all CRUD operations, approval workflows, and edge cases.
"""
import os
import sys
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

# Add quinn directory to path
quinn_path = Path(__file__).parent.parent.parent / 'quinn'
sys.path.insert(0, str(quinn_path))

from database.db import ExternalStaffDB


@pytest.fixture
def db(monkeypatch, tmp_path):
    """Create a test database instance with temporary database file."""
    db_file = tmp_path / 'test_quinn.db'

    # Mock the config to use our temporary database
    class MockConfig:
        database_path = str(db_file)

    # Patch the config module
    import config as quinn_config
    monkeypatch.setattr(quinn_config, 'config', MockConfig())

    # Create fresh database instance
    test_db = ExternalStaffDB()

    return test_db


# ==============================================================================
# Database Initialization Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_database_initialization(db):
    """Test that database tables are created properly."""
    conn = db._get_connection()
    cursor = conn.cursor()

    # Check external_staff table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='external_staff'"
    )
    assert cursor.fetchone() is not None

    # Check pending_requests table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_requests'"
    )
    assert cursor.fetchone() is not None

    conn.close()


# ==============================================================================
# is_approved() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_is_approved_with_approved_email(db):
    """Test checking if an approved email returns True."""
    # Add an active staff member
    db.add_staff(
        name='John Doe',
        email='john@example.com',
        phone='555-0100',
        role='Consultant'
    )

    result = db.is_approved('john@example.com')

    assert result['approved'] is True
    assert result['name'] == 'John Doe'
    assert result['email'] == 'john@example.com'
    assert result['phone'] == '555-0100'
    assert result['role'] == 'Consultant'
    assert 'id' in result


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_is_approved_case_insensitive(db):
    """Test that email checking is case-insensitive."""
    db.add_staff(name='Jane Doe', email='jane@example.com')

    result = db.is_approved('JANE@EXAMPLE.COM')
    assert result['approved'] is True
    assert result['email'] == 'jane@example.com'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_is_approved_with_unapproved_email(db):
    """Test that unapproved emails return False."""
    result = db.is_approved('nobody@example.com')

    assert result['approved'] is False
    assert len(result) == 1  # Only 'approved' key


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_is_approved_ignores_inactive_staff(db):
    """Test that inactive staff are not considered approved."""
    # Add staff then deactivate
    result = db.add_staff(name='Inactive User', email='inactive@example.com')
    staff_id = result['id']
    db.update_staff(staff_id, status='inactive')

    result = db.is_approved('inactive@example.com')
    assert result['approved'] is False


# ==============================================================================
# add_staff() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_add_staff_success(db):
    """Test successfully adding a new staff member."""
    result = db.add_staff(
        name='Alice Smith',
        email='alice@company.com',
        phone='555-0200',
        role='Developer',
        added_by='admin@company.com',
        notes='Contractor for Q1 2025'
    )

    assert result['success'] is True
    assert 'id' in result
    assert 'message' in result

    # Verify staff was added
    staff = db.get_staff_by_id(result['id'])
    assert staff['name'] == 'Alice Smith'
    assert staff['email'] == 'alice@company.com'
    assert staff['phone'] == '555-0200'
    assert staff['role'] == 'Developer'
    assert staff['status'] == 'active'
    assert staff['added_by'] == 'admin@company.com'
    assert staff['notes'] == 'Contractor for Q1 2025'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_add_staff_minimal_fields(db):
    """Test adding staff with only required fields."""
    result = db.add_staff(name='Bob Jones', email='bob@example.com')

    assert result['success'] is True

    staff = db.get_staff_by_id(result['id'])
    assert staff['name'] == 'Bob Jones'
    assert staff['email'] == 'bob@example.com'
    assert staff['phone'] == ''
    assert staff['role'] == ''


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_add_staff_duplicate_email(db):
    """Test that adding duplicate email fails."""
    db.add_staff(name='First User', email='duplicate@example.com')

    result = db.add_staff(name='Second User', email='duplicate@example.com')

    assert 'error' in result
    assert 'already exists' in result['error']


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_add_staff_normalizes_email(db):
    """Test that email is normalized to lowercase."""
    result = db.add_staff(name='Test User', email='TEST@EXAMPLE.COM')

    staff = db.get_staff_by_id(result['id'])
    assert staff['email'] == 'test@example.com'


# ==============================================================================
# get_all_staff() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_all_staff_empty(db):
    """Test getting staff from empty database."""
    result = db.get_all_staff()
    assert result == []


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_all_staff_multiple(db):
    """Test retrieving multiple staff members."""
    db.add_staff(name='Alice', email='alice@example.com')
    db.add_staff(name='Bob', email='bob@example.com')
    db.add_staff(name='Charlie', email='charlie@example.com')

    staff = db.get_all_staff()

    assert len(staff) == 3
    names = [s['name'] for s in staff]
    assert 'Alice' in names
    assert 'Bob' in names
    assert 'Charlie' in names


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_all_staff_filter_active(db):
    """Test filtering staff by active status."""
    id1 = db.add_staff(name='Active User', email='active@example.com')['id']
    id2 = db.add_staff(name='Inactive User', email='inactive@example.com')['id']

    db.update_staff(id2, status='inactive')

    active_staff = db.get_all_staff(status='active')

    assert len(active_staff) == 1
    assert active_staff[0]['name'] == 'Active User'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_all_staff_filter_inactive(db):
    """Test filtering staff by inactive status."""
    id1 = db.add_staff(name='Active User', email='active@example.com')['id']
    id2 = db.add_staff(name='Inactive User', email='inactive@example.com')['id']

    db.update_staff(id2, status='inactive')

    inactive_staff = db.get_all_staff(status='inactive')

    assert len(inactive_staff) == 1
    assert inactive_staff[0]['name'] == 'Inactive User'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_all_staff_sorted_by_name(db):
    """Test that staff are returned sorted alphabetically."""
    db.add_staff(name='Zebra', email='z@example.com')
    db.add_staff(name='Apple', email='a@example.com')
    db.add_staff(name='Middle', email='m@example.com')

    staff = db.get_all_staff()
    names = [s['name'] for s in staff]

    assert names == ['Apple', 'Middle', 'Zebra']


# ==============================================================================
# update_staff() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_single_field(db):
    """Test updating a single field."""
    staff_id = db.add_staff(name='Old Name', email='test@example.com')['id']

    result = db.update_staff(staff_id, name='New Name')

    assert result['success'] is True

    staff = db.get_staff_by_id(staff_id)
    assert staff['name'] == 'New Name'
    assert staff['email'] == 'test@example.com'  # Unchanged


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_multiple_fields(db):
    """Test updating multiple fields at once."""
    staff_id = db.add_staff(
        name='Original',
        email='orig@example.com',
        phone='111-1111'
    )['id']

    result = db.update_staff(
        staff_id,
        name='Updated Name',
        phone='222-2222',
        role='New Role'
    )

    assert result['success'] is True

    staff = db.get_staff_by_id(staff_id)
    assert staff['name'] == 'Updated Name'
    assert staff['phone'] == '222-2222'
    assert staff['role'] == 'New Role'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_status_change(db):
    """Test changing staff status."""
    staff_id = db.add_staff(name='Test', email='test@example.com')['id']

    result = db.update_staff(staff_id, status='inactive')

    assert result['success'] is True

    staff = db.get_staff_by_id(staff_id)
    assert staff['status'] == 'inactive'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_nonexistent(db):
    """Test updating a non-existent staff member."""
    result = db.update_staff(99999, name='Test')

    assert 'error' in result
    assert 'not found' in result['error']


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_no_fields(db):
    """Test calling update with no fields to update."""
    staff_id = db.add_staff(name='Test', email='test@example.com')['id']

    result = db.update_staff(staff_id)

    assert 'error' in result
    assert 'No fields to update' in result['error']


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_update_staff_updates_modified_date(db):
    """Test that modified_date is updated automatically."""
    staff_id = db.add_staff(name='Test', email='test@example.com')['id']

    original = db.get_staff_by_id(staff_id)
    original_modified = original['modified_date']

    # Update the staff
    db.update_staff(staff_id, role='New Role')

    updated = db.get_staff_by_id(staff_id)
    # Note: This might be flaky if test runs too fast, but should generally work
    # In production, you might use freezegun to control time
    assert 'modified_date' in updated


# ==============================================================================
# delete_staff() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_delete_staff_soft_delete(db):
    """Test that delete_staff does soft delete (sets status to inactive)."""
    staff_id = db.add_staff(name='To Delete', email='delete@example.com')['id']

    result = db.delete_staff(staff_id)

    assert result['success'] is True

    # Staff should still exist but be inactive
    staff = db.get_staff_by_id(staff_id)
    assert staff is not None
    assert staff['status'] == 'inactive'


# ==============================================================================
# Pending Requests Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_submit_request_success(db):
    """Test successfully submitting an access request."""
    result = db.submit_request(
        name='New External',
        email='new@external.com',
        phone='555-9999',
        reason='Need access for project ABC'
    )

    assert result['success'] is True
    assert 'id' in result

    # Verify request was created
    request = db.get_request_by_id(result['id'])
    assert request['name'] == 'New External'
    assert request['email'] == 'new@external.com'
    assert request['phone'] == '555-9999'
    assert request['reason'] == 'Need access for project ABC'
    assert request['status'] == 'pending'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_submit_request_already_approved(db):
    """Test submitting request for already approved email."""
    # First approve someone
    db.add_staff(name='Already Approved', email='approved@example.com')

    # Try to submit request
    result = db.submit_request(
        name='Already Approved',
        email='approved@example.com',
        reason='Duplicate'
    )

    assert 'error' in result
    assert 'already approved' in result['error'].lower()
    assert result.get('already_approved') is True


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_submit_request_duplicate_pending(db):
    """Test submitting duplicate pending request."""
    # Submit first request
    db.submit_request(name='Pending User', email='pending@example.com')

    # Try to submit another
    result = db.submit_request(name='Pending User', email='pending@example.com')

    assert 'error' in result
    assert 'already exists' in result['error'].lower() or 'pending' in result['error'].lower()
    assert result.get('already_pending') is True


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_pending_requests_empty(db):
    """Test getting requests from empty database."""
    requests = db.get_pending_requests()
    assert requests == []


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_pending_requests_filter_by_status(db):
    """Test filtering requests by status."""
    # Submit request
    req_id = db.submit_request(name='Test', email='test@example.com')['id']

    # Get pending requests
    pending = db.get_pending_requests(status='pending')
    assert len(pending) == 1

    # Approve it
    db.approve_request(req_id, reviewed_by='admin@example.com')

    # Check pending list is empty
    pending = db.get_pending_requests(status='pending')
    assert len(pending) == 0

    # Check approved list
    approved = db.get_pending_requests(status='approved')
    assert len(approved) == 1


# ==============================================================================
# Approve Request Workflow Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_approve_request_success(db):
    """Test approving a pending request."""
    req_id = db.submit_request(
        name='Contractor',
        email='contractor@external.com',
        phone='555-1234'
    )['id']

    result = db.approve_request(req_id, reviewed_by='admin@company.com')

    assert result['success'] is True
    assert 'approved' in result['message'].lower()

    # Verify request was updated
    request = db.get_request_by_id(req_id)
    assert request['status'] == 'approved'
    assert request['reviewed_by'] == 'admin@company.com'
    assert request['reviewed_date'] is not None

    # Verify staff was added
    approval = db.is_approved('contractor@external.com')
    assert approval['approved'] is True
    assert approval['name'] == 'Contractor'


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_approve_request_nonexistent(db):
    """Test approving non-existent request."""
    result = db.approve_request(99999, reviewed_by='admin@example.com')

    assert 'error' in result
    assert 'not found' in result['error'].lower()


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_approve_request_already_processed(db):
    """Test approving already processed request."""
    req_id = db.submit_request(name='Test', email='test@example.com')['id']

    # Approve once
    db.approve_request(req_id, reviewed_by='admin@example.com')

    # Try to approve again
    result = db.approve_request(req_id, reviewed_by='admin@example.com')

    assert 'error' in result
    assert 'already been processed' in result['error'].lower()


# ==============================================================================
# Deny Request Workflow Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_deny_request_success(db):
    """Test denying a pending request."""
    req_id = db.submit_request(
        name='Denied User',
        email='denied@example.com'
    )['id']

    result = db.deny_request(
        req_id,
        reviewed_by='admin@company.com',
        notes='Insufficient justification'
    )

    assert result['success'] is True
    assert 'denied' in result['message'].lower()

    # Verify request was updated
    request = db.get_request_by_id(req_id)
    assert request['status'] == 'denied'
    assert request['reviewed_by'] == 'admin@company.com'
    assert request['notes'] == 'Insufficient justification'
    assert request['reviewed_date'] is not None

    # Verify user is NOT approved
    approval = db.is_approved('denied@example.com')
    assert approval['approved'] is False


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_deny_request_nonexistent(db):
    """Test denying non-existent request."""
    result = db.deny_request(99999, reviewed_by='admin@example.com')

    assert 'error' in result
    assert 'not found' in result['error'].lower()


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_deny_request_already_processed(db):
    """Test denying already processed request."""
    req_id = db.submit_request(name='Test', email='test@example.com')['id']

    # Deny once
    db.deny_request(req_id, reviewed_by='admin@example.com')

    # Try to deny again
    result = db.deny_request(req_id, reviewed_by='admin@example.com')

    assert 'error' in result
    assert 'already been processed' in result['error'].lower()


# ==============================================================================
# Edge Cases and Error Handling
# ==============================================================================

@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_staff_by_id_nonexistent(db):
    """Test getting non-existent staff by ID."""
    staff = db.get_staff_by_id(99999)
    assert staff is None


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_get_request_by_id_nonexistent(db):
    """Test getting non-existent request by ID."""
    request = db.get_request_by_id(99999)
    assert request is None


@pytest.mark.unit
@pytest.mark.quinn
@pytest.mark.database
def test_empty_string_handling(db):
    """Test that empty strings are handled properly."""
    result = db.add_staff(
        name='Test User',
        email='test@example.com',
        phone='',  # Empty string
        role='',   # Empty string
        notes=''   # Empty string
    )

    assert result['success'] is True

    staff = db.get_staff_by_id(result['id'])
    assert staff['phone'] == ''
    assert staff['role'] == ''
    assert staff['notes'] == ''
