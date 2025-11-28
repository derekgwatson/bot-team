"""Configuration loader for Banji."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port
from shared.playwright.buz import BuzOrgs

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Banji."""

    def __init__(self):
        # Validate required environment variables upfront
        self._validate_environment()

        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Banji")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Authentication config
        self.auth = data.get("auth", {}) or {}

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = get_port("banji")

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

        # Browser headless mode - always default to headless
        # Can be overridden per-request from web UI for debugging
        self.browser_headless = True

        # Load Buz organizations from shared .secrets/buz/ directory
        self.buz_orgs, self.buz_orgs_missing_auth = BuzOrgs.load_orgs()

        # Validate at least one org is configured
        if not self.buz_orgs and not self.buz_orgs_missing_auth:
            raise ValueError(
                "No Buz organizations configured. Set BUZ_ORGS environment variable "
                "with comma-separated org names, then configure credentials for each org."
            )

        # Warn about missing auth but don't crash
        if self.buz_orgs_missing_auth:
            BuzOrgs.print_setup_instructions(self.buz_orgs_missing_auth)

    def _validate_environment(self):
        """
        Validate required environment variables are set.
        Provides helpful error messages for missing configuration.
        """
        missing = []
        warnings = []

        # Check required variables
        if not os.environ.get("BUZ_ORGS"):
            missing.append("BUZ_ORGS - Comma-separated list of organization names (e.g., 'watsonblinds,designerdrapes')")

        # Check optional but recommended
        if not os.environ.get("BOT_API_KEY"):
            warnings.append("BOT_API_KEY - Required for bot-to-bot communication")

        if missing:
            error_msg = "\n❌ Missing required environment variables:\n\n"
            for var in missing:
                error_msg += f"  • {var}\n"
            error_msg += "\n📝 Create a .env file in the banji/ directory with these variables."
            error_msg += "\n💡 See banji/.env.example for a template."
            raise ValueError(error_msg)

        if warnings:
            print("\n⚠️  Optional environment variables not set:")
            for var in warnings:
                print(f"  • {var}")
            print()

    def get_org_config(self, org_name):
        """
        Get configuration for a specific organization.

        Args:
            org_name: Name of the organization (e.g., 'designer_drapes')

        Returns:
            dict: Organization config with storage_state_path

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

    @property
    def is_fully_configured(self):
        """Check if all organizations have authentication configured."""
        return len(self.buz_orgs_missing_auth) == 0

    @property
    def setup_instructions(self):
        """Get setup instructions for missing auth."""
        if self.is_fully_configured:
            return None

        instructions = []
        for org_name, expected_path in self.buz_orgs_missing_auth.items():
            instructions.append({
                'org_name': org_name,
                'expected_path': expected_path,
                'command': f"python tools/buz_auth_bootstrap.py {org_name}"
            })
        return instructions


# Global config instance
config = Config()
