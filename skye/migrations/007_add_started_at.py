"""Add started_at column to track when jobs begin executing.

This enables showing 'running' status in the UI when a job has started
but not yet completed.
"""


def up(conn):
    cursor = conn.cursor()
    cursor.execute('''
        ALTER TABLE job_executions ADD COLUMN started_at TIMESTAMP
    ''')


def down(conn):
    # SQLite doesn't support DROP COLUMN easily
    pass
