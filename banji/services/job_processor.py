"""Background job processor for Banji.

Runs in a background thread and processes jobs from the queue.
Only one job is processed at a time (Playwright can only have one browser).
"""
import threading
import time
import logging
from typing import Optional, Callable, Dict, Any

from banji.database import db
from banji.services.browser import BrowserManager
from banji.services.quotes import LoginPage, QuotePage
from config import config

logger = logging.getLogger(__name__)


class JobProcessor:
    """Background job processor that handles async jobs."""

    def __init__(self, poll_interval: int = 5):
        """
        Initialize job processor.

        Args:
            poll_interval: Seconds between checking for new jobs
        """
        self.poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self):
        """Start the background processor thread."""
        if self._running:
            logger.warning("Job processor already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("Job processor started")

    def stop(self, timeout: float = 30.0):
        """Stop the background processor thread."""
        if not self._running:
            return

        logger.info("Stopping job processor...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Job processor thread did not stop cleanly")

        self._running = False
        logger.info("Job processor stopped")

    def is_running(self) -> bool:
        """Check if the processor is running."""
        return self._running and self._thread and self._thread.is_alive()

    def _run(self):
        """Main processing loop."""
        logger.info("Job processor thread started")

        while not self._stop_event.is_set():
            try:
                # Check for and process a pending job
                job = db.get_pending_job()

                if job:
                    logger.info(f"Processing job {job['id']} ({job['job_type']})")
                    self._process_job(job)
                else:
                    # No jobs, wait before checking again
                    self._stop_event.wait(self.poll_interval)

            except Exception as e:
                logger.exception(f"Error in job processor loop: {e}")
                # Wait before retrying to avoid tight error loops
                self._stop_event.wait(self.poll_interval)

        logger.info("Job processor thread exiting")

    def _process_job(self, job: Dict[str, Any]):
        """Process a single job based on its type."""
        job_id = job['id']
        job_type = job['job_type']

        try:
            if job_type == 'batch_refresh_pricing':
                self._process_batch_refresh_pricing(job)
            else:
                raise ValueError(f"Unknown job type: {job_type}")

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            db.fail_job(job_id, str(e))

    def _process_batch_refresh_pricing(self, job: Dict[str, Any]):
        """
        Process a batch refresh pricing job.

        This opens a browser, logs in, and refreshes pricing for each quote.
        Progress is updated after each quote.
        """
        job_id = job['id']
        org = job['org']
        payload = job['payload']
        quote_ids = payload.get('quote_ids', [])
        headless = payload.get('headless', True)

        total = len(quote_ids)
        db.update_job_progress(job_id, 0, total, f"Starting batch refresh for {total} quotes")

        logger.info(f"Job {job_id}: Starting batch refresh for {total} quotes (org: {org})")

        results = []
        successful = 0
        failed = 0

        try:
            # Get organization configuration
            org_config = config.get_org_config(org)

            # Use browser manager context to ensure cleanup
            with BrowserManager(config, org_config, headless=headless) as browser_manager:
                page = browser_manager.page

                # Verify authentication
                login_page = LoginPage(page, config, org_config)
                login_page.login()

                db.update_job_progress(job_id, 0, total, "Logged in, starting quote processing")

                # Process each quote
                quote_page = QuotePage(page, config, org_config)

                for i, quote_id in enumerate(quote_ids):
                    # Check if we should stop
                    if self._stop_event.is_set():
                        logger.warning(f"Job {job_id}: Interrupted by stop signal")
                        db.update_job_progress(
                            job_id, i, total,
                            f"Interrupted after {i}/{total} quotes"
                        )
                        break

                    db.update_job_progress(
                        job_id, i, total,
                        f"Processing quote {i + 1}/{total}: {quote_id}"
                    )

                    try:
                        result = quote_page.refresh_pricing(quote_id)
                        result['success'] = True
                        results.append(result)
                        successful += 1
                        logger.info(f"Job {job_id}: Quote {quote_id} processed successfully")

                    except Exception as e:
                        logger.error(f"Job {job_id}: Quote {quote_id} failed: {e}")
                        results.append({
                            'quote_id': quote_id,
                            'success': False,
                            'error': str(e)
                        })
                        failed += 1

            # Job completed
            final_result = {
                'total_quotes': total,
                'successful': successful,
                'failed': failed,
                'results': results
            }

            db.complete_job(job_id, final_result)
            logger.info(f"Job {job_id}: Completed - {successful}/{total} successful")

        except Exception as e:
            # Browser/login level failure
            logger.exception(f"Job {job_id}: Fatal error: {e}")
            db.fail_job(job_id, f"Fatal error: {str(e)}")


# Global processor instance
processor = JobProcessor()
