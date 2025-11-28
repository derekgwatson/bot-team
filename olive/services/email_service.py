"""
Email Service for Olive
Sends email notifications via Mabel (the centralized email bot)
"""

import os
import logging
import requests
from typing import Optional
from config import config
from shared.http_client import BotHttpClient

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications via Mabel"""

    def __init__(self):
        self.mabel_url = config.mabel_url
        self.from_address = config.email_from_address

    def _get_mabel_client(self, timeout: int = 10) -> BotHttpClient:
        """Get a BotHttpClient for Mabel"""
        return BotHttpClient(self.mabel_url, timeout=timeout)

    def send_email(self, to_email: str, subject: str, body: str,
                   html_body: Optional[str] = None) -> bool:
        """
        Send an email via Mabel

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Prepare request payload for Mabel
            payload = {
                "to": to_email,
                "subject": subject,
                "text_body": body,
                "metadata": {
                    "caller": "olive",
                    "correlation_id": f"olive-{os.urandom(8).hex()}"
                }
            }

            # Add HTML body if provided
            if html_body:
                payload["html_body"] = html_body

            # Add from address if configured
            if self.from_address:
                payload["from_address"] = self.from_address

            # Send request to Mabel via BotHttpClient (adds X-API-Key automatically)
            mabel = self._get_mabel_client()
            response = mabel.post('/api/send-email', json=payload)

            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email} via Mabel")
                return True
            else:
                logger.error(f"Mabel returned error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email via Mabel: {str(e)}")
            return False

    def send_offboarding_notification(self, request_data: dict) -> bool:
        """
        Send offboarding notification to HR/IT

        Args:
            request_data: Dictionary with offboarding request data

        Returns:
            bool: True if email sent successfully
        """
        subject = f"Staff Offboarding: {request_data['full_name']}"

        # Plain text version
        body = f"""
Staff member offboarding initiated:

Name: {request_data['full_name']}
Position: {request_data.get('position', 'N/A')}
Section: {request_data.get('section', 'N/A')}
Last Day: {request_data['last_day']}

Contact Information:
- Personal Email: {request_data.get('personal_email', 'N/A')}
- Mobile: {request_data.get('phone_mobile', 'N/A')}

System Access Being Removed:
- Google Workspace: {'Yes' if request_data.get('had_google_access') else 'No'}
- Zendesk: {'Yes' if request_data.get('had_zendesk_access') else 'No'}
- Wiki: Yes (automatic removal via Paige sync)
- Buz: {'Yes' if request_data.get('had_buz_access') else 'No'}

Notes: {request_data.get('notes', 'None')}

---
This is an automated notification from Olive (Staff Offboarding Bot)
http://localhost:8012
"""

        # HTML version
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #d9534f;">Staff Member Offboarding</h2>

    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">Staff Details</h3>
        <p><strong>Name:</strong> {request_data['full_name']}</p>
        <p><strong>Position:</strong> {request_data.get('position', 'N/A')}</p>
        <p><strong>Section:</strong> {request_data.get('section', 'N/A')}</p>
        <p><strong>Last Day:</strong> {request_data['last_day']}</p>
    </div>

    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">Contact Information</h3>
        <p><strong>Personal Email:</strong> {request_data.get('personal_email', 'N/A')}</p>
        <p><strong>Mobile:</strong> {request_data.get('phone_mobile', 'N/A')}</p>
    </div>

    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">System Access Being Removed</h3>
        <p><strong>Google Workspace:</strong> {'✓ Yes' if request_data.get('had_google_access') else '✗ No'}</p>
        <p><strong>Zendesk:</strong> {'✓ Yes' if request_data.get('had_zendesk_access') else '✗ No'}</p>
        <p><strong>Wiki:</strong> ✓ Yes (automatic removal via Paige sync)</p>
        <p><strong>Buz:</strong> {'✓ Yes' if request_data.get('had_buz_access') else '✗ No'}</p>
    </div>

    {f'<div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 15px 0;"><h3 style="margin-top: 0;">Notes</h3><p>{request_data["notes"]}</p></div>' if request_data.get('notes') else ''}

    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
    <p style="font-size: 12px; color: #666;">
        This is an automated notification from Olive (Staff Offboarding Bot)<br>
        <a href="http://localhost:8012">View Olive Dashboard</a>
    </p>
</body>
</html>
"""

        return self.send_email(config.notification_email, subject, body, html_body)


# Global email service instance
email_service = EmailService()
