"""Quote-related API endpoints for Banji."""
from flask import Blueprint, request, jsonify
from shared.auth.bot_api import api_key_required
from services.browser import BrowserManager
from services.quotes import LoginPage, QuotePage
from config import config
import logging

logger = logging.getLogger(__name__)

quotes_bp = Blueprint('quotes', __name__)


@quotes_bp.route('/refresh-pricing', methods=['POST'])
@api_key_required
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

    logger.info(f"Received refresh-pricing request for quote: {quote_id}, org: {org}")

    try:
        # Get organization configuration
        org_config = config.get_org_config(org)

        # Use browser manager context to ensure cleanup
        with BrowserManager(config) as browser_manager:
            page = browser_manager.page

            # Login to Buz (with org-specific credentials)
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


@quotes_bp.route('/health', methods=['GET'])
def quotes_health():
    """Health check for quotes API."""
    return jsonify({
        'status': 'healthy',
        'service': 'quotes',
        'browser_mode': 'headless' if config.browser_headless else 'headed'
    }), 200
