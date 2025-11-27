"""
Database service for Hugo's Buz user cache.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from shared.migrations import MigrationRunner


class UserDatabase:
    """SQLite database for caching Buz users."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'hugo.db')
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

    # User CRUD operations

    def get_users(
        self,
        org_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        user_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get users with optional filters.

        Args:
            org_key: Filter by organization
            is_active: Filter by active status
            user_type: Filter by 'employee' or 'customer'

        Returns:
            List of user dictionaries
        """
        conn = self.get_connection()

        query = 'SELECT * FROM users WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        if user_type:
            query += ' AND user_type = ?'
            params.append(user_type)

        query += ' ORDER BY org_key, full_name'

        cursor = conn.execute(query, params)
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return users

    def get_user_by_email(self, email: str, org_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.

        Args:
            email: User's email address
            org_key: Optional org filter (user may exist in multiple orgs)

        Returns:
            User dictionary or None
        """
        conn = self.get_connection()

        if org_key:
            cursor = conn.execute(
                'SELECT * FROM users WHERE email = ? AND org_key = ?',
                (email, org_key)
            )
        else:
            cursor = conn.execute(
                'SELECT * FROM users WHERE email = ? ORDER BY org_key',
                (email,)
            )

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_user_orgs(self, email: str) -> List[str]:
        """
        Get all orgs a user has access to.

        Args:
            email: User's email address

        Returns:
            List of org_key values
        """
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT org_key FROM users WHERE email = ? AND is_active = 1',
            (email,)
        )
        orgs = [row['org_key'] for row in cursor.fetchall()]
        conn.close()
        return orgs

    def upsert_user(
        self,
        email: str,
        org_key: str,
        full_name: str = '',
        user_type: str = 'employee',
        is_active: bool = True,
        mfa_enabled: bool = False,
        user_group: str = '',
        last_session: str = ''
    ) -> Dict[str, Any]:
        """
        Insert or update a user.

        Args:
            email: User's email address
            org_key: Organization key
            full_name: User's full name
            user_type: 'employee' or 'customer'
            is_active: Active status
            mfa_enabled: MFA enabled flag
            user_group: User's group/role
            last_session: Last session timestamp

        Returns:
            Result dictionary with success status
        """
        conn = self.get_connection()

        # Check if user exists
        cursor = conn.execute(
            'SELECT id FROM users WHERE email = ? AND org_key = ?',
            (email, org_key)
        )
        existing = cursor.fetchone()

        if existing:
            # Update
            conn.execute('''
                UPDATE users SET
                    full_name = ?,
                    user_type = ?,
                    is_active = ?,
                    mfa_enabled = ?,
                    user_group = ?,
                    last_session = ?,
                    last_synced = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE email = ? AND org_key = ?
            ''', (
                full_name, user_type, 1 if is_active else 0,
                1 if mfa_enabled else 0, user_group, last_session,
                email, org_key
            ))
            action = 'updated'
        else:
            # Insert
            conn.execute('''
                INSERT INTO users (
                    email, org_key, full_name, user_type, is_active,
                    mfa_enabled, user_group, last_session
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email, org_key, full_name, user_type, 1 if is_active else 0,
                1 if mfa_enabled else 0, user_group, last_session
            ))
            action = 'created'

        conn.commit()
        conn.close()

        return {'success': True, 'action': action, 'email': email, 'org_key': org_key}

    def update_user_status(
        self,
        email: str,
        org_key: str,
        is_active: bool
    ) -> Dict[str, Any]:
        """
        Update a user's active status.

        Args:
            email: User's email
            org_key: Organization key
            is_active: New active status

        Returns:
            Result dictionary
        """
        conn = self.get_connection()

        cursor = conn.execute(
            'SELECT is_active FROM users WHERE email = ? AND org_key = ?',
            (email, org_key)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'success': False, 'error': f'User {email} not found in {org_key}'}

        old_status = bool(row['is_active'])

        conn.execute('''
            UPDATE users SET
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = ? AND org_key = ?
        ''', (1 if is_active else 0, email, org_key))

        conn.commit()
        conn.close()

        return {
            'success': True,
            'email': email,
            'org_key': org_key,
            'old_status': old_status,
            'new_status': is_active
        }

    def bulk_upsert_users(self, users: List[Dict[str, Any]], org_key: str) -> Dict[str, Any]:
        """
        Bulk upsert users from a sync operation.

        Args:
            users: List of user dictionaries
            org_key: Organization key

        Returns:
            Result dictionary with counts
        """
        conn = self.get_connection()
        created = 0
        updated = 0

        for user in users:
            cursor = conn.execute(
                'SELECT id FROM users WHERE email = ? AND org_key = ?',
                (user['email'], org_key)
            )
            existing = cursor.fetchone()

            if existing:
                conn.execute('''
                    UPDATE users SET
                        full_name = ?,
                        user_type = ?,
                        is_active = ?,
                        mfa_enabled = ?,
                        user_group = ?,
                        last_session = ?,
                        last_synced = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = ? AND org_key = ?
                ''', (
                    user.get('full_name', ''),
                    user.get('user_type', 'employee'),
                    1 if user.get('is_active', True) else 0,
                    1 if user.get('mfa_enabled', False) else 0,
                    user.get('group', ''),
                    user.get('last_session', ''),
                    user['email'], org_key
                ))
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO users (
                        email, org_key, full_name, user_type, is_active,
                        mfa_enabled, user_group, last_session
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['email'],
                    org_key,
                    user.get('full_name', ''),
                    user.get('user_type', 'employee'),
                    1 if user.get('is_active', True) else 0,
                    1 if user.get('mfa_enabled', False) else 0,
                    user.get('group', ''),
                    user.get('last_session', '')
                ))
                created += 1

        conn.commit()
        conn.close()

        return {
            'success': True,
            'org_key': org_key,
            'created': created,
            'updated': updated,
            'total': created + updated
        }

    # Sync log operations

    def log_sync(
        self,
        org_key: str,
        user_count: int,
        status: str = 'success',
        error_message: str = '',
        duration_seconds: float = 0
    ) -> int:
        """
        Log a sync operation.

        Returns:
            ID of the log entry
        """
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO sync_log (org_key, user_count, status, error_message, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
        ''', (org_key, user_count, status, error_message, duration_seconds))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_last_sync(self, org_key: str) -> Optional[Dict[str, Any]]:
        """Get the last sync record for an org."""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT * FROM sync_log WHERE org_key = ? ORDER BY synced_at DESC LIMIT 1',
            (org_key,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_sync_history(self, org_key: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get sync history."""
        conn = self.get_connection()

        if org_key:
            cursor = conn.execute(
                'SELECT * FROM sync_log WHERE org_key = ? ORDER BY synced_at DESC LIMIT ?',
                (org_key, limit)
            )
        else:
            cursor = conn.execute(
                'SELECT * FROM sync_log ORDER BY synced_at DESC LIMIT ?',
                (limit,)
            )

        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    # Activity log operations

    def log_activity(
        self,
        action: str,
        email: str,
        org_key: str,
        old_value: str = '',
        new_value: str = '',
        performed_by: str = 'system',
        success: bool = True,
        error_message: str = ''
    ) -> int:
        """Log an activity/change."""
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO activity_log (
                action, email, org_key, old_value, new_value,
                performed_by, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            action, email, org_key, old_value, new_value,
            performed_by, 1 if success else 0, error_message
        ))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_activity_log(
        self,
        email: Optional[str] = None,
        org_key: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get activity log with optional filters."""
        conn = self.get_connection()

        query = 'SELECT * FROM activity_log WHERE 1=1'
        params = []

        if email:
            query += ' AND email = ?'
            params.append(email)

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        query += ' ORDER BY performed_at DESC LIMIT ?'
        params.append(limit)

        cursor = conn.execute(query, params)
        log = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return log

    # Statistics

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        conn = self.get_connection()

        # Total users by org
        cursor = conn.execute('''
            SELECT org_key, COUNT(*) as total,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
            FROM users GROUP BY org_key
        ''')
        by_org = {row['org_key']: {
            'total': row['total'],
            'active': row['active'],
            'inactive': row['inactive']
        } for row in cursor.fetchall()}

        # Total counts
        cursor = conn.execute('SELECT COUNT(*) as total FROM users')
        total = cursor.fetchone()['total']

        cursor = conn.execute('SELECT COUNT(*) as active FROM users WHERE is_active = 1')
        active = cursor.fetchone()['active']

        conn.close()

        return {
            'total_users': total,
            'active_users': active,
            'inactive_users': total - active,
            'by_org': by_org
        }


# Singleton instance
user_db = UserDatabase()
