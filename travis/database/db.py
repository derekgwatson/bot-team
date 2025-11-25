"""
Travis Database Manager
Handles SQLite database connections and operations for location tracking
"""

import sqlite3
import secrets
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from shared.migrations import MigrationRunner

logger = logging.getLogger(__name__)


class Database:
    """
    Database manager for Travis's SQLite database
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'travis.db'

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

    # ══════════════════════════════════════════════════════════════
    # Staff operations
    # ══════════════════════════════════════════════════════════════

    def create_staff(self, name: str, email: str) -> Dict[str, Any]:
        """
        Create a new staff member

        Args:
            name: Staff member's name
            email: Staff member's email (unique identifier)

        Returns:
            Staff dictionary with generated device_token
        """
        device_token = secrets.token_urlsafe(32)

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO staff (name, email, device_token)
                   VALUES (?, ?, ?)""",
                (name, email, device_token)
            )
            conn.commit()
            staff_id = cursor.lastrowid
            logger.info(f"Created staff: {name} ({email})")

            return self.get_staff_by_id(staff_id)
        finally:
            conn.close()

    def get_staff_by_id(self, staff_id: int) -> Optional[Dict[str, Any]]:
        """Get staff member by ID"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM staff WHERE id = ?",
                (staff_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_staff_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get staff member by email"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM staff WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_staff_by_token(self, device_token: str) -> Optional[Dict[str, Any]]:
        """Get staff member by device token (for authentication)"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM staff WHERE device_token = ?",
                (device_token,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_staff(self) -> List[Dict[str, Any]]:
        """Get all staff members"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM staff ORDER BY name"
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_staff_status(self, staff_id: int, status: str) -> bool:
        """
        Update staff member's current status

        Args:
            staff_id: Staff ID
            status: New status (off_duty, in_transit, at_customer, on_break)

        Returns:
            True if updated, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE staff SET current_status = ? WHERE id = ?",
                (status, staff_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def regenerate_device_token(self, staff_id: int) -> Optional[str]:
        """
        Generate a new device token for a staff member

        Args:
            staff_id: Staff ID

        Returns:
            New device token or None if staff not found
        """
        new_token = secrets.token_urlsafe(32)
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE staff SET device_token = ? WHERE id = ?",
                (new_token, staff_id)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Regenerated device token for staff {staff_id}")
                return new_token
            return None
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════
    # Journey operations
    # ══════════════════════════════════════════════════════════════

    def create_journey(
        self,
        staff_id: int,
        job_reference: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_address: Optional[str] = None,
        customer_lat: Optional[float] = None,
        customer_lng: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new journey for a staff member

        Args:
            staff_id: Staff member ID
            job_reference: External job/appointment reference
            customer_name: Customer's name
            customer_address: Destination address
            customer_lat: Destination latitude (for geofencing)
            customer_lng: Destination longitude (for geofencing)

        Returns:
            Journey dictionary
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO journeys
                   (staff_id, job_reference, customer_name, customer_address, customer_lat, customer_lng)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (staff_id, job_reference, customer_name, customer_address, customer_lat, customer_lng)
            )
            conn.commit()
            journey_id = cursor.lastrowid
            logger.info(f"Created journey {journey_id} for staff {staff_id}")

            return self.get_journey_by_id(journey_id)
        finally:
            conn.close()

    def get_journey_by_id(self, journey_id: int) -> Optional[Dict[str, Any]]:
        """Get journey by ID"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM journeys WHERE id = ?",
                (journey_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_active_journey(self, staff_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the active journey for a staff member

        Args:
            staff_id: Staff member ID

        Returns:
            Active journey (in_progress status) or None
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM journeys
                   WHERE staff_id = ? AND status = 'in_progress'
                   ORDER BY started_at DESC LIMIT 1""",
                (staff_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_journey_by_job_reference(self, job_reference: str) -> Optional[Dict[str, Any]]:
        """Get journey by external job reference"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM journeys WHERE job_reference = ? ORDER BY created_at DESC LIMIT 1",
                (job_reference,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def start_journey(self, journey_id: int) -> bool:
        """
        Mark a journey as started (in_progress)

        Args:
            journey_id: Journey ID

        Returns:
            True if updated, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE journeys
                   SET status = 'in_progress', started_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (journey_id,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Started journey {journey_id}")
                return True
            return False
        finally:
            conn.close()

    def arrive_journey(self, journey_id: int) -> bool:
        """
        Mark a journey as arrived

        Args:
            journey_id: Journey ID

        Returns:
            True if updated, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE journeys
                   SET status = 'arrived', arrived_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (journey_id,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Journey {journey_id} arrived")
                return True
            return False
        finally:
            conn.close()

    def complete_journey(self, journey_id: int) -> bool:
        """
        Mark a journey as completed

        Args:
            journey_id: Journey ID

        Returns:
            True if updated, False if not found
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """UPDATE journeys
                   SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (journey_id,)
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Completed journey {journey_id}")
                return True
            return False
        finally:
            conn.close()

    def cancel_journey(self, journey_id: int) -> bool:
        """Cancel a journey"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "UPDATE journeys SET status = 'cancelled' WHERE id = ?",
                (journey_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_staff_journeys(
        self,
        staff_id: int,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get journeys for a staff member

        Args:
            staff_id: Staff member ID
            status: Optional status filter
            limit: Maximum number of journeys to return

        Returns:
            List of journey dictionaries
        """
        conn = self.get_connection()
        try:
            if status:
                cursor = conn.execute(
                    """SELECT * FROM journeys
                       WHERE staff_id = ? AND status = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (staff_id, status, limit)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM journeys
                       WHERE staff_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (staff_id, limit)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════
    # Location ping operations
    # ══════════════════════════════════════════════════════════════

    def record_ping(
        self,
        staff_id: int,
        latitude: float,
        longitude: float,
        journey_id: Optional[int] = None,
        accuracy: Optional[float] = None,
        heading: Optional[float] = None,
        speed: Optional[float] = None,
        altitude: Optional[float] = None,
        battery_level: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ) -> int:
        """
        Record a location ping from a device

        Args:
            staff_id: Staff member ID
            latitude: GPS latitude
            longitude: GPS longitude
            journey_id: Associated journey ID (if on a journey)
            accuracy: GPS accuracy in meters
            heading: Direction of travel (0-360)
            speed: Speed in m/s
            altitude: Altitude in meters
            battery_level: Device battery percentage

        Returns:
            Ping ID
        """
        conn = self.get_connection()
        try:
            if timestamp:
                cursor = conn.execute(
                    """INSERT INTO location_pings
                       (staff_id, journey_id, latitude, longitude, accuracy, heading, speed, altitude, battery_level, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (staff_id, journey_id, latitude, longitude, accuracy, heading, speed, altitude, battery_level, timestamp)
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO location_pings
                       (staff_id, journey_id, latitude, longitude, accuracy, heading, speed, altitude, battery_level)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (staff_id, journey_id, latitude, longitude, accuracy, heading, speed, altitude, battery_level)
                )
            conn.commit()

            # Update staff's last ping timestamp
            conn.execute(
                "UPDATE staff SET last_ping_at = CURRENT_TIMESTAMP WHERE id = ?",
                (staff_id,)
            )
            conn.commit()

            return cursor.lastrowid
        finally:
            conn.close()

    def get_latest_ping(self, staff_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the most recent location ping for a staff member

        Args:
            staff_id: Staff member ID

        Returns:
            Latest ping dictionary or None
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM location_pings
                   WHERE staff_id = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (staff_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_journey_pings(
        self,
        journey_id: int,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get location pings for a specific journey

        Args:
            journey_id: Journey ID
            limit: Maximum number of pings to return

        Returns:
            List of ping dictionaries (oldest first for path drawing)
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM location_pings
                   WHERE journey_id = ?
                   ORDER BY timestamp ASC LIMIT ?""",
                (journey_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_recent_pings(
        self,
        staff_id: int,
        minutes: int = 60,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent pings for a staff member

        Args:
            staff_id: Staff member ID
            minutes: How many minutes back to look
            limit: Maximum pings to return

        Returns:
            List of ping dictionaries (newest first)
        """
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """SELECT * FROM location_pings
                   WHERE staff_id = ?
                   AND timestamp > datetime('now', '-' || ? || ' minutes')
                   ORDER BY timestamp DESC LIMIT ?""",
                (staff_id, minutes, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def cleanup_old_pings(self, hours: int = 48) -> int:
        """
        Delete pings older than specified hours for completed/cancelled journeys

        Args:
            hours: Hours to keep pings

        Returns:
            Number of pings deleted
        """
        conn = self.get_connection()
        try:
            # Delete old pings for completed/cancelled journeys
            cursor = conn.execute(
                """DELETE FROM location_pings
                   WHERE journey_id IN (
                       SELECT id FROM journeys
                       WHERE status IN ('completed', 'cancelled')
                   )
                   AND timestamp < datetime('now', '-' || ? || ' hours')""",
                (hours,)
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"Cleaned up {count} old location pings")
            return count
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════
    # Privacy-aware location retrieval
    # ══════════════════════════════════════════════════════════════

    def get_shareable_location(self, staff_id: int) -> Dict[str, Any]:
        """
        Get location data that's safe to share with customers.
        Only returns coordinates when staff is 'in_transit'.

        Args:
            staff_id: Staff member ID

        Returns:
            Dict with shareable location info or status message
        """
        staff = self.get_staff_by_id(staff_id)
        if not staff:
            return {"shareable": False, "error": "Staff not found"}

        status = staff.get("current_status", "off_duty")

        if status == "in_transit":
            # Safe to share location
            ping = self.get_latest_ping(staff_id)
            if ping:
                return {
                    "shareable": True,
                    "status": "in_transit",
                    "latitude": ping["latitude"],
                    "longitude": ping["longitude"],
                    "heading": ping.get("heading"),
                    "speed": ping.get("speed"),
                    "timestamp": ping["timestamp"]
                }
            else:
                return {
                    "shareable": False,
                    "status": "in_transit",
                    "message": "Location not yet available"
                }

        elif status == "at_customer":
            # Don't share location - they're at another customer's home
            return {
                "shareable": False,
                "status": "at_customer",
                "message": "Currently with previous customer"
            }

        elif status == "on_break":
            return {
                "shareable": False,
                "status": "on_break",
                "message": "On break"
            }

        else:  # off_duty or unknown
            return {
                "shareable": False,
                "status": status,
                "message": "Not currently active"
            }


# Global database instance
db = Database()
