"""
Google Groups management service
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import config
import traceback


class GoogleGroupsService:
    """
    Service for managing Google Groups memberships
    """

    def __init__(self):
        """Initialize Google Admin SDK service"""
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the Google Admin SDK Directory service"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                config.credentials_file,
                scopes=['https://www.googleapis.com/auth/admin.directory.group']
            )

            # Service account needs domain-wide delegation
            delegated_credentials = credentials.with_subject('derek@watsonblinds.com.au')

            self.service = build('admin', 'directory_v1', credentials=delegated_credentials)
            print("✓ Google Groups service initialized")

        except Exception as e:
            print(f"✗ Error initializing Google Groups service: {e}")
            traceback.print_exc()
            self.service = None

    def add_member(self, email):
        """
        Add a member to the allstaff group

        Args:
            email: Email address to add

        Returns:
            Dict with success status or error
        """
        if not self.service:
            return {'error': 'Google Groups service not initialized'}

        try:
            member = {
                'email': email,
                'role': 'MEMBER'
            }

            self.service.members().insert(
                groupKey=config.allstaff_group,
                body=member
            ).execute()

            return {
                'success': True,
                'message': f'Added {email} to {config.allstaff_group}'
            }

        except HttpError as e:
            if e.resp.status == 409:
                # Member already exists
                return {
                    'success': True,
                    'message': f'{email} is already in the group'
                }
            else:
                print(f"Error adding member to group: {e}")
                return {
                    'error': f'Google API error: {e.resp.status}'
                }

        except Exception as e:
            print(f"Unexpected error adding member: {e}")
            traceback.print_exc()
            return {
                'error': f'Unexpected error: {str(e)}'
            }

    def remove_member(self, email):
        """
        Remove a member from the allstaff group

        Args:
            email: Email address to remove

        Returns:
            Dict with success status or error
        """
        if not self.service:
            return {'error': 'Google Groups service not initialized'}

        try:
            self.service.members().delete(
                groupKey=config.allstaff_group,
                memberKey=email
            ).execute()

            return {
                'success': True,
                'message': f'Removed {email} from {config.allstaff_group}'
            }

        except HttpError as e:
            if e.resp.status == 404:
                # Member doesn't exist in group
                return {
                    'success': True,
                    'message': f'{email} was not in the group'
                }
            else:
                print(f"Error removing member from group: {e}")
                return {
                    'error': f'Google API error: {e.resp.status}'
                }

        except Exception as e:
            print(f"Unexpected error removing member: {e}")
            traceback.print_exc()
            return {
                'error': f'Unexpected error: {str(e)}'
            }

    def is_member(self, email):
        """
        Check if an email is a member of the allstaff group

        Args:
            email: Email address to check

        Returns:
            Boolean
        """
        if not self.service:
            return False

        try:
            self.service.members().get(
                groupKey=config.allstaff_group,
                memberKey=email
            ).execute()
            return True

        except HttpError as e:
            if e.resp.status == 404:
                return False
            else:
                print(f"Error checking group membership: {e}")
                return False

        except Exception as e:
            print(f"Unexpected error checking membership: {e}")
            return False


# Global service instance
groups_service = GoogleGroupsService()
