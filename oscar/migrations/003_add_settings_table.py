"""
Add settings table for Oscar admin configuration.

This table stores key-value pairs for configurable settings like:
- HR notification email address
- VOIP ticket group assignment
- etc.
"""


def up(conn):
    """Create settings table"""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT DEFAULT 'system'
        )
    ''')

    # Insert default settings
    default_settings = [
        ('hr_notification_email', '', 'Email address to notify for new onboarding requests'),
        ('hr_notification_name', 'HR', 'Display name for HR notification recipient'),
        ('voip_ticket_group_id', '', 'Zendesk group ID for VOIP setup tickets'),
        ('voip_ticket_group_name', '', 'Zendesk group name for VOIP setup tickets (display only)'),
    ]

    for key, value, description in default_settings:
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value, description)
            VALUES (?, ?, ?)
        ''', (key, value, description))


def down(conn):
    """Drop settings table"""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS settings')
