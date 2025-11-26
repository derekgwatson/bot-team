"""
Database module for Doc

Tracks:
- Bot registry (synced from Chester)
- Health checkup results
- Test run history
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
import json

from config import config
from shared.migrations import MigrationRunner

logger = logging.getLogger(__name__)


class DocDatabase:
    """Database manager for Doc"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = config.database_path

        # Ensure path is relative to bot directory
        if not Path(db_path).is_absolute():
            db_path = str(config.base_dir / db_path)

        self.db_path = db_path
        self._ensure_directory()
        self._run_migrations()

    def _ensure_directory(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _run_migrations(self):
        """Run database migrations"""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)
        logger.info(f"Database initialized at {self.db_path}")

    # ─────────────────────────────────────────────────────────────────────────────
    # Bot Registry
    # ─────────────────────────────────────────────────────────────────────────────

    def get_bot(self, name: str) -> Optional[dict]:
        """Get a bot by name"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bots WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_bots(self) -> List[dict]:
        """Get all bots in the registry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bots ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def upsert_bot(
        self,
        name: str,
        port: int,
        url: str,
        description: str = None,
        capabilities: list = None
    ) -> int:
        """Insert or update a bot in the registry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            capabilities_json = json.dumps(capabilities) if capabilities else None

            cursor.execute(
                """
                INSERT INTO bots (name, port, url, description, capabilities, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    port = excluded.port,
                    url = excluded.url,
                    description = COALESCE(excluded.description, bots.description),
                    capabilities = COALESCE(excluded.capabilities, bots.capabilities),
                    last_synced_at = excluded.last_synced_at
                """,
                (name, port, url, description, capabilities_json, now)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_sync_timestamp(self):
        """Update the last sync timestamp for all bots"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("UPDATE bots SET last_synced_at = ?", (now,))
            conn.commit()
        finally:
            conn.close()

    def get_bot_count(self) -> int:
        """Get the number of bots in the registry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bots")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def delete_bot(self, name: str) -> bool:
        """Remove a bot from the registry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bots WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────────
    # Health Checkups
    # ─────────────────────────────────────────────────────────────────────────────

    def record_checkup(
        self,
        bot_name: str,
        status: str,
        response_time_ms: int = None,
        status_code: int = None,
        error_message: str = None
    ) -> int:
        """Record a health checkup result"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO checkups (bot_name, checked_at, status, response_time_ms, status_code, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bot_name, now, status, response_time_ms, status_code, error_message)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_latest_checkup(self, bot_name: str) -> Optional[dict]:
        """Get the most recent checkup for a bot"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM checkups
                WHERE bot_name = ?
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                (bot_name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_checkup_history(self, bot_name: str = None, limit: int = 50) -> List[dict]:
        """Get checkup history, optionally filtered by bot"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if bot_name:
                cursor.execute(
                    """
                    SELECT * FROM checkups
                    WHERE bot_name = ?
                    ORDER BY checked_at DESC
                    LIMIT ?
                    """,
                    (bot_name, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM checkups
                    ORDER BY checked_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_bot_vitals(self, bot_name: str, hours: int = 24) -> dict:
        """Get vital statistics for a bot over the past N hours"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                    AVG(response_time_ms) as avg_response_time,
                    MIN(response_time_ms) as min_response_time,
                    MAX(response_time_ms) as max_response_time
                FROM checkups
                WHERE bot_name = ?
                AND checked_at >= datetime('now', ?)
                """,
                (bot_name, f'-{hours} hours')
            )
            row = cursor.fetchone()
            if row and row['total_checks'] > 0:
                return {
                    'bot_name': bot_name,
                    'period_hours': hours,
                    'total_checks': row['total_checks'],
                    'healthy_count': row['healthy_count'] or 0,
                    'uptime_percent': round((row['healthy_count'] or 0) / row['total_checks'] * 100, 2),
                    'avg_response_time_ms': round(row['avg_response_time'] or 0, 2),
                    'min_response_time_ms': row['min_response_time'],
                    'max_response_time_ms': row['max_response_time']
                }
            return {
                'bot_name': bot_name,
                'period_hours': hours,
                'total_checks': 0,
                'healthy_count': 0,
                'uptime_percent': None,
                'avg_response_time_ms': None,
                'min_response_time_ms': None,
                'max_response_time_ms': None
            }
        finally:
            conn.close()

    def get_team_vitals(self, hours: int = 24) -> dict:
        """Get vital statistics for the entire team"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Overall stats
            cursor.execute(
                """
                SELECT
                    COUNT(DISTINCT bot_name) as bots_checked,
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                    AVG(response_time_ms) as avg_response_time
                FROM checkups
                WHERE checked_at >= datetime('now', ?)
                """,
                (f'-{hours} hours',)
            )
            overall = cursor.fetchone()

            # Per-bot status (latest check for each)
            cursor.execute(
                """
                SELECT c1.*
                FROM checkups c1
                INNER JOIN (
                    SELECT bot_name, MAX(checked_at) as max_checked
                    FROM checkups
                    GROUP BY bot_name
                ) c2 ON c1.bot_name = c2.bot_name AND c1.checked_at = c2.max_checked
                ORDER BY c1.bot_name
                """
            )
            latest_by_bot = [dict(row) for row in cursor.fetchall()]

            healthy_bots = sum(1 for b in latest_by_bot if b['status'] == 'healthy')

            return {
                'period_hours': hours,
                'bots_checked': overall['bots_checked'] or 0,
                'total_checks': overall['total_checks'] or 0,
                'overall_uptime_percent': round(
                    (overall['healthy_count'] or 0) / overall['total_checks'] * 100, 2
                ) if overall['total_checks'] else None,
                'avg_response_time_ms': round(overall['avg_response_time'] or 0, 2) if overall['avg_response_time'] else None,
                'current_status': {
                    'healthy': healthy_bots,
                    'unhealthy': len(latest_by_bot) - healthy_bots,
                    'total': len(latest_by_bot)
                },
                'bots': latest_by_bot
            }
        finally:
            conn.close()

    def cleanup_old_checkups(self, days: int = 30) -> int:
        """Remove checkup records older than N days"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM checkups
                WHERE checked_at < datetime('now', ?)
                """,
                (f'-{days} days',)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────────
    # Test Runs
    # ─────────────────────────────────────────────────────────────────────────────

    def start_test_run(self, marker: str = None) -> int:
        """Start a new test run. Returns the run ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO test_runs (started_at, marker, status)
                VALUES (?, ?, 'running')
                """,
                (now, marker)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def complete_test_run(
        self,
        run_id: int,
        status: str,
        total_tests: int = 0,
        passed: int = 0,
        failed: int = 0,
        errors: int = 0,
        skipped: int = 0,
        duration_seconds: float = None,
        output: str = None,
        error_message: str = None
    ):
        """Complete a test run with results"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                UPDATE test_runs
                SET completed_at = ?,
                    status = ?,
                    total_tests = ?,
                    passed = ?,
                    failed = ?,
                    errors = ?,
                    skipped = ?,
                    duration_seconds = ?,
                    output = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (now, status, total_tests, passed, failed, errors, skipped,
                 duration_seconds, output, error_message, run_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_test_run(self, run_id: int) -> Optional[dict]:
        """Get a specific test run"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_latest_test_run(self, marker: str = None) -> Optional[dict]:
        """Get the most recent test run, optionally filtered by marker"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if marker:
                cursor.execute(
                    """
                    SELECT * FROM test_runs
                    WHERE marker = ?
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (marker,)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM test_runs
                    ORDER BY started_at DESC
                    LIMIT 1
                    """
                )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_test_run_history(self, limit: int = 20, marker: str = None) -> List[dict]:
        """Get test run history"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if marker:
                cursor.execute(
                    """
                    SELECT * FROM test_runs
                    WHERE marker = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (marker, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM test_runs
                    ORDER BY started_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_running_test_run(self) -> Optional[dict]:
        """Get the currently running test run, if any"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM test_runs
                WHERE status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


# Singleton instance
db = DocDatabase()
