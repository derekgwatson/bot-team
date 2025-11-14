import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration loader for Sally"""

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
