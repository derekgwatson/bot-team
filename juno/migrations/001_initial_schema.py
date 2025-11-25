"""Initial database schema for Juno's customer tracking."""


def up(conn):
    """Create tracking tables."""
    cursor = conn.cursor()

    # Tracking links table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            journey_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            destination_address TEXT,
            destination_lat REAL,
            destination_lng REAL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            first_viewed_at DATETIME,
            view_count INTEGER DEFAULT 0,
            arrived_at DATETIME,
            completed_at DATETIME
        )
    ''')

    # Tracking events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_link_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tracking_link_id) REFERENCES tracking_links(id) ON DELETE CASCADE
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_links_code ON tracking_links(code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_links_journey_id ON tracking_links(journey_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_links_staff_id ON tracking_links(staff_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_links_status ON tracking_links(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_links_expires_at ON tracking_links(expires_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_link_id ON tracking_events(tracking_link_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON tracking_events(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_created_at ON tracking_events(created_at)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS tracking_events')
    cursor.execute('DROP TABLE IF EXISTS tracking_links')
