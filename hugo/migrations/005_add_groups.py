"""
Migration 005: Add groups table for caching available user groups per org.

Groups are synced periodically from Buz rather than loaded dynamically
on each user edit, improving performance and UX.
"""


def up(conn):
    """Create the groups table."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_name TEXT NOT NULL,
            group_type TEXT,  -- e.g., 'Administrator', 'Customer User', 'Installer User'
            user_count INTEGER DEFAULT 0,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, group_name)
        )
    ''')

    # Index for efficient lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_groups_org
        ON groups(org_key)
    ''')

    conn.commit()


def down(conn):
    """Drop the groups table."""
    cursor = conn.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_groups_org')
    cursor.execute('DROP TABLE IF EXISTS groups')
    conn.commit()
