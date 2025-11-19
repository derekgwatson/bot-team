"""
Database service for Rita's access request system.
"""

import sqlite3
import os
from shared.migrations import MigrationRunner


class AccessDatabase:
    """SQLite database for access request workflow"""

    def __init__(self, db_path="database/rita.db"):
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure DB exists and apply migrations"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        runner = MigrationRunner(db_path=self.db_path, migrations_dir=migrations_dir)
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get connection to Rita's DB"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─────────────────────────────────────────────────────────────
    # ACCESS REQUEST LOGIC
    # ─────────────────────────────────────────────────────────────

    def submit_access_request(self, name, email, phone=None, reason=None, request_type="allstaff_email"):
        """Submit a new access request"""

        conn = self.get_connection()

        # Check for existing pending request
        cursor = conn.execute(
            "SELECT id FROM access_requests WHERE email = ? AND status = 'pending'",
            (email,),
        )
        if cursor.fetchone():
            conn.close()
            return {
                "error": "A request for this email is already pending review",
                "already_pending": True,
            }

        # Create request
        cursor = conn.execute(
            """
            INSERT INTO access_requests (name, email, phone, reason, request_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, phone or "", reason or "", request_type),
        )

        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "success": True,
            "request_id": request_id,
            "message": "Access request submitted successfully",
        }

    def get_access_requests(self, status="pending"):
        """Return requests (filtered by status)"""
        conn = self.get_connection()

        if status:
            cursor = conn.execute(
                """
                SELECT * FROM access_requests
                WHERE status = ?
                ORDER BY created_date DESC
                """,
                (status,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM access_requests ORDER BY created_date DESC"
            )

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_access_request_by_id(self, request_id):
        conn = self.get_connection()
        cursor = conn.execute(
            "SELECT * FROM access_requests WHERE id = ?", (request_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def approve_access_request(self, request_id, reviewed_by, notes=None):
        """Approve a request (does NOT touch Peter's DB)"""

        conn = self.get_connection()

        cursor = conn.execute(
            "SELECT * FROM access_requests WHERE id = ?", (request_id,)
        )
        request = cursor.fetchone()

        if not request:
            conn.close()
            return {"error": "Request not found"}

        if request["status"] != "pending":
            conn.close()
            return {"error": f"Request is already {request['status']}"}

        conn.execute(
            """
            UPDATE access_requests
            SET status = 'approved',
                reviewed_by = ?,
                notes = ?,
                modified_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reviewed_by, notes or "", request_id),
        )

        conn.commit()
        conn.close()

        return {"success": True, "message": f"Approved {request['name']}"}

    def deny_access_request(self, request_id, reviewed_by, notes=None):
        """Deny a request"""

        conn = self.get_connection()

        cursor = conn.execute(
            "SELECT * FROM access_requests WHERE id = ?", (request_id,)
        )
        request = cursor.fetchone()

        if not request:
            conn.close()
            return {"error": "Request not found"}

        conn.execute(
            """
            UPDATE access_requests
            SET status = 'denied',
                reviewed_by = ?,
                notes = ?,
                modified_date = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reviewed_by, notes or "", request_id),
        )

        conn.commit()
        conn.close()

        return {"success": True, "message": f"Denied {request['name']}"}


# Singleton instance
access_db = AccessDatabase()
