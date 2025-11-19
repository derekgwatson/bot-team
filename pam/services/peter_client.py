import requests  # only needed if you want to keep using the exception types
from config import config
from shared.http_client import BotHttpClient


class PeterClient:
    """
    Client for calling Peter's API to get contact data
    """

    def __init__(self):
        # Don't cache the base_url - read it dynamically from config to support session-based switching
        self.contacts_endpoint = config.peter_contacts_endpoint
        self.search_endpoint = config.peter_search_endpoint

    @property
    def base_url(self):
        """Get Peter's base URL dynamically (respects session-based dev/prod switching)"""
        return config.peter_api_url

    @property
    def client(self) -> BotHttpClient:
        """
        Build a BotHttpClient for the current base_url.

        This means if config.peter_api_url switches between dev/prod
        for the session, we always hit the right one.
        """
        return BotHttpClient(self.base_url)

    def check_health(self):
        """
        Check if Peter is available and responding

        Returns:
            Dict with 'healthy' (bool) and 'error' (str) if unhealthy
        """
        try:
            response = self.client.get("/health", timeout=3)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "healthy":
                return {"healthy": True}
            else:
                return {"healthy": False, "error": "Peter is not healthy"}

        except requests.exceptions.ConnectionError:
            return {
                "healthy": False,
                "error": f"Can't reach Peter at {self.base_url}. He might not be running.",
            }
        except requests.exceptions.Timeout:
            return {
                "healthy": False,
                "error": "Peter is taking too long to respond",
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": f"Error checking Peter: {str(e)}",
            }

    def get_all_contacts(self):
        """
        Get all contacts from Peter's API

        Returns:
            List of contact dictionaries, or error dict
        """
        try:
            response = self.client.get(self.contacts_endpoint, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get("contacts", [])

        except requests.exceptions.ConnectionError as e:
            print(f"Error calling Peter's API: {e}")
            return {
                "error": "📞 Can't reach Peter right now. He's probably not running. "
                         "Try starting Peter first, or check the dev widget above to switch to prod."
            }
        except requests.exceptions.Timeout:
            print("Peter API timeout")
            return {"error": "📞 Peter is taking too long to respond. He might be busy."}
        except requests.exceptions.RequestException as e:
            print(f"Error calling Peter's API: {e}")
            return {"error": f"📞 Problem talking to Peter: {str(e)}"}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"error": f"Unexpected error: {str(e)}"}

    def search_contacts(self, query):
        """
        Search contacts via Peter's API

        Args:
            query: Search query string

        Returns:
            List of matching contacts, or error dict
        """
        try:
            response = self.client.get(
                self.search_endpoint,
                params={"q": query},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

        except requests.exceptions.ConnectionError as e:
            print(f"Error calling Peter's API: {e}")
            return {
                "error": "📞 Can't reach Peter right now. He's probably not running. "
                         "Try starting Peter first, or check the dev widget above to switch to prod."
            }
        except requests.exceptions.Timeout:
            print("Peter API timeout")
            return {"error": "📞 Peter is taking too long to respond. He might be busy."}
        except requests.exceptions.RequestException as e:
            print(f"Error calling Peter's API: {e}")
            return {"error": f"📞 Problem talking to Peter: {str(e)}"}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"error": f"Unexpected error: {str(e)}"}


# Global client instance
peter_client = PeterClient()
