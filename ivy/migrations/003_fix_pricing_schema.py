"""
Migration: Rebuild pricing_coefficients table to match Buz export structure.

The original schema had generic coefficient fields (base_value, min_value, etc.)
but Buz exports specific pricing columns (sell_each, sell_sqm, cost_each, etc.)
"""


def up(conn):
    """Rebuild pricing table with correct columns."""
    # Drop old table and recreate with proper structure
    conn.execute('DROP TABLE IF EXISTS pricing_coefficients')

    conn.execute('''
        CREATE TABLE pricing_coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            group_code TEXT NOT NULL,
            item_code TEXT NOT NULL,
            description TEXT DEFAULT '',
            price_group_code TEXT DEFAULT '',
            effective_date TEXT,
            is_active BOOLEAN DEFAULT 1,

            -- Sell prices
            sell_each REAL DEFAULT 0,
            sell_lm_wide REAL DEFAULT 0,
            sell_lm_height REAL DEFAULT 0,
            sell_lm_depth REAL DEFAULT 0,
            sell_sqm REAL DEFAULT 0,
            sell_percentage_on_main REAL DEFAULT 0,
            sell_minimum REAL DEFAULT 0,

            -- Cost prices
            cost_each REAL DEFAULT 0,
            cost_lm_wide REAL DEFAULT 0,
            cost_lm_height REAL DEFAULT 0,
            cost_lm_depth REAL DEFAULT 0,
            cost_sqm REAL DEFAULT 0,
            cost_percentage_on_main REAL DEFAULT 0,
            cost_minimum REAL DEFAULT 0,

            -- Install costs
            install_cost_each REAL DEFAULT 0,
            install_cost_lm_width REAL DEFAULT 0,
            install_cost_height REAL DEFAULT 0,
            install_cost_depth REAL DEFAULT 0,
            install_cost_sqm REAL DEFAULT 0,
            install_cost_percentage_of_main REAL DEFAULT 0,
            install_cost_minimum REAL DEFAULT 0,

            -- Install sell prices
            install_sell_each REAL DEFAULT 0,
            install_sell_minimum REAL DEFAULT 0,
            install_sell_lm_wide REAL DEFAULT 0,
            install_sell_sqm REAL DEFAULT 0,
            install_sell_height REAL DEFAULT 0,
            install_sell_depth REAL DEFAULT 0,
            install_sell_percentage_of_main REAL DEFAULT 0,

            -- Supplier info
            supplier_code TEXT DEFAULT '',
            supplier_description TEXT DEFAULT '',

            -- Metadata
            pk_id TEXT,
            sort_order INTEGER DEFAULT 0,
            extra_data TEXT DEFAULT '{}',
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(org_key, group_code, item_code, price_group_code)
        )
    ''')

    # Recreate indexes
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pricing_org ON pricing_coefficients(org_key)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pricing_group ON pricing_coefficients(group_code)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pricing_item ON pricing_coefficients(item_code)')


def down(conn):
    """Revert to old schema (data will be lost)."""
    conn.execute('DROP TABLE IF EXISTS pricing_coefficients')

    conn.execute('''
        CREATE TABLE pricing_coefficients (
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
