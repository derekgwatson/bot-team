"""
Migration 003: Add auth_health table to track Buz auth status.

Stores the last successful auth check for each org so we can warn
when auth needs renewal.
"""


def up(conn):
    """Create the auth_health table."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auth_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL UNIQUE,
            last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,  -- 'healthy', 'failed', 'expired'
            error_message TEXT,
            last_healthy TIMESTAMP,
            consecutive_failures INTEGER DEFAULT 0
        )
    ''')
    conn.commit()


def down(conn):
    """Drop the auth_health table."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS auth_health')
    conn.commit()
