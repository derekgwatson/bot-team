"""
Email Service for Oscar
Sends email notifications for onboarding events
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from config import config

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""

    def __init__(self):
        self.smtp_host = config.smtp_host
        self.smtp_port = config.smtp_port
        self.smtp_username = config.smtp_username
        self.smtp_password = config.smtp_password
        self.from_address = config.email_from_address

    def send_email(self, to_email: str, subject: str, body: str,
                   html_body: Optional[str] = None) -> bool:
        """
        Send an email
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML email body
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_address
            msg['To'] = to_email
            msg['Subject'] = subject

            # Attach plain text version
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)

            # Attach HTML version if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_onboarding_notification(self, request_data: dict) -> bool:
        """
        Send onboarding notification to HR/Payroll
        Args:
            request_data: Dictionary with onboarding request data
        Returns:
            bool: True if email sent successfully
        """
        subject = f"New Staff Onboarding: {request_data['full_name']}"

        # Plain text version
        body = f"""
New staff member onboarding initiated:

Name: {request_data['full_name']}
Preferred Name: {request_data.get('preferred_name', 'N/A')}
Position: {request_data['position']}
Section: {request_data['section']}
Start Date: {request_data['start_date']}

Contact Information:
- Personal Email: {request_data['personal_email']}
- Mobile: {request_data.get('phone_mobile', 'N/A')}
- Fixed Line: {request_data.get('phone_fixed', 'N/A')}

System Access:
- Google Workspace: {'Yes' if request_data.get('google_access') else 'No'}
- Zendesk: {'Yes' if request_data.get('zendesk_access') else 'No'}
- VOIP: {'Yes' if request_data.get('voip_access') else 'No'}

Notes: {request_data.get('notes', 'None')}

---
This is an automated notification from Oscar (Staff Onboarding Bot)
http://localhost:8011
"""

        # HTML version
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #2c5aa0;">New Staff Member Onboarding</h2>

    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">Staff Details</h3>
        <p><strong>Name:</strong> {request_data['full_name']}</p>
        <p><strong>Preferred Name:</strong> {request_data.get('preferred_name', 'N/A')}</p>
        <p><strong>Position:</strong> {request_data['position']}</p>
        <p><strong>Section:</strong> {request_data['section']}</p>
        <p><strong>Start Date:</strong> {request_data['start_date']}</p>
    </div>

    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">Contact Information</h3>
        <p><strong>Personal Email:</strong> {request_data['personal_email']}</p>
        <p><strong>Mobile:</strong> {request_data.get('phone_mobile', 'N/A')}</p>
        <p><strong>Fixed Line:</strong> {request_data.get('phone_fixed', 'N/A')}</p>
    </div>

    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3 style="margin-top: 0;">System Access Requirements</h3>
        <p><strong>Google Workspace:</strong> {'✓ Yes' if request_data.get('google_access') else '✗ No'}</p>
        <p><strong>Zendesk:</strong> {'✓ Yes' if request_data.get('zendesk_access') else '✗ No'}</p>
        <p><strong>VOIP:</strong> {'✓ Yes' if request_data.get('voip_access') else '✗ No'}</p>
    </div>

    {f'<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0;"><h3 style="margin-top: 0;">Notes</h3><p>{request_data["notes"]}</p></div>' if request_data.get('notes') else ''}

    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
    <p style="font-size: 12px; color: #666;">
        This is an automated notification from Oscar (Staff Onboarding Bot)<br>
        <a href="http://localhost:8011">View Oscar Dashboard</a>
    </p>
</body>
</html>
"""

        return self.send_email(config.notification_email, subject, body, html_body)


# Global email service instance
email_service = EmailService()
