import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration loader for Olive"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_file = self.base_dir / 'config.yaml'
        self._config = self._load_config()

        # Load shared organization config
        shared_config_path = self.base_dir / self._config['shared_config']
        with open(shared_config_path, 'r') as f:
            self._shared_config = yaml.safe_load(f)

    def _load_config(self):
        """Load configuration from YAML file"""
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f)

    @property
    def name(self):
        return self._config.get('name', 'olive')

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
        return self._config.get('server', {}).get('port', 8012)

    @property
    def organization_domains(self):
        return self._shared_config['organization']['domains']

    @property
    def admin_emails(self):
        # Read from environment variable (comma-separated list)
        env_emails = os.environ.get('ADMIN_EMAILS', '')
        if env_emails:
            return [email.strip() for email in env_emails.split(',') if email.strip()]
        # Fallback to config file (for backward compatibility)
        return self._config.get('auth', {}).get('admin_emails', [])

    @property
    def bots(self):
        return self._config.get('bots', {})

    @property
    def secret_key(self):
        return os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Email configuration
    @property
    def notification_email(self):
        return os.environ.get('NOTIFICATION_EMAIL', '')

    @property
    def smtp_host(self):
        return self._config.get('email', {}).get('smtp_host', 'smtp.gmail.com')

    @property
    def smtp_port(self):
        return self._config.get('email', {}).get('smtp_port', 587)

    @property
    def smtp_username(self):
        return os.environ.get('SMTP_USERNAME', '')

    @property
    def smtp_password(self):
        return os.environ.get('SMTP_PASSWORD', '')

    @property
    def email_from_address(self):
        return self._config.get('email', {}).get('from_address', 'olive@watsonblinds.com.au')

config = Config()
