"""Add quiet flag to jobs for cleaner execution logs.

Jobs marked as 'quiet' will only appear in execution history when they fail.
This reduces log noise from high-frequency jobs that succeed most of the time.
"""


def up(conn):
    """Add quiet column to jobs table."""
    conn.execute('''
        ALTER TABLE jobs ADD COLUMN quiet INTEGER DEFAULT 0
    ''')

    # Mark known high-frequency jobs as quiet by default
    high_frequency_jobs = [
        'oscar-voip-ticket-check',
        'quinn-peter-sync',
    ]
    for job_id in high_frequency_jobs:
        conn.execute(
            'UPDATE jobs SET quiet = 1 WHERE job_id = ?',
            (job_id,)
        )


def down(conn):
    """SQLite doesn't support DROP COLUMN easily."""
    pass
