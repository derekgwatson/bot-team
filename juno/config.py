"""
Juno Configuration Loader
Loads configuration from YAML and environment variables
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Juno"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load config.local.yaml if it exists (gitignored overrides)
        local_config_file = self.base_dir / "config.local.yaml"

        # Load main config.yaml
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Merge with local config if it exists
        if local_config_file.exists():
            with open(local_config_file, "r", encoding="utf-8") as f:
                local_data = yaml.safe_load(f) or {}
                data.update(local_data)

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "juno")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.emoji = data.get("emoji", "🗺️")
        self.personality = data.get("personality", "Warm and reassuring")

        # Auth config from yaml (mode comes from config.yaml)
        self._auth_yaml = data.get("auth", {}) or {}

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("juno")

        # ── Tracking settings ─────────────────────────────────
        tracking = data.get("tracking", {}) or {}
        self.link_expiry_hours = tracking.get("link_expiry_hours", 24)
        self.post_arrival_expiry_minutes = tracking.get("post_arrival_expiry_minutes", 30)
        self.code_length = tracking.get("code_length", 12)

        # ── Travis integration ────────────────────────────────
        travis = data.get("travis", {}) or {}
        self.travis_base_url = travis.get("base_url", "http://localhost:8021")
        self.poll_interval = travis.get("poll_interval", 10)

        # ── Map settings ──────────────────────────────────────
        map_config = data.get("map", {}) or {}
        self.default_lat = map_config.get("default_lat", -35.2809)
        self.default_lng = map_config.get("default_lng", 149.1300)
        self.default_zoom = map_config.get("default_zoom", 12)

        # ── Database settings ─────────────────────────────────
        database = data.get("database", {}) or {}
        self.cleanup_days = database.get("cleanup_days", 7)

        # ── Logging settings ──────────────────────────────────
        logging_config = data.get("logging", {}) or {}
        self.log_level = logging_config.get("level", "INFO")

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key (required)
        self.secret_key = os.environ.get("FLASK_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("FLASK_SECRET_KEY environment variable is required")

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Google Maps API key (optional - for ETA calculation)
        self.google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

        # ── Authentication settings ────────────────────────────────
        # Load allowed domains from shared organization config
        shared_config_path = self.base_dir.parent / "shared" / "config" / "organization.yaml"
        if shared_config_path.exists():
            with open(shared_config_path, "r", encoding="utf-8") as f:
                shared_data = yaml.safe_load(f) or {}
            organization = shared_data.get("organization", {}) or {}
            self.allowed_domains = organization.get("domains", [])
        else:
            self.allowed_domains = []

        # Admin emails (optional - for future admin-only features)
        self.admin_emails = []

    @property
    def auth(self):
        """Auth config for GatewayAuth - reads mode from config.yaml."""
        return {
            **self._auth_yaml,
            'allowed_domains': self.allowed_domains,
            'admin_emails': self.admin_emails,
        }


# Global config instance
config = Config()
