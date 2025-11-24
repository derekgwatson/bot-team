"""Seed default scheduled jobs for the bot team."""
import json


def up(conn):
    cursor = conn.cursor()

    # Fiona-Mavis Sync - every 4 hours
    cursor.execute('''
        INSERT OR IGNORE INTO jobs
        (job_id, name, description, target_bot, endpoint, method, schedule_type, schedule_config, enabled, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'fiona_mavis_sync',
        'Fiona-Mavis Sync',
        'Sync fabric descriptions between Fiona and Mavis. Adds missing fabrics and reports flagged items.',
        'fiona',
        '/api/sync/auto',
        'POST',
        'cron',
        json.dumps({'hour': '*/4', 'minute': '15'}),
        1,
        'skye-setup'
    ))

    # Mavis-Unleashed Sync - every 4 hours (offset by 30 min)
    cursor.execute('''
        INSERT OR IGNORE INTO jobs
        (job_id, name, description, target_bot, endpoint, method, schedule_type, schedule_config, enabled, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'mavis_unleashed_sync',
        'Mavis-Unleashed Sync',
        'Sync product data from Unleashed API into Mavis database.',
        'mavis',
        '/api/sync/run',
        'POST',
        'cron',
        json.dumps({'hour': '*/4', 'minute': '0'}),
        1,
        'skye-setup'
    ))

    # Quinn-Peter Sync - every 5 minutes
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
    cursor.execute("DELETE FROM jobs WHERE job_id IN ('fiona_mavis_sync', 'mavis_unleashed_sync', 'quinn_peter_sync')")
