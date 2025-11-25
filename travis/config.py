"""
Travis Configuration Loader
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
    """Configuration loader for Travis"""

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
        self.name = data.get("name", "travis")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.emoji = data.get("emoji", "🚗")
        self.personality = data.get("personality", "Friendly road companion")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("travis")

        # ── Location settings ──────────────────────────────────
        location = data.get("location", {}) or {}
        self.ping_interval = location.get("ping_interval", 30)
        self.stale_threshold = location.get("stale_threshold", 120)
        self.history_retention_hours = location.get("history_retention_hours", 24)

        # ── Privacy settings ───────────────────────────────────
        privacy = data.get("privacy", {}) or {}
        self.share_only_in_transit = privacy.get("share_only_in_transit", True)
        self.customer_proximity_buffer = privacy.get("customer_proximity_buffer", 100)

        # ── Status values ──────────────────────────────────────
        status = data.get("status", {}) or {}
        self.status_values = status.get("values", ["off_duty", "in_transit", "at_customer", "on_break"])

        # ── Database settings ─────────────────────────────────
        database = data.get("database", {}) or {}
        self.cleanup_hours = database.get("cleanup_hours", 48)

        # ── Logging settings ──────────────────────────────────
        logging_config = data.get("logging", {}) or {}
        self.log_level = logging_config.get("level", "INFO")
        self.log_pings = logging_config.get("log_pings", False)

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key
        self.secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")


# Global config instance
config = Config()
