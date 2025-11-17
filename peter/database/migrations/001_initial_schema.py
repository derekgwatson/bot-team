"""
Initial database schema for Peter's staff database.

Creates the staff and sections tables.
"""

def up(conn):
    """Create initial schema"""
    cursor = conn.cursor()

    # Staff table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position TEXT DEFAULT '',
            section TEXT DEFAULT '',
            extension TEXT DEFAULT '',
            phone_fixed TEXT DEFAULT '',
            phone_mobile TEXT DEFAULT '',
            work_email TEXT DEFAULT '',
            personal_email TEXT DEFAULT '',
            zendesk_access BOOLEAN DEFAULT 0,
            buz_access BOOLEAN DEFAULT 0,
            google_access BOOLEAN DEFAULT 0,
            wiki_access BOOLEAN DEFAULT 0,
            voip_access BOOLEAN DEFAULT 0,
            show_on_phone_list BOOLEAN DEFAULT 1,
            include_in_allstaff BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system',
            modified_by TEXT DEFAULT 'system',
            notes TEXT DEFAULT ''
        )
    ''')

    # Sections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Index for common queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_section ON staff(section)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_email ON staff(work_email)')


def down(conn):
    """Drop all tables"""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS staff')
    cursor.execute('DROP TABLE IF EXISTS sections')
