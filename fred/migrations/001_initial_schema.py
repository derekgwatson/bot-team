"""Initial database schema for Fred's pending operations."""


def up(conn):
    """Create pending_operations table."""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            operation_data TEXT NOT NULL,
            target_email TEXT,
            target_name TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system',
            executed_date TIMESTAMP DEFAULT NULL,
            executed_by TEXT DEFAULT NULL,
            result_data TEXT DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            external_reference TEXT DEFAULT NULL
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_status ON pending_operations(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_type ON pending_operations(operation_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_created ON pending_operations(created_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_email ON pending_operations(target_email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_external_ref ON pending_operations(external_reference)')


def down(conn):
    """Drop pending_operations table."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS pending_operations')
