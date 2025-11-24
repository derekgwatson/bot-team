import yaml
import os
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

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
        self.emoji = data.get('emoji', '🎫')

        # Server config
        self.server_host = data['server']['host']
        self.server_port = get_port("sadie")

        # Database config
        self.database_path = data['database']['path']

        # Zendesk config (from environment variables)
        self.zendesk_subdomain = os.environ.get('ZENDESK_SUBDOMAIN')
        self.zendesk_email = os.environ.get('ZENDESK_EMAIL')
        self.zendesk_api_token = os.environ.get('ZENDESK_API_TOKEN')

        # Google OAuth config (from environment variables)
        self.google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

        # Allowed domains for all-staff access (comma-separated list)
        env_domains = os.environ.get('ALLOWED_DOMAINS', '')
        if env_domains:
            self.allowed_domains = [domain.strip() for domain in env_domains.split(',')]
        else:
            auth_section = data.get('auth') or {}
            self.allowed_domains = auth_section.get('allowed_domains', [])

        # Flask secret key
        self.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

        # Bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get('BOT_API_KEY')

config = Config()
