import yaml
import os
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


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
        self.peter_contacts_endpoint = data['peter_api']['contacts_endpoint']
        self.peter_search_endpoint = data['peter_api']['search_endpoint']

    def _get_bot_url(self, bot_name: str, default_url: str) -> str:
        """
        Get the URL for a bot, respecting dev mode configuration.

        In dev mode, checks Flask session for overrides:
        - If session says use 'prod' for this bot, use prod URL
        - Otherwise use default (localhost for dev)

        Returns the URL for the bot API
        """
        try:
            from flask import session, has_request_context

            # Check if we're in a request context and have dev config
            if has_request_context():
                dev_config = session.get('dev_bot_config', {})
                if dev_config.get(bot_name) == 'prod':
                    # Use production URL
                    return f"https://{bot_name}.watsonblinds.com.au"
        except:
            # If Flask isn't available or there's no request context, use default
            pass

        # Default to environment variable or default (localhost for dev)
        return default_url

    @property
    def quinn_api_url(self):
        """Get Quinn's API URL"""
        default = os.environ.get('QUINN_API_URL', 'http://localhost:8006')
        return self._get_bot_url('quinn', default)

    @property
    def peter_api_url(self):
        """Get Peter's API URL"""
        default = os.environ.get('PETER_API_URL', 'http://localhost:8003')
        return self._get_bot_url('peter', default)

config = Config()
