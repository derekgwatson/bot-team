"""Database manager for Banji's job queue."""
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from shared.migrations import MigrationRunner


class Database:
    """Database manager for Banji's async job queue."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'banji.db'
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
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Jobs ────────────────────────────────────────────────────────

    def create_job(
        self,
        job_type: str,
        org: str,
        payload: Dict[str, Any]
    ) -> str:
        """
        Create a new job. Returns the job ID.

        Args:
            job_type: Type of job (e.g., 'batch_refresh_pricing')
            org: Buz organization
            payload: Job-specific data (e.g., quote_ids list)

        Returns:
            Job ID (UUID string)
        """
        job_id = str(uuid.uuid4())
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO jobs (id, job_type, org, payload, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (job_id, job_type, org, json.dumps(payload)))

        conn.commit()
        conn.close()
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a job by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            job = dict(row)
            if job.get('payload'):
                try:
                    job['payload'] = json.loads(job['payload'])
                except json.JSONDecodeError:
                    pass
            if job.get('result'):
                try:
                    job['result'] = json.loads(job['result'])
                except json.JSONDecodeError:
                    pass
            return job
        return None

    def get_pending_job(self) -> Optional[Dict]:
        """
        Get the oldest pending job and mark it as processing.
        Returns None if no pending jobs.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Atomically claim a job
        cursor.execute("""
            UPDATE jobs
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
            )
            RETURNING *
        """)

        row = cursor.fetchone()
        conn.commit()
        conn.close()

        if row:
            job = dict(row)
            if job.get('payload'):
                try:
                    job['payload'] = json.loads(job['payload'])
                except json.JSONDecodeError:
                    pass
            return job
        return None

    def update_job_progress(
        self,
        job_id: str,
        progress_current: int,
        progress_total: int,
        progress_message: str = None
    ):
        """Update job progress (for long-running jobs)."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE jobs
            SET progress_current = ?,
                progress_total = ?,
                progress_message = ?
            WHERE id = ?
        """, (progress_current, progress_total, progress_message, job_id))

        conn.commit()
        conn.close()

    def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark a job as completed with results."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE jobs
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                result = ?
            WHERE id = ?
        """, (json.dumps(result), job_id))

        conn.commit()
        conn.close()

    def fail_job(self, job_id: str, error: str):
        """Mark a job as failed with error message."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE jobs
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE id = ?
        """, (error, job_id))

        conn.commit()
        conn.close()

    def get_jobs(
        self,
        status: str = None,
        org: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get jobs with optional filters."""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if org:
            query += " AND org = ?"
            params.append(org)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            job = dict(row)
            if job.get('payload'):
                try:
                    job['payload'] = json.loads(job['payload'])
                except json.JSONDecodeError:
                    pass
            if job.get('result'):
                try:
                    job['result'] = json.loads(job['result'])
                except json.JSONDecodeError:
                    pass
            results.append(job)
        return results

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """Delete completed/failed jobs older than N days. Returns count deleted."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM jobs
            WHERE status IN ('completed', 'failed')
            AND completed_at < datetime('now', ? || ' days')
        """, (f'-{days}',))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def reset_stuck_jobs(self, minutes: int = 30) -> int:
        """
        Reset jobs stuck in 'processing' state for too long.
        Returns count reset.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE jobs
            SET status = 'pending',
                started_at = NULL,
                progress_current = 0,
                progress_message = 'Reset after being stuck'
            WHERE status = 'processing'
            AND started_at < datetime('now', ? || ' minutes')
        """, (f'-{minutes}',))

        reset_count = cursor.rowcount
        conn.commit()
        conn.close()
        return reset_count

    def get_stats(self) -> Dict:
        """Get job queue statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM jobs
        """)

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else {
            'total': 0,
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0
        }


# Global database instance
db = Database()
