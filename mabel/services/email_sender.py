"""Email sending service using SMTP."""

import base64
import logging
import smtplib
import time
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Optional

from .email_models import EmailRequest
from .templates import render_email_template, TemplateError


logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when email sending fails."""
    pass


class EmailSender:
    """
    Handles sending emails via SMTP.

    Supports:
    - Plain text and HTML emails
    - Multipart messages (both text and HTML)
    - Attachments
    - Template rendering
    """

    def __init__(self, config) -> None:
        """
        Initialize the email sender.

        Args:
            config: Config instance with SMTP settings
        """
        self.config = config

    def send(self, request: EmailRequest) -> str:
        """
        Send an email via SMTP.

        Args:
            request: EmailRequest with all email details

        Returns:
            Message ID (generated or from SMTP server)

        Raises:
            EmailSendError: If sending fails for any reason
        """
        start_time = time.time()

        try:
            # Build the email message
            msg = self._build_message(request)

            # Send via SMTP
            self._send_via_smtp(msg, request)

            # Log success
            duration_ms = (time.time() - start_time) * 1000
            self._log_send_result(request, True, duration_ms)

            # Return message ID
            message_id = msg.get('Message-ID', self._generate_message_id())
            return message_id

        except Exception as e:
            # Log failure
            duration_ms = (time.time() - start_time) * 1000
            self._log_send_result(request, False, duration_ms, str(e))
            raise EmailSendError(f"Failed to send email: {e}") from e

    def _build_message(self, request: EmailRequest) -> EmailMessage:
        """
        Build an EmailMessage from the request.

        Args:
            request: EmailRequest

        Returns:
            EmailMessage ready to send

        Raises:
            EmailSendError: If message building fails
        """
        msg = EmailMessage()

        # Set headers
        msg['Subject'] = request.subject

        # From address
        from_address = request.from_address or self.config.default_from
        from_name = request.from_name or self.config.default_sender_name
        msg['From'] = formataddr((from_name, from_address))

        # To, Cc, Bcc
        msg['To'] = ', '.join(request.to)
        if request.cc:
            msg['Cc'] = ', '.join(request.cc)
        # Bcc is not set in headers (blind carbon copy)

        # Reply-To
        msg['Reply-To'] = self.config.default_reply_to

        # Message-ID
        msg['Message-ID'] = self._generate_message_id()

        # Determine content (direct or template-based)
        text_body = request.text_body
        html_body = request.html_body

        # If template is specified, render it
        if request.template:
            try:
                template_vars = request.template_vars or {}
                rendered_text, rendered_html = render_email_template(
                    request.template,
                    template_vars
                )

                # Use rendered content if not already provided
                if text_body is None:
                    text_body = rendered_text
                if html_body is None:
                    html_body = rendered_html

            except TemplateError as e:
                raise EmailSendError(f"Template rendering failed: {e}") from e

        # Set content
        if text_body and html_body:
            # Multipart: both text and HTML
            msg.set_content(text_body)
            msg.add_alternative(html_body, subtype='html')
        elif html_body:
            # HTML only
            msg.set_content(html_body, subtype='html')
        elif text_body:
            # Text only
            msg.set_content(text_body)
        else:
            raise EmailSendError("No email body content available")

        # Add attachments
        if request.attachments:
            for attachment in request.attachments:
                try:
                    # Decode base64 content
                    content = base64.b64decode(attachment.content_base64)

                    # Parse content type
                    maintype, subtype = self._parse_content_type(attachment.content_type)

                    # Add attachment
                    msg.add_attachment(
                        content,
                        maintype=maintype,
                        subtype=subtype,
                        filename=attachment.filename
                    )
                except Exception as e:
                    raise EmailSendError(
                        f"Failed to add attachment '{attachment.filename}': {e}"
                    ) from e

        return msg

    def _send_via_smtp(self, msg: EmailMessage, request: EmailRequest) -> None:
        """
        Send the message via SMTP.

        Args:
            msg: EmailMessage to send
            request: Original request (for recipients)

        Raises:
            EmailSendError: If SMTP operation fails
        """
        # Collect all recipients (to, cc, bcc)
        all_recipients = list(request.to)
        if request.cc:
            all_recipients.extend(request.cc)
        if request.bcc:
            all_recipients.extend(request.bcc)

        try:
            # Connect to SMTP server
            if self.config.smtp_use_tls:
                smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)

            # Login if credentials provided
            if self.config.smtp_username and self.config.smtp_password:
                smtp.login(self.config.smtp_username, self.config.smtp_password)

            # Send email
            smtp.send_message(msg, to_addrs=all_recipients)

            # Close connection
            smtp.quit()

        except smtplib.SMTPException as e:
            raise EmailSendError(f"SMTP error: {e}") from e
        except Exception as e:
            raise EmailSendError(f"Connection error: {e}") from e

    def _generate_message_id(self) -> str:
        """Generate a unique message ID."""
        # Use email.utils.make_msgid for RFC-compliant message IDs
        return make_msgid(domain=self.config.smtp_host)

    def _parse_content_type(self, content_type: str) -> tuple:
        """
        Parse content type into maintype and subtype.

        Args:
            content_type: MIME type like 'application/pdf'

        Returns:
            Tuple of (maintype, subtype)
        """
        parts = content_type.split('/')
        if len(parts) == 2:
            return parts[0], parts[1]
        # Fallback
        return 'application', 'octet-stream'

    def _log_send_result(
        self,
        request: EmailRequest,
        success: bool,
        duration_ms: float,
        error: Optional[str] = None
    ) -> None:
        """
        Log the result of a send operation.

        Args:
            request: EmailRequest
            success: Whether send succeeded
            duration_ms: Duration in milliseconds
            error: Error message if failed
        """
        # Redact sensitive info, limit recipient list
        to_summary = ', '.join(request.to[:3])
        if len(request.to) > 3:
            to_summary += f" ... (+{len(request.to) - 3} more)"

        caller = request.get_metadata_value('caller', 'unknown')
        correlation_id = request.get_metadata_value('correlation_id', 'none')

        log_data = {
            'subject': request.subject,
            'to': to_summary,
            'caller': caller,
            'correlation_id': correlation_id,
            'success': success,
            'duration_ms': round(duration_ms, 2)
        }

        if success:
            logger.info(f"Email sent successfully: {log_data}")
        else:
            log_data['error'] = error
            logger.error(f"Email send failed: {log_data}")

    def test_connection(self) -> bool:
        """
        Test SMTP connection without sending email.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.config.smtp_use_tls:
                smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=5)
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=5)

            # Login if credentials provided
            if self.config.smtp_username and self.config.smtp_password:
                smtp.login(self.config.smtp_username, self.config.smtp_password)

            # Send NOOP command
            smtp.noop()

            smtp.quit()
            return True

        except Exception as e:
            logger.warning(f"SMTP connection test failed: {e}")
            return False
