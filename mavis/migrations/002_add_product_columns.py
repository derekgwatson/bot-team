"""Add missing product columns for existing databases.

This handles databases created before these columns were added to the schema.
"""


def up(conn):
    """Add is_sellable, is_obsolete, product_sub_group if missing."""
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(unleashed_products)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'is_sellable' not in columns:
        cursor.execute('''
            ALTER TABLE unleashed_products
            ADD COLUMN is_sellable INTEGER DEFAULT 1
        ''')
        print("  Added column: is_sellable")

    if 'is_obsolete' not in columns:
        cursor.execute('''
            ALTER TABLE unleashed_products
            ADD COLUMN is_obsolete INTEGER DEFAULT 0
        ''')
        print("  Added column: is_obsolete")

    if 'product_sub_group' not in columns:
        cursor.execute('''
            ALTER TABLE unleashed_products
            ADD COLUMN product_sub_group TEXT
        ''')
        print("  Added column: product_sub_group")


def down(conn):
    """SQLite doesn't support DROP COLUMN easily, so this is a no-op."""
    pass
