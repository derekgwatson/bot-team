"""
Add finish_date field to staff table.

Supports Olive offboarding bot - tracks when staff members leave the organization.
The finish_date field is set when a staff member is offboarded and their status
is changed to 'finished'.
"""

def up(conn):
    """Add finish_date column to staff table"""
    cursor = conn.cursor()

    # Add finish_date field
    cursor.execute('''
        ALTER TABLE staff
        ADD COLUMN finish_date DATE
    ''')

    # Add 'finished' as a valid status value (extend existing status field)
    # Note: SQLite doesn't support adding CHECK constraints to existing columns,
    # so we document that 'finished' is now a valid status value
    # Existing status values: 'active', 'inactive', 'onboarding', 'offboarding'
    # New status value: 'finished'

    conn.commit()


def down(conn):
    """
    Remove finish_date column from staff table

    Note: SQLite doesn't support DROP COLUMN directly, so this would require
    recreating the table. For simplicity, we'll leave the column in place
    if rolling back (it can be NULL and won't affect existing functionality).
    """
    # SQLite limitation - can't drop columns easily
    # In production, you'd recreate the table without the column
    pass
