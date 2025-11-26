"""Quote-related API endpoints for Banji."""
from flask import Blueprint, request, jsonify
from services.auth import api_or_session_auth
from services.browser import BrowserManager
from services.quotes import LoginPage, QuotePage
from config import config
import logging

logger = logging.getLogger(__name__)

quotes_bp = Blueprint('quotes', __name__)


def get_headless_mode(data):
    """
    Determine headless mode for browser.

    API calls (with X-API-Key) always use headless mode.
    Web UI calls (session auth) can optionally use headed mode for debugging.

    Args:
        data: Request JSON data

    Returns:
        bool: True for headless, False for headed
    """
    # If API key is present, always use headless
    if request.headers.get("X-API-Key"):
        return True

    # For session auth (web UI), allow override
    # Default to headless, but allow headed=true to show browser
    if data and data.get('headed'):
        return False

    return True


@quotes_bp.route('/refresh-pricing', methods=['POST'])
@api_or_session_auth
def refresh_pricing():
    """
    Refresh pricing for a quote by triggering bulk edit save.

    Request body:
        {
            "quote_id": "Q-12345",
            "org": "designer_drapes"  # required: which Buz organization
        }

    Returns:
        {
            "success": true,
            "quote_id": "Q-12345",
            "org": "designer_drapes",
            "price_before": 1000.00,
            "price_after": 1200.00,
            "price_changed": true,
            "change_amount": 200.00,
            "change_percent": 20.0,
            "screenshot": "/screenshots/Q-12345_20250120_143022.png"  # if applicable
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    if 'quote_id' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required field: quote_id'
        }), 400

    if 'org' not in data:
        available_orgs = ', '.join(config.buz_orgs.keys())
        return jsonify({
            'success': False,
            'error': f'Missing required field: org. Available orgs: {available_orgs}'
        }), 400

    quote_id = data['quote_id']
    org = data['org']
    headless = get_headless_mode(data)

    logger.info(f"Received refresh-pricing request for quote: {quote_id}, org: {org}, headless: {headless}")

    try:
        # Get organization configuration
        org_config = config.get_org_config(org)

        # Use browser manager context to ensure cleanup
        # Pass org_config to load storage state for authentication
        with BrowserManager(config, org_config, headless=headless) as browser_manager:
            page = browser_manager.page

            # Verify authentication (storage state handles actual auth)
            login_page = LoginPage(page, config, org_config)
            login_page.login()

            # Execute quote pricing refresh workflow
            quote_page = QuotePage(page, config, org_config)
            result = quote_page.refresh_pricing(quote_id)

            # Add success flag and org info
            result['success'] = True
            result['org'] = org

            logger.info(f"Pricing refresh successful for {quote_id} (org: {org})")
            return jsonify(result), 200

    except ValueError as e:
        # Business logic errors (page not found, selectors failed, etc.)
        logger.error(f"Pricing refresh failed for {quote_id} (org: {org}): {e}")
        return jsonify({
            'success': False,
            'quote_id': quote_id,
            'org': org,
            'error': str(e)
        }), 400

    except Exception as e:
        # Unexpected errors
        logger.exception(f"Unexpected error during pricing refresh for {quote_id} (org: {org})")
        return jsonify({
            'success': False,
            'quote_id': quote_id,
            'org': org,
            'error': f'Internal error: {str(e)}'
        }), 500


@quotes_bp.route('/batch-refresh-pricing', methods=['POST'])
@api_or_session_auth
def batch_refresh_pricing():
    """
    Refresh pricing for multiple quotes in a single browser session.

    This is more efficient than calling /refresh-pricing multiple times
    because the browser stays open between quotes (no repeated startup cost).

    Request body:
        {
            "quote_ids": ["Q-12345", "Q-12346", "Q-12347"],
            "org": "designer_drapes"
        }

    Returns:
        {
            "success": true,
            "org": "designer_drapes",
            "total_quotes": 3,
            "successful": 2,
            "failed": 1,
            "results": [
                {
                    "quote_id": "Q-12345",
                    "success": true,
                    "price_before": 1000.00,
                    "price_after": 1200.00,
                    "price_changed": true,
                    "change_amount": 200.00,
                    "change_percent": 20.0
                },
                {
                    "quote_id": "Q-12346",
                    "success": false,
                    "error": "Could not navigate to quote Q-12346 - timeout"
                },
                ...
            ]
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    if 'quote_ids' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required field: quote_ids (array of quote IDs)'
        }), 400

    if not isinstance(data['quote_ids'], list):
        return jsonify({
            'success': False,
            'error': 'quote_ids must be an array'
        }), 400

    if len(data['quote_ids']) == 0:
        return jsonify({
            'success': False,
            'error': 'quote_ids array cannot be empty'
        }), 400

    if 'org' not in data:
        available_orgs = ', '.join(config.buz_orgs.keys())
        return jsonify({
            'success': False,
            'error': f'Missing required field: org. Available orgs: {available_orgs}'
        }), 400

    quote_ids = data['quote_ids']
    org = data['org']
    headless = get_headless_mode(data)

    logger.info(f"Received batch-refresh-pricing request for {len(quote_ids)} quotes, org: {org}, headless: {headless}")

    try:
        # Get organization configuration
        org_config = config.get_org_config(org)

        # Use browser manager context to ensure cleanup
        # Single browser session for all quotes
        with BrowserManager(config, org_config, headless=headless) as browser_manager:
            page = browser_manager.page

            # Verify authentication (storage state handles actual auth)
            login_page = LoginPage(page, config, org_config)
            login_page.login()

            # Execute batch quote pricing refresh workflow
            quote_page = QuotePage(page, config, org_config)
            result = quote_page.refresh_pricing_batch(quote_ids)

            # Add success flag and org info
            result['success'] = True
            result['org'] = org

            logger.info(f"Batch pricing refresh completed for org {org}: {result['successful']}/{result['total_quotes']} successful")
            return jsonify(result), 200

    except ValueError as e:
        # Business logic errors
        logger.error(f"Batch pricing refresh failed for org {org}: {e}")
        return jsonify({
            'success': False,
            'org': org,
            'error': str(e)
        }), 400

    except Exception as e:
        # Unexpected errors
        logger.exception(f"Unexpected error during batch pricing refresh for org {org}")
        return jsonify({
            'success': False,
            'org': org,
            'error': f'Internal error: {str(e)}'
        }), 500


@quotes_bp.route('/health', methods=['GET'])
def quotes_health():
    """Health check for quotes API."""
    return jsonify({
        'status': 'healthy',
        'service': 'quotes',
        'browser_mode': 'headless' if config.browser_headless else 'headed'
    }), 200
