"""Configuration loader for Chester."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class Config:
    """Configuration management for Chester."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "Chester")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = server.get("port", 8008)

        # ── Bot team registry (from YAML) ─────────────────────
        # e.g. {"sally": {"url": "..."}, "zac": {"url": "..."}, ...}
        self.bot_team = data.get("bot_team", {}) or {}

        # ── Health check config (from YAML) ───────────────────
        health = data.get("health_check", {}) or {}
        self.health_check_timeout = health.get("timeout", 0.5)
        self.health_check_interval = health.get("check_interval", 60)
        self.health_check_enabled = health.get("enabled", True)

        # ── New bot template config (from YAML) ───────────────
        self.new_bot_template = data.get("new_bot_template", {}) or {}

        # ── Secrets / env-specific settings (from .env) ───────

        # Flask secret key
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

    # ─────────────────────────────────────────────────────────
    # Helper methods for bot registry
    # ─────────────────────────────────────────────────────────

    def get_bot_config(self, bot_name: str) -> dict | None:
        """
        Get the config entry for a specific bot, e.g. 'sally', 'zac', 'pam'.

        Returns:
            Dict for that bot (from bot_team), or None if not found.
        """
        return self.bot_team.get(bot_name)

    def get_bot_url(self, bot_name: str, default: str | None = None) -> str | None:
        """
        Get the base URL for a specific bot from the bot_team section.

        Returns:
            URL string, or default / None if not found.
        """
        bot_cfg = self.get_bot_config(bot_name)
        if not bot_cfg:
            return default
        return bot_cfg.get("url", default)

    def get_all_bots(self) -> list[str]:
        """
        Get a list of all bot names defined in the bot_team section.
        """
        return list(self.bot_team.keys())

    @property
    def sally_url(self) -> str | None:
        """
        Convenience property for Sally's URL.
        """
        return self.get_bot_url("sally")


# Global config instance
config = Config()
