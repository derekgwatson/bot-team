"""
Juno Database Manager
Handles SQLite database connections and operations for tracking links
"""

import sqlite3
import secrets
import string
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from shared.migrations import MigrationRunner

logger = logging.getLogger(__name__)


class Database:
    """
    Database manager for Juno's SQLite database
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'juno.db'

        self.db_path = str(db_path)
        logger.info(f"Database path: {self.db_path}")
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)
        logger.info("Database migrations completed")

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection with row factory set

        Returns:
            SQLite connection with Row factory
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_code(self, length: int = 12) -> str:
        """Generate a unique tracking code"""
        # Use URL-safe characters (no confusing characters like 0/O, 1/l)
        alphabet = string.ascii_lowercase + string.digits
        alphabet = alphabet.replace('0', '').replace('o', '').replace('l', '').replace('1', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    # ══════════════════════════════════════════════════════════════
    # Tracking link operations
    # ══════════════════════════════════════════════════════════════

    def create_tracking_link(
        self,
        journey_id: int,
        staff_id: int,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        destination_address: Optional[str] = None,
        destination_lat: Optional[float] = None,
        destination_lng: Optional[float] = None,
        expiry_hours: int = 24,
        code_length: int = 12
    ) -> Dict[str, Any]:
        """
        Create a new tracking link for a customer

        Args:
            journey_id: Travis journey ID
            staff_id: Travis staff ID
            customer_name: Customer's name
            customer_phone: Customer's phone number
            customer_email: Customer's email
            destination_address: Delivery/visit address
            destination_lat: Destination latitude
            destination_lng: Destination longitude
            expiry_hours: Hours until link expires
            code_length: Length of tracking code

        Returns:
            Tracking link dictionary with code
        """
        code = self._generate_code(code_length)
        expires_at = datetime.now() + timedelta(hours=expiry_hours)

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO tracking_links
                   (code, journey_id, staff_id, customer_name, customer_phone, customer_email,
                    destination_address, destination_lat, destination_lng, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, journey_id, staff_id, customer_name, customer_phone, customer_email,
                 destination_address, destination_lat, destination_lng, expires_at)
            )
            conn.commit()
            link_id = cursor.lastrowid

            # Log creation event
            self._log_event(conn, link_id, 'created', {
                'journey_id': journey_id,
                'staff_id': staff_id,
                'customer_name': customer_name
            })

            logger.info(f"Created tracking link {code} for journey {journey_id}")

            return self.get_tracking_link_by_id(link_id)
        finally:
            conn.close()

    def get_tracking_link_by_id(self, link_id: int) -> Optional[Dict[str, Any]]:
        """Get tracking link by ID"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM tracking_links WHERE id = ?",
                (link_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_tracking_link_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get tracking link by code"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM tracking_links WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_active_link_by_journey(self, journey_id: int) -> Optional[Dict[str, Any]]:
        """Get active tracking link for a journey"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM tracking_links
                   WHERE journey_id = ? AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1""",
                (journey_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def record_view(self, code: str) -> bool:
        """
        Record that a tracking link was viewed

        Args:
            code: Tracking code

        Returns:
            True if recorded, False if link not found
        """
        conn = self.get_connection()
        try:
            # Get link
            cursor = conn.execute(
                "SELECT id, first_viewed_at FROM tracking_links WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            link_id = row['id']
            first_view = row['first_viewed_at']

            # Update view count and first_viewed_at if needed
            if first_view is None:
                conn.execute(
                    """UPDATE tracking_links
                       SET view_count = view_count + 1, first_viewed_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (link_id,)
                )
            else:
                conn.execute(
                    "UPDATE tracking_links SET view_count = view_count + 1 WHERE id = ?",
                    (link_id,)
                )

            conn.commit()

            # Log view event
            self._log_event(conn, link_id, 'viewed', {'first_view': first_view is None})

            return True
        finally:
            conn.close()

    def mark_arrived(self, code: str) -> bool:
        """
        Mark tracking link as arrived

        Args:
            code: Tracking code

        Returns:
            True if updated, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM tracking_links WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            link_id = row['id']

            conn.execute(
                """UPDATE tracking_links
                   SET status = 'arrived', arrived_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (link_id,)
            )
            conn.commit()

            # Log arrival event
            self._log_event(conn, link_id, 'arrived', {})

            logger.info(f"Tracking link {code} marked as arrived")
            return True
        finally:
            conn.close()

    def mark_expired(self, code: str) -> bool:
        """Mark tracking link as expired"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE tracking_links SET status = 'expired' WHERE code = ?",
                (code,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_cancelled(self, code: str) -> bool:
        """Mark tracking link as cancelled"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE tracking_links SET status = 'cancelled' WHERE code = ?",
                (code,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def expire_old_links(self) -> int:
        """
        Expire links that have passed their expiry time

        Returns:
            Number of links expired
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE tracking_links
                   SET status = 'expired'
                   WHERE status = 'active'
                   AND expires_at < CURRENT_TIMESTAMP"""
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"Expired {count} tracking links")
            return count
        finally:
            conn.close()

    def cleanup_old_links(self, days: int = 7) -> int:
        """
        Delete old tracking links

        Args:
            days: Delete links older than this many days

        Returns:
            Number of links deleted
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """DELETE FROM tracking_links
                   WHERE created_at < datetime('now', '-' || ? || ' days')
                   AND status IN ('expired', 'cancelled', 'arrived')""",
                (days,)
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"Cleaned up {count} old tracking links")
            return count
        finally:
            conn.close()

    def get_all_active_links(self) -> List[Dict[str, Any]]:
        """Get all active tracking links"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM tracking_links
                   WHERE status = 'active'
                   ORDER BY created_at DESC"""
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_active_links_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """
        Get active tracking links for a phone number

        Args:
            phone: Customer phone number (normalized to digits only)

        Returns:
            List of active tracking links for this phone
        """
        # Normalize phone - keep only digits for comparison
        normalized = ''.join(c for c in phone if c.isdigit())
        if len(normalized) < 8:
            return []

        conn = self.get_connection()
        try:
            # Look for active links where the stored phone ends with these digits
            # This handles cases where country codes may differ
            cursor = conn.execute(
                """SELECT * FROM tracking_links
                   WHERE status = 'active'
                   AND customer_phone IS NOT NULL
                   AND REPLACE(REPLACE(REPLACE(customer_phone, ' ', ''), '-', ''), '+', '') LIKE '%' || ?
                   ORDER BY created_at DESC""",
                (normalized[-10:],)  # Match last 10 digits
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════
    # Event logging
    # ══════════════════════════════════════════════════════════════

    def _log_event(
        self,
        conn: sqlite3.Connection,
        link_id: int,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """Log a tracking event"""
        conn.execute(
            """INSERT INTO tracking_events (tracking_link_id, event_type, event_data)
               VALUES (?, ?, ?)""",
            (link_id, event_type, json.dumps(event_data))
        )
        conn.commit()

    def get_link_events(self, link_id: int) -> List[Dict[str, Any]]:
        """Get events for a tracking link"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM tracking_events
                   WHERE tracking_link_id = ?
                   ORDER BY created_at ASC""",
                (link_id,)
            )
            events = []
            for row in cursor.fetchall():
                event = dict(row)
                if event.get('event_data'):
                    event['event_data'] = json.loads(event['event_data'])
                events.append(event)
            return events
        finally:
            conn.close()


# Global database instance
db = Database()
