"""Configuration loader for Chester."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Chester."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Chester")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = server_cfg.get("port", 8008)

        # Bot team registry
        self.bot_team = data.get("bot_team", {}) or {}

        # Health check config
        health_cfg = data.get("health_check", {}) or {}
        self.health_check_timeout = health_cfg.get("timeout", 0.5)
        self.health_check_interval = health_cfg.get("check_interval", 60)
        self.health_check_enabled = health_cfg.get("enabled", True)

        # New bot template config
        self.new_bot_template = data.get("new_bot_template", {}) or {}

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")


# Global config instance
config = Config()
