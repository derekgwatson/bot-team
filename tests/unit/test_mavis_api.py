"""
Unit tests for Mavis API routes.
"""

import os
import sys
import json
import pytest
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment before importing app
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['UNLEASHED_API_ID'] = 'test-api-id'
os.environ['UNLEASHED_API_KEY'] = 'test-api-key'
os.environ['BOT_API_KEY'] = 'test-bot-api-key'
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'

# Import Database directly using importlib to avoid sys.modules caching issues
module_path = project_root / 'mavis' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('mavis_database_db', module_path)
mavis_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mavis_db_module)
MavisDatabase = mavis_db_module.Database


@pytest.fixture
def mavis_app(tmp_path):
    """Create Mavis Flask app with test database."""
    # Clear any cached modules that could conflict with mavis's modules
    modules_to_clear = [k for k in sys.modules.keys()
                        if k.startswith(('config', 'database', 'services', 'api', 'web', 'app'))]
    saved_modules = {k: sys.modules.pop(k) for k in modules_to_clear}

    # Add mavis to path (must be first to take precedence)
    mavis_path = str(project_root / 'mavis')
    if mavis_path in sys.path:
        sys.path.remove(mavis_path)
    sys.path.insert(0, mavis_path)

    try:
        # Create test database
        test_db = MavisDatabase(str(tmp_path / 'test_mavis.db'))

        # Import mavis's modules fresh
        # Note: Use sys.modules to get the actual submodule, since database/__init__.py
        # exports 'db' which shadows the submodule when accessed via attribute
        import database.db
        import services.sync_service
        db_module = sys.modules['database.db']

        # Patch the db instances
        original_db = db_module.db
        original_sync_db = services.sync_service.db
        db_module.db = test_db
        services.sync_service.db = test_db

        # Import app after patching
        from app import app
        app.config['TESTING'] = True

        yield app

        # Restore original values
        db_module.db = original_db
        services.sync_service.db = original_sync_db
    finally:
        # Clean up: remove mavis modules to avoid polluting other tests
        modules_to_remove = [k for k in sys.modules.keys()
                             if k.startswith(('config', 'database', 'services', 'api', 'web', 'app'))]
        for k in modules_to_remove:
            sys.modules.pop(k, None)

        # Restore previously saved modules
        sys.modules.update(saved_modules)

        # Remove mavis from path
        if mavis_path in sys.path:
            sys.path.remove(mavis_path)


@pytest.fixture
def client(mavis_app):
    """Create test client."""
    return mavis_app.test_client()


@pytest.fixture
def auth_headers():
    """Headers with API key for authenticated requests."""
    return {'X-API-Key': 'test-bot-api-key'}


@pytest.mark.unit
@pytest.mark.mavis
class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_ok(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get('/health')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] in ['healthy', 'degraded']
        assert data['bot'] == 'Mavis'
        assert 'unleashed_sync' in data

    def test_health_includes_sync_status(self, client):
        """Test health endpoint includes sync status."""
        response = client.get('/health')

        data = json.loads(response.data)
        sync_status = data['unleashed_sync']
        assert 'status' in sync_status
        assert 'last_successful_sync_at' in sync_status


@pytest.mark.unit
@pytest.mark.mavis
class TestInfoEndpoint:
    """Test info endpoint."""

    def test_info_returns_bot_info(self, client):
        """Test info endpoint returns bot information."""
        response = client.get('/info')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Mavis'
        assert 'description' in data
        assert 'version' in data
        assert 'endpoints' in data


@pytest.mark.unit
@pytest.mark.mavis
class TestProductEndpoints:
    """Test product API endpoints."""

    def test_get_product_requires_auth(self, client):
        """Test that product endpoint requires authentication."""
        response = client.get('/api/products?code=TEST')
        assert response.status_code == 401

    def test_get_product_missing_code(self, client, auth_headers):
        """Test get product without code parameter."""
        response = client.get('/api/products', headers=auth_headers)

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_product_not_found(self, client, auth_headers):
        """Test get product that doesn't exist."""
        response = client.get('/api/products?code=NOTFOUND', headers=auth_headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_bulk_products_requires_auth(self, client):
        """Test that bulk endpoint requires authentication."""
        response = client.post(
            '/api/products/bulk',
            json={'codes': ['TEST']},
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_bulk_products_missing_codes(self, client, auth_headers):
        """Test bulk lookup without codes field."""
        response = client.post(
            '/api/products/bulk',
            json={},
            headers=auth_headers,
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_bulk_products_empty_list(self, client, auth_headers):
        """Test bulk lookup with empty codes list."""
        response = client.post(
            '/api/products/bulk',
            json={'codes': []},
            headers=auth_headers,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['products'] == []
        assert data['not_found'] == []

    def test_products_changed_since_requires_timestamp(self, client, auth_headers):
        """Test changed-since requires timestamp parameter."""
        response = client.get('/api/products/changed-since', headers=auth_headers)

        assert response.status_code == 400


@pytest.mark.unit
@pytest.mark.mavis
class TestSyncEndpoints:
    """Test sync API endpoints."""

    def test_sync_status_requires_auth(self, client):
        """Test that sync status requires authentication."""
        response = client.get('/api/sync/status')
        assert response.status_code == 401

    def test_sync_status_returns_status(self, client, auth_headers):
        """Test sync status endpoint."""
        response = client.get('/api/sync/status', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data

    def test_sync_run_requires_auth(self, client):
        """Test that sync run requires authentication."""
        response = client.post('/api/sync/run')
        assert response.status_code == 401

    def test_sync_history_requires_auth(self, client):
        """Test that sync history requires authentication."""
        response = client.get('/api/sync/history')
        assert response.status_code == 401

    def test_sync_history_returns_history(self, client, auth_headers):
        """Test sync history endpoint."""
        response = client.get('/api/sync/history', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'history' in data
        assert 'count' in data


@pytest.mark.unit
@pytest.mark.mavis
class TestIntroEndpoint:
    """Test intro endpoint."""

    def test_intro_requires_auth(self, client):
        """Test that intro requires authentication."""
        response = client.get('/api/intro')
        assert response.status_code == 401

    def test_intro_returns_info(self, client, auth_headers):
        """Test intro endpoint returns bot info."""
        response = client.get('/api/intro', headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['name'] == 'Mavis'
        assert 'capabilities' in data
        assert 'endpoints' in data
