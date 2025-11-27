"""Database manager for Grant's permission management."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
from contextlib import contextmanager
from shared.migrations import MigrationRunner


def utc_now_iso() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    """Database manager for Grant's permissions."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'grant.db'
        self.db_path = str(db_path)
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations."""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Permission Operations
    # ─────────────────────────────────────────────────────────────

    def get_permission(self, email: str, bot_name: str) -> Optional[Dict]:
        """Get a specific permission for a user and bot."""
        email = email.lower().strip()
        bot_name = bot_name.lower().strip()

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM permissions WHERE email = ? AND bot_name = ?",
            (email, bot_name)
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_permissions_for_user(self, email: str) -> List[Dict]:
        """Get all permissions for a user."""
        email = email.lower().strip()

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM permissions WHERE email = ? ORDER BY bot_name",
            (email,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_permissions_for_bot(self, bot_name: str) -> List[Dict]:
        """Get all permissions for a bot."""
        bot_name = bot_name.lower().strip()

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM permissions WHERE bot_name = ? ORDER BY email",
            (bot_name,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_permissions(self) -> List[Dict]:
        """Get all permissions."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM permissions ORDER BY email, bot_name"
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def grant_permission(
        self,
        email: str,
        bot_name: str,
        role: str,
        granted_by: str
    ) -> Dict:
        """
        Grant or update permission for a user on a bot.
        Returns the permission record.
        """
        email = email.lower().strip()
        bot_name = bot_name.lower().strip()
        role = role.lower().strip()
        now = utc_now_iso()

        if role not in ('user', 'admin'):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'admin'.")

        with self.connection() as conn:
            cursor = conn.cursor()

            # Check if permission exists
            cursor.execute(
                "SELECT id, role FROM permissions WHERE email = ? AND bot_name = ?",
                (email, bot_name)
            )
            existing = cursor.fetchone()

            if existing:
                old_role = existing['role']
                # Update existing permission
                cursor.execute(
                    """UPDATE permissions SET role = ?, granted_by = ?, granted_at = ?
                       WHERE email = ? AND bot_name = ?""",
                    (role, granted_by, now, email, bot_name)
                )
                action = 'modify'
            else:
                old_role = None
                # Insert new permission
                cursor.execute(
                    """INSERT INTO permissions (email, bot_name, role, granted_by, granted_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (email, bot_name, role, granted_by, now)
                )
                action = 'grant'

            # Record audit trail
            cursor.execute(
                """INSERT INTO permission_changes
                   (email, bot_name, action, old_role, new_role, changed_by, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (email, bot_name, action, old_role, role, granted_by, now)
            )

        return self.get_permission(email, bot_name)

    def revoke_permission(self, email: str, bot_name: str, revoked_by: str) -> bool:
        """
        Revoke permission for a user on a bot.
        Returns True if revoked, False if no permission existed.
        """
        email = email.lower().strip()
        bot_name = bot_name.lower().strip()
        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()

            # Get existing permission for audit
            cursor.execute(
                "SELECT role FROM permissions WHERE email = ? AND bot_name = ?",
                (email, bot_name)
            )
            existing = cursor.fetchone()

            if not existing:
                return False

            old_role = existing['role']

            # Delete permission
            cursor.execute(
                "DELETE FROM permissions WHERE email = ? AND bot_name = ?",
                (email, bot_name)
            )

            # Record audit trail
            cursor.execute(
                """INSERT INTO permission_changes
                   (email, bot_name, action, old_role, new_role, changed_by, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (email, bot_name, 'revoke', old_role, None, revoked_by, now)
            )

        return True

    def check_access(self, email: str, bot_name: str) -> Dict:
        """
        Check if a user has access to a bot.
        Returns {allowed: bool, role: str|None}.
        """
        permission = self.get_permission(email, bot_name)

        # Also check for wildcard (*) permission
        if not permission:
            permission = self.get_permission(email, '*')

        if permission:
            return {
                'allowed': True,
                'role': permission['role'],
                'is_admin': permission['role'] == 'admin'
            }
        else:
            return {
                'allowed': False,
                'role': None,
                'is_admin': False
            }

    # ─────────────────────────────────────────────────────────────
    # Audit Operations
    # ─────────────────────────────────────────────────────────────

    def get_audit_log(
        self,
        email: str = None,
        bot_name: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get audit log entries, optionally filtered."""
        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if email:
            conditions.append("email = ?")
            params.append(email.lower().strip())

        if bot_name:
            conditions.append("bot_name = ?")
            params.append(bot_name.lower().strip())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(
            f"""SELECT * FROM permission_changes
                WHERE {where_clause}
                ORDER BY changed_at DESC
                LIMIT ?""",
            params + [limit]
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ─────────────────────────────────────────────────────────────
    # Bot Registry Operations
    # ─────────────────────────────────────────────────────────────

    def sync_bots(self, bots: List[Dict]) -> Dict:
        """Sync bot registry from Chester."""
        now = utc_now_iso()
        synced = 0

        with self.connection() as conn:
            cursor = conn.cursor()

            # Clear existing bots
            cursor.execute("DELETE FROM bots")

            # Insert new bots
            for bot in bots:
                cursor.execute(
                    """INSERT INTO bots (name, description, port, synced_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        bot.get('name', '').lower(),
                        bot.get('description', ''),
                        bot.get('port'),
                        now
                    )
                )
                synced += 1

        return {'synced': synced, 'synced_at': now}

    def get_bots(self) -> List[Dict]:
        """Get all registered bots."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bots ORDER BY name")
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_bot(self, name: str) -> Optional[Dict]:
        """Get a bot by name."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bots WHERE name = ?", (name.lower(),))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    # ─────────────────────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get statistics about permissions."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT email) FROM permissions")
        unique_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT bot_name) FROM permissions")
        bots_with_permissions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM permissions")
        total_permissions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM permissions WHERE role = 'admin'")
        admin_permissions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM bots")
        registered_bots = cursor.fetchone()[0]

        conn.close()

        return {
            'unique_users': unique_users,
            'bots_with_permissions': bots_with_permissions,
            'total_permissions': total_permissions,
            'admin_permissions': admin_permissions,
            'registered_bots': registered_bots
        }

    def get_unique_users(self) -> List[str]:
        """Get list of unique user emails with permissions."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT email FROM permissions ORDER BY email")
        rows = cursor.fetchall()
        conn.close()

        return [row['email'] for row in rows]


# Global database instance (initialized when config is loaded)
db = None


def init_db(db_path: str = None):
    """Initialize the database."""
    global db
    db = Database(db_path)
    return db


def get_db() -> Database:
    """Get the database instance."""
    global db
    if db is None:
        db = Database()
    return db
