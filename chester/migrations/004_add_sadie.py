"""Add Sadie bot to the bot team."""


def up(conn):
    """Insert Sadie bot data."""
    cursor = conn.cursor()

    # Get deployment defaults for template substitution
    cursor.execute('SELECT * FROM deployment_defaults WHERE id = 1')
    defaults = cursor.fetchone()

    # Add Sadie
    name = 'sadie'
    description = 'Zendesk Ticket Information'
    port = 8010
    skip_nginx = 0

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
    """Remove Sadie bot data."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bots WHERE name = 'sadie'")
