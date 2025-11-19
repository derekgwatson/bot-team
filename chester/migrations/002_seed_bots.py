"""Seed initial bot data."""


def up(conn):
    """Insert initial bot team data."""
    cursor = conn.cursor()

    bots_data = [
        ('fred', 'Google Workspace User Management', 8001, 0),
        ('iris', 'Google Workspace Reporting & Analytics', 8002, 0),
        ('peter', 'Phone Directory Manager', 8003, 0),
        ('sally', 'SSH Command Executor', 8004, 1),  # skip_nginx = True
        ('dorothy', 'Deployment Orchestrator', 8005, 0),
        ('quinn', 'External Staff Access Manager', 8006, 0),
        ('zac', 'Zendesk User Manager', 8007, 0),
        ('chester', 'Bot Team Concierge', 8008, 0),
        ('pam', 'Phone Directory Presenter', 8009, 0),
        ('sadie', 'Zendesk Ticket Manager', 8010, 0),
        ('oscar', 'Staff Onboarding Orchestrator', 8011, 0),
        ('rita', 'User Access Manager', 8013, 0),
    ]

    # Get deployment defaults for template substitution
    cursor.execute('SELECT * FROM deployment_defaults WHERE id = 1')
    defaults = cursor.fetchone()

    for name, description, port, skip_nginx in bots_data:
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
    """Remove all bot data."""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bots')
