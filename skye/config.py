"""Configuration loader for Skye."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Skye."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Skye")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = server_cfg.get("port", 8019)

        # Database config
        db_cfg = data.get("database", {}) or {}
        db_path = db_cfg.get("path", "database/skye.db")
        self.database_path = base_dir / db_path

        # Scheduler config
        scheduler_cfg = data.get("scheduler", {}) or {}
        self.scheduler_timezone = scheduler_cfg.get("timezone", "Australia/Sydney")
        self.misfire_grace_time = scheduler_cfg.get("misfire_grace_time", 60)
        self.max_instances = scheduler_cfg.get("max_instances", 3)

        # Job templates
        self.job_templates = data.get("job_templates", {}) or {}

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Admin emails (env override)
        admin_cfg = data.get("admin", {}) or {}
        admin_emails_env = os.environ.get("SKYE_ADMIN_EMAILS", "")
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


# Global config instance
config = Config()
