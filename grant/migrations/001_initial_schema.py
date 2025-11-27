"""Initial database schema for Grant's permission management."""


def up(conn):
    """Create permissions and audit tables."""
    cursor = conn.cursor()

    # Permissions table - who has access to what
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            granted_by TEXT NOT NULL,
            granted_at TEXT NOT NULL,
            UNIQUE(email, bot_name)
        )
    ''')

    # Audit trail for permission changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permission_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            bot_name TEXT NOT NULL,
            action TEXT NOT NULL,
            old_role TEXT,
            new_role TEXT,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL
        )
    ''')

    # Bot registry cache (synced from Chester)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            port INTEGER,
            synced_at TEXT NOT NULL
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_permissions_email ON permissions(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_permissions_bot ON permissions(bot_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_permissions_role ON permissions(role)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_email ON permission_changes(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_bot ON permission_changes(bot_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON permission_changes(changed_at)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS permissions')
    cursor.execute('DROP TABLE IF EXISTS permission_changes')
    cursor.execute('DROP TABLE IF EXISTS bots')
