"""
SQLite database management for external staff
"""
import sqlite3
import os
from datetime import datetime
from config import config


class ExternalStaffDB:
    """
    Database handler for external staff management
    """

    def __init__(self):
        """Initialize database connection and create tables if needed"""
        self.db_path = config.database_path

        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Create database tables if they don't exist"""
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema = f.read()

        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.commit()
        conn.close()

    def _get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def is_approved(self, email):
        """
        Check if an email address is approved

        Args:
            email: Email address to check

        Returns:
            Dict with approval status and staff info, or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM external_staff WHERE email = ? AND status = 'active'",
            (email.lower(),)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'approved': True,
                'id': row['id'],
                'name': row['name'],
                'email': row['email'],
                'phone': row['phone'],
                'role': row['role']
            }

        return {'approved': False}

    def get_all_staff(self, status=None):
        """
        Get all external staff members

        Args:
            status: Filter by status ('active', 'inactive', or None for all)

        Returns:
            List of staff dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM external_staff WHERE status = ? ORDER BY name",
                (status,)
            )
        else:
            cursor.execute("SELECT * FROM external_staff ORDER BY name")

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def add_staff(self, name, email, phone='', role='', added_by='', notes=''):
        """
        Add a new external staff member

        Args:
            name: Full name
            email: Email address (must be unique)
            phone: Phone number (optional)
            role: Role/position (optional)
            added_by: Email of person who added them
            notes: Additional notes (optional)

        Returns:
            Dict with success status and staff ID, or error
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO external_staff
                   (name, email, phone, role, added_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, email.lower(), phone, role, added_by, notes)
            )
            conn.commit()
            staff_id = cursor.lastrowid
            conn.close()

            return {
                'success': True,
                'id': staff_id,
                'message': f'Added {name} ({email})'
            }

        except sqlite3.IntegrityError:
            conn.close()
            return {
                'error': f'Email {email} already exists in the database'
            }
        except Exception as e:
            conn.close()
            return {
                'error': f'Database error: {str(e)}'
            }

    def update_staff(self, staff_id, name=None, email=None, phone=None, role=None, status=None, notes=None):
        """
        Update an existing staff member

        Args:
            staff_id: Staff member ID
            name: New name (optional)
            email: New email (optional)
            phone: New phone (optional)
            role: New role (optional)
            status: New status (optional)
            notes: New notes (optional)

        Returns:
            Dict with success status or error
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build update query dynamically
        updates = []
        values = []

        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if email is not None:
            updates.append("email = ?")
            values.append(email.lower())
        if phone is not None:
            updates.append("phone = ?")
            values.append(phone)
        if role is not None:
            updates.append("role = ?")
            values.append(role)
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)

        if not updates:
            conn.close()
            return {'error': 'No fields to update'}

        updates.append("modified_date = ?")
        values.append(datetime.now().isoformat())
        values.append(staff_id)

        try:
            cursor.execute(
                f"UPDATE external_staff SET {', '.join(updates)} WHERE id = ?",
                values
            )
            conn.commit()

            if cursor.rowcount == 0:
                conn.close()
                return {'error': 'Staff member not found'}

            conn.close()
            return {
                'success': True,
                'message': f'Updated staff member ID {staff_id}'
            }

        except Exception as e:
            conn.close()
            return {
                'error': f'Database error: {str(e)}'
            }

    def get_staff_by_id(self, staff_id):
        """Get a staff member by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM external_staff WHERE id = ?", (staff_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def delete_staff(self, staff_id):
        """
        Delete (actually deactivate) a staff member

        Args:
            staff_id: Staff member ID

        Returns:
            Dict with success status or error
        """
        # We don't actually delete, we deactivate
        return self.update_staff(staff_id, status='inactive')


# Global database instance
db = ExternalStaffDB()
