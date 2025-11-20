"""Configuration loader for Banji."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Banji."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Banji")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = server_cfg.get("port", 8012)

        # Browser config
        browser_cfg = data.get("browser", {}) or {}
        self.browser_default_timeout = browser_cfg.get("default_timeout", 30000)
        self.browser_screenshot_on_failure = browser_cfg.get("screenshot_on_failure", True)
        self.browser_screenshot_dir = browser_cfg.get("screenshot_dir", "screenshots")

        # Buz config
        buz_cfg = data.get("buz", {}) or {}
        self.buz_login_timeout = buz_cfg.get("login_timeout", 10000)
        self.buz_navigation_timeout = buz_cfg.get("navigation_timeout", 5000)
        self.buz_save_timeout = buz_cfg.get("save_timeout", 10000)

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Browser headless mode (env var overrides)
        # Default to headless in production (when FLASK_DEBUG is False/unset)
        # Set BUZ_HEADLESS=false explicitly for headed mode
        headless_env = os.environ.get("BUZ_HEADLESS", "").lower()
        if headless_env in ["true", "false"]:
            self.browser_headless = headless_env == "true"
        else:
            # Auto-detect: headless if not in debug mode
            is_debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
            self.browser_headless = not is_debug

        # Load Buz organizations (multi-tenant support)
        # Each org has its own credentials and base URL
        self.buz_orgs = self._load_buz_organizations()

        # Validate at least one org is configured
        if not self.buz_orgs:
            raise ValueError(
                "No Buz organizations configured. Set BUZ_ORGS environment variable "
                "with comma-separated org names, then configure credentials for each org."
            )

    def _load_buz_organizations(self):
        """
        Load Buz organization configurations from environment variables.

        Expected env vars:
            BUZ_ORGS=designer_drapes,canberra,tweed
            BUZ_DESIGNER_DRAPES_URL=https://designerdrapes.buz.com
            BUZ_DESIGNER_DRAPES_USERNAME=sales@designerdrapes.com
            BUZ_DESIGNER_DRAPES_PASSWORD=password123
            BUZ_CANBERRA_URL=https://canberra.buz.com
            BUZ_CANBERRA_USERNAME=sales@canberra.com
            BUZ_CANBERRA_PASSWORD=password456
            ... etc

        Returns:
            dict: {
                'designer_drapes': {
                    'name': 'designer_drapes',
                    'url': 'https://...',
                    'username': '...',
                    'password': '...'
                },
                ...
            }
        """
        orgs_env = os.environ.get("BUZ_ORGS", "").strip()
        if not orgs_env:
            return {}

        orgs = {}
        org_names = [name.strip() for name in orgs_env.split(",") if name.strip()]

        for org_name in org_names:
            # Convert to uppercase for env var names
            org_upper = org_name.upper()

            # Load credentials for this org
            url = os.environ.get(f"BUZ_{org_upper}_URL")
            username = os.environ.get(f"BUZ_{org_upper}_USERNAME")
            password = os.environ.get(f"BUZ_{org_upper}_PASSWORD")

            # Validate all required fields present
            if not url:
                raise ValueError(f"Missing BUZ_{org_upper}_URL for organization '{org_name}'")
            if not username:
                raise ValueError(f"Missing BUZ_{org_upper}_USERNAME for organization '{org_name}'")
            if not password:
                raise ValueError(f"Missing BUZ_{org_upper}_PASSWORD for organization '{org_name}'")

            # Store org config
            orgs[org_name] = {
                'name': org_name,
                'url': url,
                'username': username,
                'password': password
            }

        return orgs

    def get_org_config(self, org_name):
        """
        Get configuration for a specific organization.

        Args:
            org_name: Name of the organization (e.g., 'designer_drapes')

        Returns:
            dict: Organization config with url, username, password

        Raises:
            ValueError: If org_name is not configured
        """
        if org_name not in self.buz_orgs:
            available = ', '.join(self.buz_orgs.keys())
            raise ValueError(
                f"Unknown organization '{org_name}'. "
                f"Available organizations: {available}"
            )
        return self.buz_orgs[org_name]


# Global config instance
config = Config()
