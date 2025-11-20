"""Unit tests for email models and validation."""

import pytest
from pydantic import ValidationError

from services.email_models import EmailAddress, EmailAttachment, EmailRequest


class TestEmailAddress:
    """Test EmailAddress model."""

    def test_valid_email_address(self):
        """Test valid email address."""
        addr = EmailAddress(address="test@example.com")
        assert addr.address == "test@example.com"
        assert addr.display_name is None

    def test_email_with_display_name(self):
        """Test email with display name."""
        addr = EmailAddress(address="test@example.com", display_name="Test User")
        assert addr.address == "test@example.com"
        assert addr.display_name == "Test User"

    def test_format_without_display_name(self):
        """Test formatting without display name."""
        addr = EmailAddress(address="test@example.com")
        assert addr.format() == "test@example.com"

    def test_format_with_display_name(self):
        """Test formatting with display name."""
        addr = EmailAddress(address="test@example.com", display_name="Test User")
        assert addr.format() == "Test User <test@example.com>"

    def test_invalid_email_address(self):
        """Test invalid email address raises error."""
        with pytest.raises(ValidationError):
            EmailAddress(address="not-an-email")


class TestEmailAttachment:
    """Test EmailAttachment model."""

    def test_valid_attachment(self):
        """Test valid attachment."""
        att = EmailAttachment(
            filename="test.pdf",
            content_type="application/pdf",
            content_base64="SGVsbG8gV29ybGQ="
        )
        assert att.filename == "test.pdf"
        assert att.content_type == "application/pdf"
        assert att.content_base64 == "SGVsbG8gV29ybGQ="

    def test_empty_filename_fails(self):
        """Test empty filename raises error."""
        with pytest.raises(ValidationError):
            EmailAttachment(
                filename="",
                content_type="application/pdf",
                content_base64="SGVsbG8gV29ybGQ="
            )

    def test_empty_content_fails(self):
        """Test empty content raises error."""
        with pytest.raises(ValidationError):
            EmailAttachment(
                filename="test.pdf",
                content_type="application/pdf",
                content_base64=""
            )


class TestEmailRequest:
    """Test EmailRequest model."""

    def test_minimal_valid_request(self):
        """Test minimal valid email request."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test Email",
            text_body="Hello, World!"
        )
        assert req.to == ["recipient@example.com"]
        assert req.subject == "Test Email"
        assert req.text_body == "Hello, World!"

    def test_to_field_normalization_from_string(self):
        """Test 'to' field is normalized from string to list."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            text_body="Body"
        )
        assert isinstance(req.to, list)
        assert req.to == ["recipient@example.com"]

    def test_to_field_normalization_from_list(self):
        """Test 'to' field is kept as list."""
        req = EmailRequest(
            to=["recipient1@example.com", "recipient2@example.com"],
            subject="Test",
            text_body="Body"
        )
        assert isinstance(req.to, list)
        assert len(req.to) == 2

    def test_cc_bcc_normalization(self):
        """Test cc and bcc fields are normalized to lists."""
        req = EmailRequest(
            to="recipient@example.com",
            cc="cc@example.com",
            bcc=["bcc1@example.com", "bcc2@example.com"],
            subject="Test",
            text_body="Body"
        )
        assert req.cc == ["cc@example.com"]
        assert req.bcc == ["bcc1@example.com", "bcc2@example.com"]

    def test_missing_to_field_fails(self):
        """Test missing 'to' field raises error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailRequest(
                subject="Test",
                text_body="Body"
            )
        # Should complain about missing 'to'
        assert 'to' in str(exc_info.value)

    def test_empty_to_list_fails(self):
        """Test empty 'to' list raises error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailRequest(
                to=[],
                subject="Test",
                text_body="Body"
            )
        assert 'to' in str(exc_info.value).lower() or 'recipient' in str(exc_info.value).lower()

    def test_invalid_recipient_email_fails(self):
        """Test invalid recipient email raises error."""
        with pytest.raises(ValidationError):
            EmailRequest(
                to="not-an-email",
                subject="Test",
                text_body="Body"
            )

    def test_invalid_from_address_fails(self):
        """Test invalid from_address raises error."""
        with pytest.raises(ValidationError):
            EmailRequest(
                from_address="not-an-email",
                to="recipient@example.com",
                subject="Test",
                text_body="Body"
            )

    def test_no_content_fails(self):
        """Test missing all content fields raises error."""
        with pytest.raises(ValidationError) as exc_info:
            EmailRequest(
                to="recipient@example.com",
                subject="Test"
            )
        # Should mention content requirement
        error_msg = str(exc_info.value).lower()
        assert 'text_body' in error_msg or 'html_body' in error_msg or 'template' in error_msg

    def test_empty_subject_fails(self):
        """Test empty subject raises error."""
        with pytest.raises(ValidationError):
            EmailRequest(
                to="recipient@example.com",
                subject="",
                text_body="Body"
            )

    def test_html_body_only(self):
        """Test email with only HTML body."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            html_body="<p>Hello!</p>"
        )
        assert req.html_body == "<p>Hello!</p>"
        assert req.text_body is None

    def test_both_text_and_html_body(self):
        """Test email with both text and HTML body."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            text_body="Hello",
            html_body="<p>Hello</p>"
        )
        assert req.text_body == "Hello"
        assert req.html_body == "<p>Hello</p>"

    def test_template_based_content(self):
        """Test email with template."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            template="example_welcome",
            template_vars={"user_name": "Derek"}
        )
        assert req.template == "example_welcome"
        assert req.template_vars == {"user_name": "Derek"}

    def test_with_attachments(self):
        """Test email with attachments."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            text_body="Body",
            attachments=[
                EmailAttachment(
                    filename="test.pdf",
                    content_type="application/pdf",
                    content_base64="SGVsbG8="
                )
            ]
        )
        assert len(req.attachments) == 1
        assert req.attachments[0].filename == "test.pdf"

    def test_with_metadata(self):
        """Test email with metadata."""
        req = EmailRequest(
            to="recipient@example.com",
            subject="Test",
            text_body="Body",
            metadata={
                "caller": "pam",
                "correlation_id": "123-abc",
                "tags": ["welcome"]
            }
        )
        assert req.metadata["caller"] == "pam"
        assert req.get_metadata_value("caller") == "pam"
        assert req.get_metadata_value("missing_key", "default") == "default"

    def test_complete_request(self):
        """Test a complete email request with all fields."""
        req = EmailRequest(
            from_address="sender@example.com",
            from_name="Sender Name",
            to=["recipient1@example.com", "recipient2@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            subject="Complete Test Email",
            text_body="Plain text body",
            html_body="<p>HTML body</p>",
            template="example_welcome",
            template_vars={"user_name": "Test"},
            attachments=[
                EmailAttachment(
                    filename="doc.pdf",
                    content_type="application/pdf",
                    content_base64="base64content"
                )
            ],
            metadata={
                "caller": "test_bot",
                "correlation_id": "test-123"
            }
        )
        assert req.from_address == "sender@example.com"
        assert len(req.to) == 2
        assert len(req.cc) == 1
        assert len(req.bcc) == 1
        assert req.attachments is not None
        assert len(req.attachments) == 1
