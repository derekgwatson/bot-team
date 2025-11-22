import yaml
import os
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Bot info
        self.name = data['name']
        self.description = data['description']
        self.version = data['version']
        self.emoji = data.get('emoji', '👥')

        # Server config
        self.server_host = data['server']['host']
        self.server_port = data['server']['port']

        # Store Peter URL default (will be made session-aware via property)
        self._peter_url_default = data.get('peter_url', 'http://localhost:8003')

        # Sync config
        sync_config = data.get('sync', {})
        self.sync_interval_seconds = sync_config.get('interval_seconds', 300)

        # Database config (deprecated - Quinn no longer uses a database)
        self.database_path = os.path.join(os.path.dirname(__file__), data['database']['path'])

        # Load shared organization config
        shared_config_path = os.path.join(os.path.dirname(__file__), data['shared_config'])
        with open(shared_config_path, 'r', encoding='utf-8') as f:
            shared_data = yaml.safe_load(f)

        # Organization config
        self.organization_domains = shared_data['organization']['domains']

        # Google Groups config
        self.credentials_file = os.path.join(os.path.dirname(__file__), data['google_groups']['credentials_file'])
        # Read allstaff group from env first, fallback to config file
        self.allstaff_group = os.environ.get('GOOGLE_ALLSTAFF_GROUP') or data['google_groups'].get('allstaff_group', '')

        # Admin emails from env (comma-separated list) or fallback to config file
        env_emails = os.environ.get('ADMIN_EMAILS', '')
        if env_emails:
            self.admin_emails = [email.strip() for email in env_emails.split(',') if email.strip()]
        else:
            # Get auth section (may be None if empty in yaml)
            auth_section = data.get('auth') or {}
            self.admin_emails = auth_section.get('admin_emails', [])

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
    def peter_url(self):
        """Get Peter's API URL (session-aware)"""
        return self._get_bot_url('peter', self._peter_url_default)

config = Config()
