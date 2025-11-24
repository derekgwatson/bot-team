import yaml
import os
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port
from dotenv import load_dotenv

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
        self.emoji = data.get('emoji', '👤')

        # Server config
        self.server_host = data['server']['host']
        self.server_port = get_port("zac")

        # Database config
        self.database_path = data['database']['path']

        # Zendesk config (from environment variables)
        self.zendesk_subdomain = os.environ.get('ZENDESK_SUBDOMAIN')
        self.zendesk_email = os.environ.get('ZENDESK_EMAIL')
        self.zendesk_api_token = os.environ.get('ZENDESK_API_TOKEN')

        # Google OAuth config (from environment variables)
        self.google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        # Admin emails from env (comma-separated list)
        env_emails = os.environ.get('ADMIN_EMAILS', '')
        if env_emails:
            self.admin_emails = [email.strip() for email in env_emails.split(',')]
        else:
            auth_section = data.get('auth') or {}
            self.admin_emails = auth_section.get('admin_emails', [])

        # Flask secret key
        self.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

        # Bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get('BOT_API_KEY')

config = Config()
