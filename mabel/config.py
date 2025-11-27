"""Configuration loader for Mabel email bot."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class Config:
    """
    Configuration manager for Mabel.

    Loads config.yaml and environment variables, providing a clean interface
    to all configuration values needed by the application.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml. If None, looks in same directory as this file.

        Raises:
            ConfigError: If required configuration is missing or invalid.
        """
        # Load environment variables
        load_dotenv()

        # Determine config file path
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")

        # Load YAML config
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        # Validate and load required values
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that all required configuration is present."""
        # Check config.yaml structure
        required_keys = ['name', 'version', 'server', 'email']
        for key in required_keys:
            if key not in self._config:
                raise ConfigError(f"Missing required config key: {key}")

        # Check required environment variables
        required_env_vars = [
            'BOT_API_KEY',
            'EMAIL_SMTP_USERNAME',
            'EMAIL_SMTP_PASSWORD',
            'FLASK_SECRET_KEY'
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please set these in your .env file or environment."
            )

    # Application metadata
    @property
    def name(self) -> str:
        """Bot name."""
        return self._config['name']

    @property
    def version(self) -> str:
        """Bot version."""
        return self._config['version']

    @property
    def description(self) -> str:
        """Bot description."""
        return self._config.get('description', '')

    @property
    def emoji(self) -> str:
        """Bot emoji."""
        return self._config.get('emoji', '📧')

    # Server configuration
    @property
    def server_host(self) -> str:
        """Server host to bind to."""
        return self._config['server'].get('host', '0.0.0.0')

    @property
    def server_port(self) -> int:
        """Server port from shared config (chester/config.yaml)."""
        return get_port("mabel")

    @property
    def log_level(self) -> str:
        """Logging level."""
        return self._config['server'].get('log_level', 'INFO')

    # Email configuration
    @property
    def default_from(self) -> str:
        """Default from email address."""
        return self._config['email']['default_from']

    @property
    def default_reply_to(self) -> str:
        """Default reply-to email address."""
        return self._config['email']['default_reply_to']

    @property
    def default_sender_name(self) -> str:
        """Default sender display name."""
        return self._config['email']['default_sender_name']

    @property
    def smtp_host(self) -> str:
        """SMTP server host."""
        return self._config['email']['smtp']['host']

    @property
    def smtp_port(self) -> int:
        """SMTP server port."""
        return int(self._config['email']['smtp']['port'])

    @property
    def smtp_use_tls(self) -> bool:
        """Whether to use TLS for SMTP."""
        return bool(self._config['email']['smtp'].get('use_tls', True))

    @property
    def smtp_username(self) -> str:
        """SMTP username from environment."""
        username_var = self._config['email']['smtp']['username_env_var']
        return os.getenv(username_var, '')

    @property
    def smtp_password(self) -> str:
        """SMTP password from environment."""
        password_var = self._config['email']['smtp']['password_env_var']
        return os.getenv(password_var, '')

    # Security configuration
    @property
    def internal_api_key(self) -> str:
        """Internal API key for inter-bot authentication (shared across all bots)."""
        return os.getenv('BOT_API_KEY', '')

    @property
    def flask_secret_key(self) -> str:
        """Flask secret key from environment."""
        return os.getenv('FLASK_SECRET_KEY', '')

    # Authentication settings
    @property
    def allowed_domains(self) -> list:
        """Allowed email domains for OAuth login."""
        # Load from shared organization config
        shared_config_path = Path(__file__).parent.parent / "shared" / "config" / "organization.yaml"
        if shared_config_path.exists():
            with open(shared_config_path, "r", encoding="utf-8") as f:
                shared_data = yaml.safe_load(f) or {}
            organization = shared_data.get("organization", {}) or {}
            return organization.get("domains", [])
        return []

    @property
    def admin_emails(self) -> list:
        """Admin email addresses (empty for Mabel - any allowed domain user is fine)."""
        return []

    @property
    def auth(self) -> dict:
        """Auth config for GatewayAuth."""
        return {
            'mode': 'domain',
            'allowed_domains': self.allowed_domains,
            'admin_emails': self.admin_emails,
        }
