"""Add timeout column for gunicorn worker timeout per bot."""


def up(conn):
    """Add timeout column to bots table."""
    cursor = conn.cursor()

    # Add timeout column with default of 120 seconds (current Dorothy default)
    cursor.execute('''
        ALTER TABLE bots ADD COLUMN timeout INTEGER DEFAULT 120
    ''')

    # Set longer timeout for bots that use Playwright/browser automation
    # These bots can have long-running operations that need more time
    playwright_bots = ['banji', 'hugo', 'ivy']
    for bot_name in playwright_bots:
        cursor.execute('''
            UPDATE bots SET timeout = 600 WHERE name = ?
        ''', (bot_name,))


def down(conn):
    """Remove timeout column (SQLite doesn't support DROP COLUMN easily)."""
    # SQLite doesn't support DROP COLUMN, so we'd need to recreate the table
    # For simplicity, leave the column in place
    pass
