"""
Migration helper for adding bots to Chester's database.

This module eliminates duplication by reading bot configuration from
the bot's own config.yaml file and the shared ports.yaml.
"""

import yaml
from pathlib import Path
from typing import Dict, Optional


def get_bot_config_from_yaml(bot_name: str) -> Optional[Dict]:
    """
    Read bot configuration from the bot's config.yaml file.

    Args:
        bot_name: Name of the bot (e.g., 'oscar', 'fred')

    Returns:
        Dictionary with bot config data or None if not found
    """
    # Get the bot-team root directory
    bot_team_root = Path(__file__).parent.parent.parent
    bot_config_path = bot_team_root / bot_name / 'config.yaml'

    if not bot_config_path.exists():
        return None

    with open(bot_config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config


def get_bot_port(bot_name: str) -> Optional[int]:
    """
    Get bot port from shared ports.yaml.

    Args:
        bot_name: Name of the bot

    Returns:
        Port number or None if not found
    """
    ports_config_path = Path(__file__).parent.parent / 'config' / 'ports.yaml'

    if not ports_config_path.exists():
        return None

    with open(ports_config_path, 'r') as f:
        config = yaml.safe_load(f)

    ports = config.get('ports', {})
    return ports.get(bot_name.lower())


def prepare_bot_for_migration(bot_name: str) -> Dict:
    """
    Prepare bot data for migration by reading from config files.

    This is the main function to use in migrations. It reads from:
    - {bot_name}/config.yaml for description
    - shared/config/ports.yaml for port

    Args:
        bot_name: Name of the bot (e.g., 'oscar')

    Returns:
        Dictionary with name, description, port, skip_nginx

    Raises:
        ValueError: If bot config or port cannot be found
    """
    # Read bot's config.yaml
    bot_config = get_bot_config_from_yaml(bot_name)
    if not bot_config:
        raise ValueError(f"Could not find config.yaml for bot '{bot_name}'")

    # Get port from shared config
    port = get_bot_port(bot_name)
    if port is None:
        raise ValueError(f"Could not find port for bot '{bot_name}' in shared/config/ports.yaml")

    # Extract description
    description = bot_config.get('description', '')
    if not description:
        raise ValueError(f"Bot '{bot_name}' missing 'description' in config.yaml")

    # Determine if nginx should be skipped (internal-only bots like Sally)
    # Default to False (use nginx) unless explicitly set
    skip_nginx = bot_config.get('skip_nginx', False)

    return {
        'name': bot_name,
        'description': description,
        'port': port,
        'skip_nginx': skip_nginx
    }
