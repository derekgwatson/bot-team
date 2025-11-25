"""Initial database schema for Monica's ChromeOS monitoring."""


def up(conn):
    """Create monitoring tables."""
    cursor = conn.cursor()

    # Stores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_code TEXT UNIQUE NOT NULL,
            display_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Devices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            device_label TEXT NOT NULL,
            agent_token TEXT UNIQUE NOT NULL,
            last_heartbeat_at DATETIME,
            last_status TEXT DEFAULT 'offline',
            last_public_ip TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE,
            UNIQUE(store_id, device_label)
        )
    ''')

    # Heartbeats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            public_ip TEXT,
            user_agent TEXT,
            latency_ms REAL,
            download_mbps REAL,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        )
    ''')

    # Registration codes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            store_code TEXT NOT NULL,
            device_label TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            used_at DATETIME,
            used_by_device_id INTEGER,
            expires_at DATETIME,
            FOREIGN KEY (used_by_device_id) REFERENCES devices(id) ON DELETE SET NULL
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_store_id ON devices(store_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_agent_token ON devices(agent_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_heartbeats_device_id ON heartbeats(device_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp ON heartbeats(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_heartbeats_device_timestamp ON heartbeats(device_id, timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_registration_codes_code ON registration_codes(code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_registration_codes_used_at ON registration_codes(used_at)')

    # Trigger for updated_at
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_device_timestamp
        AFTER UPDATE ON devices
        FOR EACH ROW
        BEGIN
            UPDATE devices SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TRIGGER IF EXISTS update_device_timestamp')
    cursor.execute('DROP TABLE IF EXISTS heartbeats')
    cursor.execute('DROP TABLE IF EXISTS registration_codes')
    cursor.execute('DROP TABLE IF EXISTS devices')
    cursor.execute('DROP TABLE IF EXISTS stores')
