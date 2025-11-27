"""Add fabric_type column to store the product group type from Unleashed.

The fabric_type stores values like 'Roller', 'Awning', etc.
derived from the product_group field in Unleashed (e.g., 'Fabric - Roller').
"""


def up(conn):
    """Add fabric_type column to fabric_descriptions table."""
    cursor = conn.cursor()

    # Add the fabric_type column
    cursor.execute('''
        ALTER TABLE fabric_descriptions
        ADD COLUMN fabric_type TEXT
    ''')

    # Add index for filtering by fabric type
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_fabric_type
        ON fabric_descriptions(fabric_type)
    ''')


def down(conn):
    """Remove fabric_type column.

    Note: SQLite doesn't support DROP COLUMN easily in older versions,
    so this would require table recreation in production.
    """
    # SQLite 3.35+ supports DROP COLUMN
    cursor = conn.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_fabric_type')
    # For older SQLite versions, this may fail
    # cursor.execute('ALTER TABLE fabric_descriptions DROP COLUMN fabric_type')
