import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Oscar"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "oscar")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = server.get("port", 8011)

        # ── Shared organization config (from shared YAML) ─────
        # config.yaml has e.g.:
        # shared_config: "../shared/config/organization.yaml"
        shared_config_rel = data.get("shared_config")
        if not shared_config_rel:
            raise RuntimeError("Oscar config.yaml is missing 'shared_config' path")

        shared_config_path = self.base_dir / shared_config_rel
        with open(shared_config_path, "r") as f:
            shared_data = yaml.safe_load(f) or {}

        self.organization_domains = shared_data.get("organization", {}).get(
            "domains", []
        )

        # ── Admin emails (env override, then YAML) ─────────────
        env_emails = os.environ.get("ADMIN_EMAILS", "")
        if env_emails:
            self.admin_emails = [
                email.strip()
                for email in env_emails.split(",")
                if email.strip()
            ]
        else:
            self.admin_emails = (
                data.get("auth", {}).get("admin_emails", []) or []
            )

        # ── Bots registry (from YAML) ─────────────────────────
        self.bots = data.get("bots", {}) or {}

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key (support both FLASK_SECRET_KEY and legacy SECRET_KEY)
        self.secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # ── Email configuration ────────────────────────────────
        self.notification_email = os.environ.get("NOTIFICATION_EMAIL", "")

        email_cfg = data.get("email", {}) or {}
        self.smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = email_cfg.get("smtp_port", 587)

        self.smtp_username = os.environ.get("SMTP_USERNAME", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")

        self.email_from_address = email_cfg.get(
            "from_address",
            "oscar@watsonblinds.com.au",
        )


config = Config()
