"""Price checking service - calls Banji to check quote prices."""

import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation
from shared.http_client import BotHttpClient
from config import config

logger = logging.getLogger(__name__)


class PriceChecker:
    """Service for checking quote prices via Banji."""

    def __init__(self, banji_url: str = None):
        self.banji_url = banji_url or config.banji_url
        self.banji = BotHttpClient(self.banji_url, timeout=120)  # Browser ops can be slow

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
