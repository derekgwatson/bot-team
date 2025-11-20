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
            "quote_id": "Q-12345"
        }

    Returns:
        {
            "success": true,
            "quote_id": "Q-12345",
            "price_before": 1000.00,
            "price_after": 1200.00,
            "price_changed": true,
            "change_amount": 200.00,
            "change_percent": 20.0,
            "screenshot": "/screenshots/Q-12345_20250120_143022.png"  # if applicable
        }
    """
    data = request.get_json()

    if not data or 'quote_id' not in data:
        return jsonify({
            'success': False,
            'error': 'Missing required field: quote_id'
        }), 400

    quote_id = data['quote_id']
    logger.info(f"Received refresh-pricing request for quote: {quote_id}")

    try:
        # Use browser manager context to ensure cleanup
        with BrowserManager(config) as browser_manager:
            page = browser_manager.page

            # Login to Buz
            login_page = LoginPage(page, config)
            login_page.login()

            # Execute quote pricing refresh workflow
            quote_page = QuotePage(page, config)
            result = quote_page.refresh_pricing(quote_id)

            # Add success flag
            result['success'] = True

            logger.info(f"Pricing refresh successful for {quote_id}")
            return jsonify(result), 200

    except ValueError as e:
        # Business logic errors (page not found, selectors failed, etc.)
        logger.error(f"Pricing refresh failed for {quote_id}: {e}")
        return jsonify({
            'success': False,
            'quote_id': quote_id,
            'error': str(e)
        }), 400

    except Exception as e:
        # Unexpected errors
        logger.exception(f"Unexpected error during pricing refresh for {quote_id}")
        return jsonify({
            'success': False,
            'quote_id': quote_id,
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
