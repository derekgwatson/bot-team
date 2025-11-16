"""Initial database schema for Chester."""


def up(conn):
    """Create initial tables."""
    cursor = conn.cursor()

    # Bot deployment configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            port INTEGER NOT NULL,
            repo TEXT,
            path TEXT,
            service TEXT,
            domain TEXT,
            nginx_config_name TEXT,
            workers INTEGER DEFAULT 3,
            skip_nginx BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Deployment defaults table (single row)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deployment_defaults (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            repo TEXT NOT NULL,
            path_template TEXT NOT NULL,
            service_template TEXT NOT NULL,
            domain_template TEXT NOT NULL,
            nginx_config_template TEXT NOT NULL,
            workers INTEGER DEFAULT 3
        )
    ''')

    # Insert default deployment config
    cursor.execute('''
        INSERT INTO deployment_defaults
        (id, repo, path_template, service_template, domain_template, nginx_config_template, workers)
        VALUES (1, ?, ?, ?, ?, ?, ?)
    ''', (
        'git@github.com:derekgwatson/bot-team.git',
        '/var/www/bot-team/{bot_name}',
        'gunicorn-bot-team-{bot_name}',
        '{bot_name}.watsonblinds.com.au',
        'bot-team-{bot_name}.conf',
        3
    ))


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS bots')
    cursor.execute('DROP TABLE IF EXISTS deployment_defaults')
