"""Price checking service - calls Banji to check quote prices."""

import logging
import time
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from shared.http_client import BotHttpClient
from config import config

logger = logging.getLogger(__name__)

# Default polling configuration
DEFAULT_POLL_INTERVAL = 5  # seconds between status checks
DEFAULT_MAX_WAIT_TIME = 3600  # 1 hour max wait time


class PriceChecker:
    """Service for checking quote prices via Banji."""

    def __init__(self, banji_url: str = None):
        self.banji_url = banji_url or config.banji_url
        # Short timeout for quick operations and polling
        self.banji = BotHttpClient(self.banji_url, timeout=30)
        # Polling configuration
        self.poll_interval = DEFAULT_POLL_INTERVAL
        self.max_wait_time = DEFAULT_MAX_WAIT_TIME

    def check_price(self, quote_id: str, org: str) -> Dict:
        """
        Check the current price of a quote via Banji.

        Returns:
            {
                'success': bool,
                'quote_id': str,
                'org': str,
                'price_before': str or None,  # Price before refresh
                'price_after': str or None,   # Price after refresh (current price)
                'price_changed': bool,
                'error': str or None,
                'raw_response': dict
            }
        """
        logger.info(f"Checking price for quote {quote_id} (org: {org})")

        try:
            response = self.banji.post('/api/quotes/refresh-pricing', json={
                'quote_id': quote_id,
                'org': org
            })

            data = response.json()

            if response.status_code == 200 and data.get('success'):
                # Successful price check
                result = {
                    'success': True,
                    'quote_id': quote_id,
                    'org': org,
                    'price_before': str(data.get('price_before')) if data.get('price_before') is not None else None,
                    'price_after': str(data.get('price_after')) if data.get('price_after') is not None else None,
                    'price_changed': data.get('price_changed', False),
                    'error': None,
                    'raw_response': data
                }
                logger.info(f"Price check successful for {quote_id}: {result['price_after']}")
                return result
            else:
                # Banji returned an error
                error_msg = data.get('error', f'HTTP {response.status_code}')
                result = {
                    'success': False,
                    'quote_id': quote_id,
                    'org': org,
                    'price_before': None,
                    'price_after': None,
                    'price_changed': False,
                    'error': error_msg,
                    'raw_response': data
                }
                logger.warning(f"Price check failed for {quote_id}: {error_msg}")
                return result

        except Exception as e:
            # Network or other error
            error_msg = str(e)
            logger.error(f"Price check error for {quote_id}: {error_msg}")
            return {
                'success': False,
                'quote_id': quote_id,
                'org': org,
                'price_before': None,
                'price_after': None,
                'price_changed': False,
                'error': error_msg,
                'raw_response': None
            }

    def check_prices_batch(self, quote_ids: List[str], org: str) -> List[Dict]:
        """
        Check prices for multiple quotes using Banji's async job queue.

        This submits a job to Banji and polls for completion. The job runs
        in Banji's background worker and can take as long as needed without
        HTTP timeout issues.

        Args:
            quote_ids: List of quote IDs to check
            org: The organization (all quotes must be from the same org)

        Returns:
            List of result dicts, one per quote (same format as check_price)
        """
        if not quote_ids:
            return []

        logger.info(f"Batch checking {len(quote_ids)} quotes for org {org} (async)")

        try:
            # Step 1: Submit job to Banji
            response = self.banji.post('/api/quotes/batch-refresh-pricing-async', json={
                'quote_ids': quote_ids,
                'org': org
            })

            if response.status_code != 202:
                data = response.json()
                error_msg = data.get('error', f'HTTP {response.status_code}')
                logger.error(f"Failed to submit batch job for org {org}: {error_msg}")
                return self._make_error_results(quote_ids, org, error_msg)

            data = response.json()
            job_id = data.get('job_id')
            logger.info(f"Submitted job {job_id} for {len(quote_ids)} quotes (org: {org})")

            # Step 2: Poll for completion
            result = self._poll_job(job_id, quote_ids, org)
            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Batch check error for org {org}: {error_msg}")
            return self._make_error_results(quote_ids, org, error_msg)

    def _poll_job(self, job_id: str, quote_ids: List[str], org: str) -> List[Dict]:
        """
        Poll for job completion and return results.

        Args:
            job_id: The job ID to poll
            quote_ids: Original quote IDs (for error results if needed)
            org: Organization

        Returns:
            List of result dicts
        """
        start_time = time.time()
        last_progress = None

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.max_wait_time:
                logger.error(f"Job {job_id} timed out after {elapsed:.0f}s")
                return self._make_error_results(
                    quote_ids, org,
                    f"Job timed out after {self.max_wait_time} seconds"
                )

            try:
                response = self.banji.get(f'/api/quotes/jobs/{job_id}')
                if response.status_code != 200:
                    logger.error(f"Failed to get job status: HTTP {response.status_code}")
                    time.sleep(self.poll_interval)
                    continue

                job = response.json().get('job', {})
                status = job.get('status')
                progress_msg = job.get('progress_message')

                # Log progress updates (but not every poll)
                if progress_msg and progress_msg != last_progress:
                    logger.info(f"Job {job_id}: {progress_msg}")
                    last_progress = progress_msg

                if status == 'completed':
                    result_data = job.get('result', {})
                    logger.info(
                        f"Job {job_id} completed: "
                        f"{result_data.get('successful', 0)}/{result_data.get('total_quotes', 0)} successful"
                    )
                    return self._format_batch_results(result_data, org)

                elif status == 'failed':
                    error = job.get('error', 'Unknown error')
                    logger.error(f"Job {job_id} failed: {error}")
                    return self._make_error_results(quote_ids, org, error)

                elif status in ('pending', 'processing'):
                    # Still running, wait and poll again
                    time.sleep(self.poll_interval)

                else:
                    logger.warning(f"Job {job_id} has unknown status: {status}")
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.warning(f"Error polling job {job_id}: {e}")
                time.sleep(self.poll_interval)

    def _format_batch_results(self, result_data: Dict, org: str) -> List[Dict]:
        """Format Banji's batch results to our standard format."""
        results = []
        for item in result_data.get('results', []):
            if item.get('success'):
                results.append({
                    'success': True,
                    'quote_id': item['quote_id'],
                    'org': org,
                    'price_before': str(item.get('price_before')) if item.get('price_before') is not None else None,
                    'price_after': str(item.get('price_after')) if item.get('price_after') is not None else None,
                    'price_changed': item.get('price_changed', False),
                    'error': None,
                    'raw_response': item
                })
            else:
                results.append({
                    'success': False,
                    'quote_id': item['quote_id'],
                    'org': org,
                    'price_before': None,
                    'price_after': None,
                    'price_changed': False,
                    'error': item.get('error', 'Unknown error'),
                    'raw_response': item
                })
        return results

    def _make_error_results(self, quote_ids: List[str], org: str, error_msg: str) -> List[Dict]:
        """Create error results for all quotes."""
        return [{
            'success': False,
            'quote_id': qid,
            'org': org,
            'price_before': None,
            'price_after': None,
            'price_changed': False,
            'error': error_msg,
            'raw_response': None
        } for qid in quote_ids]

    def check_prices_multi_org(self, quotes: List[Dict]) -> List[Dict]:
        """
        Check prices for quotes across multiple organizations.

        Groups quotes by org and makes one batch call per org.

        Args:
            quotes: List of dicts with 'quote_id' and 'org' keys

        Returns:
            List of result dicts, one per quote
        """
        if not quotes:
            return []

        # Group quotes by org
        by_org = defaultdict(list)
        for q in quotes:
            by_org[q['org']].append(q['quote_id'])

        # Process each org as a batch
        all_results = []
        for org, quote_ids in by_org.items():
            results = self.check_prices_batch(quote_ids, org)
            all_results.extend(results)

        return all_results


