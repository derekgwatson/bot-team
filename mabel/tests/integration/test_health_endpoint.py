"""Integration tests for health check endpoints."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    # Set required environment variables for testing
    os.environ['MABEL_INTERNAL_API_KEY'] = 'test-api-key-12345'
    os.environ['EMAIL_SMTP_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_SMTP_PASSWORD'] = 'test-password'
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-xyz'

    from app import app
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Test that health endpoint returns 200 OK."""
        response = client.get('/health')

        assert response.status_code == 200

    def test_health_endpoint_returns_correct_structure(self, client):
        """Test that health endpoint returns correct JSON structure."""
        response = client.get('/health')
        data = response.get_json()

        assert 'status' in data
        assert 'name' in data
        assert 'version' in data
        assert 'uptime_seconds' in data

        assert data['status'] == 'ok'
        assert data['name'] == 'mabel'
        assert data['version'] == '0.1.0'

    def test_health_endpoint_uptime_is_numeric(self, client):
        """Test that uptime is a numeric value."""
        response = client.get('/health')
        data = response.get_json()

        assert isinstance(data['uptime_seconds'], (int, float))
        assert data['uptime_seconds'] >= 0

    def test_health_endpoint_does_not_require_auth(self, client):
        """Test that health endpoint does not require authentication."""
        # Should work without X-Internal-Api-Key header
        response = client.get('/health')

        assert response.status_code == 200


class TestHealthDeepEndpoint:
    """Test /health/deep endpoint."""

    def test_health_deep_with_successful_smtp_connection(self, client):
        """Test deep health check with successful SMTP connection."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            response = client.get('/health/deep')

            assert response.status_code == 200
            data = response.get_json()

            assert data['status'] == 'ok'
            assert data['smtp_ok'] is True
            assert 'details' in data
            assert 'smtp_host' in data['details']
            assert 'smtp_port' in data['details']
            assert 'smtp_use_tls' in data['details']
            assert 'smtp_test_duration_ms' in data['details']

    def test_health_deep_with_failed_smtp_connection(self, client):
        """Test deep health check with failed SMTP connection."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = False

            response = client.get('/health/deep')

            # Should return 503 (Service Unavailable) when SMTP is down
            assert response.status_code == 503
            data = response.get_json()

            assert data['status'] == 'degraded'
            assert data['smtp_ok'] is False

    def test_health_deep_returns_correct_structure(self, client):
        """Test that deep health check returns correct structure."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            response = client.get('/health/deep')
            data = response.get_json()

            # Check all required fields
            assert 'status' in data
            assert 'name' in data
            assert 'version' in data
            assert 'uptime_seconds' in data
            assert 'smtp_ok' in data
            assert 'details' in data

            # Check details structure
            details = data['details']
            assert 'smtp_host' in details
            assert 'smtp_port' in details
            assert 'smtp_use_tls' in details
            assert 'smtp_test_duration_ms' in details

    def test_health_deep_smtp_details(self, client):
        """Test that SMTP details match configuration."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            response = client.get('/health/deep')
            data = response.get_json()

            details = data['details']
            assert details['smtp_host'] == 'smtp.example.com'
            assert details['smtp_port'] == 587
            assert details['smtp_use_tls'] is True

    def test_health_deep_duration_is_numeric(self, client):
        """Test that SMTP test duration is numeric."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            response = client.get('/health/deep')
            data = response.get_json()

            duration = data['details']['smtp_test_duration_ms']
            assert isinstance(duration, (int, float))
            assert duration >= 0

    def test_health_deep_does_not_require_auth(self, client):
        """Test that deep health endpoint does not require authentication."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            # Should work without X-Internal-Api-Key header
            response = client.get('/health/deep')

            assert response.status_code == 200

    def test_health_deep_metadata_fields(self, client):
        """Test that metadata fields (name, version, uptime) are present."""
        with patch('services.email_sender.EmailSender.test_connection') as mock_test:
            mock_test.return_value = True

            response = client.get('/health/deep')
            data = response.get_json()

            assert data['name'] == 'mabel'
            assert data['version'] == '0.1.0'
            assert isinstance(data['uptime_seconds'], (int, float))
            assert data['uptime_seconds'] >= 0
