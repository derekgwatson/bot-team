import yaml
import os

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

        # Auth config
        self.oauth_client_id = data['auth']['oauth_client_id']
        self.oauth_client_secret = data['auth']['oauth_client_secret']
        self.allowed_domains = data['auth'].get('allowed_domains', [])

        # Peter API config
        self.peter_api_url = data['peter_api']['url']
        self.peter_contacts_endpoint = data['peter_api']['contacts_endpoint']
        self.peter_search_endpoint = data['peter_api']['search_endpoint']

        # Other bots
        self.bots = data.get('bots', {})

config = Config()
