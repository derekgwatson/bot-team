"""Add scheduled job for Nigel daily price check."""
import json


def up(conn):
    cursor = conn.cursor()

    # Nigel Price Check - daily at 6am Sydney time
    cursor.execute('''
        INSERT OR IGNORE INTO jobs
        (job_id, name, description, target_bot, endpoint, method, schedule_type, schedule_config, enabled, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'nigel_price_check',
        'Nigel Price Check',
        'Check prices for all monitored quotes and detect discrepancies via Banji',
        'nigel',
        '/api/quotes/check-all',
        'POST',
        'cron',
        json.dumps({'hour': '6', 'minute': '0'}),
        1,
        'skye-setup'
    ))


def down(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE job_id = 'nigel_price_check'")
