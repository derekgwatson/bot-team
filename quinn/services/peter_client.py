"""
Service to communicate with Peter (the HR database bot)
"""
from config import config
from shared.http_client import BotHttpClient


class PeterClient:
    """Client for calling Peter's API"""

    def __init__(self):
        # Don't cache a fixed base_url; we'll build a client on demand
        # so session-based dev/prod switching via config.peter_url still works.
        pass

    @property
    def base_url(self) -> str:
        """Get Peter's base URL dynamically (respects session-based dev/prod switching)"""
        return config.peter_url

    @property
    def client(self) -> BotHttpClient:
        """
        Build a BotHttpClient for the current base_url.

        Cheap to construct, and lets us honour dynamic peter_url changes.
        """
        return BotHttpClient(self.base_url)

    def get_allstaff_emails(self):
        """
        Get list of email addresses that should be in the allstaff group
        (external staff without Google accounts)

        Returns:
            List of email addresses, or empty list on error
        """
        try:
            response = self.client.get("/api/staff/allstaff-members")

            if response.status_code == 200:
                data = response.json()
                return data.get("emails", [])
            else:
                print(f"Error getting allstaff members from Peter: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error calling Peter: {e}")
            return []

    def get_allstaff_managers(self):
        """
        Get list of manager email addresses for the allstaff group
        (internal staff with Google accounts who can send to the group)

        Returns:
            List of email addresses, or empty list on error
        """
        try:
            response = self.client.get("/api/staff/allstaff-managers")

            if response.status_code == 200:
                data = response.json()
                return data.get("emails", [])
            else:
                print(f"Error getting allstaff managers from Peter: {response.status_code}")
                return []

        except Exception as e:
            print(f"Error calling Peter: {e}")
            return []

    def is_staff_member(self, email: str):
        """
        Check if an email belongs to a staff member
        (Used by Pam for access control)

        Args:
            email: Email address to check

        Returns:
            Dict with approval status
        """
        try:
            response = self.client.get(
                "/api/contacts/search",
                params={"q": email},
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                # Check if email matches exactly
                for staff in results:
                    if staff.get("email", "").lower() == email.lower():
                        return {
                            "approved": True,
                            "name": staff.get("name"),
                            "email": email,
                        }

                return {"approved": False}
            else:
                print(f"Error searching Peter: {response.status_code}")
                return {"approved": False}

        except Exception as e:
            print(f"Error calling Peter: {e}")
            return {"approved": False}


# Singleton instance
peter_client = PeterClient()
