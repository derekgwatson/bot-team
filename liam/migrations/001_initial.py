"""
Initial migration for Liam - creates verification_log table.
"""


def up(conn):
    """Create the verification_log table."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS verification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            verified_date TEXT NOT NULL,
            lead_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            message TEXT DEFAULT '',
            ticket_id INTEGER DEFAULT NULL,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Index for querying by org
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_verification_org
        ON verification_log(org_key)
    ''')

    # Index for querying by date
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_verification_date
        ON verification_log(verified_date)
    ''')

    # Index for querying by status
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_verification_status
        ON verification_log(status)
    ''')


def down(conn):
    """Drop the verification_log table."""
    conn.execute('DROP TABLE IF EXISTS verification_log')
