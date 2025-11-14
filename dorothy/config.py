import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration loader for Dorothy"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_file = self.base_dir / 'config.yaml'
        self._config = self._load_config()

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
    def default_server(self):
        return self._config.get('deployment', {}).get('default_server', 'prod')

    @property
    def deployment_timeout(self):
        return self._config.get('deployment', {}).get('deployment_timeout', 600)

    @property
    def verification_checks(self):
        return self._config.get('deployment', {}).get('verification_checks', [])

    @property
    def bots(self):
        """Get bot configurations"""
        return self._config.get('bots', {})

    @property
    def defaults(self):
        """Get default bot configuration"""
        return self._config.get('defaults', {})

    def get_bot_config(self, bot_name):
        """
        Get configuration for a specific bot

        Merges defaults with bot-specific config and replaces {bot_name} placeholders
        """
        bot_config = self.bots.get(bot_name)
        if not bot_config:
            return None

        # Start with defaults, then merge bot-specific config
        merged = self._deep_merge(self.defaults.copy(), bot_config)

        # Replace {bot_name} placeholders in all string values
        merged = self._replace_placeholders(merged, bot_name)

        return merged

    def _replace_placeholders(self, config: dict, bot_name: str) -> dict:
        """Replace {bot_name} placeholders in config values"""
        result = {}
        for key, value in config.items():
            if isinstance(value, str):
                result[key] = value.format(bot_name=bot_name)
            elif isinstance(value, dict):
                result[key] = self._replace_placeholders(value, bot_name)
            elif isinstance(value, list):
                result[key] = [
                    item.format(bot_name=bot_name) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

config = Config()
