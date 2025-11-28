#!/usr/bin/env python3
"""
Cleanup stale sync records in Ivy's database.

Usage: python ivy/tools/cleanup_stale_syncs.py [--dry-run]
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

# Find the database
DB_PATH = Path(__file__).parent.parent / 'database' / 'ivy.db'


def get_stale_syncs(conn):
    """Find syncs that are stuck in running or waiting_for_lock status."""
    cursor = conn.execute("""
        SELECT id, org_key, sync_type, status, started_at, completed_at
        FROM sync_log
        WHERE status IN ('running', 'waiting_for_lock')
        ORDER BY started_at DESC
    """)
    return cursor.fetchall()


def mark_sync_failed(conn, sync_id: int, error_message: str):
    """Mark a sync as failed with an error message."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        UPDATE sync_log
        SET status = 'failed',
            error_message = ?,
            completed_at = ?
        WHERE id = ?
    """, (error_message, now, sync_id))
    conn.commit()


def main():
    dry_run = '--dry-run' in sys.argv

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    stale_syncs = get_stale_syncs(conn)

    if not stale_syncs:
        print("No stale syncs found.")
        conn.close()
        return

    print(f"Found {len(stale_syncs)} stale sync(s):\n")

    for sync in stale_syncs:
        sync_id, org_key, sync_type, status, started_at, completed_at = sync
        print(f"  ID: {sync_id}")
        print(f"  Org: {org_key}")
        print(f"  Type: {sync_type}")
        print(f"  Status: {status}")
        print(f"  Started: {started_at}")
        print(f"  Completed: {completed_at or 'N/A'}")
        print()

        if not dry_run:
            error_msg = "Sync was interrupted or crashed (cleaned up manually)"
            mark_sync_failed(conn, sync_id, error_msg)
            print(f"  -> Marked as failed\n")

    if dry_run:
        print("Dry run - no changes made. Remove --dry-run to apply changes.")
    else:
        print(f"Cleaned up {len(stale_syncs)} stale sync(s).")

    conn.close()


if __name__ == '__main__':
    main()
