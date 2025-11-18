"""
Database service for Peter's staff database
"""
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.migrations import MigrationRunner

class StaffDatabase:
    """SQLite database for staff information"""

    def __init__(self, db_path='database/staff.db'):
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database and tables exist using migrations"""
        # Create database directory if needed
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        # Run migrations
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        runner = MigrationRunner(db_path=self.db_path, migrations_dir=migrations_dir)
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_staff(self, status='active'):
        """
        Get all staff members

        Args:
            status: Filter by status ('active', 'inactive', 'all')

        Returns:
            List of staff dictionaries
        """
        conn = self.get_connection()

        if status == 'all':
            cursor = conn.execute('SELECT * FROM staff ORDER BY section, name')
        else:
            cursor = conn.execute(
                'SELECT * FROM staff WHERE status = ? ORDER BY section, name',
                (status,)
            )

        staff = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return staff

    def get_phone_list_staff(self):
        """
        Get staff who should appear on the phone list

        Returns:
            List of staff dictionaries
        """
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT * FROM staff WHERE show_on_phone_list = 1 AND status = ? ORDER BY section, name',
            ('active',)
        )

        staff = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return staff

    def get_allstaff_members(self):
        """
        Get email addresses for all-staff group

        Returns:
            List of email addresses (both work and personal)
        """
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT work_email, personal_email FROM staff WHERE include_in_allstaff = 1 AND status = ?',
            ('active',)
        )

        emails = []
        for row in cursor.fetchall():
            # Add work email if present
            if row['work_email']:
                emails.append(row['work_email'])
            # Add personal email if present and no work email
            elif row['personal_email']:
                emails.append(row['personal_email'])

        conn.close()
        return emails

    def search_staff(self, query):
        """
        Search for staff by name, extension, or phone

        Args:
            query: Search string

        Returns:
            List of matching staff dictionaries
        """
        conn = self.get_connection()

        # Use LIKE for partial matching
        search_pattern = f'%{query}%'

        cursor = conn.execute('''
            SELECT * FROM staff
            WHERE (name LIKE ? OR
                   extension LIKE ? OR
                   phone_fixed LIKE ? OR
                   phone_mobile LIKE ? OR
                   work_email LIKE ?)
            AND status = ?
            ORDER BY name
        ''', (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, 'active'))

        staff = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return staff

    def get_staff_by_id(self, staff_id):
        """
        Get a staff member by ID

        Args:
            staff_id: Staff ID

        Returns:
            Staff dictionary or None
        """
        conn = self.get_connection()
        cursor = conn.execute('SELECT * FROM staff WHERE id = ?', (staff_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def add_staff(self, name, position='', section='', extension='', phone_fixed='',
                  phone_mobile='', work_email='', personal_email='',
                  zendesk_access=False, buz_access=False, google_access=False,
                  wiki_access=False, voip_access=False,
                  show_on_phone_list=True, include_in_allstaff=True,
                  status='active', created_by='system', notes=''):
        """
        Add a new staff member

        Returns:
            Dictionary with success status and staff ID
        """
        # Validate extension matches fixed line if both provided
        if extension and phone_fixed:
            fixed_digits = ''.join(c for c in phone_fixed if c.isdigit())
            if len(fixed_digits) >= 4:
                last_four = fixed_digits[-4:]
                if extension != last_four:
                    return {
                        'error': f'Extension {extension} does not match last 4 digits of fixed line ({last_four})'
                    }

        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO staff (
                name, position, section, extension, phone_fixed, phone_mobile,
                work_email, personal_email,
                zendesk_access, buz_access, google_access, wiki_access, voip_access,
                show_on_phone_list, include_in_allstaff, status,
                created_by, modified_by, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, position, section, extension, phone_fixed, phone_mobile,
            work_email, personal_email,
            1 if zendesk_access else 0,
            1 if buz_access else 0,
            1 if google_access else 0,
            1 if wiki_access else 0,
            1 if voip_access else 0,
            1 if show_on_phone_list else 0,
            1 if include_in_allstaff else 0,
            status,
            created_by, created_by, notes
        ))

        staff_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            'success': True,
            'id': staff_id,
            'message': f'Added {name}'
        }

    def update_staff(self, staff_id, modified_by='system', **kwargs):
        """
        Update a staff member

        Args:
            staff_id: Staff ID
            modified_by: Who made the update
            **kwargs: Fields to update

        Returns:
            Dictionary with success status
        """
        # Validate extension matches fixed line if both provided
        if 'extension' in kwargs and 'phone_fixed' in kwargs:
            extension = kwargs['extension']
            phone_fixed = kwargs['phone_fixed']
            if extension and phone_fixed:
                fixed_digits = ''.join(c for c in phone_fixed if c.isdigit())
                if len(fixed_digits) >= 4:
                    last_four = fixed_digits[-4:]
                    if extension != last_four:
                        return {
                            'error': f'Extension {extension} does not match last 4 digits of fixed line ({last_four})'
                        }

        # Build update query dynamically
        valid_fields = [
            'name', 'position', 'section', 'extension', 'phone_fixed', 'phone_mobile',
            'work_email', 'personal_email',
            'zendesk_access', 'buz_access', 'google_access', 'wiki_access', 'voip_access',
            'show_on_phone_list', 'include_in_allstaff', 'status', 'notes', 'finish_date'
        ]

        update_fields = []
        values = []

        for key, value in kwargs.items():
            if key in valid_fields:
                update_fields.append(f'{key} = ?')
                # Convert booleans to integers for SQLite
                if isinstance(value, bool):
                    values.append(1 if value else 0)
                else:
                    values.append(value)

        if not update_fields:
            return {'error': 'No valid fields to update'}

        # Add modified_by
        update_fields.append('modified_by = ?')
        values.append(modified_by)

        # Add staff_id for WHERE clause
        values.append(staff_id)

        conn = self.get_connection()
        query = f'UPDATE staff SET {", ".join(update_fields)} WHERE id = ?'
        conn.execute(query, values)
        conn.commit()

        # Get updated staff
        cursor = conn.execute('SELECT name FROM staff WHERE id = ?', (staff_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'success': True,
                'message': f'Updated {row["name"]}'
            }
        else:
            return {'error': 'Staff member not found'}

    def delete_staff(self, staff_id):
        """
        Delete a staff member (actually sets status to 'inactive')

        Args:
            staff_id: Staff ID

        Returns:
            Dictionary with success status
        """
        return self.update_staff(staff_id, status='inactive', modified_by='system')

    def hard_delete_staff(self, staff_id):
        """
        Permanently delete a staff member (use with caution!)

        Args:
            staff_id: Staff ID

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()
        cursor = conn.execute('SELECT name FROM staff WHERE id = ?', (staff_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'error': 'Staff member not found'}

        name = row['name']
        conn.execute('DELETE FROM staff WHERE id = ?', (staff_id,))
        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f'Permanently deleted {name}'
        }

    # Section management methods

    def get_all_sections(self):
        """
        Get all sections ordered by display_order

        Returns:
            List of section dictionaries
        """
        conn = self.get_connection()
        cursor = conn.execute('SELECT * FROM sections ORDER BY display_order, name')
        sections = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return sections

    def add_section(self, name, display_order=None):
        """
        Add a new section

        Args:
            name: Section name
            display_order: Optional display order (defaults to max + 1)

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()

        # If no display order provided, use max + 1
        if display_order is None:
            cursor = conn.execute('SELECT MAX(display_order) as max_order FROM sections')
            row = cursor.fetchone()
            display_order = (row['max_order'] or 0) + 1

        try:
            cursor = conn.execute(
                'INSERT INTO sections (name, display_order) VALUES (?, ?)',
                (name, display_order)
            )
            section_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return {
                'success': True,
                'id': section_id,
                'message': f'Added section {name}'
            }
        except Exception as e:
            conn.close()
            return {'error': str(e)}

    def update_section(self, section_id, name=None, display_order=None):
        """
        Update a section

        Args:
            section_id: Section ID
            name: New name (optional)
            display_order: New display order (optional)

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()

        updates = []
        values = []

        if name is not None:
            updates.append('name = ?')
            values.append(name)

        if display_order is not None:
            updates.append('display_order = ?')
            values.append(display_order)

        if not updates:
            conn.close()
            return {'error': 'No fields to update'}

        values.append(section_id)

        try:
            conn.execute(
                f'UPDATE sections SET {", ".join(updates)} WHERE id = ?',
                values
            )
            conn.commit()
            conn.close()

            return {
                'success': True,
                'message': 'Section updated'
            }
        except Exception as e:
            conn.close()
            return {'error': str(e)}

    def delete_section(self, section_id):
        """
        Delete a section

        Args:
            section_id: Section ID

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()

        # Get section name first
        cursor = conn.execute('SELECT name FROM sections WHERE id = ?', (section_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'error': 'Section not found'}

        section_name = row['name']

        # Check if any staff are in this section
        cursor = conn.execute('SELECT COUNT(*) as count FROM staff WHERE section = ?', (section_name,))
        count = cursor.fetchone()['count']

        if count > 0:
            conn.close()
            return {
                'error': f'Cannot delete section "{section_name}" because {count} staff member(s) are assigned to it'
            }

        # Delete the section
        conn.execute('DELETE FROM sections WHERE id = ?', (section_id,))
        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f'Deleted section {section_name}'
        }

    # Access request methods

    def submit_access_request(self, name, email, phone=None, reason=None):
        """
        Submit a new access request (for external staff without Google accounts)

        Args:
            name: Person's name
            email: Personal email address
            phone: Phone number (optional)
            reason: Reason for access request (optional)

        Returns:
            Dictionary with success status or error
        """
        conn = self.get_connection()

        # Check if email already exists as active staff
        cursor = conn.execute(
            'SELECT id FROM staff WHERE (work_email = ? OR personal_email = ?) AND status = ?',
            (email, email, 'active')
        )
        if cursor.fetchone():
            conn.close()
            return {
                'error': 'This email is already approved for access',
                'already_approved': True
            }

        # Check if there's already a pending request
        cursor = conn.execute(
            'SELECT id FROM access_requests WHERE email = ? AND status = ?',
            (email, 'pending')
        )
        if cursor.fetchone():
            conn.close()
            return {
                'error': 'A request for this email is already pending review',
                'already_pending': True
            }

        # Create the request
        cursor = conn.execute(
            '''INSERT INTO access_requests (name, email, phone, reason)
               VALUES (?, ?, ?, ?)''',
            (name, email, phone, reason)
        )
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            'success': True,
            'request_id': request_id,
            'message': 'Access request submitted successfully'
        }

    def get_access_requests(self, status='pending'):
        """
        Get access requests

        Args:
            status: Filter by status ('pending', 'approved', 'denied', or None for all)

        Returns:
            List of request dictionaries
        """
        conn = self.get_connection()

        if status:
            cursor = conn.execute(
                'SELECT * FROM access_requests WHERE status = ? ORDER BY request_date DESC',
                (status,)
            )
        else:
            cursor = conn.execute('SELECT * FROM access_requests ORDER BY request_date DESC')

        requests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return requests

    def get_access_request_by_id(self, request_id):
        """Get a specific access request by ID"""
        conn = self.get_connection()
        cursor = conn.execute('SELECT * FROM access_requests WHERE id = ?', (request_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def approve_access_request(self, request_id, reviewed_by, create_staff=True):
        """
        Approve an access request

        Args:
            request_id: Request ID
            reviewed_by: Email of person approving
            create_staff: Whether to automatically create staff entry (default True)

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()

        # Get request details
        cursor = conn.execute('SELECT * FROM access_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()

        if not request:
            conn.close()
            return {'error': 'Request not found'}

        if request['status'] != 'pending':
            conn.close()
            return {'error': f'Request is already {request["status"]}'}

        # Update request status
        conn.execute(
            '''UPDATE access_requests
               SET status = 'approved', reviewed_by = ?, reviewed_date = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (reviewed_by, request_id)
        )

        staff_id = None

        # Optionally create staff entry
        if create_staff:
            try:
                cursor = conn.execute(
                    '''INSERT INTO staff (name, personal_email, phone_mobile, status, include_in_allstaff,
                                         show_on_phone_list, created_by, modified_by, notes)
                       VALUES (?, ?, ?, 'active', 1, 0, ?, ?, ?)''',
                    (
                        request['name'],
                        request['email'],
                        request['phone'] or '',
                        reviewed_by,
                        reviewed_by,
                        f"Access approved via request on {datetime.now().strftime('%Y-%m-%d')}. Reason: {request['reason'] or 'N/A'}"
                    )
                )
                staff_id = cursor.lastrowid
            except Exception as e:
                conn.close()
                return {'error': f'Failed to create staff entry: {str(e)}'}

        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f'Access request approved for {request["name"]}',
            'staff_id': staff_id
        }

    def deny_access_request(self, request_id, reviewed_by, notes=None):
        """
        Deny an access request

        Args:
            request_id: Request ID
            reviewed_by: Email of person denying
            notes: Reason for denial (optional)

        Returns:
            Dictionary with success status
        """
        conn = self.get_connection()

        # Get request details
        cursor = conn.execute('SELECT * FROM access_requests WHERE id = ?', (request_id,))
        request = cursor.fetchone()

        if not request:
            conn.close()
            return {'error': 'Request not found'}

        if request['status'] != 'pending':
            conn.close()
            return {'error': f'Request is already {request["status"]}'}

        # Update request status
        conn.execute(
            '''UPDATE access_requests
               SET status = 'denied', reviewed_by = ?, reviewed_date = CURRENT_TIMESTAMP, notes = ?
               WHERE id = ?''',
            (reviewed_by, notes, request_id)
        )
        conn.commit()
        conn.close()

        return {
            'success': True,
            'message': f'Access request denied for {request["name"]}'
        }

# Singleton instance
staff_db = StaffDatabase()
