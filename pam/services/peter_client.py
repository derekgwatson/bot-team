import requests
from config import config

class PeterClient:
    """
    Client for calling Peter's API to get contact data
    """

    def __init__(self):
        self.base_url = config.peter_api_url
        self.contacts_endpoint = config.peter_contacts_endpoint
        self.search_endpoint = config.peter_search_endpoint

    def check_health(self):
        """
        Check if Peter is available and responding

        Returns:
            Dict with 'healthy' (bool) and 'error' (str) if unhealthy
        """
        try:
            url = f"{self.base_url}/health"
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'healthy':
                return {'healthy': True}
            else:
                return {'healthy': False, 'error': 'Peter is not healthy'}

        except requests.exceptions.ConnectionError:
            return {
                'healthy': False,
                'error': f"Can't reach Peter at {self.base_url}. He might not be running."
            }
        except requests.exceptions.Timeout:
            return {
                'healthy': False,
                'error': 'Peter is taking too long to respond'
            }
        except Exception as e:
            return {
                'healthy': False,
                'error': f'Error checking Peter: {str(e)}'
            }

    def get_all_contacts(self):
        """
        Get all contacts from Peter's API

        Returns:
            List of contact dictionaries, or error dict
        """
        try:
            url = f"{self.base_url}{self.contacts_endpoint}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get('contacts', [])

        except requests.exceptions.ConnectionError as e:
            print(f"Error calling Peter's API: {e}")
            return {
                'error': "📞 Can't reach Peter right now. He's probably not running. "
                        "Try starting Peter first, or check the dev widget above to switch to prod."
            }
        except requests.exceptions.Timeout:
            print("Peter API timeout")
            return {'error': "📞 Peter is taking too long to respond. He might be busy."}
        except requests.exceptions.RequestException as e:
            print(f"Error calling Peter's API: {e}")
            return {'error': f"📞 Problem talking to Peter: {str(e)}"}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {'error': f'Unexpected error: {str(e)}'}

    def search_contacts(self, query):
        """
        Search contacts via Peter's API

        Args:
            query: Search query string

        Returns:
            List of matching contacts, or error dict
        """
        try:
            url = f"{self.base_url}{self.search_endpoint}"
            response = requests.get(url, params={'q': query}, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get('results', [])

        except requests.exceptions.ConnectionError as e:
            print(f"Error calling Peter's API: {e}")
            return {
                'error': "📞 Can't reach Peter right now. He's probably not running. "
                        "Try starting Peter first, or check the dev widget above to switch to prod."
            }
        except requests.exceptions.Timeout:
            print("Peter API timeout")
            return {'error': "📞 Peter is taking too long to respond. He might be busy."}
        except requests.exceptions.RequestException as e:
            print(f"Error calling Peter's API: {e}")
            return {'error': f"📞 Problem talking to Peter: {str(e)}"}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {'error': f'Unexpected error: {str(e)}'}

    def group_by_section(self, contacts):
        """
        Group contacts by section for display

        Args:
            contacts: List of contact dictionaries

        Returns:
            Dictionary with sections as keys, contact lists as values
        """
        sections = {}
        for contact in contacts:
            section = contact.get('section', 'Unknown')
            if section not in sections:
                sections[section] = []
            sections[section].append(contact)
        return sections

# Global client instance
peter_client = PeterClient()
