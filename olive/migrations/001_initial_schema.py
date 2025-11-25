"""Initial database schema for Olive's offboarding workflows."""


def up(conn):
    """Create offboarding tables."""
    cursor = conn.cursor()

    # Main offboarding requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offboarding_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            position TEXT,
            section TEXT,
            last_day DATE NOT NULL,
            personal_email TEXT,
            phone_mobile TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            completed_date TIMESTAMP,
            had_google_access BOOLEAN DEFAULT FALSE,
            had_zendesk_access BOOLEAN DEFAULT FALSE,
            had_wiki_access BOOLEAN DEFAULT FALSE,
            had_buz_access BOOLEAN DEFAULT FALSE,
            google_email TEXT,
            zendesk_user_id TEXT,
            peter_staff_id TEXT,
            wiki_username TEXT,
            buz_instances TEXT
        )
    ''')

    # Workflow steps tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflow_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offboarding_request_id INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            started_date TIMESTAMP,
            completed_date TIMESTAMP,
            success BOOLEAN,
            result_data TEXT,
            error_message TEXT,
            requires_manual_action BOOLEAN DEFAULT FALSE,
            zendesk_ticket_id TEXT,
            FOREIGN KEY (offboarding_request_id) REFERENCES offboarding_requests(id)
        )
    ''')

    # Activity log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offboarding_request_id INTEGER,
            activity_type TEXT NOT NULL,
            description TEXT NOT NULL,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            metadata TEXT,
            FOREIGN KEY (offboarding_request_id) REFERENCES offboarding_requests(id)
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_offboarding_status ON offboarding_requests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_offboarding_created_date ON offboarding_requests(created_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflow_request ON workflow_steps(offboarding_request_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_request ON activity_log(offboarding_request_id)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS activity_log')
    cursor.execute('DROP TABLE IF EXISTS workflow_steps')
    cursor.execute('DROP TABLE IF EXISTS offboarding_requests')
