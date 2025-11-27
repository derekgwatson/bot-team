"""
Unit tests for Scout database operations.
"""

import os
import sys
import pytest
import json
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'

# Add scout to path before importing its modules
sys.path.insert(0, str(project_root / 'scout'))

# Clear any cached config module to ensure scout's config is loaded
if 'config' in sys.modules:
    del sys.modules['config']

# Import ScoutDatabase directly using importlib to avoid sys.modules caching issues
module_path = project_root / 'scout' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('scout_database_db', module_path)
scout_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout_db_module)
ScoutDatabase = scout_db_module.ScoutDatabase


@pytest.fixture
def scout_db(tmp_path):
    """Create an isolated Scout database for testing."""
    db_path = tmp_path / "scout_test.db"
    return ScoutDatabase(str(db_path))


@pytest.mark.unit
@pytest.mark.scout
class TestIssueOperations:
    """Test issue tracking operations."""

    def test_record_issue_new(self, scout_db):
        """Test recording a new issue."""
        issue_id = scout_db.record_issue(
            issue_type='missing_description',
            issue_key='batch',
            issue_details={'codes': ['FAB001', 'FAB002']},
            ticket_id=12345,
            ticket_url='https://zendesk.com/tickets/12345'
        )

        assert issue_id is not None
        assert issue_id > 0

        # Verify the issue was stored
        issue = scout_db.get_issue('missing_description', 'batch')
        assert issue is not None
        assert issue['issue_type'] == 'missing_description'
        assert issue['issue_key'] == 'batch'
        assert issue['ticket_id'] == 12345
        assert issue['status'] == 'open'

    def test_record_issue_update_existing(self, scout_db):
        """Test updating an existing issue."""
        # Create initial issue
        issue_id1 = scout_db.record_issue(
            issue_type='sync_stale',
            issue_key='sync_stale',
            issue_details={'hours_since': 30}
        )

        # Record same issue again (should update last_seen)
        issue_id2 = scout_db.record_issue(
            issue_type='sync_stale',
            issue_key='sync_stale',
            issue_details={'hours_since': 35}
        )

        assert issue_id1 == issue_id2

        # Should still be one issue
        issues = scout_db.get_open_issues(issue_type='sync_stale')
        assert len(issues) == 1

    def test_is_issue_reported(self, scout_db):
        """Test checking if an issue is already reported."""
        assert scout_db.is_issue_reported('missing_description', 'batch') is False

        scout_db.record_issue(
            issue_type='missing_description',
            issue_key='batch'
        )

        assert scout_db.is_issue_reported('missing_description', 'batch') is True

    def test_is_issue_reported_resolved(self, scout_db):
        """Test that resolved issues are not considered reported."""
        scout_db.record_issue(
            issue_type='sync_failed',
            issue_key='sync_failed'
        )

        assert scout_db.is_issue_reported('sync_failed', 'sync_failed') is True

        scout_db.resolve_issue('sync_failed', 'sync_failed')

        assert scout_db.is_issue_reported('sync_failed', 'sync_failed') is False

    def test_resolve_issue(self, scout_db):
        """Test resolving an issue."""
        scout_db.record_issue(
            issue_type='obsolete_fabric',
            issue_key='batch'
        )

        assert scout_db.is_issue_reported('obsolete_fabric', 'batch') is True

        resolved = scout_db.resolve_issue('obsolete_fabric', 'batch')
        assert resolved is True

        issue = scout_db.get_issue('obsolete_fabric', 'batch')
        assert issue['status'] == 'resolved'
        assert issue['resolved_at'] is not None

    def test_resolve_nonexistent_issue(self, scout_db):
        """Test resolving an issue that doesn't exist."""
        resolved = scout_db.resolve_issue('nonexistent', 'key')
        assert resolved is False

    def test_reopen_resolved_issue(self, scout_db):
        """Test that recording a resolved issue reopens it."""
        # Create and resolve issue
        scout_db.record_issue(
            issue_type='incomplete_description',
            issue_key='batch'
        )
        scout_db.resolve_issue('incomplete_description', 'batch')

        # Record same issue again
        scout_db.record_issue(
            issue_type='incomplete_description',
            issue_key='batch',
            issue_details={'new': 'details'}
        )

        issue = scout_db.get_issue('incomplete_description', 'batch')
        assert issue['status'] == 'open'

    def test_get_open_issues(self, scout_db):
        """Test getting open issues."""
        # Create some issues
        scout_db.record_issue('type1', 'key1')
        scout_db.record_issue('type2', 'key2')
        scout_db.record_issue('type1', 'key3')

        # Resolve one
        scout_db.resolve_issue('type2', 'key2')

        open_issues = scout_db.get_open_issues()
        assert len(open_issues) == 2

        # Filter by type
        type1_issues = scout_db.get_open_issues(issue_type='type1')
        assert len(type1_issues) == 2

    def test_get_all_issues(self, scout_db):
        """Test getting all issues with limit."""
        for i in range(15):
            scout_db.record_issue(f'type{i % 3}', f'key{i}')

        all_issues = scout_db.get_all_issues(limit=10)
        assert len(all_issues) == 10

    def test_get_issue_stats(self, scout_db):
        """Test getting issue statistics."""
        # Create various issues
        scout_db.record_issue('missing_description', 'batch', ticket_id=1)
        scout_db.record_issue('obsolete_fabric', 'batch', ticket_id=2)
        scout_db.record_issue('sync_stale', 'sync_stale')

        # Resolve one
        scout_db.resolve_issue('sync_stale', 'sync_stale')

        stats = scout_db.get_issue_stats()

        assert stats['total'] == 3
        assert stats['open'] == 2
        assert stats['resolved'] == 1
        assert stats['with_tickets'] == 2
        assert stats['by_type']['missing_description'] == 1
        assert stats['by_type']['obsolete_fabric'] == 1


