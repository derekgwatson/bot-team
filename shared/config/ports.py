"""
Shared port configuration for bot-team.

This module provides a single source of truth for all bot port assignments.
Ports are read from chester/config.yaml's bot_team section.
"""

import yaml
from pathlib import Path

# Load chester's config.yaml as the single source of truth for bot ports
_CHESTER_CONFIG_PATH = Path(__file__).parent.parent.parent / "chester" / "config.yaml"


def _load_ports() -> dict[str, int]:
    """Load port assignments from chester's config.yaml."""
    try:
        with open(_CHESTER_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}

        bot_team = config.get("bot_team", {})
        ports = {}
        for bot_name, bot_info in bot_team.items():
            if isinstance(bot_info, dict) and "port" in bot_info:
                ports[bot_name] = bot_info["port"]
        return ports
    except Exception as e:
        print(f"Warning: Could not load ports from chester/config.yaml: {e}")
        return {}


_PORTS = _load_ports()


def get_port(bot_name: str) -> int:
    """
    Get the assigned port for a bot from chester/config.yaml.

    Raises:
        RuntimeError: If the bot is not configured in chester/config.yaml

    Example:
        port = get_port("olive")
    """
    if bot_name not in _PORTS:
        raise RuntimeError(
            f"Port not configured for '{bot_name}'. "
            f"Add it to chester/config.yaml under bot_team.{bot_name}.port"
        )
    return _PORTS[bot_name]


def get_all_ports() -> dict[str, int]:
    """
    Get all bot port assignments.

    Returns:
        Dict mapping bot names to their assigned ports.
    """
    return _PORTS.copy()
