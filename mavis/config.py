import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Mavis"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "mavis")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("mavis")

        # ── Database config (from YAML) ──────────────────────
        db_config = data.get("database", {}) or {}
        self.database_path = db_config.get("path", "database/mavis.db")

        # ── Unleashed API config ──────────────────────────────
        unleashed_config = data.get("unleashed", {}) or {}
        self.unleashed_base_url = os.environ.get(
            "UNLEASHED_BASE_URL",
            unleashed_config.get("base_url", "https://api.unleashedsoftware.com")
        )
        self.unleashed_page_size = unleashed_config.get("page_size", 200)
        self.unleashed_timeout = unleashed_config.get("timeout", 30)

        # Unleashed credentials (from environment only - never in config)
        self.unleashed_api_id = os.environ.get("UNLEASHED_API_ID")
        self.unleashed_api_key = os.environ.get("UNLEASHED_API_KEY")

        # Validate required credentials
        self._validate_unleashed_credentials()

        # ── Sync config (from YAML) ──────────────────────────
        sync_config = data.get("sync", {}) or {}
        self.sync_product_fields = sync_config.get("product_fields", [])

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key
        self.flask_secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

    def _validate_unleashed_credentials(self):
        """Validate that required Unleashed credentials are present"""
        missing = []
        if not self.unleashed_api_id:
            missing.append("UNLEASHED_API_ID")
        if not self.unleashed_api_key:
            missing.append("UNLEASHED_API_KEY")

        if missing and not os.environ.get("SKIP_ENV_VALIDATION"):
            raise RuntimeError(
                f"Missing required Unleashed credentials: {', '.join(missing)}. "
                "Set these environment variables before starting Mavis."
            )


config = Config()
