from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import config
import os
from datetime import datetime, timedelta

class GoogleReportsService:
    """Service for interacting with Google Workspace Reports API"""

    SCOPES = [
        'https://www.googleapis.com/auth/admin.reports.usage.readonly',
        'https://www.googleapis.com/auth/admin.reports.audit.readonly'
    ]

    def __init__(self):
        self.credentials = None
        self.service = None
        self._initialize()

    def _initialize(self):
        """Initialize Google Workspace Reports API credentials and service"""
        try:
            if not os.path.exists(config.google_credentials_file):
                print(f"Warning: Credentials file not found at {config.google_credentials_file}")
                return

            # Create credentials with domain-wide delegation
            credentials = service_account.Credentials.from_service_account_file(
                config.google_credentials_file,
                scopes=self.SCOPES
            )

            # Delegate credentials to admin user
            if config.google_admin_email:
                self.credentials = credentials.with_subject(config.google_admin_email)
            else:
                self.credentials = credentials

            # Build the Reports API service
            # Use 'admin' service with 'reports_v1' like the Directory API
            self.service = build('admin', 'reports_v1', credentials=self.credentials)

        except Exception as e:
            print(f"Error initializing Google Reports service: {e}")
            import traceback
            traceback.print_exc()
            self.service = None

    def get_user_usage(self, email=None, date=None):
        """
        Get usage statistics for users

        Args:
            email: Optional specific user email
            date: Optional date (YYYY-MM-DD format), defaults to 5 days ago

        Returns:
            List of user usage dictionaries or error
        """
        if not self.service:
            return {'error': 'Google Reports service not initialized'}

        try:
            # Reports API requires date format: YYYY-MM-DD
            # Data is usually available with 3-5 day delay
            if not date:
                five_days_ago = datetime.now() - timedelta(days=5)
                date = five_days_ago.strftime('%Y-%m-%d')

            print(f"DEBUG: Requesting usage data for date: {date}, email: {email if email else 'all'}")

            params = {
                'userKey': email if email else 'all',
                'date': date,
                'parameters': 'accounts:gmail_used_quota_in_mb,accounts:drive_used_quota_in_mb,accounts:total_quota_in_mb,accounts:used_quota_in_mb'
            }

            results = self.service.userUsageReport().get(**params).execute()

            usage_reports = results.get('usageReports', [])
            print(f"DEBUG: Got {len(usage_reports)} usage reports")

            return [self._format_usage_report(report) for report in usage_reports]

        except HttpError as e:
            print(f"DEBUG: HttpError status: {e.resp.status}")
            print(f"DEBUG: HttpError content: {e.content}")
            if e.resp.status == 400:
                return {'error': 'Invalid date or user. Usage data may not be available yet.'}
            if e.resp.status == 403:
                return {'error': 'Permission denied. Make sure Reports API scopes are authorized in Workspace Admin.'}
            return {'error': f'API error: {e}'}
        except Exception as e:
            print(f"DEBUG: Exception: {e}")
            import traceback
            traceback.print_exc()
            return {'error': f'Unexpected error: {e}'}

    def _format_usage_report(self, report):
        """Format usage report data for API responses"""
        # Extract parameters
        params = {}
        for param in report.get('parameters', []):
            param_name = param.get('name', '').replace('accounts:', '')

            if param_name in ['gmail_used_quota_in_mb', 'drive_used_quota_in_mb',
                            'total_quota_in_mb', 'used_quota_in_mb']:
                # These are reported as integers in MB
                value_key = 'intValue' if 'intValue' in param else None
                if value_key:
                    params[param_name] = param.get(value_key, 0)

        # Convert MB to GB for readability
        gmail_gb = params.get('gmail_used_quota_in_mb', 0) / 1024
        drive_gb = params.get('drive_used_quota_in_mb', 0) / 1024
        total_used_gb = params.get('used_quota_in_mb', 0) / 1024
        total_quota_gb = params.get('total_quota_in_mb', 0) / 1024

        return {
            'email': report.get('entity', {}).get('userEmail', 'unknown'),
            'date': report.get('date', ''),
            'gmail_used_gb': round(gmail_gb, 2),
            'drive_used_gb': round(drive_gb, 2),
            'total_used_gb': round(total_used_gb, 2),
            'total_quota_gb': round(total_quota_gb, 2) if total_quota_gb > 0 else None,
            'gmail_used_mb': params.get('gmail_used_quota_in_mb', 0),
            'drive_used_mb': params.get('drive_used_quota_in_mb', 0),
            'total_used_mb': params.get('used_quota_in_mb', 0)
        }

# Singleton instance
reports_service = GoogleReportsService()
