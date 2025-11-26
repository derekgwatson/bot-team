"""Add sleep/wake tracking fields to devices and heartbeats tables."""


def up(conn):
    """Add columns for tracking device sleep/wake events."""
    cursor = conn.cursor()

    # Add columns to devices table for last wake event
    cursor.execute('''
        ALTER TABLE devices ADD COLUMN last_wake_at DATETIME
    ''')
    cursor.execute('''
        ALTER TABLE devices ADD COLUMN last_sleep_duration_seconds INTEGER
    ''')

    # Add columns to heartbeats table for wake event data
    cursor.execute('''
        ALTER TABLE heartbeats ADD COLUMN is_wake_event INTEGER DEFAULT 0
    ''')
    cursor.execute('''
        ALTER TABLE heartbeats ADD COLUMN sleep_duration_seconds INTEGER
    ''')
    cursor.execute('''
        ALTER TABLE heartbeats ADD COLUMN network_ok_on_wake INTEGER
    ''')


def down(conn):
    """Remove sleep/wake tracking columns.

    Note: SQLite doesn't support DROP COLUMN in older versions,
    so we'd need to recreate the tables. For simplicity, we leave
    this as a no-op and the columns will remain.
    """
    pass
