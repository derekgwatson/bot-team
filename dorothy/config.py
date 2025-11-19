"""Configuration loader for Dorothy (Deployment Orchestrator)."""

from pathlib import Path
import yaml
from dotenv import load_dotenv
from shared.config.ports import get_port
from shared.config.env_loader import SHARED_ENV  # noqa: F401

# Load environment variables from .env
load_dotenv()


class Config:
    """Configuration management for Dorothy."""

    BOT_NAME = "dorothy"

    def __init__(self) -> None:
        base_dir = Path(__file__).parent
        config_path = base_dir / "config.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # ── Core info (from YAML) ─────────────────────────────
        self.name: str = data.get("name", "dorothy")
        self.description: str = data.get("description", "")
        self.version: str = data.get("version", "0.1.0")

        # ── Server config (from YAML + env) ──────────────────
        server = data.get("server", {}) or {}
        self.server_host: str = server.get("host", "0.0.0.0")

        # Port ALWAYS comes from ports.yaml
        shared_port = get_port(self.BOT_NAME)
        if shared_port is None:
            raise RuntimeError(
                f"No port found for '{self.BOT_NAME}' in ports.yaml. "
                "Every bot must have a port assignment."
            )

        self.server_port: int = int(shared_port)

        # ── Deployment config (from YAML) ────────────────────
        self.deployment: dict = data.get("deployment", {}) or {}
        self.deployment_timeout: int = self.deployment.get(
            "deployment_timeout",
            600,
        )
        self.verification_checks: list[str] = self.deployment.get(
            "verification_checks",
            [],
        )
        self.default_server: str = self.deployment.get("default_server", "prod")

        # ── Bot metadata (from YAML; optional) ───────────────
        # This is *descriptive only* – actual deployment config lives in Chester.
        self.bots: dict = data.get("bots", {}) or {}

        # ── Services (chester, sally, etc.) ──────────────────
        # Supports env overrides like CHESTER_URL, SALLY_URL.
        raw_services = data.get("services", {}) or {}
        self.services: dict[str, dict] = {}

        for service_name, cfg in raw_services.items():
            cfg = cfg or {}

            # Compute base URL strictly from ports.yaml
            service_port = get_port(service_name)
            if service_port is None:
                raise RuntimeError(
                    f"No port assigned for service '{service_name}' in ports.yaml."
                )

            base_url = f"http://127.0.0.1:{service_port}"
            cfg["base_url"] = base_url

            self.services[service_name] = cfg

    # ─────────────────────────────────────────────────────────
    # Helper methods for services
    # ─────────────────────────────────────────────────────────

    def get_auth_headers(self) -> dict:
        """
        Headers for authenticated calls to other bots (e.g. Chester, Sally)
        using the shared BOT_API_KEY.
        """
        if not self.bot_api_key:
            return {}
        # Replace 'X-Bot-API-Key' with whatever header Chester actually checks
        return {"X-Bot-API-Key": self.bot_api_key}

    def get_service_config(self, name: str) -> dict | None:
        """
        Get the config dict for a named service (e.g. 'chester', 'sally').
        """
        return self.services.get(name)

    def get_service_url(self, name: str, default: str | None = None) -> str | None:
        """
        Get the base URL for a service, with optional default.
        """
        svc = self.get_service_config(name)
        if not svc:
            return default
        return svc.get("base_url") or default

    @property
    def chester_url(self) -> str | None:
        """
        Backwards-compatible alias for existing code that expects config.sally_url.
        """
        return self.chester_base_url

    @property
    def chester_base_url(self) -> str | None:
        """
        Base URL for Chester (may be overridden by CHESTER_URL env var).
        """
        return self.get_service_url("chester")

    @property
    def chester_deployment_bots_url(self) -> str | None:
        """
        Full URL for Chester's deployment bots endpoint, combining base_url
        with the deployment_bots_path from the YAML.
        """
        svc = self.get_service_config("chester") or {}
        base_url = svc.get("base_url")
        path = svc.get("deployment_bots_path", "/api/deployment/bots")

        if not base_url:
            return None

        return f"{base_url.rstrip('/')}{path}"

    @property
    def chester_manage_ui_url(self) -> str | None:
        """
        Full URL for Chester's manage UI, combining base_url with manage_ui_path.
        """
        svc = self.get_service_config("chester") or {}
        base_url = svc.get("base_url")
        path = svc.get("manage_ui_path", "/manage")

        if not base_url:
            return None

        return f"{base_url.rstrip('/')}{path}"

    @property
    def sally_url(self) -> str | None:
        """
        Backwards-compatible alias for existing code that expects config.sally_url.
        """
        return self.sally_base_url

    @property
    def sally_base_url(self) -> str | None:
        """
        Convenience property for Sally's base URL (internal-only service).
        """
        return self.get_service_url("sally")

    # ─────────────────────────────────────────────────────────
    # Helper methods for bot metadata
    # ─────────────────────────────────────────────────────────

    def get_bot_description(self, bot_name: str) -> str | None:
        """
        Get the human-readable description for a bot from the bots section.
        """
        bot_cfg = self.bots.get(bot_name) or {}
        return bot_cfg.get("description")

    def get_all_bot_names(self) -> list[str]:
        """
        List of bot names defined in the bots section.
        """
        return list(self.bots.keys())

    def get_all_bots(self) -> list[str]:
        """
        Backwards-compatible alias for existing code that expects config.get_all_bots().
        """
        return self.get_all_bot_names()


# Global config instance
config = Config()
