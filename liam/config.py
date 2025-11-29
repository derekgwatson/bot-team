"""Configuration loader for Liam."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from shared.config.env_loader import SHARED_ENV  # noqa: F401
from shared.config.ports import get_port

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for Liam."""

    def __init__(self):
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Bot info
        self.name = data.get("name", "Liam")
        self.description = data.get("description", "")
        self.version = data.get("version", "1.0.0")
        self.personality = data.get("personality", "")

        # Authentication config
        self.auth = data.get("auth", {}) or {}

        # Server config
        server_cfg = data.get("server", {}) or {}
        self.server_host = server_cfg.get("host", "0.0.0.0")
        self.server_port = get_port("liam")

        # OData org configuration
        self._odata_orgs = data.get("odata_orgs", {}) or {}

        # Verification settings
        verification_cfg = data.get("verification", {}) or {}
        self.skip_days = verification_cfg.get("skip_days", [5, 6])  # Sat, Sun
        self.request_timeout = verification_cfg.get("request_timeout", 30)

        # Alert settings
        alerts_cfg = data.get("alerts", {}) or {}
        self.zendesk_group = alerts_cfg.get("zendesk_group", "IT Support")
        self.subject_template = alerts_cfg.get(
            "subject_template",
            "Buz OData Alert: No leads recorded for {org_name} on {date}"
        )

        # Flask secret key (env)
        self.secret_key = os.environ.get(
            "FLASK_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )

        # Bot API key for bot-to-bot communication (env)
        self.bot_api_key = os.environ.get("BOT_API_KEY")

        # Load OData credentials from environment
        self._load_odata_credentials()

    def _load_odata_credentials(self):
        """Load OData credentials from environment variables."""
        self.odata_orgs = {}
        self.missing_credentials = {}

        for org_key, org_config in self._odata_orgs.items():
            code = org_config.get("code", "").upper()
            username_var = f"BUZ_ODATA_{code}_USERNAME"
            password_var = f"BUZ_ODATA_{code}_PASSWORD"

            username = os.environ.get(username_var)
            password = os.environ.get(password_var)

            if username and password:
                self.odata_orgs[org_key] = {
                    "code": code,
                    "display_name": org_config.get("display_name", org_key.title()),
                    "is_primary": org_config.get("is_primary", False),
                    "username": username,
                    "password": password,
                    "url": f"https://api.buzmanager.com/reports/{code}",
                }
            else:
                self.missing_credentials[org_key] = {
                    "code": code,
                    "display_name": org_config.get("display_name", org_key.title()),
                    "missing": [
                        var for var, val in [
                            (username_var, username),
                            (password_var, password)
                        ] if not val
                    ]
                }

    def get_org_config(self, org_key: str) -> dict:
        """
        Get configuration for a specific organization.

        Args:
            org_key: Name of the organization

        Returns:
            dict: Organization config with credentials

        Raises:
            ValueError: If org_key is not configured
        """
        if org_key not in self.odata_orgs:
            if org_key in self.missing_credentials:
                missing = self.missing_credentials[org_key]["missing"]
                raise ValueError(
                    f"Organization '{org_key}' is missing credentials: {', '.join(missing)}"
                )
            available = ', '.join(self.odata_orgs.keys())
            raise ValueError(
                f"Unknown organization '{org_key}'. "
                f"Available organizations: {available}"
            )
        return self.odata_orgs[org_key]

    @property
    def available_orgs(self) -> list:
        """Get list of available org names with credentials configured."""
        return list(self.odata_orgs.keys())

    @property
    def primary_orgs(self) -> list:
        """Get list of primary orgs (where zero leads is definitely a problem)."""
        return [
            org_key for org_key, org_config in self.odata_orgs.items()
            if org_config.get("is_primary", False)
        ]

    @property
    def is_fully_configured(self) -> bool:
        """Check if all organizations have credentials configured."""
        return len(self.missing_credentials) == 0

    def print_setup_instructions(self):
        """Print setup instructions for missing credentials."""
        if not self.missing_credentials:
            return

        print("\n Warning: Some organizations are missing OData credentials")
        for org_key, info in self.missing_credentials.items():
            print(f"  - {info['display_name']} ({info['code']}): {', '.join(info['missing'])}")
        print("\n Add these to /bot-team/.env:")
        for org_key, info in self.missing_credentials.items():
            code = info["code"]
            print(f"    BUZ_ODATA_{code}_USERNAME=your-username")
            print(f"    BUZ_ODATA_{code}_PASSWORD=your-password")
        print()


# Global config instance
config = Config()
