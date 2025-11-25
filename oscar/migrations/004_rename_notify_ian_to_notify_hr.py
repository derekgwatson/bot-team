"""
Rename notify_ian step to notify_hr in existing workflow steps.

This migration updates any existing workflow steps that still use the old
'notify_ian' step name to the new 'notify_hr' name.
"""


def up(conn):
    """Rename notify_ian to notify_hr in workflow_steps"""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE workflow_steps
        SET step_name = 'notify_hr'
        WHERE step_name = 'notify_ian'
    """)

    # Update description too if it mentions Ian
    cursor.execute("""
        UPDATE workflow_steps
        SET manual_action_instructions = REPLACE(manual_action_instructions, 'Ian', 'HR')
        WHERE step_name = 'notify_hr' AND manual_action_instructions LIKE '%Ian%'
    """)


def down(conn):
    """Revert notify_hr back to notify_ian"""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE workflow_steps
        SET step_name = 'notify_ian'
        WHERE step_name = 'notify_hr'
    """)
