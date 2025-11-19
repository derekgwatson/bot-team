"""
Initial database schema for Rita's access request database.

Creates the access_requests table.
"""

def up(conn):
    """Create initial schema"""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            -- what kind of thing they're asking for, e.g. 'allstaff_email', 'zendesk_access'
            request_type TEXT DEFAULT 'allstaff_email',
            -- pending / approved / denied
            status TEXT DEFAULT 'pending',
            -- optional reference back to a staff record in Peter or elsewhere
            staff_ref TEXT DEFAULT '',
            reviewed_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Indexes for common queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_requests_status ON access_requests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_requests_email ON access_requests(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_requests_type ON access_requests(request_type)')


def down(conn):
    """Drop all tables"""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS access_requests')
