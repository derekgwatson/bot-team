"""Initial database schema for Banji's job queue."""


def up(conn):
    """Create initial tables."""
    cursor = conn.cursor()

    # Jobs table for async processing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            org TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            progress_current INTEGER DEFAULT 0,
            progress_total INTEGER DEFAULT 0,
            progress_message TEXT,
            result TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # Index for finding pending jobs quickly
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_jobs_status_created
        ON jobs (status, created_at)
    ''')

    # Index for finding jobs by org
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_jobs_org
        ON jobs (org)
    ''')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS jobs')
