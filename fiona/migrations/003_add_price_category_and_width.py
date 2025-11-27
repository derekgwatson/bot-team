"""Add price_category and width columns from Unleashed.

price_category: The product_sub_group from Unleashed (e.g., 'A', 'B', 'C', 'Premium')
width: The fabric width in meters from Unleashed
"""


def up(conn):
    """Add price_category and width columns to fabric_descriptions table."""
    cursor = conn.cursor()

    # Add the price_category column (from product_sub_group)
    cursor.execute('''
        ALTER TABLE fabric_descriptions
        ADD COLUMN price_category TEXT
    ''')

    # Add the width column
    cursor.execute('''
        ALTER TABLE fabric_descriptions
        ADD COLUMN width REAL
    ''')

    # Add index for filtering by price category
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_fabric_price_category
        ON fabric_descriptions(price_category)
    ''')


def down(conn):
    """Remove price_category and width columns."""
    cursor = conn.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_fabric_price_category')
    # SQLite 3.35+ supports DROP COLUMN
    # cursor.execute('ALTER TABLE fabric_descriptions DROP COLUMN price_category')
    # cursor.execute('ALTER TABLE fabric_descriptions DROP COLUMN width')
