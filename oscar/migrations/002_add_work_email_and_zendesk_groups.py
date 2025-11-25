"""Add work_email and zendesk_groups columns if missing.

This migration handles databases created before these columns were added.
"""


def up(conn):
    """Add work_email and zendesk_groups columns if they don't exist."""
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute('PRAGMA table_info(onboarding_requests)')
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Add work_email if missing
    if 'work_email' not in existing_columns:
        cursor.execute('''
            ALTER TABLE onboarding_requests
            ADD COLUMN work_email TEXT DEFAULT NULL
        ''')
        print("  Added column: work_email")

    # Add zendesk_groups if missing
    if 'zendesk_groups' not in existing_columns:
        cursor.execute('''
            ALTER TABLE onboarding_requests
            ADD COLUMN zendesk_groups TEXT DEFAULT NULL
        ''')
        print("  Added column: zendesk_groups")


def down(conn):
    """SQLite doesn't support DROP COLUMN easily, so this is a no-op."""
    pass
