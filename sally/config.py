import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Sally"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_file = self.base_dir / 'config.yaml'
        self._config = self._load_config()

        # Flask secret key
        self.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

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
        return self._config.get('name', 'sally')

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
        return self._config.get('server', {}).get('port', 8004)

    @property
    def ssh_default_user(self):
        return self._config.get('ssh', {}).get('default_user', 'ubuntu')

    @property
    def ssh_connect_timeout(self):
        return self._config.get('ssh', {}).get('connect_timeout', 10)

    @property
    def ssh_command_timeout(self):
        return self._config.get('ssh', {}).get('command_timeout', 300)

    @property
    def ssh_key_path(self):
        """Get SSH private key path from environment"""
        return os.environ.get('SSH_PRIVATE_KEY_PATH', str(self.base_dir / 'id_rsa'))

    @property
    def servers(self):
        """Get configured servers"""
        return self._config.get('servers') or {}


config = Config()
