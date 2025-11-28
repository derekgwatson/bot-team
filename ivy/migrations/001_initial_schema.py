"""
Initial database schema for Ivy's Buz inventory and pricing cache.

Creates tables for caching inventory items, pricing coefficients,
and tracking sync operations.
"""


def up(conn):
    """Create initial schema."""
    cursor = conn.cursor()

    # Inventory groups table - stores group codes/names from Buz
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_code TEXT NOT NULL,
            group_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            item_count INTEGER DEFAULT 0,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, group_code)
        )
    ''')

    # Inventory items table - stores individual items from Buz export
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_code TEXT NOT NULL,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            description TEXT DEFAULT '',
            unit_of_measure TEXT DEFAULT '',
            is_active BOOLEAN DEFAULT 1,
            supplier_code TEXT DEFAULT '',
            supplier_name TEXT DEFAULT '',
            cost_price REAL DEFAULT 0,
            sell_price REAL DEFAULT 0,
            min_qty REAL DEFAULT 0,
            max_qty REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            extra_data TEXT DEFAULT '{}',
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, group_code, item_code)
        )
    ''')

    # Pricing groups table - stores pricing group codes/names from Buz
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pricing_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_code TEXT NOT NULL,
            group_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            coefficient_count INTEGER DEFAULT 0,
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, group_code)
        )
    ''')

    # Pricing coefficients table - stores pricing data from Buz export
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pricing_coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_code TEXT NOT NULL,
            coefficient_code TEXT NOT NULL,
            coefficient_name TEXT NOT NULL,
            description TEXT DEFAULT '',
            coefficient_type TEXT DEFAULT '',
            is_active BOOLEAN DEFAULT 1,
            base_value REAL DEFAULT 0,
            min_value REAL DEFAULT 0,
            max_value REAL DEFAULT 0,
            unit TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            extra_data TEXT DEFAULT '{}',
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, group_code, coefficient_code)
        )
    ''')

    # Sync log table - tracks sync operations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            sync_type TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            item_count INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            duration_seconds REAL DEFAULT 0
        )
    ''')

    # Activity log for tracking changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            org_key TEXT NOT NULL,
            old_value TEXT DEFAULT '',
            new_value TEXT DEFAULT '',
            performed_by TEXT DEFAULT 'system',
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT 1,
            error_message TEXT DEFAULT ''
        )
    ''')

    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_groups_org ON inventory_groups(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_items_org ON inventory_items(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_items_group ON inventory_items(group_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_items_code ON inventory_items(item_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_items_active ON inventory_items(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_groups_org ON pricing_groups(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_coeff_org ON pricing_coefficients(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_coeff_group ON pricing_coefficients(group_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_coeff_code ON pricing_coefficients(coefficient_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_org ON sync_log(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_type ON sync_log(sync_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_entity ON activity_log(entity_type, entity_id)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS activity_log')
    cursor.execute('DROP TABLE IF EXISTS sync_log')
    cursor.execute('DROP TABLE IF EXISTS pricing_coefficients')
    cursor.execute('DROP TABLE IF EXISTS pricing_groups')
    cursor.execute('DROP TABLE IF EXISTS inventory_items')
    cursor.execute('DROP TABLE IF EXISTS inventory_groups')
