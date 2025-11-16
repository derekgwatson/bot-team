"""Add public_facing flag to bots table."""


def up(conn):
    """Add public_facing column and set it for public bots."""
    cursor = conn.cursor()

    # Add public_facing column (default 0 = not public)
    cursor.execute('''
        ALTER TABLE bots
        ADD COLUMN public_facing BOOLEAN DEFAULT 0
    ''')

    # Mark public-facing bots
    # Pam - phone directory presenter (for all staff)
    # Quinn - external staff access requests (for all staff)
    # Peter - phone directory admin (for managers who update phone list)
    public_bots = ['pam', 'quinn', 'peter']

    for bot_name in public_bots:
        cursor.execute('''
            UPDATE bots
            SET public_facing = 1
            WHERE name = ?
        ''', (bot_name,))

    conn.commit()


def down(conn):
    """Remove public_facing column."""
    cursor = conn.cursor()

    # SQLite doesn't support DROP COLUMN directly in older versions
    # So we need to recreate the table without the column
    cursor.execute('''
        CREATE TABLE bots_backup AS
        SELECT id, name, description, port, repo, path, service, domain,
               nginx_config_name, workers, skip_nginx, created_at, updated_at
        FROM bots
    ''')

    cursor.execute('DROP TABLE bots')

    cursor.execute('ALTER TABLE bots_backup RENAME TO bots')

    conn.commit()
