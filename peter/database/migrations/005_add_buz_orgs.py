"""
Add buz_orgs field for multi-store Buz access tracking.

This allows tracking which specific Buz stores a staff member has access to,
rather than just a boolean flag. Hugo uses this to sync access changes.

The buz_orgs field stores a comma-separated list of org keys (e.g., "canberra,tweed").
The existing buz_access boolean is retained for backward compatibility and indicates
whether the user has access to ANY Buz store.
"""


def up(conn):
    """Add buz_orgs column."""
    cursor = conn.cursor()

    # Add buz_orgs column (comma-separated list of org keys)
    cursor.execute('''
        ALTER TABLE staff ADD COLUMN buz_orgs TEXT DEFAULT ''
    ''')


def down(conn):
    """Remove buz_orgs column (SQLite doesn't support DROP COLUMN easily)."""
    # SQLite < 3.35 doesn't support DROP COLUMN
    # For a proper rollback, we'd need to recreate the table
    # For now, just leave the column in place
    pass
