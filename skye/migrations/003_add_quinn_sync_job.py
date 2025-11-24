"""Add Quinn-Peter sync job to the scheduler."""
import json


def up(conn):
    cursor = conn.cursor()

    # Quinn-Peter Sync - every 5 minutes
    # This moves scheduling responsibility from Quinn's internal threading to Skye
    cursor.execute('''
        INSERT OR IGNORE INTO jobs
        (job_id, name, description, target_bot, endpoint, method, schedule_type, schedule_config, enabled, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'quinn_peter_sync',
        'Quinn-Peter Sync',
        'Sync allstaff Google Group with Peter staff database. Adds/removes members as needed.',
        'quinn',
        '/api/sync/now',
        'POST',
        'interval',
        json.dumps({'minutes': 5}),
        1,
        'skye-setup'
    ))


def down(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE job_id = 'quinn_peter_sync'")