def compare_prices(expected: str, actual: str) -> Tuple[bool, Optional[str]]:
    """
    Compare two prices and determine if there's a discrepancy.

    Args:
        expected: The expected price (from database)
        actual: The actual price (from Banji)

    Returns:
        Tuple of (has_discrepancy: bool, difference: str or None)
    """
    if expected is None or actual is None:
        return False, None

    try:
        expected_dec = Decimal(expected.replace(',', '').replace('$', '').strip())
        actual_dec = Decimal(actual.replace(',', '').replace('$', '').strip())

        if expected_dec != actual_dec:
            difference = actual_dec - expected_dec
            return True, str(difference)
        return False, None

    except (InvalidOperation, ValueError) as e:
        logger.warning(f"Could not compare prices '{expected}' vs '{actual}': {e}")
        # If we can't parse prices, do string comparison
        if expected.strip() != actual.strip():
            return True, f"'{expected}' -> '{actual}'"
        return False, None


def format_price_change(expected: str, actual: str, difference: str) -> str:
    """Format a price change for display."""
    try:
        diff_dec = Decimal(difference)
        if diff_dec > 0:
            return f"Price increased by ${diff_dec:,.2f} (was ${expected}, now ${actual})"
        else:
            return f"Price decreased by ${abs(diff_dec):,.2f} (was ${expected}, now ${actual})"
    except (InvalidOperation, ValueError):
        return f"Price changed from {expected} to {actual}"
