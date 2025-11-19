import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

from shared.config.loader import load_shared_yaml
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Iris"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # ── Bot-local config.yaml ─────────────────────────────
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Shared organization config ────────────────────────
        org_cfg = load_shared_yaml("organization").get("organization", {}) or {}
        self.organization_name = org_cfg.get("name", "Watson Blinds Group")
        self.organization_domains = org_cfg.get("domains", []) or []
        self.organization_primary_domain = org_cfg.get("primary_domain", "")

        # ── Bot info (from YAML) ──────────────────────────────
        self.name = data.get("name", "iris")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config ─────────────────────────────────────
        server = data.get("server", {}) or {}
        # Host still comes from Iris's own config
        self.server_host = server.get("host", "0.0.0.0")
        # Port from shared ports.yaml, with local default fallback
        self.server_port = get_port("iris", default=None)
        if self.server_port is None:
            raise RuntimeError("Iris has no port assigned in ports.yaml")

        # ── Google Workspace config ───────────────────────────
        gw = data.get("google_workspace", {}) or {}

        # credentials file path (relative to Iris's directory if not absolute)
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
        self.bots = data.get("bots", {}) or {}

        # ── Common shared bits (from .env) ────────────────────
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        self.bot_api_key = os.environ.get("BOT_API_KEY")


config = Config()
