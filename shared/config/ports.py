"""
Shared port configuration for bot-team.

This module provides a single source of truth for all bot port assignments.
"""

from .loader import load_shared_yaml

_ports_cfg = load_shared_yaml("ports")
_PORTS = _ports_cfg.get("ports", {}) or {}


def get_port(bot_name: str, default: int | None = None) -> int | None:
    """
    Get the assigned port for a bot from shared/config/ports.yaml.

    Example:
        port = get_port("olive", 8012)
    """
    return _PORTS.get(bot_name, default)

