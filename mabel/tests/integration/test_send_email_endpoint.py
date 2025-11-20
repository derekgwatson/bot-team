"""Integration tests for send-email API endpoint."""

import os
from unittest.mock import MagicMock, patch

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


@pytest.fixture
def mock_email_sender():
    """Mock the EmailSender to avoid real SMTP calls."""
    with patch('services.email_sender.EmailSender.send') as mock_send:
        mock_send.return_value = 'test-message-id-123'
        yield mock_send


class TestSendEmailEndpoint:
    """Test /api/send-email endpoint."""

    def test_send_email_without_api_key_returns_401(self, client):
        """Test that requests without API key are rejected."""
        response = client.post('/api/send-email', json={
            'to': 'recipient@example.com',
            'subject': 'Test',
            'text_body': 'Test body'
        })

        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'unauthorized'

    def test_send_email_with_invalid_api_key_returns_401(self, client):
        """Test that requests with invalid API key are rejected."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'Test',
                                   'text_body': 'Test body'
                               },
                               headers={'X-Internal-Api-Key': 'wrong-key'})

        assert response.status_code == 401
        data = response.get_json()
        assert data['error'] == 'unauthorized'

    def test_send_email_with_valid_api_key_succeeds(self, client, mock_email_sender):
        """Test successful email send with valid API key."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'Test Email',
                                   'text_body': 'This is a test'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'sent'
        assert data['message_id'] == 'test-message-id-123'
        assert data['to'] == ['recipient@example.com']
        assert data['subject'] == 'Test Email'
        assert data['provider'] == 'smtp'

        # Verify EmailSender.send was called
        mock_email_sender.assert_called_once()

    def test_send_email_with_missing_to_returns_400(self, client):
        """Test that missing 'to' field returns validation error."""
        response = client.post('/api/send-email',
                               json={
                                   'subject': 'Test',
                                   'text_body': 'Body'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'
        assert 'details' in data

    def test_send_email_with_missing_content_returns_400(self, client):
        """Test that missing all content fields returns validation error."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'Test'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'

    def test_send_email_with_invalid_email_returns_400(self, client):
        """Test that invalid email address returns validation error."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'not-an-email',
                                   'subject': 'Test',
                                   'text_body': 'Body'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'

    def test_send_email_with_correlation_id_header(self, client, mock_email_sender):
        """Test that correlation ID from header is plumbed through."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'Test',
                                   'text_body': 'Body'
                               },
                               headers={
                                   'X-Internal-Api-Key': 'test-api-key-12345',
                                   'X-Correlation-Id': 'test-correlation-123'
                               })

        assert response.status_code == 200

        # Verify the email request has the correlation_id
        call_args = mock_email_sender.call_args
        email_request = call_args[0][0]
        assert email_request.metadata is not None
        assert email_request.metadata['correlation_id'] == 'test-correlation-123'

    def test_send_email_with_non_json_content_returns_400(self, client):
        """Test that non-JSON content returns validation error."""
        response = client.post('/api/send-email',
                               data='not json',
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'

    def test_send_email_with_html_body(self, client, mock_email_sender):
        """Test sending email with HTML body."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'HTML Test',
                                   'html_body': '<p>This is HTML</p>'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'sent'

    def test_send_email_with_multiple_recipients(self, client, mock_email_sender):
        """Test sending email to multiple recipients."""
        response = client.post('/api/send-email',
                               json={
                                   'to': ['recipient1@example.com', 'recipient2@example.com'],
                                   'cc': ['cc@example.com'],
                                   'subject': 'Multiple Recipients',
                                   'text_body': 'Body'
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert len(data['to']) == 2

    def test_send_email_with_attachments(self, client, mock_email_sender):
        """Test sending email with attachments."""
        response = client.post('/api/send-email',
                               json={
                                   'to': 'recipient@example.com',
                                   'subject': 'With Attachment',
                                   'text_body': 'See attachment',
                                   'attachments': [
                                       {
                                           'filename': 'test.txt',
                                           'content_type': 'text/plain',
                                           'content_base64': 'SGVsbG8gV29ybGQ='
                                       }
                                   ]
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200

    def test_send_email_failure_returns_502(self, client):
        """Test that SMTP send failure returns 502."""
        from services.email_sender import EmailSendError

        with patch('services.email_sender.EmailSender.send') as mock_send:
            mock_send.side_effect = EmailSendError("SMTP connection failed")

            response = client.post('/api/send-email',
                                   json={
                                       'to': 'recipient@example.com',
                                       'subject': 'Test',
                                       'text_body': 'Body'
                                   },
                                   headers={'X-Internal-Api-Key': 'test-api-key-12345'})

            assert response.status_code == 502
            data = response.get_json()
            assert data['error'] == 'send_failed'
            # Error details should be redacted
            assert 'SMTP connection failed' not in data['details']


class TestSendBatchEndpoint:
    """Test /api/send-batch endpoint."""

    def test_send_batch_without_api_key_returns_401(self, client):
        """Test that batch requests without API key are rejected."""
        response = client.post('/api/send-batch', json={
            'emails': [
                {'to': 'recipient@example.com', 'subject': 'Test', 'text_body': 'Body'}
            ]
        })

        assert response.status_code == 401

    def test_send_batch_with_valid_emails_succeeds(self, client, mock_email_sender):
        """Test successful batch email send."""
        response = client.post('/api/send-batch',
                               json={
                                   'emails': [
                                       {
                                           'to': 'recipient1@example.com',
                                           'subject': 'Email 1',
                                           'text_body': 'Body 1'
                                       },
                                       {
                                           'to': 'recipient2@example.com',
                                           'subject': 'Email 2',
                                           'text_body': 'Body 2'
                                       }
                                   ]
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'completed'
        assert data['total'] == 2
        assert data['success_count'] == 2
        assert data['failure_count'] == 0
        assert len(data['results']) == 2

        # Verify each result
        assert data['results'][0]['status'] == 'sent'
        assert data['results'][1]['status'] == 'sent'

    def test_send_batch_with_missing_emails_array_returns_400(self, client):
        """Test that missing 'emails' array returns validation error."""
        response = client.post('/api/send-batch',
                               json={},
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'

    def test_send_batch_with_empty_emails_array_returns_400(self, client):
        """Test that empty 'emails' array returns validation error."""
        response = client.post('/api/send-batch',
                               json={'emails': []},
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 400

    def test_send_batch_with_mixed_results(self, client):
        """Test batch with some successes and some failures."""
        with patch('services.email_sender.EmailSender.send') as mock_send:
            # First call succeeds, second fails
            from services.email_sender import EmailSendError
            mock_send.side_effect = ['msg-id-1', EmailSendError("Failed")]

            response = client.post('/api/send-batch',
                                   json={
                                       'emails': [
                                           {
                                               'to': 'recipient1@example.com',
                                               'subject': 'Email 1',
                                               'text_body': 'Body 1'
                                           },
                                           {
                                               'to': 'recipient2@example.com',
                                               'subject': 'Email 2',
                                               'text_body': 'Body 2'
                                           }
                                       ]
                                   },
                                   headers={'X-Internal-Api-Key': 'test-api-key-12345'})

            assert response.status_code == 200
            data = response.get_json()
            assert data['success_count'] == 1
            assert data['failure_count'] == 1
            assert data['results'][0]['status'] == 'sent'
            assert data['results'][1]['status'] == 'send_failed'

    def test_send_batch_with_validation_errors(self, client, mock_email_sender):
        """Test batch with validation errors."""
        response = client.post('/api/send-batch',
                               json={
                                   'emails': [
                                       {
                                           'to': 'valid@example.com',
                                           'subject': 'Valid',
                                           'text_body': 'Body'
                                       },
                                       {
                                           # Missing 'to' field
                                           'subject': 'Invalid',
                                           'text_body': 'Body'
                                       }
                                   ]
                               },
                               headers={'X-Internal-Api-Key': 'test-api-key-12345'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['success_count'] == 1
        assert data['failure_count'] == 1
        assert data['results'][0]['status'] == 'sent'
        assert data['results'][1]['status'] == 'validation_error'
