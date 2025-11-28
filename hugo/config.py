"""Configuration loader for Hugo."""
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
    """Configuration management for Hugo."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Hugo")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Authentication config
        self.auth = data.get("auth", {}) or {}

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = get_port("hugo")

        # Browser config
        browser_cfg = data.get("browser", {}) or {}
        self.browser_default_timeout = browser_cfg.get("default_timeout", 30000)
        self.browser_screenshot_on_failure = browser_cfg.get("screenshot_on_failure", True)
        self.browser_screenshot_dir = browser_cfg.get("screenshot_dir", "screenshots")

        # Buz config
        buz_cfg = data.get("buz", {}) or {}
        self.buz_navigation_timeout = buz_cfg.get("navigation_timeout", 30000)
        self.buz_save_timeout = buz_cfg.get("save_timeout", 300000)

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Browser headless mode
        self.browser_headless = os.environ.get("BUZ_HEADLESS", "true").lower() == "true"

        # Debug mode - enables headed browser and pause points
        self.browser_debug = os.environ.get("BUZ_DEBUG", "false").lower() == "true"
        if self.browser_debug:
            # Debug mode forces headed browser
            self.browser_headless = False

        # Load Buz organizations from shared .secrets/buz/ directory
        self.buz_orgs, self.buz_orgs_missing_auth = BuzOrgs.load_orgs()

        # Warn about missing auth but don't crash (allows bot to start for non-Buz routes)
        if self.buz_orgs_missing_auth:
            BuzOrgs.print_setup_instructions(self.buz_orgs_missing_auth)

    def get_org_config(self, org_name: str) -> dict:
        """
        Get configuration for a specific organization.

        Args:
            org_name: Name of the organization

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
    def available_orgs(self) -> list:
        """Get list of available org names."""
        return list(self.buz_orgs.keys())

    @property
    def is_fully_configured(self) -> bool:
        """Check if all organizations have authentication configured."""
        return len(self.buz_orgs_missing_auth) == 0


# Global config instance
config = Config()
