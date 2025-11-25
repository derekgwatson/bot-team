"""Initial database schema for Travis's field staff location tracking."""


def up(conn):
    """Create location tracking tables."""
    cursor = conn.cursor()

    # Staff table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            device_token TEXT UNIQUE,
            current_status TEXT DEFAULT 'off_duty',
            last_ping_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Journeys table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journeys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            job_reference TEXT,
            customer_name TEXT,
            customer_address TEXT,
            customer_lat REAL,
            customer_lng REAL,
            status TEXT DEFAULT 'pending',
            started_at DATETIME,
            arrived_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    ''')

    # Location pings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_pings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            journey_id INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            accuracy REAL,
            heading REAL,
            speed REAL,
            altitude REAL,
            battery_level REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE SET NULL
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_email ON staff(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_device_token ON staff(device_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(current_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_journeys_staff_id ON journeys(staff_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_journeys_status ON journeys(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_journeys_job_reference ON journeys(job_reference)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pings_staff_id ON location_pings(staff_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pings_journey_id ON location_pings(journey_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pings_timestamp ON location_pings(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pings_staff_timestamp ON location_pings(staff_id, timestamp DESC)')

    # Trigger for updated_at
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_staff_timestamp
        AFTER UPDATE ON staff
        FOR EACH ROW
        BEGIN
            UPDATE staff SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TRIGGER IF EXISTS update_staff_timestamp')
    cursor.execute('DROP TABLE IF EXISTS location_pings')
    cursor.execute('DROP TABLE IF EXISTS journeys')
    cursor.execute('DROP TABLE IF EXISTS staff')
