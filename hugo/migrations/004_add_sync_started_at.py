"""Add started_at column to sync_log for tracking running syncs."""


def up(conn):
    """Add started_at column."""
    cursor = conn.cursor()
    cursor.execute('''
        ALTER TABLE sync_log ADD COLUMN started_at TIMESTAMP
    ''')


def down(conn):
    """SQLite doesn't support DROP COLUMN easily."""
    pass
