import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Scout"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        # Load main config.yaml
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # ── Bot info (from YAML) ───────────────────────────────
        self.name = data.get("name", "scout")
        self.description = data.get("description", "")
        self.version = data.get("version", "0.0.0")

        # ── Server config (from YAML) ─────────────────────────
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = server.get("port", 8019)

        # ── Database config (from YAML) ──────────────────────
        db_config = data.get("database", {}) or {}
        self.database_path = db_config.get("path", "database/scout.db")

        # ── Bot URLs ────────────────────────────────────────────
        bots_config = data.get("bots", {}) or {}

        # Mavis
        mavis_config = bots_config.get("mavis", {}) or {}
        self.mavis_dev_url = mavis_config.get("dev_url", "http://localhost:8017")
        self.mavis_prod_url = mavis_config.get("prod_url", "https://mavis.watsonblinds.com.au")

        # Fiona
        fiona_config = bots_config.get("fiona", {}) or {}
        self.fiona_dev_url = fiona_config.get("dev_url", "http://localhost:8018")
        self.fiona_prod_url = fiona_config.get("prod_url", "https://fiona.watsonblinds.com.au")

        # Sadie
        sadie_config = bots_config.get("sadie", {}) or {}
        self.sadie_dev_url = sadie_config.get("dev_url", "http://localhost:8010")
        self.sadie_prod_url = sadie_config.get("prod_url", "https://sadie.watsonblinds.com.au")

        # Peter
        peter_config = bots_config.get("peter", {}) or {}
        self.peter_dev_url = peter_config.get("dev_url", "http://localhost:8002")
        self.peter_prod_url = peter_config.get("prod_url", "https://peter.watsonblinds.com.au")

        # Fred
        fred_config = bots_config.get("fred", {}) or {}
        self.fred_dev_url = fred_config.get("dev_url", "http://localhost:8012")
        self.fred_prod_url = fred_config.get("prod_url", "https://fred.watsonblinds.com.au")

        # ── Check configuration ─────────────────────────────────
        checks_config = data.get("checks", {}) or {}

        self.check_missing_descriptions = checks_config.get("missing_descriptions", {})
        self.check_obsolete_fabrics = checks_config.get("obsolete_fabrics", {})
        self.check_incomplete_descriptions = checks_config.get("incomplete_descriptions", {})
        self.check_sync_health = checks_config.get("sync_health", {})
        self.check_user_sync = checks_config.get("user_sync", {})

        # ── Secrets / env-specific settings ────────────────────

        # Flask secret key
        self.flask_secret_key = (
            os.environ.get("FLASK_SECRET_KEY")
            or os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
        )

        # Shared bot API key for bot-to-bot communication
        self.bot_api_key = os.environ.get("BOT_API_KEY")

    def get_mavis_url(self) -> str:
        """Get Mavis URL based on environment"""
        if os.environ.get("MAVIS_URL"):
            return os.environ.get("MAVIS_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.mavis_dev_url
        return self.mavis_prod_url

    def get_fiona_url(self) -> str:
        """Get Fiona URL based on environment"""
        if os.environ.get("FIONA_URL"):
            return os.environ.get("FIONA_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.fiona_dev_url
        return self.fiona_prod_url

    def get_sadie_url(self) -> str:
        """Get Sadie URL based on environment"""
        if os.environ.get("SADIE_URL"):
            return os.environ.get("SADIE_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.sadie_dev_url
        return self.sadie_prod_url

    def get_peter_url(self) -> str:
        """Get Peter URL based on environment"""
        if os.environ.get("PETER_URL"):
            return os.environ.get("PETER_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.peter_dev_url
        return self.peter_prod_url

    def get_fred_url(self) -> str:
        """Get Fred URL based on environment"""
        if os.environ.get("FRED_URL"):
            return os.environ.get("FRED_URL")
        if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
            return self.fred_dev_url
        return self.fred_prod_url


config = Config()
