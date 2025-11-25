"""
Add run_separately column to workflow_steps table.

This column indicates steps that should be excluded from "Create All"
and must be run manually (e.g., notify_hr should only run after
all other steps succeed).
"""


def up(conn):
    """Add run_separately column to workflow_steps"""
    cursor = conn.cursor()

    cursor.execute("""
        ALTER TABLE workflow_steps
        ADD COLUMN run_separately BOOLEAN DEFAULT 0
    """)

    # Mark existing notify_hr steps as run_separately
    cursor.execute("""
        UPDATE workflow_steps
        SET run_separately = 1
        WHERE step_name = 'notify_hr'
    """)


def down(conn):
    """Remove run_separately column - SQLite doesn't support DROP COLUMN easily"""
    # SQLite doesn't support DROP COLUMN, so we'd need to recreate the table
    # For simplicity, we'll just leave the column in place
    pass
