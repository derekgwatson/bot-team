"""Add wiki_access column to onboarding_requests table."""


def up(conn):
    """Add wiki_access column."""
    cursor = conn.cursor()
    cursor.execute('''
        ALTER TABLE onboarding_requests
        ADD COLUMN wiki_access BOOLEAN DEFAULT 0
    ''')


def down(conn):
    """Remove wiki_access column (SQLite doesn't support DROP COLUMN easily)."""
    # SQLite doesn't support DROP COLUMN in older versions
    # For a proper down migration, would need to recreate the table
    pass
