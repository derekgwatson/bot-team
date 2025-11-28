"""
Migration: Add progress tracking to sync_log table.

Adds columns to track sync progress percentage and current stage message.
"""


def up(conn):
    """Add progress columns to sync_log."""
    conn.execute('''
        ALTER TABLE sync_log ADD COLUMN progress INTEGER DEFAULT 0
    ''')
    conn.execute('''
        ALTER TABLE sync_log ADD COLUMN progress_message TEXT DEFAULT ''
    ''')


def down(conn):
    """Remove progress columns (SQLite doesn't support DROP COLUMN easily)."""
    # SQLite < 3.35 doesn't support DROP COLUMN
    # For rollback, we'd need to recreate the table
    pass
