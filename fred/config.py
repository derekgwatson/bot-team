import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Fred"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "fred")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")
        self.emoji = data.get("emoji", "👤")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("fred")

        # ── Google Workspace config ───────────────────────────
        gw = data.get("google_workspace", {}) or {}

        # credentials file path (relative to Fred's directory if not absolute)
        credentials_path = gw.get("credentials_file", "credentials.json")
        if not os.path.isabs(credentials_path):
            credentials_path = self.base_dir / credentials_path
        self.google_credentials_file = str(credentials_path)

        # domain & admin email: env overrides YAML
        self.google_domain = (
            os.environ.get("GOOGLE_WORKSPACE_DOMAIN")
            or gw.get("domain", "example.com")
        )

        self.google_admin_email = (
            os.environ.get("GOOGLE_WORKSPACE_ADMIN_EMAIL")
            or gw.get("admin_email", "")
        )

        # ── Bots registry (from YAML) ─────────────────────────
        # e.g. URLs / metadata for other bots Fred talks to
        self.bots = data.get("bots", {}) or {}

        # ── Common shared bits (from .env) ────────────────────
        # Optional: align with other bots
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        self.bot_api_key = os.environ.get("BOT_API_KEY")


config = Config()
