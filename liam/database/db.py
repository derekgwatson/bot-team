"""
Database service for Liam's leads verification history.
"""
import sqlite3
import os
from typing import Optional, List, Dict, Any
from shared.migrations import MigrationRunner


class LeadsDatabase:
    """SQLite database for storing leads verification results."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'liam.db')
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database and tables exist using migrations."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
        runner = MigrationRunner(db_path=self.db_path, migrations_dir=migrations_dir)
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Verification log operations

    def log_verification(
        self,
        org_key: str,
        date: str,
        lead_count: int,
        status: str,
        message: str = '',
        ticket_id: Optional[int] = None
    ) -> int:
        """
        Log a verification result.

        Args:
            org_key: Organization key
            date: Date that was verified (YYYY-MM-DD)
            lead_count: Number of leads found
            status: 'ok', 'alert', 'error', or 'skipped'
            message: Optional message/description
            ticket_id: Zendesk ticket ID if one was created

        Returns:
            ID of the log entry
        """
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO verification_log (org_key, verified_date, lead_count, status, message, ticket_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (org_key, date, lead_count, status, message, ticket_id))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_verification_history(
        self,
        org_key: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get verification history.

        Args:
            org_key: Optional filter by organization
            limit: Maximum records to return

        Returns:
            List of verification records
        """
        conn = self.get_connection()

        if org_key:
            cursor = conn.execute(
                '''SELECT * FROM verification_log
                   WHERE org_key = ?
                   ORDER BY verified_at DESC
                   LIMIT ?''',
                (org_key, limit)
            )
        else:
            cursor = conn.execute(
                '''SELECT * FROM verification_log
                   ORDER BY verified_at DESC
                   LIMIT ?''',
                (limit,)
            )

        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    def get_latest_verification(self, org_key: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent verification for an org.

        Args:
            org_key: Organization key

        Returns:
            Most recent verification record or None
        """
        conn = self.get_connection()
        cursor = conn.execute(
            '''SELECT * FROM verification_log
               WHERE org_key = ?
               ORDER BY verified_at DESC
               LIMIT 1''',
            (org_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_verifications_for_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Get all verifications for a specific date.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            List of verification records for that date
        """
        conn = self.get_connection()
        cursor = conn.execute(
            '''SELECT * FROM verification_log
               WHERE verified_date = ?
               ORDER BY org_key''',
            (date,)
        )
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def get_stats(self) -> Dict[str, Any]:
        """
        Get verification statistics.

        Returns:
            Dict with stats by org and overall
        """
        conn = self.get_connection()

        # Overall stats
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total_checks,
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok_count,
                SUM(CASE WHEN status = 'alert' THEN 1 ELSE 0 END) as alert_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_count
            FROM verification_log
        ''')
        row = cursor.fetchone()
        overall = {
            'total_checks': row['total_checks'] or 0,
            'ok_count': row['ok_count'] or 0,
            'alert_count': row['alert_count'] or 0,
            'error_count': row['error_count'] or 0,
            'skipped_count': row['skipped_count'] or 0
        }

        # Stats by org
        cursor = conn.execute('''
            SELECT
                org_key,
                COUNT(*) as total_checks,
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok_count,
                SUM(CASE WHEN status = 'alert' THEN 1 ELSE 0 END) as alert_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                MAX(verified_at) as last_check
            FROM verification_log
            WHERE status != 'skipped'
            GROUP BY org_key
        ''')
        by_org = {}
        for row in cursor.fetchall():
            by_org[row['org_key']] = {
                'total_checks': row['total_checks'],
                'ok_count': row['ok_count'],
                'alert_count': row['alert_count'],
                'error_count': row['error_count'],
                'last_check': row['last_check']
            }

        # Recent alerts
        cursor = conn.execute('''
            SELECT * FROM verification_log
            WHERE status = 'alert'
            ORDER BY verified_at DESC
            LIMIT 10
        ''')
        recent_alerts = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'overall': overall,
            'by_org': by_org,
            'recent_alerts': recent_alerts
        }

    def get_alerts_count(self, days: int = 7) -> int:
        """
        Get count of alerts in the last N days.

        Args:
            days: Number of days to look back

        Returns:
            Count of alert records
        """
        conn = self.get_connection()
        cursor = conn.execute(
            '''SELECT COUNT(*) as count FROM verification_log
               WHERE status = 'alert'
               AND verified_at >= datetime('now', ? || ' days')''',
            (f'-{days}',)
        )
        count = cursor.fetchone()['count']
        conn.close()
        return count


# Singleton instance
leads_db = LeadsDatabase()
