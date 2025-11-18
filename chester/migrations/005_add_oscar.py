"""Add Oscar bot to the bot team."""

import sys
from pathlib import Path

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.migrations.bot_helper import prepare_bot_for_migration


def up(conn):
    """Insert Oscar bot data."""
    cursor = conn.cursor()

    # Get deployment defaults for template substitution
    cursor.execute('SELECT * FROM deployment_defaults WHERE id = 1')
    defaults = cursor.fetchone()

    # Read Oscar's configuration from config files (single source of truth)
    bot_data = prepare_bot_for_migration('oscar')
    name = bot_data['name']
    description = bot_data['description']
    port = bot_data['port']
    skip_nginx = 1 if bot_data['skip_nginx'] else 0

    cursor.execute('''
        INSERT OR IGNORE INTO bots
        (name, description, port, repo, path, service, domain, nginx_config_name, workers, skip_nginx)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        name,
        description,
        port,
        defaults[1],  # repo
        defaults[2].format(bot_name=name),  # path_template
        defaults[3].format(bot_name=name),  # service_template
        defaults[4].format(bot_name=name),  # domain_template
        defaults[5].format(bot_name=name),  # nginx_config_template
        defaults[6],  # workers
        skip_nginx
    ))


def down(conn):
    """Remove Oscar bot data."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bots WHERE name = 'oscar'")
