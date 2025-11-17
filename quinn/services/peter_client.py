"""
Service to communicate with Peter (the HR database bot)
"""
import requests
from config import config


class PeterClient:
    """Client for calling Peter's API"""

    def __init__(self):
        self.base_url = config.peter_url

    def get_allstaff_emails(self):
        """
        Get list of email addresses that should be in the allstaff group

        Returns:
            List of email addresses, or empty list on error
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/staff/allstaff-members',
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('emails', [])
            else:
                print(f"Error getting allstaff members from Peter: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error calling Peter: {e}")
            return []

    def is_staff_member(self, email):
        """
        Check if an email belongs to a staff member
        (Used by Pam for access control)

        Args:
            email: Email address to check

        Returns:
            Dict with approval status
        """
        try:
            # Search for staff by email
            response = requests.get(
                f'{self.base_url}/api/contacts/search',
                params={'q': email},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                # Check if email matches exactly
                for staff in results:
                    if staff.get('email', '').lower() == email.lower():
                        return {
                            'approved': True,
                            'name': staff.get('name'),
                            'email': email
                        }

                return {'approved': False}
            else:
                print(f"Error searching Peter: {response.status_code}")
                return {'approved': False}

        except Exception as e:
            print(f"Error calling Peter: {e}")
            return {'approved': False}


# Singleton instance
peter_client = PeterClient()
