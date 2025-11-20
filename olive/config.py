import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

from shared.config.loader import load_shared_yaml
from shared.config.ports import get_port
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Olive"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # ── Bot-local config.yaml ──────────────────────────────
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Shared organization config ────────────────────────
        org_cfg = load_shared_yaml("organization").get("organization", {}) or {}
        self.organization_name = org_cfg.get("name", "Watson Blinds Group")
        self.organization_domains = org_cfg.get("domains", []) or []
        self.organization_primary_domain = org_cfg.get("primary_domain", "")

        # ── Basic bot info (from YAML) ────────────────────────
        self.name = data.get("name", "olive")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config ─────────────────────────────────────
        server = data.get("server", {}) or {}
        # Host still comes from Olive's own config
        self.server_host = server.get("host", "0.0.0.0")
        # Port from shared ports.yaml, with local default fallback
        self.server_port = get_port("olive", server.get("port", 8012))

        # ── Admin emails (env override, then YAML) ────────────
        env_emails = os.environ.get("ADMIN_EMAILS", "")
        if env_emails:
            self.admin_emails = [
                email.strip()
                for email in env_emails.split(",")
                if email.strip()
            ]
        else:
            self.admin_emails = data.get("auth", {}).get("admin_emails", []) or []

        # ── Bots registry (from Olive's config) ───────────────
        self.bots = data.get("bots", {}) or {}

        # ── Secrets / env-specific settings ───────────────────

        # Flask secret key
        self.flask_secret_key = os.environ.get("FLASK_SECRET_KEY")

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # ── Email configuration ───────────────────────────────
        self.notification_email = os.environ.get("NOTIFICATION_EMAIL", "")

        email_cfg = data.get("email", {}) or {}
        self.smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = email_cfg.get("smtp_port", 587)

        self.smtp_username = os.environ.get("SMTP_USERNAME", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")

        self.email_from_address = email_cfg.get(
            "from_address",
            "olive@watsonblinds.com.au",
        )


config = Config()
