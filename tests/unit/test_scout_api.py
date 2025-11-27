"""
Unit tests for Scout API routes.
"""

import os
import sys
import pytest
import json
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
scout_path = project_root / 'scout'

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['BOT_API_KEY'] = 'test-api-key'

# Clear any cached config and set up scout's path BEFORE loading the module
if 'config' in sys.modules:
    del sys.modules['config']
sys.path.insert(0, str(scout_path))
sys.path.insert(0, str(project_root))

# Import ScoutDatabase directly using importlib to avoid sys.modules caching issues
module_path = scout_path / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('scout_database_db', module_path)
scout_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout_db_module)
ScoutDatabase = scout_db_module.ScoutDatabase


@pytest.fixture
def scout_app(tmp_path):
    """Create Scout Flask app for testing."""
    # Clear any cached modules that could conflict with scout's modules
    modules_to_clear = [k for k in sys.modules.keys()
                        if k.startswith(('config', 'database', 'services', 'api', 'web', 'app'))]
    saved_modules = {k: sys.modules.pop(k) for k in modules_to_clear}

    # Add scout to path (must be first to take precedence)
    scout_path = str(project_root / 'scout')
    if scout_path in sys.path:
        sys.path.remove(scout_path)
    sys.path.insert(0, scout_path)

    try:
        # Create test database
        test_db = ScoutDatabase(str(tmp_path / "scout_test.db"))

        # Import scout's modules fresh
        import database.db
        import services.checker

        # Patch the db instances
        original_db = database.db.db
        original_checker_db = services.checker.db
        database.db.db = test_db
        services.checker.db = test_db

        # Import app after patching
        from app import app
        app.config['TESTING'] = True

        yield app, test_db

        # Restore original values
        database.db.db = original_db
        services.checker.db = original_checker_db
    finally:
        # Clean up: remove scout modules to avoid polluting other tests
        modules_to_remove = [k for k in sys.modules.keys()
                             if k.startswith(('config', 'database', 'services', 'api', 'web', 'app'))]
        for k in modules_to_remove:
            sys.modules.pop(k, None)

        # Restore previously saved modules
        sys.modules.update(saved_modules)

        # Remove scout from path
        if scout_path in sys.path:
            sys.path.remove(scout_path)


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

    def test_health_includes_version(self, client):
        """Test health check includes version info."""
        response = client.get('/health')
        data = json.loads(response.data)

        # Health endpoint should include standard fields
        assert 'status' in data
        assert data['status'] == 'healthy'
        assert 'version' in data


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
        """Test checks status returns last run info."""
        response = client.get('/api/checks/status', headers=api_headers)
        assert response.status_code == 200

        data = json.loads(response.data)
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
