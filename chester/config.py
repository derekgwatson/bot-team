"""Configuration loader for Chester."""
import os
import yaml
from pathlib import Path

class Config:
    """Configuration management for Chester."""

    def __init__(self):
        self.config_path = Path(__file__).parent / 'config.yaml'
        self.config = self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def name(self):
        return self.config.get('name', 'Chester')

    @property
    def description(self):
        return self.config.get('description', '')

    @property
    def version(self):
        return self.config.get('version', '1.0.0')

    @property
    def personality(self):
        return self.config.get('personality', '')

    @property
    def server_host(self):
        return self.config.get('server', {}).get('host', '0.0.0.0')

    @property
    def server_port(self):
        return self.config.get('server', {}).get('port', 8008)

    @property
    def bot_team(self):
        """Get the bot team registry."""
        return self.config.get('bot_team', {})

    @property
    def health_check_timeout(self):
        return self.config.get('health_check', {}).get('timeout', 5)

    @property
    def health_check_interval(self):
        return self.config.get('health_check', {}).get('check_interval', 60)

    @property
    def new_bot_template(self):
        """Get the new bot template configuration."""
        return self.config.get('new_bot_template', {})

# Global config instance
config = Config()
