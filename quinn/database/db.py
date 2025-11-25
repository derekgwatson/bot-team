"""
SQLite database management for external staff
"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from config import config
from shared.migrations import MigrationRunner


class ExternalStaffDB:
    """
    Database handler for external staff management
    """

    def __init__(self, db_path=None):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path or config.database_path

        # Ensure database directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # Only create directory if path has a directory component
            os.makedirs(db_dir, exist_ok=True)

        # Run migrations
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)

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

    def submit_request(self, name, email, phone='', reason=''):
        """
        Submit a new access request

        Args:
            name: Full name
            email: Email address
            phone: Phone number (optional)
            reason: Reason for access request (optional)

        Returns:
            Dict with success status and request ID, or error
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if already approved
            existing = self.is_approved(email)
            if existing.get('approved'):
                conn.close()
                return {
                    'error': 'This email is already approved',
                    'already_approved': True
                }

            # Check for existing pending request
            cursor.execute(
                "SELECT id FROM pending_requests WHERE email = ? AND status = 'pending'",
                (email.lower(),)
            )
            if cursor.fetchone():
                conn.close()
                return {
                    'error': 'A pending request already exists for this email',
                    'already_pending': True
                }

            cursor.execute(
                """INSERT INTO pending_requests
                   (name, email, phone, reason)
                   VALUES (?, ?, ?, ?)""",
                (name, email.lower(), phone, reason)
            )
            conn.commit()
            request_id = cursor.lastrowid
            conn.close()

            return {
                'success': True,
                'id': request_id,
                'message': f'Access request submitted for {email}'
            }

        except Exception as e:
            conn.close()
            return {
                'error': f'Database error: {str(e)}'
            }

    def get_pending_requests(self, status='pending'):
        """
        Get pending access requests

        Args:
            status: Filter by status ('pending', 'approved', 'denied', or None for all)

        Returns:
            List of request dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM pending_requests WHERE status = ? ORDER BY request_date DESC",
                (status,)
            )
        else:
            cursor.execute("SELECT * FROM pending_requests ORDER BY request_date DESC")

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_request_by_id(self, request_id):
        """Get a pending request by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pending_requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def approve_request(self, request_id, reviewed_by):
        """
        Approve an access request and add to external_staff

        Args:
            request_id: Request ID
            reviewed_by: Email of person approving

        Returns:
            Dict with success status or error
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get the request
            request = self.get_request_by_id(request_id)
            if not request:
                return {'error': 'Request not found'}

            if request['status'] != 'pending':
                return {'error': 'Request has already been processed'}

            # Add to external_staff table
            result = self.add_staff(
                name=request['name'],
                email=request['email'],
                phone=request['phone'],
                role='',
                added_by=reviewed_by,
                notes=f"Approved from access request (ID: {request_id})"
            )

            if 'error' in result:
                # If already exists, that's okay - they're already approved
                if 'already exists' in result['error']:
                    pass
                else:
                    return result

            # Update request status
            cursor.execute(
                """UPDATE pending_requests
                   SET status = 'approved',
                       reviewed_by = ?,
                       reviewed_date = ?
                   WHERE id = ?""",
                (reviewed_by, datetime.now().isoformat(), request_id)
            )
            conn.commit()
            conn.close()

            return {
                'success': True,
                'message': f"Approved access for {request['email']}"
            }

        except Exception as e:
            conn.close()
            return {
                'error': f'Database error: {str(e)}'
            }

    def deny_request(self, request_id, reviewed_by, notes=''):
        """
        Deny an access request

        Args:
            request_id: Request ID
            reviewed_by: Email of person denying
            notes: Reason for denial (optional)

        Returns:
            Dict with success status or error
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get the request
            request = self.get_request_by_id(request_id)
            if not request:
                return {'error': 'Request not found'}

            if request['status'] != 'pending':
                return {'error': 'Request has already been processed'}

            # Update request status
            cursor.execute(
                """UPDATE pending_requests
                   SET status = 'denied',
                       reviewed_by = ?,
                       reviewed_date = ?,
                       notes = ?
                   WHERE id = ?""",
                (reviewed_by, datetime.now().isoformat(), notes, request_id)
            )
            conn.commit()
            conn.close()

            return {
                'success': True,
                'message': f"Denied access for {request['email']}"
            }

        except Exception as e:
            conn.close()
            return {
                'error': f'Database error: {str(e)}'
            }


# Global database instance
# Only instantiate if not in testing mode (tests will create their own instances)
db = None
if not os.environ.get('TESTING'):
    try:
        db = ExternalStaffDB()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        print("Database will need to be manually initialized.")


def get_db():
    """
    Get the database instance, initializing it if necessary.
    This is useful for lazy initialization in production.
    """
    global db
    if db is None:
        db = ExternalStaffDB()
    return db
