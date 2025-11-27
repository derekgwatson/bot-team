"""
Migration 002: Add pending_changes table for queued user status changes.

This enables batching multiple changes together for efficient processing.
"""


def up(conn):
    """Create the pending_changes table."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            org_key TEXT NOT NULL,
            action TEXT NOT NULL,  -- 'activate' or 'deactivate'
            user_type TEXT NOT NULL,  -- 'employee' or 'customer'
            requested_by TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
            processed_at TIMESTAMP,
            error_message TEXT,
            UNIQUE(email, org_key, status)  -- Prevent duplicate pending changes for same user/org
        )
    ''')

    # Index for efficient queue processing
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_changes_status
        ON pending_changes(status, org_key)
    ''')

    conn.commit()


def down(conn):
    """Drop the pending_changes table."""
    cursor = conn.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_pending_changes_status')
    cursor.execute('DROP TABLE IF EXISTS pending_changes')
    conn.commit()
