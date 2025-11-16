"""Chester service - queries Chester for bot deployment configurations."""
import requests
from typing import Dict, List, Optional


class ChesterService:
    """Service for querying Chester's API for bot deployment configurations."""

    def __init__(self, chester_url: str = 'http://localhost:8008'):
        """
        Initialize Chester service.

        Args:
            chester_url: Base URL for Chester's API
        """
        self.chester_url = chester_url
        self.cache = {}  # Simple in-memory cache

    def get_bot_config(self, bot_name: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get deployment configuration for a specific bot from Chester.

        Args:
            bot_name: Name of the bot
            use_cache: Whether to use cached config (default True)

        Returns:
            Bot configuration dict or None if not found
        """
        # Check cache first
        if use_cache and bot_name in self.cache:
            return self.cache[bot_name]

        try:
            response = requests.get(
                f"{self.chester_url}/api/deployment/bots/{bot_name}",
                timeout=5
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            if data.get('success'):
                bot_config = data.get('bot')
                # Cache the result
                self.cache[bot_name] = bot_config
                return bot_config

            return None

        except requests.exceptions.ConnectionError:
            print(f"Warning: Could not connect to Chester at {self.chester_url}")
            return None
        except requests.exceptions.Timeout:
            print(f"Warning: Chester request timed out")
            return None
        except Exception as e:
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
        # Check if we have all bots cached
        if use_cache and '__all_bots__' in self.cache:
            return self.cache['__all_bots__']

        try:
            response = requests.get(
                f"{self.chester_url}/api/deployment/bots",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success'):
                bots = data.get('bots', [])
                # Cache the result
                self.cache['__all_bots__'] = bots
                # Also cache individual bots
                for bot in bots:
                    self.cache[bot['name']] = bot
                return bots

            return []

        except Exception as e:
            print(f"Warning: Error querying Chester for all bots: {e}")
            return []

    def clear_cache(self):
        """Clear the bot configuration cache."""
        self.cache = {}

    def is_chester_available(self) -> bool:
        """
        Check if Chester is available and responding.

        Returns:
            True if Chester is healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.chester_url}/health",
                timeout=3
            )
            return response.status_code == 200
        except:
            return False
