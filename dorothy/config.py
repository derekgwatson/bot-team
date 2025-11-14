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
        """Load configuration from YAML file"""
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f)

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

    def get_bot_config(self, bot_name):
        """Get configuration for a specific bot"""
        return self.bots.get(bot_name)

config = Config()
