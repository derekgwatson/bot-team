import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Doc"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "Doc")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = server.get("port", 8023)

        # ── Database config (from YAML) ──────────────────────
        db_config = data.get("database", {}) or {}
        self.database_path = db_config.get("path", "database/doc.db")

        # ── Chester config ────────────────────────────────────
        chester_config = data.get("chester", {}) or {}
        self.chester_dev_url = chester_config.get("dev_url", "http://localhost:8008")
        self.chester_prod_url = chester_config.get("prod_url", "https://chester.watsonblinds.com.au")

        # ── Checkup config ────────────────────────────────────
        checkup_config = data.get("checkup", {}) or {}
        self.checkup_timeout = checkup_config.get("timeout", 5)
        self.checkup_batch_size = checkup_config.get("batch_size", 10)

        # ── Test runner config ────────────────────────────────
        tests_config = data.get("tests", {}) or {}
        self.tests_project_root = tests_config.get("project_root", "/home/user/bot-team")
        self.tests_default_timeout = tests_config.get("default_timeout", 300)
        self.tests_max_timeout = tests_config.get("max_timeout", 600)

        # ── Secrets / env-specific settings ────────────────────
        self.flask_secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # ── Admin emails (env override or config.yaml) ────────
        admin_cfg = data.get("admin", {}) or {}
        admin_emails_env = os.environ.get("DOC_ADMIN_EMAILS", "")
        if admin_emails_env:
            self.admin_emails = [e.strip() for e in admin_emails_env.split(",") if e.strip()]
        else:
            self.admin_emails = admin_cfg.get("emails", []) or []

        # ── Load shared organization config for allowed domains ──
        shared_config_path = self.base_dir.parent / "shared" / "config" / "organization.yaml"
        with open(shared_config_path, "r") as f:
            shared_data = yaml.safe_load(f) or {}

        organization = shared_data.get("organization", {}) or {}
        self.allowed_domains = organization.get("domains", [])

    def get_chester_url(self) -> str:
        """Get Chester URL based on environment"""
        if os.environ.get("CHESTER_URL"):
            return os.environ.get("CHESTER_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.chester_dev_url
        return self.chester_prod_url

    def is_dev_mode(self) -> bool:
        """Check if running in development mode"""
        return os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    @property
    def auth(self):
        """Auth config for GatewayAuth."""
        return {
            'mode': 'admin',
            'allowed_domains': self.allowed_domains,
            'admin_emails': self.admin_emails,
        }


config = Config()
