"""Initial database schema for Mavis's Unleashed integration."""


def up(conn):
    """Create Unleashed data tables."""
    cursor = conn.cursor()

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unleashed_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL UNIQUE,
            product_description TEXT,
            product_group TEXT,
            product_sub_group TEXT,
            default_sell_price REAL,
            sell_price_tier_9 REAL,
            unit_of_measure TEXT,
            width REAL,
            is_sellable INTEGER DEFAULT 1,
            is_obsolete INTEGER DEFAULT 0,
            raw_payload TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Sync metadata table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT NOT NULL,
            status TEXT NOT NULL,
            records_processed INTEGER DEFAULT 0,
            records_created INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            error_message TEXT
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_code ON unleashed_products(product_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_group ON unleashed_products(product_group)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_updated ON unleashed_products(updated_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_type ON sync_metadata(sync_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_started ON sync_metadata(started_at)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS sync_metadata')
    cursor.execute('DROP TABLE IF EXISTS unleashed_products')
