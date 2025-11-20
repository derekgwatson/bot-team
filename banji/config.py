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

        # Buz-specific environment variables
        self.buz_base_url = os.environ.get("BUZ_BASE_URL")
        self.buz_username = os.environ.get("BUZ_USERNAME")
        self.buz_password = os.environ.get("BUZ_PASSWORD")

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

        # Validate required Buz credentials
        if not self.buz_base_url:
            raise ValueError("BUZ_BASE_URL environment variable is required")
        if not self.buz_username:
            raise ValueError("BUZ_USERNAME environment variable is required")
        if not self.buz_password:
            raise ValueError("BUZ_PASSWORD environment variable is required")


# Global config instance
config = Config()
