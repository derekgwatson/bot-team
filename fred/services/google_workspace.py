from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import config
import os

class GoogleWorkspaceService:
    """Service for interacting with Google Workspace Admin SDK"""

    SCOPES = [
        'https://www.googleapis.com/auth/admin.directory.user',
        'https://www.googleapis.com/auth/admin.directory.user.readonly'
    ]

    def __init__(self):
        self.credentials = None
        self.service = None
        self._initialize()

    def _initialize(self):
        """Initialize Google Workspace API credentials and service"""
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

            # Build the Admin SDK service
            self.service = build('admin', 'directory_v1', credentials=self.credentials)

        except Exception as e:
            print(f"Error initializing Google Workspace service: {e}")
            self.service = None

    def list_users(self, max_results=100, archived=False):
        """
        List users in the Google Workspace domain

        Args:
            max_results: Maximum number of users to return
            archived: If True, only return archived users

        Returns:
            List of user dictionaries
        """
        if not self.service:
            return {'error': 'Google Workspace service not initialized'}

        try:
            query = 'isArchived=true' if archived else 'isArchived=false'

            results = self.service.users().list(
                customer='my_customer',
                maxResults=max_results,
                orderBy='email',
                query=query
            ).execute()

            users = results.get('users', [])

            # Simplify user data
            return [self._format_user(user) for user in users]

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def get_user(self, email):
        """
        Get a specific user by email

        Args:
            email: User's email address

        Returns:
            User dictionary or error
        """
        if not self.service:
            return {'error': 'Google Workspace service not initialized'}

        try:
            user = self.service.users().get(userKey=email).execute()
            return self._format_user(user)

        except HttpError as e:
            if e.resp.status == 404:
                return {'error': 'User not found'}
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def create_user(self, email, first_name, last_name, password):
        """
        Create a new user in Google Workspace

        Args:
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            password: Initial password

        Returns:
            Created user dictionary or error
        """
        if not self.service:
            return {'error': 'Google Workspace service not initialized'}

        try:
            user_body = {
                'primaryEmail': email,
                'name': {
                    'givenName': first_name,
                    'familyName': last_name
                },
                'password': password,
                'changePasswordAtNextLogin': True
            }

            user = self.service.users().insert(body=user_body).execute()
            return self._format_user(user)

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def archive_user(self, email):
        """
        Archive a user (suspend and mark as archived)

        Args:
            email: User's email address

        Returns:
            Success message or error
        """
        if not self.service:
            return {'error': 'Google Workspace service not initialized'}

        try:
            user_body = {
                'suspended': True,
                'archived': True
            }

            self.service.users().update(
                userKey=email,
                body=user_body
            ).execute()

            return {'success': True, 'message': f'User {email} archived successfully'}

        except HttpError as e:
            if e.resp.status == 404:
                return {'error': 'User not found'}
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def delete_user(self, email):
        """
        Permanently delete a user

        Args:
            email: User's email address

        Returns:
            Success message or error
        """
        if not self.service:
            return {'error': 'Google Workspace service not initialized'}

        try:
            self.service.users().delete(userKey=email).execute()
            return {'success': True, 'message': f'User {email} deleted successfully'}

        except HttpError as e:
            if e.resp.status == 404:
                return {'error': 'User not found'}
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def _format_user(self, user):
        """Format user data for API responses"""
        return {
            'email': user.get('primaryEmail'),
            'aliases': user.get('aliases', []),  # Email aliases for this account
            'first_name': user.get('name', {}).get('givenName', ''),
            'last_name': user.get('name', {}).get('familyName', ''),
            'full_name': user.get('name', {}).get('fullName', ''),
            'suspended': user.get('suspended', False),
            'archived': user.get('archived', False),
            'created_time': user.get('creationTime', ''),
            'last_login': user.get('lastLoginTime', '')
        }

# Singleton instance
workspace_service = GoogleWorkspaceService()
