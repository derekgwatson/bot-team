import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Fiona"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "fiona")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # Authentication config (admin_emails injected after loading from env/yaml below)
        self._auth_yaml = data.get("auth", {}) or {}

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("fiona")

        # ── Database config (from YAML) ──────────────────────
        db_config = data.get("database", {}) or {}
        self.database_path = db_config.get("path", "database/fiona.db")

        # ── Mavis integration config ──────────────────────────
        mavis_config = data.get("mavis", {}) or {}
        self.mavis_dev_url = mavis_config.get("dev_url", "http://localhost:8017")
        self.mavis_prod_url = mavis_config.get("prod_url", "https://mavis.watsonblinds.com.au")

        # ── Google Sheets import config ──────────────────────
        sheets_config = data.get("google_sheets", {}) or {}
        self.spreadsheet_id = os.environ.get(
            "FIONA_SPREADSHEET_ID",
            sheets_config.get("spreadsheet_id", "")
        )
        self.sheet_name = sheets_config.get("sheet_name", "Friendly_Descriptions")
        self.google_credentials_file = os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS",
            str(self.base_dir / "credentials.json")
        )

        # ── Admin access config ──────────────────────────────
        # Admin emails can be set in YAML or as comma-separated env var
        admin_config = data.get("admin", {}) or {}
        admin_emails_env = os.environ.get("FIONA_ADMIN_EMAILS", "")
        if admin_emails_env:
            self.admin_emails = [e.strip() for e in admin_emails_env.split(",") if e.strip()]
        else:
            # Get from YAML, ensuring it's a list (YAML returns None for empty/commented lists)
            self.admin_emails = admin_config.get("emails", []) or []

        # ── Load shared organization config for allowed domains ──
        shared_config_path = self.base_dir.parent / "shared" / "config" / "organization.yaml"
        with open(shared_config_path, "r") as f:
            shared_data = yaml.safe_load(f) or {}
        organization = shared_data.get("organization", {}) or {}
        self.allowed_domains = organization.get("domains", [])

        # Build auth config for GatewayAuth (inject admin_emails and allowed_domains)
        self.auth = {
            **self._auth_yaml,
            'admin_emails': self.admin_emails,
            'allowed_domains': self.allowed_domains,
        }

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key (required)
        self.flask_secret_key = os.environ.get("FLASK_SECRET_KEY")
        if not self.flask_secret_key:
            raise ValueError("FLASK_SECRET_KEY environment variable is required")

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

    def get_mavis_url(self) -> str:
        """Get Mavis URL based on environment"""
        # Allow override via environment variable
        if os.environ.get("MAVIS_URL"):
            return os.environ.get("MAVIS_URL")

        # In dev mode, use localhost
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.mavis_dev_url

        # In production, use the production URL
        return self.mavis_prod_url


config = Config()
