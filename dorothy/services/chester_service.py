"""Chester service - queries Chester for bot deployment configurations."""
from typing import Dict, List, Optional

from dorothy.config import config
from shared.http_client import BotHttpClient


class ChesterService:
    """Service for querying Chester's API for bot deployment configurations."""

    def __init__(self, chester_url: Optional[str] = None, timeout: int = 5):
        """
        Initialize Chester service.

        Args:
            chester_url: Base URL for Chester's API. If not provided,
                         uses config.chester_base_url.
        """
        base_url = chester_url or config.chester_base_url
        if not base_url:
            # Fails fast instead of silently making up a URL
            raise RuntimeError(
                "ChesterService could not determine Chester base URL. "
                "Check ports.yaml and Dorothy's config."
            )

        self.chester_url = base_url.rstrip("/")
        self.client = BotHttpClient(self.chester_url, timeout=timeout)
        self.cache: Dict[str, Dict] = {}  # Simple in-memory cache

        response = self.client.get("api/deployment/bots", timeout=5)
        print("Chester /api/deployment/bots ->", response.status_code, response.text[:200])

    def get_bot_config(self, bot_name: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get deployment configuration for a specific bot from Chester.

        Args:
            bot_name: Name of the bot
            use_cache: Whether to use cached config (default True)

        Returns:
            Bot configuration dict or None if not found
        """
        if use_cache and bot_name in self.cache:
            return self.cache[bot_name]

        try:
            response = self.client.get(f"api/deployment/bots/{bot_name}", timeout=5)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                bot_config = data.get("bot")
                if bot_config is not None:
                    self.cache[bot_name] = bot_config
                return bot_config

            return None

        except Exception as e:
            # Includes auth errors, connection issues, etc.
            print(f"Warning: Error querying Chester for {bot_name}: {e}")
            return None

    def get_all_bots(self, use_cache: bool = True) -> List[Dict]:
        """
        Get deployment configurations for all bots from Chester.

        Args:
            use_cache: Whether to use cached configs (default True)

        Returns:
            List of bot configuration dicts
        """
        if use_cache and "__all_bots__" in self.cache:
            return self.cache["__all_bots__"]

        try:
            response = self.client.get("api/deployment/bots", timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                bots = data.get("bots", []) or []
                # Cache the result
                self.cache["__all_bots__"] = bots
                # Also cache individual bots
                for bot in bots:
                    name = bot.get("name")
                    if name:
                        self.cache[name] = bot
                return bots

            return []

        except Exception as e:
            print(f"Warning: Error querying Chester for all bots: {e}")
            return []

    def clear_cache(self) -> None:
        """Clear the bot configuration cache."""
        self.cache = {}

    def is_chester_available(self) -> bool:
        """
        Check if Chester is available and responding.

        Returns:
            True if Chester is healthy, False otherwise
        """
        try:
            response = self.client.get("health", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
