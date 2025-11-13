import os
import yaml
from pathlib import Path

class Config:
    """Configuration loader for Iris"""

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
        return self._config.get('name', 'iris')

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
        return self._config.get('server', {}).get('port', 8002)

    @property
    def google_credentials_file(self):
        path = self._config.get('google_workspace', {}).get('credentials_file', 'credentials.json')
        # Make it relative to iris's directory
        if not os.path.isabs(path):
            path = self.base_dir / path
        return str(path)

    @property
    def google_domain(self):
        return self._config.get('google_workspace', {}).get('domain', 'example.com')

    @property
    def google_admin_email(self):
        return self._config.get('google_workspace', {}).get('admin_email', '')

    @property
    def bots(self):
        return self._config.get('bots', {})

config = Config()
