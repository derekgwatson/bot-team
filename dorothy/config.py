import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from services.chester_service import ChesterService

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration loader for Dorothy"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_file = self.base_dir / 'config.yaml'
        self._config = self._load_config()

        # Initialize Chester service for bot configuration
        chester_url = os.environ.get('CHESTER_URL') or self._config.get('chester', {}).get('url', 'http://localhost:8008')
        self.chester = ChesterService(chester_url)

    def _load_config(self):
        """
        Load configuration from YAML file with local override support

        Loads config.yaml (base config in git) and merges with config.local.yaml
        (local overrides, gitignored) if it exists.
        """
        # Load base config
        with open(self.config_file, 'r') as f:
            config = yaml.safe_load(f) or {}

        # Load local config if it exists
        local_config_file = self.base_dir / 'config.local.yaml'
        if local_config_file.exists():
            with open(local_config_file, 'r') as f:
                local_config = yaml.safe_load(f) or {}
                # Deep merge: local config overrides base config
                config = self._deep_merge(config, local_config)

        return config

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def name(self):
        return self._config.get('name', 'dorothy')

    @property
    def description(self):
        return self._config.get('description', '')

    @property
    def version(self):
        return self._config.get('version', '0.0.0')

    @property
    def server_host(self):
        return self._config.get('server', {}).get('host', '0.0.0.0')

    @property
    def server_port(self):
        return self._config.get('server', {}).get('port', 8005)

    @property
    def sally_url(self):
        """Get Sally's API URL"""
        return os.environ.get('SALLY_URL') or self._config.get('sally', {}).get('url', 'http://localhost:8004')

    @property
    def chester_url(self):
        """Get Chester's API URL"""
        return os.environ.get('CHESTER_URL') or self._config.get('chester', {}).get('url', 'http://localhost:8008')

    @property
    def default_server(self):
        return self._config.get('deployment', {}).get('default_server', 'prod')

    @property
    def deployment_timeout(self):
        return self._config.get('deployment', {}).get('deployment_timeout', 600)

    @property
    def verification_checks(self):
        return self._config.get('deployment', {}).get('verification_checks', [])

    def get_all_bots(self):
        """
        Get all bot configurations from Chester.

        Returns:
            Dict of bot configurations keyed by name, or empty dict if Chester unavailable
        """
        chester_bots = self.chester.get_all_bots()

        if chester_bots:
            # Convert list to dict keyed by name for compatibility
            return {bot['name']: bot for bot in chester_bots}

        # Chester is unavailable
        print("Warning: Chester is not available. Cannot retrieve bot configurations.")
        return {}

    def get_bot_config(self, bot_name):
        """
        Get configuration for a specific bot from Chester.

        Returns:
            Bot configuration dict, or None if not found or Chester unavailable
        """
        chester_config = self.chester.get_bot_config(bot_name)

        if not chester_config:
            print(f"Warning: Could not get configuration for {bot_name} from Chester.")

        return chester_config


config = Config()
