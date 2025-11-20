"""Unit tests for email sender service."""

import smtplib
from unittest.mock import MagicMock, Mock, patch

import pytest

from services.email_models import EmailAttachment, EmailRequest
from services.email_sender import EmailSendError, EmailSender


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.default_from = "no-reply@example.com"
    config.default_reply_to = "support@example.com"
    config.default_sender_name = "Bot Team"
    config.smtp_host = "smtp.example.com"
    config.smtp_port = 587
    config.smtp_use_tls = True
    config.smtp_username = "user@example.com"
    config.smtp_password = "password123"
    return config


@pytest.fixture
def email_sender(mock_config):
    """Create an EmailSender instance with mock config."""
    return EmailSender(mock_config)


@pytest.fixture
def simple_email_request():
    """Create a simple email request."""
    return EmailRequest(
        to="recipient@example.com",
        subject="Test Email",
        text_body="This is a test email."
    )


class TestEmailSender:
    """Test EmailSender class."""

    def test_initialization(self, mock_config):
        """Test EmailSender initialization."""
        sender = EmailSender(mock_config)
        assert sender.config == mock_config

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_simple_text_email(self, mock_smtp_class, email_sender, simple_email_request):
        """Test sending a simple text-only email."""
        # Setup mock SMTP
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Send email
        message_id = email_sender.send(simple_email_request)

        # Verify SMTP was called correctly
        mock_smtp_class.assert_called_once_with('smtp.example.com', 587)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with('user@example.com', 'password123')
        mock_smtp.send_message.assert_called_once()
        mock_smtp.quit.assert_called_once()

        # Verify message_id was generated
        assert isinstance(message_id, str)
        assert len(message_id) > 0

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_html_email(self, mock_smtp_class, email_sender):
        """Test sending an HTML-only email."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        request = EmailRequest(
            to="recipient@example.com",
            subject="Test HTML",
            html_body="<p>This is HTML</p>"
        )

        message_id = email_sender.send(request)

        mock_smtp.send_message.assert_called_once()
        assert isinstance(message_id, str)

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_multipart_email(self, mock_smtp_class, email_sender):
        """Test sending email with both text and HTML."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        request = EmailRequest(
            to="recipient@example.com",
            subject="Test Multipart",
            text_body="Plain text version",
            html_body="<p>HTML version</p>"
        )

        message_id = email_sender.send(request)

        mock_smtp.send_message.assert_called_once()
        assert isinstance(message_id, str)

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_with_attachments(self, mock_smtp_class, email_sender):
        """Test sending email with attachments."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Base64 encoded "Hello World"
        request = EmailRequest(
            to="recipient@example.com",
            subject="Test with Attachment",
            text_body="See attachment",
            attachments=[
                EmailAttachment(
                    filename="test.txt",
                    content_type="text/plain",
                    content_base64="SGVsbG8gV29ybGQ="
                )
            ]
        )

        message_id = email_sender.send(request)

        mock_smtp.send_message.assert_called_once()
        assert isinstance(message_id, str)

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_with_multiple_recipients(self, mock_smtp_class, email_sender):
        """Test sending email to multiple recipients including CC and BCC."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        request = EmailRequest(
            to=["recipient1@example.com", "recipient2@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Test Multiple Recipients",
            text_body="Body"
        )

        email_sender.send(request)

        # Verify send_message was called
        mock_smtp.send_message.assert_called_once()

        # Get the call arguments
        call_args = mock_smtp.send_message.call_args
        # to_addrs should include to, cc, and bcc
        assert 'to_addrs' in call_args.kwargs
        to_addrs = call_args.kwargs['to_addrs']
        assert len(to_addrs) == 4
        assert 'recipient1@example.com' in to_addrs
        assert 'bcc@example.com' in to_addrs

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_without_tls(self, mock_smtp_class, email_sender, simple_email_request):
        """Test sending email without TLS."""
        email_sender.config.smtp_use_tls = False
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        email_sender.send(simple_email_request)

        # starttls should not be called
        mock_smtp.starttls.assert_not_called()
        mock_smtp.send_message.assert_called_once()

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_without_credentials(self, mock_smtp_class, email_sender, simple_email_request):
        """Test sending email without SMTP credentials."""
        email_sender.config.smtp_username = ""
        email_sender.config.smtp_password = ""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        email_sender.send(simple_email_request)

        # login should not be called
        mock_smtp.login.assert_not_called()
        mock_smtp.send_message.assert_called_once()

    @patch('services.email_sender.smtplib.SMTP')
    def test_send_with_custom_from_address(self, mock_smtp_class, email_sender):
        """Test sending email with custom from address."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        request = EmailRequest(
            from_address="custom@example.com",
            from_name="Custom Sender",
            to="recipient@example.com",
            subject="Test Custom From",
            text_body="Body"
        )

        email_sender.send(request)

        mock_smtp.send_message.assert_called_once()

    @patch('services.email_sender.smtplib.SMTP')
    def test_smtp_exception_raises_email_send_error(self, mock_smtp_class, email_sender, simple_email_request):
        """Test that SMTP exceptions are converted to EmailSendError."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.send_message.side_effect = smtplib.SMTPException("SMTP Error")

        with pytest.raises(EmailSendError) as exc_info:
            email_sender.send(simple_email_request)

        assert "SMTP error" in str(exc_info.value)

    @patch('services.email_sender.smtplib.SMTP')
    def test_connection_exception_raises_email_send_error(self, mock_smtp_class, email_sender, simple_email_request):
        """Test that connection exceptions are converted to EmailSendError."""
        mock_smtp_class.side_effect = ConnectionError("Cannot connect")

        with pytest.raises(EmailSendError) as exc_info:
            email_sender.send(simple_email_request)

        assert "Connection error" in str(exc_info.value) or "Failed to send" in str(exc_info.value)

    @patch('services.email_sender.render_email_template')
    @patch('services.email_sender.smtplib.SMTP')
    def test_send_with_template(self, mock_smtp_class, mock_render, email_sender):
        """Test sending email using a template."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # Mock template rendering
        mock_render.return_value = ("Plain text content", "<p>HTML content</p>")

        request = EmailRequest(
            to="recipient@example.com",
            subject="Test Template",
            template="example_welcome",
            template_vars={"user_name": "Test User"}
        )

        email_sender.send(request)

        # Verify template was rendered
        mock_render.assert_called_once_with("example_welcome", {"user_name": "Test User"})
        mock_smtp.send_message.assert_called_once()

    @patch('services.email_sender.render_email_template')
    @patch('services.email_sender.smtplib.SMTP')
    def test_template_error_raises_email_send_error(self, mock_smtp_class, mock_render, email_sender):
        """Test that template errors are converted to EmailSendError."""
        from services.templates import TemplateError

        mock_render.side_effect = TemplateError("Template not found")

        request = EmailRequest(
            to="recipient@example.com",
            subject="Test Template Error",
            template="nonexistent_template"
        )

        with pytest.raises(EmailSendError) as exc_info:
            email_sender.send(request)

        assert "Template rendering failed" in str(exc_info.value)

    @patch('services.email_sender.smtplib.SMTP')
    def test_test_connection_success(self, mock_smtp_class, email_sender):
        """Test successful SMTP connection test."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        result = email_sender.test_connection()

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.noop.assert_called_once()
        mock_smtp.quit.assert_called_once()

    @patch('services.email_sender.smtplib.SMTP')
    def test_test_connection_failure(self, mock_smtp_class, email_sender):
        """Test failed SMTP connection test."""
        mock_smtp_class.side_effect = smtplib.SMTPException("Connection failed")

        result = email_sender.test_connection()

        assert result is False

    def test_parse_content_type(self, email_sender):
        """Test content type parsing."""
        maintype, subtype = email_sender._parse_content_type("application/pdf")
        assert maintype == "application"
        assert subtype == "pdf"

        # Test fallback
        maintype, subtype = email_sender._parse_content_type("invalid")
        assert maintype == "application"
        assert subtype == "octet-stream"
