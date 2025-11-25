"""Initial database schema for Scout's issue tracking."""


def up(conn):
    """Create issue tracking tables."""
    cursor = conn.cursor()

    # Reported issues table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reported_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT NOT NULL,
            issue_key TEXT NOT NULL,
            issue_details TEXT,
            ticket_id INTEGER,
            ticket_url TEXT,
            status TEXT DEFAULT 'open',
            first_detected_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            resolved_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(issue_type, issue_key)
        )
    ''')

    # Check runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS check_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            issues_found INTEGER DEFAULT 0,
            tickets_created INTEGER DEFAULT 0,
            error_message TEXT,
            check_results TEXT
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reported_issues_type_key ON reported_issues(issue_type, issue_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reported_issues_status ON reported_issues(status)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS check_runs')
    cursor.execute('DROP TABLE IF EXISTS reported_issues')
