import yaml
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # Loads root .env automatically

# Load bot-specific .env (can override global values)
bot_env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=bot_env_path)


class Config:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Bot info
        self.name = data['name']
        self.description = data['description']
        self.version = data['version']

        # Server config
        self.server_host = data['server']['host']
        self.server_port = data['server']['port']

        # Load shared organization config
        shared_config_path = os.path.join(os.path.dirname(__file__), data['shared_config'])
        with open(shared_config_path, 'r') as f:
            shared_data = yaml.safe_load(f)

        # Organization config
        self.allowed_domains = shared_data['organization']['domains']

        # Peter API config (keep endpoints from yaml)
        peter_api = data.get('peter_api', {})
        self.peter_contacts_endpoint = peter_api.get('contacts_endpoint', '/api/contacts')
        self.peter_search_endpoint = peter_api.get('search_endpoint', '/api/contacts/search')

        # Chester URL - service registry
        self.chester_url = os.environ.get('CHESTER_API_URL', 'http://localhost:8008')
        self.bot_api_key = os.environ.get('BOT_API_KEY')

        # Cache for bot URLs (avoid hitting Chester on every request)
        self._bot_url_cache = {}

    def _query_chester_for_bot_url(self, bot_name: str, fallback_url: str) -> str:
        """
        Query Chester's service registry for a bot's URL.

        Args:
            bot_name: Name of the bot to look up
            fallback_url: Fallback URL if Chester is unavailable

        Returns:
            Bot's API URL
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
        except Exception as e:
            # Chester unavailable - use fallback
            pass

        # Fallback to default (localhost for dev)
        return fallback_url

    def _get_bot_url(self, bot_name: str, fallback_localhost_port: int) -> str:
        """
        Get the URL for a bot via Chester's service registry.

        Flow:
        1. Check Flask session for dev mode override (prod vs localhost)
        2. Query Chester's registry for the bot's URL
        3. Fall back to localhost if Chester is unavailable

        Args:
            bot_name: Name of the bot to look up
            fallback_localhost_port: Port to use for localhost fallback

        Returns:
            Bot's API URL
        """
        try:
            from flask import session, has_request_context

            # Check if we're in a request context and have dev config override
            if has_request_context():
                dev_config = session.get('dev_bot_config', {})
                if dev_config.get(bot_name) == 'prod':
                    # User explicitly wants prod for this bot - query Chester
                    return self._query_chester_for_bot_url(
                        bot_name,
                        f"https://{bot_name}.watsonblinds.com.au"
                    )
        except:
            # If Flask isn't available or there's no request context, continue
            pass

        # Query Chester with localhost fallback
        fallback_url = f"http://localhost:{fallback_localhost_port}"
        return self._query_chester_for_bot_url(bot_name, fallback_url)

    @property
    def quinn_api_url(self):
        """Get Quinn's API URL from Chester's service registry"""
        return self._get_bot_url('quinn', 8006)

    @property
    def peter_api_url(self):
        """Get Peter's API URL from Chester's service registry"""
        return self._get_bot_url('peter', 8003)

config = Config()
