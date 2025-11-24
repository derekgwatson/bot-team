"""
Database module for Scout

Tracks:
- Issues detected by checks
- Tickets raised via Sadie
- Check run history
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import json

from config import config

logger = logging.getLogger(__name__)


class ScoutDatabase:
    """Database manager for Scout"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = config.database_path

        # Ensure path is relative to bot directory
        if not Path(db_path).is_absolute():
            db_path = str(config.base_dir / db_path)

        self.db_path = db_path
        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Table for tracking reported issues
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reported_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_type TEXT NOT NULL,
                    issue_key TEXT NOT NULL,
                    issue_details TEXT,
                    ticket_id INTEGER,
                    ticket_url TEXT,
                    status TEXT DEFAULT 'open',
                    first_detected_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    resolved_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(issue_type, issue_key)
                )
            """)

            # Table for check run history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS check_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT DEFAULT 'running',
                    issues_found INTEGER DEFAULT 0,
                    tickets_created INTEGER DEFAULT 0,
                    error_message TEXT,
                    check_results TEXT
                )
            """)

            # Index for efficient lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reported_issues_type_key
                ON reported_issues(issue_type, issue_key)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reported_issues_status
                ON reported_issues(status)
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────────
    # Issue tracking
    # ─────────────────────────────────────────────────────────────────────────────

    def get_issue(self, issue_type: str, issue_key: str) -> Optional[dict]:
        """Get a reported issue by type and key"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM reported_issues
                WHERE issue_type = ? AND issue_key = ?
                """,
                (issue_type, issue_key)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def is_issue_reported(self, issue_type: str, issue_key: str) -> bool:
        """Check if an issue has already been reported (and is still open)"""
        issue = self.get_issue(issue_type, issue_key)
        return issue is not None and issue['status'] == 'open'

    def record_issue(
        self,
        issue_type: str,
        issue_key: str,
        issue_details: dict = None,
        ticket_id: int = None,
        ticket_url: str = None
    ) -> int:
        """
        Record a new issue or update if it exists.
        Returns the issue ID.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            details_json = json.dumps(issue_details) if issue_details else None

            # Check if issue already exists
            existing = self.get_issue(issue_type, issue_key)

            if existing:
                # Update last_seen_at and reopen if resolved
                cursor.execute(
                    """
                    UPDATE reported_issues
                    SET last_seen_at = ?,
                        status = CASE WHEN status = 'resolved' THEN 'open' ELSE status END,
                        issue_details = COALESCE(?, issue_details),
                        ticket_id = COALESCE(?, ticket_id),
                        ticket_url = COALESCE(?, ticket_url)
                    WHERE issue_type = ? AND issue_key = ?
                    """,
                    (now, details_json, ticket_id, ticket_url, issue_type, issue_key)
                )
                conn.commit()
                return existing['id']
            else:
                # Insert new issue
                cursor.execute(
                    """
                    INSERT INTO reported_issues
                    (issue_type, issue_key, issue_details, ticket_id, ticket_url,
                     first_detected_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (issue_type, issue_key, details_json, ticket_id, ticket_url, now, now)
                )
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def resolve_issue(self, issue_type: str, issue_key: str) -> bool:
        """Mark an issue as resolved"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                UPDATE reported_issues
                SET status = 'resolved', resolved_at = ?
                WHERE issue_type = ? AND issue_key = ? AND status = 'open'
                """,
                (now, issue_type, issue_key)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_open_issues(self, issue_type: str = None) -> list:
        """Get all open issues, optionally filtered by type"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if issue_type:
                cursor.execute(
                    """
                    SELECT * FROM reported_issues
                    WHERE status = 'open' AND issue_type = ?
                    ORDER BY first_detected_at DESC
                    """,
                    (issue_type,)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM reported_issues
                    WHERE status = 'open'
                    ORDER BY first_detected_at DESC
                    """
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_issues(self, limit: int = 100) -> list:
        """Get all issues with limit"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM reported_issues
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_issue_stats(self) -> dict:
        """Get issue statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total issues
            cursor.execute("SELECT COUNT(*) FROM reported_issues")
            total = cursor.fetchone()[0]

            # Open issues
            cursor.execute("SELECT COUNT(*) FROM reported_issues WHERE status = 'open'")
            open_count = cursor.fetchone()[0]

            # Issues by type
            cursor.execute("""
                SELECT issue_type, COUNT(*) as count
                FROM reported_issues
                WHERE status = 'open'
                GROUP BY issue_type
            """)
            by_type = {row['issue_type']: row['count'] for row in cursor.fetchall()}

            # Issues with tickets
            cursor.execute(
                "SELECT COUNT(*) FROM reported_issues WHERE ticket_id IS NOT NULL"
            )
            with_tickets = cursor.fetchone()[0]

            return {
                'total': total,
                'open': open_count,
                'resolved': total - open_count,
                'by_type': by_type,
                'with_tickets': with_tickets
            }
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────────
    # Check run history
    # ─────────────────────────────────────────────────────────────────────────────

    def start_check_run(self) -> int:
        """Record the start of a check run. Returns the run ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO check_runs (started_at, status)
                VALUES (?, 'running')
                """,
                (now,)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def complete_check_run(
        self,
        run_id: int,
        issues_found: int = 0,
        tickets_created: int = 0,
        check_results: dict = None,
        error_message: str = None
    ):
        """Record the completion of a check run"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            status = 'failed' if error_message else 'completed'
            results_json = json.dumps(check_results) if check_results else None

            cursor.execute(
                """
                UPDATE check_runs
                SET finished_at = ?,
                    status = ?,
                    issues_found = ?,
                    tickets_created = ?,
                    check_results = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (now, status, issues_found, tickets_created, results_json, error_message, run_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_last_check_run(self) -> Optional[dict]:
        """Get the most recent check run"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM check_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('check_results'):
                    result['check_results'] = json.loads(result['check_results'])
                return result
            return None
        finally:
            conn.close()

    def get_check_history(self, limit: int = 20) -> list:
        """Get recent check run history"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM check_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = []
            for row in cursor.fetchall():
                r = dict(row)
                if r.get('check_results'):
                    r['check_results'] = json.loads(r['check_results'])
                rows.append(r)
            return rows
        finally:
            conn.close()


# Singleton instance
db = ScoutDatabase()
