"""Initial database schema for Quinn's external staff management."""


def up(conn):
    """Create external staff tables."""
    cursor = conn.cursor()

    # External staff table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            role TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by TEXT,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    ''')

    # Pending access requests
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_requests (
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

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON external_staff(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON external_staff(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_email ON pending_requests(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_request_status ON pending_requests(status)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS pending_requests')
    cursor.execute('DROP TABLE IF EXISTS external_staff')
