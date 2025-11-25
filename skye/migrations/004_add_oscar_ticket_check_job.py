"""Add scheduled job to check Oscar's pending VOIP tickets."""
import json


def up(conn):
    cursor = conn.cursor()

    # Oscar Ticket Check - every 5 minutes
    cursor.execute('''
        INSERT OR IGNORE INTO jobs
        (job_id, name, description, target_bot, endpoint, method, schedule_type, schedule_config, enabled, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'oscar_ticket_check',
        'Oscar VOIP Ticket Check',
        'Check pending VOIP tickets in Oscar and auto-complete steps when tickets are solved.',
        'oscar',
        '/api/check-pending-tickets',
        'POST',
        'interval',
        json.dumps({'minutes': 5}),
        1,
        'skye-setup'
    ))


def down(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE job_id = 'oscar_ticket_check'")
