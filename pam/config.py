import yaml
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # Loads root .env automatically
from shared.config.ports import get_port

# Load bot-specific .env (can override global values)
bot_env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=bot_env_path)


class Config:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Bot info
        self.name = data['name']
        self.description = data['description']
        self.version = data['version']

        # Server config
        self.server_host = data['server']['host']
        self.server_port = get_port("pam")

        # Load shared organization config
        shared_config_path = os.path.join(os.path.dirname(__file__), data['shared_config'])
        with open(shared_config_path, 'r', encoding='utf-8') as f:
            shared_data = yaml.safe_load(f)

        # Organization config
        self.allowed_domains = shared_data['organization']['domains']

        # Peter API config (keep endpoints from yaml)
        peter_api = data.get('peter_api', {})
        self.peter_contacts_endpoint = peter_api.get('contacts_endpoint', '/api/contacts')
        self.peter_search_endpoint = peter_api.get('search_endpoint', '/api/contacts/search')

        # Chester URL - service registry (required)
        self.chester_url = os.environ.get('CHESTER_API_URL')
        if not self.chester_url:
            raise RuntimeError(
                "CHESTER_API_URL is required but not set.\n"
                "Add it to your shared .env file (e.g., CHESTER_API_URL=http://localhost:8008)"
            )
        self.bot_api_key = os.environ.get('BOT_API_KEY')

        # Cache for bot URLs (avoid hitting Chester on every request)
        self._bot_url_cache = {}

    def _query_chester_for_bot_url(self, bot_name: str) -> str:
        """
        Query Chester's service registry for a bot's URL.

        Args:
            bot_name: Name of the bot to look up

        Returns:
            Bot's API URL

        Raises:
            RuntimeError: If Chester is unavailable or bot not found
        """
        # Check cache first
        if bot_name in self._bot_url_cache:
            return self._bot_url_cache[bot_name]

        try:
            # Query Chester's registry
            response = requests.get(
                f"{self.chester_url}/api/bots/{bot_name}",
                headers={'X-API-Key': self.bot_api_key},
                timeout=2
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('bot', {}).get('url'):
                    bot_url = data['bot']['url']
                    # Cache the result
                    self._bot_url_cache[bot_name] = bot_url
                    return bot_url
                else:
                    raise RuntimeError(f"Bot '{bot_name}' not found in Chester's registry")
            else:
                raise RuntimeError(f"Chester returned status {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to contact Chester at {self.chester_url}: {e}\n"
                f"Make sure Chester is running and CHESTER_API_URL is correct."
            )

    def _get_bot_url(self, bot_name: str) -> str:
        """
        Get the URL for a bot via Chester's service registry.

        Flow:
        1. Check Flask session for dev mode override (prod vs localhost)
        2. Query Chester's registry for the bot's URL

        Args:
            bot_name: Name of the bot to look up

        Returns:
            Bot's API URL

        Raises:
            RuntimeError: If Chester is unavailable
        """
        # Note: Dev mode overrides are handled by Chester's database
        # We always query Chester - he knows whether we're in dev or prod
        return self._query_chester_for_bot_url(bot_name)

    @property
    def quinn_api_url(self):
        """Get Quinn's API URL from Chester's service registry"""
        return self._get_bot_url('quinn')

    @property
    def peter_api_url(self):
        """Get Peter's API URL from Chester's service registry"""
        return self._get_bot_url('peter')

config = Config()
