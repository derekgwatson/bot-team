"""Configuration loader for Evelyn."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Evelyn."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Evelyn")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Authentication config
        self.auth = data.get("auth", {}) or {}

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = get_port("evelyn")

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Admin emails (env override)
        admin_cfg = data.get("admin", {}) or {}
        admin_emails_env = os.environ.get("EVELYN_ADMIN_EMAILS", "")
        if admin_emails_env:
            self.admin_emails = [e.strip() for e in admin_emails_env.split(",") if e.strip()]
        else:
            self.admin_emails = admin_cfg.get("emails", []) or []

        # Load shared organization config for allowed domains
        shared_config_path = base_dir.parent / "shared" / "config" / "organization.yaml"
        with open(shared_config_path, "r") as f:
            shared_data = yaml.safe_load(f) or {}

        # Organization config - allowed domains for authentication
        organization = shared_data.get("organization", {}) or {}
        self.allowed_domains = organization.get("domains", [])

        # Sheet profiles for specialized processing
        self.sheet_profiles = data.get("sheet_profiles", {}) or {}

    def get_profile(self, profile_name: str) -> dict | None:
        """
        Get a sheet profile by name.

        Args:
            profile_name: Name of the profile (e.g., 'supplier_jobsheet')

        Returns:
            Profile dict with 'sheets', 'description', 'filename_suffix' keys,
            or None if profile not found
        """
        return self.sheet_profiles.get(profile_name)

    def list_profiles(self) -> dict:
        """
        List all available sheet profiles.

        Returns:
            Dict of profile_name -> profile_info
        """
        return self.sheet_profiles


# Global config instance
config = Config()
