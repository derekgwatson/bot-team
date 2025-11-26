import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration loader for Nigel"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        config_file = self.base_dir / "config.yaml"

        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Bot info (from YAML)
        self.name = data.get("name", "Nigel")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.emoji = data.get("emoji", "🔍")

        # Server config (from YAML)
        server = data.get("server", {}) or {}
        self.server_host = server.get("host", "0.0.0.0")
        self.server_port = get_port("nigel")

        # Database config
        db = data.get("database", {}) or {}
        db_path = db.get("path", "database/nigel.db")
        if not os.path.isabs(db_path):
            db_path = self.base_dir / db_path
        self.db_path = str(db_path)

        # Bots registry (from YAML)
        self.bots = data.get("bots", {}) or {}

        # Banji URL (can be overridden by env var)
        banji_config = self.bots.get("banji", {}) or {}
        self.banji_url = os.environ.get(
            "BANJI_URL",
            banji_config.get("base_url", "http://localhost:8014")
        )

        # Common shared bits (from .env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        self.bot_api_key = os.environ.get("BOT_API_KEY")


config = Config()
