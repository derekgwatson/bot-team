"""Configuration loader for Grant."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Grant."""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_path = self.base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Grant")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Auth config from yaml (will be augmented with admin_emails below)
        self._auth_yaml = data.get("auth", {}) or {}

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = get_port("grant")

        # Database config
        db_cfg = data.get("database", {}) or {}
        db_path = db_cfg.get("path", "database/grant.db")
        self.database_path = self.base_dir / db_path

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Superadmin emails - these always have access to Grant's UI
        # This is the bootstrap mechanism - once Grant is running,
        # superadmins can grant access to Grant for other users
        superadmins_env = os.environ.get("GRANT_SUPERADMINS", "")
        if superadmins_env:
            self.superadmins = [e.strip().lower() for e in superadmins_env.split(",") if e.strip()]
        else:
            self.superadmins = []

        # Admin emails for GatewayAuth = superadmins
        self.admin_emails = self.superadmins

        # Load shared organization config for allowed domains
        shared_config_path = self.base_dir.parent / "shared" / "config" / "organization.yaml"
        try:
            with open(shared_config_path, "r") as f:
                shared_data = yaml.safe_load(f) or {}
            organization = shared_data.get("organization", {}) or {}
            self.allowed_domains = organization.get("domains", [])
        except FileNotFoundError:
            self.allowed_domains = []

        # Build auth config for GatewayAuth (inject admin_emails)
        self.auth = {
            **self._auth_yaml,
            'admin_emails': self.admin_emails,
            'allowed_domains': self.allowed_domains,
        }

        # Bot registry config
        bots_cfg = data.get("bots", {}) or {}
        self.sync_bots_from_chester = bots_cfg.get("sync_from_chester", True)

    def get_chester_url(self) -> str:
        """Get Chester's URL for bot registry sync."""
        chester_port = get_port("chester")
        return os.environ.get("CHESTER_API_URL", f"http://localhost:{chester_port}")


# Global config instance
config = Config()
