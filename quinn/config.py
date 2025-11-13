import yaml
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Bot info
        self.name = data['name']
        self.description = data['description']
        self.version = data['version']

        # Server config
        self.server_host = data['server']['host']
        self.server_port = data['server']['port']

        # Database config
        self.database_path = os.path.join(os.path.dirname(__file__), data['database']['path'])

        # Google Groups config
        self.credentials_file = os.path.join(os.path.dirname(__file__), data['google_groups']['credentials_file'])
        self.allstaff_group = data['google_groups']['allstaff_group']

        # Organization config
        self.organization_domains = data['organization']['domains']

        # Auth config - secrets come from environment variables
        self.oauth_client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        self.oauth_client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
        self.admin_emails = data['auth'].get('admin_emails', [])

        # Other bots
        self.bots = data.get('bots', {})

config = Config()
