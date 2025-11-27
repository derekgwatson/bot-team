"""Database service for Skye - manages scheduled jobs."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager
from datetime import datetime
from shared.migrations import MigrationRunner


class Database:
    """SQLite database manager for Skye."""

    def __init__(self, db_path: str = None, auto_migrate: bool = True):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'database' / 'skye.db'
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent.parent / 'migrations'

        # Ensure database directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        if auto_migrate:
            self.run_migrations()

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def run_migrations(self, verbose: bool = False):
        """Run database migrations."""
        runner = MigrationRunner(
            db_path=str(self.db_path),
            migrations_dir=str(self.migrations_dir)
        )
        runner.run_pending_migrations(verbose=verbose)

    # ─────────────────────────────────────────────────────────────────────────
    # Job CRUD Operations
    # ─────────────────────────────────────────────────────────────────────────

    def create_job(
        self,
        job_id: str,
        name: str,
        target_bot: str,
        endpoint: str,
        method: str = "POST",
        schedule_type: str = "cron",
        schedule_config: str = "{}",
        description: str = None,
        enabled: bool = True,
        created_by: str = None
    ) -> Optional[int]:
        """Create a new scheduled job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO jobs
                (job_id, name, description, target_bot, endpoint, method,
                 schedule_type, schedule_config, enabled, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id, name, description, target_bot, endpoint, method,
                schedule_type, schedule_config, 1 if enabled else 0, created_by
            ))
            return cursor.lastrowid

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a job by its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            if row:
                job = dict(row)
                job['enabled'] = bool(job['enabled'])
                job['quiet'] = bool(job.get('quiet', 0))
                return job
            return None

    def get_all_jobs(self, include_disabled: bool = True) -> List[Dict]:
        """Get all jobs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_disabled:
                cursor.execute('SELECT * FROM jobs ORDER BY name')
            else:
                cursor.execute('SELECT * FROM jobs WHERE enabled = 1 ORDER BY name')
            rows = cursor.fetchall()
            jobs = []
            for row in rows:
                job = dict(row)
                job['enabled'] = bool(job['enabled'])
                job['quiet'] = bool(job.get('quiet', 0))
                jobs.append(job)
            return jobs

    def get_enabled_jobs(self) -> List[Dict]:
        """Get only enabled jobs."""
        return self.get_all_jobs(include_disabled=False)

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update a job's configuration."""
        valid_fields = ['name', 'description', 'target_bot', 'endpoint', 'method',
                       'schedule_type', 'schedule_config', 'enabled', 'quiet']

        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return False

        # Convert boolean fields to int
        if 'enabled' in updates:
            updates['enabled'] = 1 if updates['enabled'] else 0
        if 'quiet' in updates:
            updates['quiet'] = 1 if updates['quiet'] else 0

        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        set_clause += ', updated_at = CURRENT_TIMESTAMP'
        query = f'UPDATE jobs SET {set_clause} WHERE job_id = ?'

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, list(updates.values()) + [job_id])
            return cursor.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            return cursor.rowcount > 0

    def set_job_enabled(self, job_id: str, enabled: bool) -> bool:
        """Enable or disable a job."""
        return self.update_job(job_id, enabled=enabled)

    # ─────────────────────────────────────────────────────────────────────────
    # Job Execution History
    # ─────────────────────────────────────────────────────────────────────────

    def record_execution(
        self,
        job_id: str,
        status: str,
        response_code: int = None,
        response_body: str = None,
        error_message: str = None,
        duration_ms: int = None
    ) -> Optional[int]:
        """Record a job execution."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO job_executions
                (job_id, status, response_code, response_body, error_message, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (job_id, status, response_code, response_body, error_message, duration_ms))

            # Update last_run on the job
            cursor.execute('''
                UPDATE jobs SET last_run = CURRENT_TIMESTAMP WHERE job_id = ?
            ''', (job_id,))

            # If successful, update last_success
            if status == 'success':
                cursor.execute('''
                    UPDATE jobs SET last_success = CURRENT_TIMESTAMP WHERE job_id = ?
                ''', (job_id,))

            return cursor.lastrowid

    def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict]:
        """Get execution history for a job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM job_executions
                WHERE job_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (job_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_executions(self, limit: int = 100, include_quiet: bool = True) -> List[Dict]:
        """Get recent executions across all jobs.

        Args:
            limit: Maximum number of executions to return
            include_quiet: If False, exclude successful runs of quiet jobs
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if include_quiet:
                cursor.execute('''
                    SELECT e.*, j.name as job_name, j.target_bot, j.quiet
                    FROM job_executions e
                    JOIN jobs j ON e.job_id = j.job_id
                    ORDER BY e.executed_at DESC
                    LIMIT ?
                ''', (limit,))
            else:
                # Exclude successful runs of quiet jobs
                cursor.execute('''
                    SELECT e.*, j.name as job_name, j.target_bot, j.quiet
                    FROM job_executions e
                    JOIN jobs j ON e.job_id = j.job_id
                    WHERE NOT (j.quiet = 1 AND e.status = 'success')
                    ORDER BY e.executed_at DESC
                    LIMIT ?
                ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_failed_executions(self, since_hours: int = 24) -> List[Dict]:
        """Get failed executions in the last N hours."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.*, j.name as job_name, j.target_bot
                FROM job_executions e
                JOIN jobs j ON e.job_id = j.job_id
                WHERE e.status = 'failed'
                AND e.executed_at > datetime('now', ?)
                ORDER BY e.executed_at DESC
            ''', (f'-{since_hours} hours',))
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_executions(self, keep_days: int = 30) -> int:
        """Delete execution records older than N days."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM job_executions
                WHERE executed_at < datetime('now', ?)
            ''', (f'-{keep_days} days',))
            return cursor.rowcount

    # ─────────────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get scheduler statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Job counts
            cursor.execute('SELECT COUNT(*) FROM jobs')
            total_jobs = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM jobs WHERE enabled = 1')
            enabled_jobs = cursor.fetchone()[0]

            # Execution counts (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM job_executions
                WHERE executed_at > datetime('now', '-24 hours')
            ''')
            executions_24h = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM job_executions
                WHERE status = 'success' AND executed_at > datetime('now', '-24 hours')
            ''')
            successes_24h = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM job_executions
                WHERE status = 'failed' AND executed_at > datetime('now', '-24 hours')
            ''')
            failures_24h = cursor.fetchone()[0]

            return {
                'total_jobs': total_jobs,
                'enabled_jobs': enabled_jobs,
                'disabled_jobs': total_jobs - enabled_jobs,
                'executions_24h': executions_24h,
                'successes_24h': successes_24h,
                'failures_24h': failures_24h,
                'success_rate_24h': round(successes_24h / executions_24h * 100, 1) if executions_24h > 0 else 0
            }


# Global database instance
db = Database()
