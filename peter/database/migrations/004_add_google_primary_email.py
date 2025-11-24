"""
Add google_primary_email field to staff table.

This field stores the user's actual Google Workspace account email address,
which may differ from their work_email if they use an alias day-to-day.

The google_primary_email is used for:
- OAuth authentication matching (Google always returns the primary email)
- Google Workspace API calls (user lookup, group management, etc.)

The work_email can still be an alias that the user prefers to use publicly.
"""


def up(conn):
    """Add google_primary_email column to staff table"""
    cursor = conn.cursor()

    # Add the new column
    cursor.execute('''
        ALTER TABLE staff ADD COLUMN google_primary_email TEXT DEFAULT ''
    ''')

    # Add an index for efficient lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_staff_google_email ON staff(google_primary_email)
    ''')


def down(conn):
    """Remove google_primary_email column (SQLite doesn't support DROP COLUMN easily)"""
    # SQLite doesn't support DROP COLUMN, so we'd need to recreate the table
    # For now, just document that this is a one-way migration
    pass
