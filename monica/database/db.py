"""
Monica Database Manager
Handles SQLite database connections and initialization
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from shared.migrations import MigrationRunner

logger = logging.getLogger(__name__)


class Database:
    """
    Database manager for Monica's SQLite database
    Follows the pattern from Oscar/Quinn bots
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'monica.db'

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

    # Store operations

    def get_or_create_store(self, store_code: str, display_name: Optional[str] = None) -> int:
        """
        Get existing store or create new one

        Args:
            store_code: Unique store code (e.g., "FYSHWICK")
            display_name: Optional display name for the store

        Returns:
            Store ID
        """
        conn = self.get_connection()
        try:
            # Try to get existing store
            cursor = conn.execute(
                "SELECT id FROM stores WHERE store_code = ?",
                (store_code,)
            )
            row = cursor.fetchone()

            if row:
                return row['id']

            # Create new store
            if display_name is None:
                display_name = store_code

            cursor = conn.execute(
                "INSERT INTO stores (store_code, display_name) VALUES (?, ?)",
                (store_code, display_name)
            )
            conn.commit()
            logger.info(f"Created new store: {store_code}")
            return cursor.lastrowid
        finally:
            conn.close()

    def get_all_stores(self) -> List[Dict[str, Any]]:
        """
        Get all stores

        Returns:
            List of store dictionaries
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM stores ORDER BY store_code")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # Device operations

    def get_or_create_device(self, store_id: int, device_label: str, agent_token: str) -> Dict[str, Any]:
        """
        Get existing device or create new one

        Args:
            store_id: Store ID
            device_label: Device label (e.g., "Front Counter")
            agent_token: Unique agent token for authentication

        Returns:
            Device dictionary
        """
        conn = self.get_connection()
        try:
            # Try to get existing device
            cursor = conn.execute(
                "SELECT * FROM devices WHERE store_id = ? AND device_label = ?",
                (store_id, device_label)
            )
            row = cursor.fetchone()

            if row:
                # Update token if different (device re-registration)
                if row['agent_token'] != agent_token:
                    conn.execute(
                        "UPDATE devices SET agent_token = ? WHERE id = ?",
                        (agent_token, row['id'])
                    )
                    conn.commit()
                    logger.info(f"Updated token for device {row['id']}")

                    # Fetch updated device to get the new token
                    cursor = conn.execute("SELECT * FROM devices WHERE id = ?", (row['id'],))
                    return dict(cursor.fetchone())

                return dict(row)

            # Create new device
            cursor = conn.execute(
                """INSERT INTO devices (store_id, device_label, agent_token, last_status)
                   VALUES (?, ?, ?, 'offline')""",
                (store_id, device_label, agent_token)
            )
            conn.commit()
            logger.info(f"Created new device: {device_label} at store {store_id}")

            # Fetch the newly created device
            cursor = conn.execute("SELECT * FROM devices WHERE id = ?", (cursor.lastrowid,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_device_by_token(self, agent_token: str) -> Optional[Dict[str, Any]]:
        """
        Get device by agent token with store information

        Args:
            agent_token: Agent token

        Returns:
            Device dictionary with store info or None if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    d.*,
                    s.store_code,
                    s.display_name as store_display_name
                FROM devices d
                JOIN stores s ON d.store_id = s.id
                WHERE d.agent_token = ?
            """, (agent_token,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_device_heartbeat(self, device_id: int, status: str, public_ip: Optional[str] = None):
        """
        Update device's last heartbeat timestamp and status

        Args:
            device_id: Device ID
            status: Status ('online', 'degraded', 'offline')
            public_ip: Optional public IP address
        """
        conn = self.get_connection()
        try:
            conn.execute(
                """UPDATE devices
                   SET last_heartbeat_at = CURRENT_TIMESTAMP,
                       last_status = ?,
                       last_public_ip = COALESCE(?, last_public_ip)
                   WHERE id = ?""",
                (status, public_ip, device_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_devices_with_stores(self) -> List[Dict[str, Any]]:
        """
        Get all devices with their store information

        Returns:
            List of device dictionaries with store info
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    d.*,
                    s.store_code,
                    s.display_name as store_display_name
                FROM devices d
                JOIN stores s ON d.store_id = s.id
                ORDER BY s.store_code, d.device_label
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_device(self, device_id: int) -> bool:
        """
        Delete a device and all its associated heartbeats

        Args:
            device_id: Device ID to delete

        Returns:
            True if device was deleted, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM devices WHERE id = ?",
                (device_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted device {device_id}")
            return deleted
        finally:
            conn.close()

    # Heartbeat operations

    def record_heartbeat(
        self,
        device_id: int,
        public_ip: str,
        user_agent: Optional[str] = None,
        latency_ms: Optional[float] = None,
        download_mbps: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Record a heartbeat from a device

        Args:
            device_id: Device ID
            public_ip: Public IP address
            user_agent: User agent string
            latency_ms: Latency in milliseconds
            download_mbps: Download speed in Mbps
            timestamp: Optional timestamp (uses current time if None)

        Returns:
            Heartbeat ID
        """
        conn = self.get_connection()
        try:
            if timestamp:
                cursor = conn.execute(
                    """INSERT INTO heartbeats
                       (device_id, timestamp, public_ip, user_agent, latency_ms, download_mbps)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (device_id, timestamp, public_ip, user_agent, latency_ms, download_mbps)
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO heartbeats
                       (device_id, public_ip, user_agent, latency_ms, download_mbps)
                       VALUES (?, ?, ?, ?, ?)""",
                    (device_id, public_ip, user_agent, latency_ms, download_mbps)
                )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_device_heartbeats(
        self,
        device_id: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent heartbeats for a device

        Args:
            device_id: Device ID
            limit: Maximum number of heartbeats to return

        Returns:
            List of heartbeat dictionaries
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM heartbeats
                   WHERE device_id = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (device_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def cleanup_old_heartbeats(self, days: int = 30):
        """
        Delete heartbeats older than specified days

        Args:
            days: Number of days to keep
        """
        conn = self.get_connection()
        try:
            conn.execute(
                """DELETE FROM heartbeats
                   WHERE timestamp < datetime('now', '-' || ? || ' days')""",
                (days,)
            )
            conn.commit()
            logger.info(f"Cleaned up heartbeats older than {days} days")
        finally:
            conn.close()

    # Registration code operations

    def create_registration_code(
        self,
        store_code: str,
        device_label: str,
        code: Optional[str] = None,
        expires_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Create a one-time registration code

        Args:
            store_code: Store code for this device
            device_label: Device label for this device
            code: Optional custom code (auto-generated if None)
            expires_hours: Hours until expiration (default 24)

        Returns:
            Registration code dictionary
        """
        import secrets

        if code is None:
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO registration_codes
                   (code, store_code, device_label, expires_at)
                   VALUES (?, ?, ?, datetime('now', '+' || ? || ' hours'))""",
                (code, store_code, device_label, expires_hours)
            )
            conn.commit()

            # Fetch the created code
            cursor = conn.execute(
                "SELECT * FROM registration_codes WHERE id = ?",
                (cursor.lastrowid,)
            )
            result = dict(cursor.fetchone())
            logger.info(f"Created registration code {code} for {store_code}/{device_label}")
            return result
        finally:
            conn.close()

    def get_registration_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get a registration code if it's valid and unused

        Args:
            code: Registration code

        Returns:
            Registration code dictionary or None if invalid/used/expired
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM registration_codes
                   WHERE code = ?
                   AND used_at IS NULL
                   AND (expires_at IS NULL OR expires_at > datetime('now'))""",
                (code,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_registration_code_by_code(self, code: str):
        """
        Delete a registration code after use

        Args:
            code: Registration code to delete
        """
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM registration_codes WHERE code = ?", (code,))
            conn.commit()
            logger.info(f"Deleted registration code {code}")
        finally:
            conn.close()

    def cleanup_expired_codes(self) -> int:
        """
        Delete all expired registration codes

        Returns:
            Number of codes deleted
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """DELETE FROM registration_codes
                   WHERE expires_at IS NOT NULL
                   AND expires_at <= datetime('now')"""
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"Cleaned up {count} expired registration codes")
            return count
        finally:
            conn.close()

    def get_all_registration_codes(self) -> List[Dict[str, Any]]:
        """
        Get all registration codes (for admin view)

        Returns:
            List of registration code dictionaries
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM registration_codes
                   ORDER BY created_at DESC"""
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_registration_code(self, code_id: int) -> bool:
        """
        Delete a registration code

        Args:
            code_id: Registration code ID

        Returns:
            True if deleted, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM registration_codes WHERE id = ?",
                (code_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted registration code {code_id}")
            return deleted
        finally:
            conn.close()


# Global database instance
db = Database()
