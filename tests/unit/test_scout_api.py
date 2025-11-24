"""
Unit tests for Scout API routes.
"""

import os
import sys
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['BOT_API_KEY'] = 'test-api-key'


@pytest.fixture
def scout_app(tmp_path):
    """Create Scout Flask app for testing."""
    sys.path.insert(0, str(project_root / 'scout'))

    # Patch database before importing app
    from database.db import ScoutDatabase
    test_db = ScoutDatabase(str(tmp_path / "scout_test.db"))

    with patch('database.db.db', test_db), \
         patch('services.checker.db', test_db), \
         patch('api.routes.db', test_db), \
         patch('web.routes.db', test_db):

        from app import app
        app.config['TESTING'] = True

        yield app, test_db


@pytest.fixture
def client(scout_app):
    """Create test client."""
    app, db = scout_app
    return app.test_client()


@pytest.fixture
def api_headers():
    """Headers for API requests."""
    return {'X-API-Key': 'test-api-key'}


@pytest.mark.unit
@pytest.mark.scout
class TestScoutHealthEndpoint:
    """Test health endpoint."""

    def test_health_returns_ok(self, client):
        """Test health check returns 200."""
        response = client.get('/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'status' in data
        assert 'bot' in data
        assert data['bot'] == 'Scout'

    def test_health_includes_scheduler_status(self, client):
        """Test health check includes scheduler info."""
        response = client.get('/health')
        data = json.loads(response.data)

        assert 'scheduler' in data
        assert 'enabled' in data['scheduler']
        assert 'running' in data['scheduler']


@pytest.mark.unit
@pytest.mark.scout
class TestScoutInfoEndpoint:
    """Test info endpoint."""

    def test_info_returns_bot_details(self, client):
        """Test info returns bot information."""
        response = client.get('/info')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['name'] == 'Scout'
        assert 'description' in data
        assert 'version' in data
        assert 'endpoints' in data
        assert 'dependencies' in data


@pytest.mark.unit
@pytest.mark.scout
class TestScoutAPIIntro:
    """Test API intro endpoint."""

    def test_intro_requires_auth(self, client):
        """Test intro endpoint requires API key."""
        response = client.get('/api/intro')
        assert response.status_code == 401

    def test_intro_returns_capabilities(self, client, api_headers):
        """Test intro returns bot capabilities."""
        response = client.get('/api/intro', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['name'] == 'Scout'
        assert 'capabilities' in data
        assert len(data['capabilities']) > 0


@pytest.mark.unit
@pytest.mark.scout
class TestScoutAPIChecks:
    """Test check-related API endpoints."""

    def test_checks_status_requires_auth(self, client):
        """Test checks status requires API key."""
        response = client.get('/api/checks/status')
        assert response.status_code == 401

    def test_checks_status_returns_info(self, client, api_headers, scout_app):
        """Test checks status returns scheduler and last run info."""
        response = client.get('/api/checks/status', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'scheduler' in data
        assert 'last_run' in data

    def test_checks_history_returns_list(self, client, api_headers, scout_app):
        """Test checks history returns list of runs."""
        app, db = scout_app

        # Create some check runs
        run_id = db.start_check_run()
        db.complete_check_run(run_id, issues_found=5)

        response = client.get('/api/checks/history', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'history' in data
        assert 'count' in data
        assert len(data['history']) == 1


@pytest.mark.unit
@pytest.mark.scout
class TestScoutAPIIssues:
    """Test issue-related API endpoints."""

    def test_issues_requires_auth(self, client):
        """Test issues endpoint requires API key."""
        response = client.get('/api/issues')
        assert response.status_code == 401

    def test_issues_returns_list(self, client, api_headers, scout_app):
        """Test issues endpoint returns list."""
        app, db = scout_app

        # Create some issues
        db.record_issue('missing_description', 'batch')
        db.record_issue('obsolete_fabric', 'batch')

        response = client.get('/api/issues', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'issues' in data
        assert 'count' in data
        assert data['count'] == 2

    def test_issues_filter_by_status(self, client, api_headers, scout_app):
        """Test filtering issues by status."""
        app, db = scout_app

        db.record_issue('type1', 'key1')
        db.record_issue('type2', 'key2')
        db.resolve_issue('type2', 'key2')

        response = client.get('/api/issues?status=open', headers=api_headers)
        data = json.loads(response.data)

        assert data['count'] == 1

    def test_issues_stats(self, client, api_headers, scout_app):
        """Test issues stats endpoint."""
        app, db = scout_app

        db.record_issue('missing_description', 'batch', ticket_id=123)
        db.record_issue('obsolete_fabric', 'batch')

        response = client.get('/api/issues/stats', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['total'] == 2
        assert data['open'] == 2
        assert data['with_tickets'] == 1

    def test_resolve_issue_via_api(self, client, api_headers, scout_app):
        """Test resolving an issue via API."""
        app, db = scout_app

        db.record_issue('sync_stale', 'sync_stale')

        response = client.post(
            '/api/issues/sync_stale/sync_stale/resolve',
            headers=api_headers
        )
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True

        # Verify resolved
        issue = db.get_issue('sync_stale', 'sync_stale')
        assert issue['status'] == 'resolved'

    def test_resolve_nonexistent_issue(self, client, api_headers):
        """Test resolving a non-existent issue."""
        response = client.post(
            '/api/issues/nonexistent/key/resolve',
            headers=api_headers
        )
        assert response.status_code == 404
