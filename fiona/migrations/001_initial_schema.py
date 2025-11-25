"""Initial database schema for Fiona's fabric descriptions."""


def up(conn):
    """Create fabric descriptions table."""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fabric_descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL UNIQUE,
            supplier_material TEXT,
            supplier_material_type TEXT,
            supplier_colour TEXT,
            watson_material TEXT,
            watson_colour TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabric_product_code ON fabric_descriptions(product_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabric_supplier_material ON fabric_descriptions(supplier_material)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabric_watson_material ON fabric_descriptions(watson_material)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fabric_updated ON fabric_descriptions(updated_at)')


def down(conn):
    """Drop fabric_descriptions table."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS fabric_descriptions')
