"""Price checking service - calls Banji to check quote prices."""

import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from shared.http_client import BotHttpClient
from config import config

logger = logging.getLogger(__name__)


class PriceChecker:
    """Service for checking quote prices via Banji."""

    def __init__(self, banji_url: str = None):
        self.banji_url = banji_url or config.banji_url
        # Batch operations can take a long time with many quotes
        self.banji = BotHttpClient(self.banji_url, timeout=600)

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
        Check prices for multiple quotes in a single browser session.

        This is much more efficient than calling check_price() multiple times
        because Banji keeps the browser open between quotes.

        Args:
            quote_ids: List of quote IDs to check
            org: The organization (all quotes must be from the same org)

        Returns:
            List of result dicts, one per quote (same format as check_price)
        """
        if not quote_ids:
            return []

        logger.info(f"Batch checking {len(quote_ids)} quotes for org {org}")

        try:
            response = self.banji.post('/api/quotes/batch-refresh-pricing', json={
                'quote_ids': quote_ids,
                'org': org
            })

            data = response.json()

            if response.status_code == 200 and data.get('success'):
                # Convert Banji's batch results to our standard format
                results = []
                for item in data.get('results', []):
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

                logger.info(f"Batch check complete: {data.get('successful', 0)}/{data.get('total_quotes', 0)} successful")
                return results
            else:
                # Entire batch failed
                error_msg = data.get('error', f'HTTP {response.status_code}')
                logger.error(f"Batch check failed for org {org}: {error_msg}")
                return [{
                    'success': False,
                    'quote_id': qid,
                    'org': org,
                    'price_before': None,
                    'price_after': None,
                    'price_changed': False,
                    'error': error_msg,
                    'raw_response': data
                } for qid in quote_ids]

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Batch check error for org {org}: {error_msg}")
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
