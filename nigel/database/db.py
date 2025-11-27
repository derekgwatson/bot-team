import sqlite3
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
from shared.migrations import MigrationRunner


class Database:
    """Database manager for Nigel's price monitoring"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'nigel.db'
        self.db_path = str(db_path)
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Monitored Quotes ───────────────────────────────────────────

    def add_quote(self, quote_id: str, org: str, notes: str = '') -> int:
        """Add a quote to be monitored. Returns the record ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO monitored_quotes (quote_id, org, notes)
            VALUES (?, ?, ?)
            ON CONFLICT(quote_id) DO UPDATE SET
                org = excluded.org,
                is_active = 1,
                notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE notes END
        """, (quote_id, org, notes))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_quote(self, quote_id: str) -> Optional[Dict]:
        """Get a monitored quote by quote_id"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM monitored_quotes WHERE quote_id = ?", (quote_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_quotes(self, active_only: bool = True) -> List[Dict]:
        """Get all monitored quotes"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute(
                "SELECT * FROM monitored_quotes WHERE is_active = 1 ORDER BY last_checked_at DESC NULLS LAST"
            )
        else:
            cursor.execute("SELECT * FROM monitored_quotes ORDER BY last_checked_at DESC NULLS LAST")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_quote_price(self, quote_id: str, price: str):
        """Update the last known price for a quote"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE monitored_quotes
            SET last_known_price = ?,
                last_checked_at = CURRENT_TIMESTAMP,
                price_updated_at = CURRENT_TIMESTAMP
            WHERE quote_id = ?
        """, (price, quote_id))

        conn.commit()
        conn.close()

    def update_quote_checked(self, quote_id: str):
        """Update the last checked timestamp for a quote"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE monitored_quotes
            SET last_checked_at = CURRENT_TIMESTAMP
            WHERE quote_id = ?
        """, (quote_id,))

        conn.commit()
        conn.close()

    def deactivate_quote(self, quote_id: str):
        """Deactivate monitoring for a quote"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE monitored_quotes
            SET is_active = 0
            WHERE quote_id = ?
        """, (quote_id,))

        conn.commit()
        conn.close()

    def activate_quote(self, quote_id: str):
        """Reactivate monitoring for a quote"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE monitored_quotes
            SET is_active = 1
            WHERE quote_id = ?
        """, (quote_id,))

        conn.commit()
        conn.close()

    def delete_quote(self, quote_id: str):
        """Remove a quote from monitoring entirely"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM monitored_quotes WHERE quote_id = ?", (quote_id,))

        conn.commit()
        conn.close()

    def add_quotes_bulk(self, quote_ids: List[str], org: str, notes: str = '') -> Dict:
        """
        Add multiple quotes to monitoring.
        Returns dict with 'added' count and 'skipped' list (already existed).
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        added = 0
        skipped = []

        for quote_id in quote_ids:
            # Check if quote already exists and is active
            cursor.execute(
                "SELECT quote_id, is_active FROM monitored_quotes WHERE quote_id = ?",
                (quote_id,)
            )
            existing = cursor.fetchone()

            if existing and existing['is_active']:
                skipped.append(quote_id)
                continue

            # Insert or reactivate
            cursor.execute("""
                INSERT INTO monitored_quotes (quote_id, org, notes)
                VALUES (?, ?, ?)
                ON CONFLICT(quote_id) DO UPDATE SET
                    org = excluded.org,
                    is_active = 1,
                    notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE notes END
            """, (quote_id, org, notes))
            added += 1

        conn.commit()
        conn.close()

        return {
            'added': added,
            'skipped': skipped,
            'skipped_count': len(skipped)
        }

    # ─── Price Checks ───────────────────────────────────────────────

    def log_price_check(
        self,
        quote_id: str,
        org: str,
        status: str,
        price_before: str = None,
        price_after: str = None,
        has_discrepancy: bool = False,
        discrepancy_amount: str = None,
        error_message: str = None,
        banji_response: Dict = None
    ) -> int:
        """Log a price check result. Returns the record ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO price_checks (
                quote_id, org, status,
                price_before, price_after,
                has_discrepancy, discrepancy_amount,
                error_message, banji_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quote_id, org, status,
            price_before, price_after,
            has_discrepancy, discrepancy_amount,
            error_message,
            json.dumps(banji_response) if banji_response else None
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_price_checks(
        self,
        quote_id: str = None,
        limit: int = 100,
        discrepancies_only: bool = False
    ) -> List[Dict]:
        """Get price check history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM price_checks WHERE 1=1"
        params = []

        if quote_id:
            query += " AND quote_id = ?"
            params.append(quote_id)

        if discrepancies_only:
            query += " AND has_discrepancy = 1"

        query += " ORDER BY checked_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            item = dict(row)
            if item.get('banji_response'):
                try:
                    item['banji_response'] = json.loads(item['banji_response'])
                except json.JSONDecodeError:
                    pass
            results.append(item)
        return results

    def get_recent_checks_summary(self, hours: int = 24) -> Dict:
        """Get summary of price checks in the last N hours"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_checks,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                SUM(CASE WHEN has_discrepancy = 1 THEN 1 ELSE 0 END) as discrepancies
            FROM price_checks
            WHERE checked_at >= datetime('now', ? || ' hours')
        """, (f'-{hours}',))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else {
            'total_checks': 0,
            'successful': 0,
            'errors': 0,
            'discrepancies': 0
        }

    # ─── Discrepancies ──────────────────────────────────────────────

    def create_discrepancy(
        self,
        quote_id: str,
        org: str,
        expected_price: str,
        actual_price: str,
        difference: str
    ) -> int:
        """Create a new discrepancy record. Returns the record ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO discrepancies (
                quote_id, org, expected_price, actual_price, difference
            ) VALUES (?, ?, ?, ?, ?)
        """, (quote_id, org, expected_price, actual_price, difference))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def get_discrepancies(
        self,
        quote_id: str = None,
        resolved: bool = None,
        notification_status: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get discrepancies with optional filters"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM discrepancies WHERE 1=1"
        params = []

        if quote_id:
            query += " AND quote_id = ?"
            params.append(quote_id)

        if resolved is not None:
            query += " AND resolved = ?"
            params.append(resolved)

        if notification_status:
            query += " AND notification_status = ?"
            params.append(notification_status)

        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_discrepancy(self, discrepancy_id: int) -> Optional[Dict]:
        """Get a specific discrepancy by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM discrepancies WHERE id = ?", (discrepancy_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_discrepancy_notification(
        self,
        discrepancy_id: int,
        notification_status: str,
        notification_method: str = None,
        notification_id: str = None
    ):
        """Update notification status for a discrepancy"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discrepancies
            SET notification_status = ?,
                notification_method = ?,
                notification_id = ?,
                notified_at = CASE WHEN ? = 'notified' THEN CURRENT_TIMESTAMP ELSE notified_at END
            WHERE id = ?
        """, (notification_status, notification_method, notification_id, notification_status, discrepancy_id))

        conn.commit()
        conn.close()

    def resolve_discrepancy(
        self,
        discrepancy_id: int,
        resolved_by: str = 'system',
        resolution_notes: str = None
    ):
        """Mark a discrepancy as resolved"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE discrepancies
            SET resolved = 1,
                resolved_at = CURRENT_TIMESTAMP,
                resolved_by = ?,
                resolution_notes = ?
            WHERE id = ?
        """, (resolved_by, resolution_notes, discrepancy_id))

        conn.commit()
        conn.close()

    def get_pending_discrepancies(self) -> List[Dict]:
        """Get discrepancies that haven't been notified yet"""
        return self.get_discrepancies(resolved=False, notification_status='pending')

    # ─── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get overall statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Count monitored quotes
        cursor.execute("SELECT COUNT(*) as count FROM monitored_quotes WHERE is_active = 1")
        active_quotes = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM monitored_quotes")
        total_quotes = cursor.fetchone()['count']

        # Count discrepancies
        cursor.execute("SELECT COUNT(*) as count FROM discrepancies WHERE resolved = 0")
        unresolved_discrepancies = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM discrepancies WHERE notification_status = 'pending'")
        pending_notifications = cursor.fetchone()['count']

        # Count price checks
        cursor.execute("SELECT COUNT(*) as count FROM price_checks")
        total_checks = cursor.fetchone()['count']

        conn.close()

        return {
            'active_quotes': active_quotes,
            'total_quotes': total_quotes,
            'unresolved_discrepancies': unresolved_discrepancies,
            'pending_notifications': pending_notifications,
            'total_price_checks': total_checks
        }


# Global database instance
db = Database()
