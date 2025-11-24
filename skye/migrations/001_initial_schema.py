"""Initial schema for Skye - scheduled jobs and execution history."""


def up(conn):
    cursor = conn.cursor()

    # Jobs table - stores scheduled job configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            target_bot TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            method TEXT DEFAULT 'POST',
            schedule_type TEXT NOT NULL DEFAULT 'cron',
            schedule_config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            last_run TIMESTAMP,
            last_success TIMESTAMP,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Job execution history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            response_code INTEGER,
            response_body TEXT,
            error_message TEXT,
            duration_ms INTEGER,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        )
    ''')

    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_enabled ON jobs(enabled)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_target_bot ON jobs(target_bot)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_job_id ON job_executions(job_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_executed_at ON job_executions(executed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_status ON job_executions(status)')


def down(conn):
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS job_executions')
    cursor.execute('DROP TABLE IF EXISTS jobs')
