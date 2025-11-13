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

        # Load shared organization config
        shared_config_path = os.path.join(os.path.dirname(__file__), data['shared_config'])
        with open(shared_config_path, 'r') as f:
            shared_data = yaml.safe_load(f)

        # Organization config
        self.allowed_domains = shared_data['organization']['domains']

        # Auth config - secrets come from environment variables
        self.oauth_client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
        self.oauth_client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

        # Peter API config
        self.peter_api_url = data['peter_api']['url']
        self.peter_contacts_endpoint = data['peter_api']['contacts_endpoint']
        self.peter_search_endpoint = data['peter_api']['search_endpoint']

        # Other bots
        self.bots = data.get('bots', {})

config = Config()
