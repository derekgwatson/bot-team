"""
Shared port configuration for bot-team.

This module provides a single source of truth for all bot port assignments.
"""

import os
import yaml
from pathlib import Path


def get_ports_config():
    """Load ports configuration from shared config."""
    config_path = Path(__file__).parent / 'ports.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config.get('ports', {})


def get_port(bot_name):
    """
    Get the assigned port for a specific bot.

    Args:
        bot_name: Name of the bot (e.g., 'peter', 'quinn')

    Returns:
        Port number (int) or None if bot not found
    """
    ports = get_ports_config()
    return ports.get(bot_name.lower())


def get_all_ports():
    """Get all bot port assignments as a dictionary."""
    return get_ports_config()
