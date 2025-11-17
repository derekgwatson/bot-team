"""
Add access request workflow for external staff.

Allows people without company Google accounts to request access,
which can be approved by admins and automatically creates a staff entry.
"""

def up(conn):
    """Create access_requests table"""
    cursor = conn.cursor()

    # Access requests table for external staff
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'denied')),
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by TEXT,
            reviewed_date TIMESTAMP,
            notes TEXT
        )
    ''')

    # Indexes for access requests
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_email ON access_requests(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_status ON access_requests(status)')

    conn.commit()


def down(conn):
    """Drop access_requests table"""
    cursor = conn.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_request_email')
    cursor.execute('DROP INDEX IF EXISTS idx_request_status')
    cursor.execute('DROP TABLE IF EXISTS access_requests')
    conn.commit()