@pytest.mark.unit
@pytest.mark.scout
class TestCheckRunOperations:
    """Test check run history operations."""

    def test_start_check_run(self, scout_db):
        """Test starting a check run."""
        run_id = scout_db.start_check_run()

        assert run_id is not None
        assert run_id > 0

        last_run = scout_db.get_last_check_run()
        assert last_run['id'] == run_id
        assert last_run['status'] == 'running'

    def test_complete_check_run_success(self, scout_db):
        """Test completing a check run successfully."""
        run_id = scout_db.start_check_run()

        check_results = {
            'missing_descriptions': {'issues_found': 5},
            'obsolete_fabrics': {'issues_found': 2}
        }

        scout_db.complete_check_run(
            run_id,
            issues_found=7,
            tickets_created=2,
            check_results=check_results
        )

        last_run = scout_db.get_last_check_run()
        assert last_run['status'] == 'completed'
        assert last_run['issues_found'] == 7
        assert last_run['tickets_created'] == 2
        assert last_run['check_results'] == check_results
        assert last_run['finished_at'] is not None

    def test_complete_check_run_failure(self, scout_db):
        """Test completing a check run with failure."""
        run_id = scout_db.start_check_run()

        scout_db.complete_check_run(
            run_id,
            error_message='Connection refused'
        )

        last_run = scout_db.get_last_check_run()
        assert last_run['status'] == 'failed'
        assert last_run['error_message'] == 'Connection refused'

    def test_get_check_history(self, scout_db):
        """Test getting check run history."""
        # Create multiple check runs
        for i in range(5):
            run_id = scout_db.start_check_run()
            scout_db.complete_check_run(run_id, issues_found=i)

        history = scout_db.get_check_history(limit=3)
        assert len(history) == 3

        # Should be in reverse chronological order
        assert history[0]['issues_found'] == 4
        assert history[1]['issues_found'] == 3
        assert history[2]['issues_found'] == 2

    def test_get_last_check_run_none(self, scout_db):
        """Test getting last check run when none exist."""
        last_run = scout_db.get_last_check_run()
        assert last_run is None
