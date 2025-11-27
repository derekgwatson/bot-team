"""
Initial database schema for Hugo's Buz user cache.

Creates tables for caching user data and tracking sync operations.
"""


def up(conn):
    """Create initial schema."""
    cursor = conn.cursor()

    # Cached Buz users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            org_key TEXT NOT NULL,
            user_type TEXT DEFAULT 'employee',
            is_active BOOLEAN DEFAULT 1,
            mfa_enabled BOOLEAN DEFAULT 0,
            user_group TEXT DEFAULT '',
            last_session TEXT DEFAULT '',
            last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email, org_key)
        )
    ''')

    # Sync log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success',
            error_message TEXT DEFAULT '',
            duration_seconds REAL DEFAULT 0
        )
    ''')

    # Activity log for tracking changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            email TEXT NOT NULL,
            org_key TEXT NOT NULL,
            old_value TEXT DEFAULT '',
            new_value TEXT DEFAULT '',
            performed_by TEXT DEFAULT 'system',
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT 1,
            error_message TEXT DEFAULT ''
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_org ON sync_log(org_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_email ON activity_log(email)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS activity_log')
    cursor.execute('DROP TABLE IF EXISTS sync_log')
    cursor.execute('DROP TABLE IF EXISTS users')
