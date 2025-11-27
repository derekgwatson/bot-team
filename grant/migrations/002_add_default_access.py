"""Add default_access column to bots table.

This allows configuring per-bot access policy:
- 'domain': Anyone from allowed domains can access (most bots)
- 'explicit': Only users with explicit permissions can access (sensitive bots)
"""


def up(conn):
    """Add default_access column to bots table."""
    cursor = conn.cursor()

    # Add default_access column - defaults to 'explicit' for safety
    # Admins must explicitly enable domain access per bot
    cursor.execute('''
        ALTER TABLE bots ADD COLUMN default_access TEXT DEFAULT 'explicit'
    ''')


def down(conn):
    """Remove default_access column (SQLite limitation - recreate table)."""
    cursor = conn.cursor()

    # SQLite doesn't support DROP COLUMN easily, so we recreate
    cursor.execute('''
        CREATE TABLE bots_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            port INTEGER,
            synced_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        INSERT INTO bots_new (id, name, description, port, synced_at)
        SELECT id, name, description, port, synced_at FROM bots
    ''')
    cursor.execute('DROP TABLE bots')
    cursor.execute('ALTER TABLE bots_new RENAME TO bots')
