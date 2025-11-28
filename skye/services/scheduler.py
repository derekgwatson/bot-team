"""
Scheduler service for Skye - manages APScheduler jobs.

This service:
- Loads jobs from the database on startup
- Executes jobs by calling other bots' APIs
- Records execution results
- Provides methods to add/remove/modify jobs at runtime
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from config import config
from shared.http_client import BotHttpClient

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled jobs using APScheduler."""

    def __init__(self, db=None):
        """Initialize the scheduler service."""
        self._scheduler = None
        self._db = db
        self._bot_api_key = config.bot_api_key
        self._running = False

        # Bot URL resolution
        self._bot_urls = {}

    def _get_db(self):
        """Lazy load database to avoid circular imports."""
        if self._db is None:
            from services.database import db
            self._db = db
        return self._db

    def _get_bot_url(self, bot_name: str) -> str:
        """
        Get the base URL for a bot.

        In production, use the bot's domain.
        In development, use localhost with the bot's port.
        """
        if bot_name in self._bot_urls:
            return self._bot_urls[bot_name]

        # Check if we're in production (SKYE_ENV=production)
        is_prod = os.getenv('SKYE_ENV', 'development') == 'production'

        if is_prod:
            # In production, use the bot's domain
            url = f"https://{bot_name}.watsonblinds.com.au"
        else:
            # In development, use localhost with port from Chester's config
            from shared.config.ports import get_port
            port = get_port(bot_name)
            if port:
                url = f"http://localhost:{port}"
            else:
                logger.warning(f"No port found for bot {bot_name}, using default")
                url = f"http://localhost:8000"

        self._bot_urls[bot_name] = url
        return url

    def start(self):
        """Start the scheduler and load jobs from database."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        # Create scheduler with timezone
        self._scheduler = BackgroundScheduler(
            jobstores={'default': MemoryJobStore()},
            timezone=config.scheduler_timezone
        )

        # Seed jobs from config templates (creates missing jobs)
        self._seed_jobs_from_templates()

        # Load jobs from database
        self._load_jobs_from_db()

        # Start scheduler
        self._scheduler.start()
        self._running = True
        logger.info(f"Scheduler started with {len(self._scheduler.get_jobs())} jobs")

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def _load_jobs_from_db(self):
        """Load all enabled jobs from the database."""
        db = self._get_db()
        jobs = db.get_enabled_jobs()

        for job_data in jobs:
            try:
                self._add_job_to_scheduler(job_data)
            except Exception as e:
                logger.error(f"Failed to load job {job_data['job_id']}: {e}")

    def _seed_jobs_from_templates(self):
        """Seed jobs from config templates if they don't exist.

        This ensures that job_templates defined in config.yaml are
        automatically created in the database on first run.
        """
        db = self._get_db()
        templates = config.job_templates

        for job_id, template in templates.items():
            # Check if job already exists
            existing = db.get_job(job_id)
            if existing:
                logger.debug(f"Job {job_id} already exists, skipping seed")
                continue

            # Extract schedule config from template
            schedule = template.get('schedule', {})
            schedule_type = schedule.get('type', 'cron')

            # Build schedule_config dict (everything except 'type')
            schedule_config = {k: v for k, v in schedule.items() if k != 'type'}

            try:
                db.create_job(
                    job_id=job_id,
                    name=template.get('name', job_id),
                    target_bot=template.get('target_bot'),
                    endpoint=template.get('endpoint'),
                    method=template.get('method', 'POST'),
                    schedule_type=schedule_type,
                    schedule_config=json.dumps(schedule_config),
                    description=template.get('description'),
                    enabled=True,
                    created_by='system'
                )
                logger.info(f"Seeded job from template: {job_id}")
            except Exception as e:
                logger.error(f"Failed to seed job {job_id}: {e}")

    def _add_job_to_scheduler(self, job_data: Dict):
        """Add a job to APScheduler based on database config."""
        job_id = job_data['job_id']
        schedule_type = job_data['schedule_type']
        schedule_config = json.loads(job_data['schedule_config'])

        # Create trigger based on schedule type
        if schedule_type == 'cron':
            trigger = CronTrigger(
                year=schedule_config.get('year'),
                month=schedule_config.get('month'),
                day=schedule_config.get('day'),
                week=schedule_config.get('week'),
                day_of_week=schedule_config.get('day_of_week'),
                hour=schedule_config.get('hour', '*'),
                minute=schedule_config.get('minute', '0'),
                second=schedule_config.get('second', '0'),
                timezone=config.scheduler_timezone
            )
        elif schedule_type == 'interval':
            trigger = IntervalTrigger(
                weeks=schedule_config.get('weeks', 0),
                days=schedule_config.get('days', 0),
                hours=schedule_config.get('hours', 0),
                minutes=schedule_config.get('minutes', 0),
                seconds=schedule_config.get('seconds', 0),
                timezone=config.scheduler_timezone
            )
        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")

        # Add job to scheduler
        self._scheduler.add_job(
            func=self._execute_job,
            trigger=trigger,
            id=job_id,
            name=job_data['name'],
            args=[job_id],
            replace_existing=True,
            misfire_grace_time=config.misfire_grace_time * 60,  # Convert to seconds
            max_instances=config.max_instances
        )

        logger.info(f"Added job to scheduler: {job_id} ({job_data['name']})")

    def _execute_job(self, job_id: str):
        """Execute a scheduled job by calling the target bot's API."""
        db = self._get_db()
        job_data = db.get_job(job_id)

        if not job_data:
            logger.error(f"Job {job_id} not found in database")
            return

        if not job_data['enabled']:
            logger.info(f"Job {job_id} is disabled, skipping")
            return

        start_time = datetime.now()
        target_bot = job_data['target_bot']
        endpoint = job_data['endpoint']
        method = job_data['method'].upper()

        # Build URL and client
        base_url = self._get_bot_url(target_bot)
        client = BotHttpClient(base_url, timeout=60)

        logger.info(f"Executing job {job_id}: {method} {base_url}{endpoint}")

        try:
            # Make request
            if method == 'GET':
                response = client.get(endpoint)
            elif method == 'POST':
                response = client.post(endpoint, json={})
            elif method == 'PUT':
                response = client.put(endpoint, json={})
            elif method == 'DELETE':
                response = client.delete(endpoint)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Calculate duration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Determine status
            if response.ok:
                status = 'success'
                logger.info(f"Job {job_id} completed successfully ({response.status_code})")
            else:
                status = 'failed'
                logger.warning(f"Job {job_id} failed with status {response.status_code}")

            # Truncate response body if too long
            response_body = response.text[:10000] if response.text else None

            # Record execution
            db.record_execution(
                job_id=job_id,
                status=status,
                response_code=response.status_code,
                response_body=response_body,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Job {job_id} failed with exception: {e}")

            db.record_execution(
                job_id=job_id,
                status='failed',
                error_message=str(e),
                duration_ms=duration_ms
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Runtime Job Management
    # ─────────────────────────────────────────────────────────────────────────

    def add_job(
        self,
        job_id: str,
        name: str,
        target_bot: str,
        endpoint: str,
        method: str = "POST",
        schedule_type: str = "cron",
        schedule_config: Dict = None,
        description: str = None,
        enabled: bool = True,
        created_by: str = None
    ) -> bool:
        """Add a new job to both database and scheduler."""
        db = self._get_db()

        # Create in database
        db.create_job(
            job_id=job_id,
            name=name,
            target_bot=target_bot,
            endpoint=endpoint,
            method=method,
            schedule_type=schedule_type,
            schedule_config=json.dumps(schedule_config or {}),
            description=description,
            enabled=enabled,
            created_by=created_by
        )

        # Add to scheduler if enabled
        if enabled and self._running:
            job_data = db.get_job(job_id)
            self._add_job_to_scheduler(job_data)

        return True

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update a job in both database and scheduler."""
        db = self._get_db()

        # Handle schedule_config serialization
        if 'schedule_config' in kwargs and isinstance(kwargs['schedule_config'], dict):
            kwargs['schedule_config'] = json.dumps(kwargs['schedule_config'])

        # Update in database
        if not db.update_job(job_id, **kwargs):
            return False

        # Reload job in scheduler
        if self._running:
            self._scheduler.remove_job(job_id, jobstore='default')
            job_data = db.get_job(job_id)
            if job_data and job_data['enabled']:
                self._add_job_to_scheduler(job_data)

        return True

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from both database and scheduler."""
        db = self._get_db()

        # Remove from scheduler
        if self._running:
            try:
                self._scheduler.remove_job(job_id, jobstore='default')
            except Exception:
                pass  # Job might not exist in scheduler

        # Remove from database
        return db.delete_job(job_id)

    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        db = self._get_db()
        if not db.set_job_enabled(job_id, True):
            return False

        # Add to scheduler
        if self._running:
            job_data = db.get_job(job_id)
            if job_data:
                self._add_job_to_scheduler(job_data)

        return True

    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        db = self._get_db()
        if not db.set_job_enabled(job_id, False):
            return False

        # Remove from scheduler
        if self._running:
            try:
                self._scheduler.remove_job(job_id, jobstore='default')
            except Exception:
                pass

        return True

    def run_job_now(self, job_id: str) -> Dict:
        """Manually trigger a job to run immediately (async).

        The job runs in the background via APScheduler. Check job history
        for the result.
        """
        db = self._get_db()
        job_data = db.get_job(job_id)

        if not job_data:
            return {'success': False, 'error': 'Job not found'}

        if not self._running or not self._scheduler:
            return {'success': False, 'error': 'Scheduler not running'}

        # Add a one-time job that runs immediately in the background
        # Use a unique ID so it doesn't conflict with the scheduled job
        run_id = f"{job_id}_manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        self._scheduler.add_job(
            func=self._execute_job,
            trigger='date',  # One-time execution
            run_date=datetime.now(),  # Run immediately
            id=run_id,
            name=f"Manual: {job_data['name']}",
            args=[job_id],
            misfire_grace_time=60
        )

        logger.info(f"Queued manual execution of job {job_id} as {run_id}")

        return {'success': True, 'queued': True, 'message': 'Job queued for execution'}

    def get_scheduled_jobs(self) -> list:
        """Get list of jobs currently scheduled in APScheduler."""
        if not self._running or not self._scheduler:
            return []

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time) if job.next_run_time else None,
                'pending': job.pending
            })
        return jobs

    def get_next_run_time(self, job_id: str) -> Optional[str]:
        """Get the next scheduled run time for a job."""
        if not self._running or not self._scheduler:
            return None

        try:
            job = self._scheduler.get_job(job_id)
            if job and job.next_run_time:
                return str(job.next_run_time)
        except Exception:
            pass

        return None


# Global scheduler instance
scheduler_service = SchedulerService()
