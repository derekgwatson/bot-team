"""
Monica Configuration Loader
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
    """Configuration loader for Monica"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load config.local.yaml if it exists (gitignored overrides)
        local_config_file = self.base_dir / "config.local.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # Merge with local config if it exists
        if local_config_file.exists():
            with open(local_config_file, "r") as f:
                local_data = yaml.safe_load(f) or {}
                data.update(local_data)

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "monica")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")

        # Authentication config
        self.auth = data.get("auth", {}) or {}
        self.emoji = data.get("emoji", "📡")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("monica")

        # ── Heartbeat thresholds ──────────────────────────────
        heartbeat = data.get("heartbeat", {}) or {}
        self.online_threshold = heartbeat.get("online_threshold", 2)
        self.degraded_threshold = heartbeat.get("degraded_threshold", 10)

        # ── Agent settings ────────────────────────────────────
        agent = data.get("agent", {}) or {}
        self.heartbeat_interval = agent.get("heartbeat_interval", 60)
        self.network_test_interval = agent.get("network_test_interval", 300)
        self.network_test_file_size = agent.get("network_test_file_size", 1048576)

        # ── Database settings ─────────────────────────────────
        database = data.get("database", {}) or {}
        self.cleanup_days = database.get("cleanup_days", 30)

        # ── Dashboard settings ────────────────────────────────
        dashboard = data.get("dashboard", {}) or {}
        self.auto_refresh = dashboard.get("auto_refresh", 30)

        # ── Logging settings ──────────────────────────────────
        logging = data.get("logging", {}) or {}
        self.log_level = logging.get("level", "INFO")
        self.log_heartbeats = logging.get("log_heartbeats", False)

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key
        self.secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication (optional)
        self.bot_api_key = os.environ.get("BOT_API_KEY")


# Global config instance
config = Config()
