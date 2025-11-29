"""API routes for Nigel - Quote Price Monitor."""

import threading
from flask import Blueprint, request, jsonify
from shared.auth.bot_api import api_key_required
from database.db import db
from services.price_checker import PriceChecker, compare_prices
from config import config
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Track running background job (only one check-all at a time)
_running_job = {'thread': None, 'started_by': None}


@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """Bot introduction."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'capabilities': [
            'Monitor quote prices over time',
            'Store baseline prices for quotes',
            'Detect price discrepancies via Banji',
            'Maintain historical price check log',
            'Web UI for viewing monitored quotes and history'
        ]
    })


# ─── Quote Management ───────────────────────────────────────────────

@api_bp.route('/quotes', methods=['GET'])
@api_key_required
def list_quotes():
    """List all monitored quotes."""
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    quotes = db.get_all_quotes(active_only=active_only)
    return jsonify({
        'success': True,
        'quotes': quotes,
        'count': len(quotes)
    })


@api_bp.route('/quotes', methods=['POST'])
@api_key_required
def add_quote():
    """
    Add a quote to be monitored.

    Request body:
        {
            "quote_id": "Q-12345",
            "org": "designer_drapes",
            "notes": "Optional notes"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    quote_id = data.get('quote_id')
    org = data.get('org')

    if not quote_id:
        return jsonify({'success': False, 'error': 'quote_id is required'}), 400
    if not org:
        return jsonify({'success': False, 'error': 'org is required'}), 400

    notes = data.get('notes', '')

    record_id = db.add_quote(quote_id, org, notes)
    quote = db.get_quote(quote_id)

    logger.info(f"Added quote {quote_id} to monitoring (org: {org})")

    return jsonify({
        'success': True,
        'message': f'Quote {quote_id} added to monitoring',
        'quote': quote
    }), 201


@api_bp.route('/quotes/<quote_id>', methods=['GET'])
@api_key_required
def get_quote(quote_id: str):
    """Get details for a monitored quote."""
    quote = db.get_quote(quote_id)

    if not quote:
        return jsonify({
            'success': False,
            'error': f'Quote {quote_id} not found'
        }), 404

    return jsonify({
        'success': True,
        'quote': quote
    })


@api_bp.route('/quotes/<quote_id>', methods=['DELETE'])
@api_key_required
def remove_quote(quote_id: str):
    """Remove a quote from monitoring."""
    quote = db.get_quote(quote_id)

    if not quote:
        return jsonify({
            'success': False,
            'error': f'Quote {quote_id} not found'
        }), 404

    db.delete_quote(quote_id)
    logger.info(f"Removed quote {quote_id} from monitoring")

    return jsonify({
        'success': True,
        'message': f'Quote {quote_id} removed from monitoring'
    })


@api_bp.route('/quotes/<quote_id>/deactivate', methods=['POST'])
@api_key_required
def deactivate_quote(quote_id: str):
    """Deactivate monitoring for a quote (keeps history)."""
    quote = db.get_quote(quote_id)

    if not quote:
        return jsonify({
            'success': False,
            'error': f'Quote {quote_id} not found'
        }), 404

    db.deactivate_quote(quote_id)
    logger.info(f"Deactivated monitoring for quote {quote_id}")

    return jsonify({
        'success': True,
        'message': f'Quote {quote_id} monitoring deactivated'
    })


@api_bp.route('/quotes/<quote_id>/activate', methods=['POST'])
@api_key_required
def activate_quote(quote_id: str):
    """Reactivate monitoring for a quote."""
    quote = db.get_quote(quote_id)

    if not quote:
        return jsonify({
            'success': False,
            'error': f'Quote {quote_id} not found'
        }), 404

    db.activate_quote(quote_id)
    logger.info(f"Reactivated monitoring for quote {quote_id}")

    return jsonify({
        'success': True,
        'message': f'Quote {quote_id} monitoring reactivated'
    })


# ─── Price Checking ─────────────────────────────────────────────────

@api_bp.route('/quotes/check', methods=['POST'])
@api_key_required
def check_quote_price():
    """
    Check the price of a single quote.

    Request body:
        {
            "quote_id": "Q-12345"
        }

    Or to check a quote not in the database:
        {
            "quote_id": "Q-12345",
            "org": "designer_drapes"
        }
    """
    data = request.get_json()

    if not data or not data.get('quote_id'):
        return jsonify({'success': False, 'error': 'quote_id is required'}), 400

    quote_id = data['quote_id']

    # Get quote from database or use provided org
    quote = db.get_quote(quote_id)
    org = data.get('org') or (quote['org'] if quote else None)

    if not org:
        return jsonify({
            'success': False,
            'error': f'Quote {quote_id} not found and no org provided'
        }), 400

    # Check the price via Banji
    checker = PriceChecker()
    result = checker.check_price(quote_id, org)

    if result['success']:
        current_price = result['price_after']

        # Determine if this is a discrepancy
        has_discrepancy = False
        discrepancy_amount = None

        if quote and quote['last_known_price']:
            # Compare with stored price
            has_discrepancy, discrepancy_amount = compare_prices(
                quote['last_known_price'],
                current_price
            )

            if has_discrepancy:
                # Create discrepancy record
                discrepancy_id = db.create_discrepancy(
                    quote_id=quote_id,
                    org=org,
                    expected_price=quote['last_known_price'],
                    actual_price=current_price,
                    difference=discrepancy_amount
                )
                logger.warning(
                    f"Price discrepancy detected for {quote_id}: "
                    f"expected {quote['last_known_price']}, got {current_price}"
                )
            else:
                logger.info(f"Price unchanged for {quote_id}: {current_price}")
        else:
            # First time seeing this quote, or no previous price
            if quote:
                logger.info(f"First price recorded for {quote_id}: {current_price}")
            else:
                # Auto-add to monitoring
                db.add_quote(quote_id, org)
                logger.info(f"Auto-added {quote_id} to monitoring with price {current_price}")

        # Update the stored price
        if quote or data.get('org'):
            db.update_quote_price(quote_id, current_price)

        # Log the price check
        db.log_price_check(
            quote_id=quote_id,
            org=org,
            status='success',
            price_before=result['price_before'],
            price_after=result['price_after'],
            has_discrepancy=has_discrepancy,
            discrepancy_amount=discrepancy_amount,
            banji_response=result['raw_response']
        )

        return jsonify({
            'success': True,
            'quote_id': quote_id,
            'org': org,
            'current_price': current_price,
            'previous_price': quote['last_known_price'] if quote else None,
            'has_discrepancy': has_discrepancy,
            'discrepancy_amount': discrepancy_amount,
            'is_new_quote': quote is None or quote['last_known_price'] is None
        })
    else:
        # Price check failed
        db.log_price_check(
            quote_id=quote_id,
            org=org,
            status='error',
            error_message=result['error'],
            banji_response=result['raw_response']
        )

        if quote:
            db.update_quote_checked(quote_id)

        return jsonify({
            'success': False,
            'quote_id': quote_id,
            'org': org,
            'error': result['error']
        }), 500


def _run_check_all_background(quotes, started_by):
    """
    Run price check in background thread.

    This is the actual work - processes all quotes and logs results to the database.
    Results are visible in the Price Checks history page.
    """
    global _running_job
    try:
        logger.info(f"Background price check started by {started_by} for {len(quotes)} quotes")

        # Build a lookup map for quick access to quote data
        quotes_map = {q['quote_id']: q for q in quotes}

        # Use batch checking - groups by org automatically
        checker = PriceChecker()
        batch_results = checker.check_prices_multi_org([
            {'quote_id': q['quote_id'], 'org': q['org']} for q in quotes
        ])

        results = {'checked': 0, 'discrepancies': 0, 'errors': 0}

        # Process each result
        for result in batch_results:
            quote_id = result['quote_id']
            org = result['org']
            quote = quotes_map.get(quote_id)

            if result['success']:
                current_price = result['price_after']
                has_discrepancy = False
                discrepancy_amount = None

                if quote and quote['last_known_price']:
                    has_discrepancy, discrepancy_amount = compare_prices(
                        quote['last_known_price'],
                        current_price
                    )

                    if has_discrepancy:
                        db.create_discrepancy(
                            quote_id=quote_id,
                            org=org,
                            expected_price=quote['last_known_price'],
                            actual_price=current_price,
                            difference=discrepancy_amount
                        )
                        results['discrepancies'] += 1

                db.update_quote_price(quote_id, current_price)
                db.log_price_check(
                    quote_id=quote_id,
                    org=org,
                    status='success',
                    price_before=result['price_before'],
                    price_after=result['price_after'],
                    has_discrepancy=has_discrepancy,
                    discrepancy_amount=discrepancy_amount,
                    banji_response=result['raw_response']
                )
                results['checked'] += 1
            else:
                db.log_price_check(
                    quote_id=quote_id,
                    org=org,
                    status='error',
                    error_message=result['error']
                )
                db.update_quote_checked(quote_id)
                results['errors'] += 1

        logger.info(
            f"Background price check completed by {started_by}: "
            f"{results['checked']}/{len(quotes)} successful, "
            f"{results['discrepancies']} discrepancies, {results['errors']} errors"
        )

    except Exception as e:
        logger.exception(f"Background price check failed: {e}")
    finally:
        # Clear running job state
        _running_job['thread'] = None
        _running_job['started_by'] = None


@api_bp.route('/quotes/check-all', methods=['POST'])
@api_key_required
def check_all_quotes():
    """
    Start a background price check for all active monitored quotes.

    This is a non-blocking endpoint - it returns immediately after starting
    the background job. The actual price checking runs asynchronously via
    Banji's job queue, and results are logged to the database.

    Check the /history endpoint or Price Checks page for results.

    Returns:
        202 Accepted with message if job started
        409 Conflict if a job is already running
    """
    global _running_job

    # Check if a job is already running
    if _running_job['thread'] is not None and _running_job['thread'].is_alive():
        return jsonify({
            'success': False,
            'error': 'A price check is already running',
            'started_by': _running_job['started_by']
        }), 409

    quotes = db.get_all_quotes(active_only=True)

    if not quotes:
        return jsonify({
            'success': True,
            'message': 'No active quotes to check',
            'total': 0
        })

    # Start background thread
    started_by = 'api'  # Could be enhanced to track caller
    thread = threading.Thread(
        target=_run_check_all_background,
        args=(quotes, started_by),
        daemon=True
    )
    thread.start()

    _running_job['thread'] = thread
    _running_job['started_by'] = started_by

    logger.info(f"Started background price check for {len(quotes)} quotes")

    return jsonify({
        'success': True,
        'message': f'Price check started for {len(quotes)} quotes',
        'total': len(quotes),
        'note': 'Check /api/history or Price Checks page for results'
    }), 202  # 202 Accepted


@api_bp.route('/quotes/check-all/status', methods=['GET'])
@api_key_required
def check_all_status():
    """
    Check if a price check job is currently running.

    Returns:
        {
            "running": true/false,
            "started_by": "api" or null
        }
    """
    is_running = _running_job['thread'] is not None and _running_job['thread'].is_alive()
    return jsonify({
        'success': True,
        'running': is_running,
        'started_by': _running_job['started_by'] if is_running else None
    })


# ─── History & Discrepancies ────────────────────────────────────────

@api_bp.route('/history', methods=['GET'])
@api_key_required
def get_history():
    """
    Get price check history.

    Query params:
        - quote_id: Filter by quote ID
        - discrepancies_only: Only show checks with discrepancies
        - limit: Max results (default 100)
    """
    quote_id = request.args.get('quote_id')
    discrepancies_only = request.args.get('discrepancies_only', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 100))

    checks = db.get_price_checks(
        quote_id=quote_id,
        discrepancies_only=discrepancies_only,
        limit=limit
    )

    return jsonify({
        'success': True,
        'history': checks,
        'count': len(checks)
    })


@api_bp.route('/discrepancies', methods=['GET'])
@api_key_required
def get_discrepancies():
    """
    Get detected discrepancies.

    Query params:
        - quote_id: Filter by quote ID
        - resolved: Filter by resolved status (true/false)
        - status: Filter by notification status
        - limit: Max results (default 100)
    """
    quote_id = request.args.get('quote_id')
    resolved = request.args.get('resolved')
    if resolved is not None:
        resolved = resolved.lower() == 'true'
    notification_status = request.args.get('status')
    limit = int(request.args.get('limit', 100))

    discrepancies = db.get_discrepancies(
        quote_id=quote_id,
        resolved=resolved,
        notification_status=notification_status,
        limit=limit
    )

    return jsonify({
        'success': True,
        'discrepancies': discrepancies,
        'count': len(discrepancies)
    })


@api_bp.route('/discrepancies/<int:discrepancy_id>/resolve', methods=['POST'])
@api_key_required
def resolve_discrepancy(discrepancy_id: int):
    """
    Mark a discrepancy as resolved.

    Request body:
        {
            "resolved_by": "user@example.com",
            "notes": "Optional resolution notes"
        }
    """
    data = request.get_json() or {}

    discrepancy = db.get_discrepancy(discrepancy_id)
    if not discrepancy:
        return jsonify({
            'success': False,
            'error': f'Discrepancy {discrepancy_id} not found'
        }), 404

    db.resolve_discrepancy(
        discrepancy_id=discrepancy_id,
        resolved_by=data.get('resolved_by', 'api'),
        resolution_notes=data.get('notes')
    )

    logger.info(f"Discrepancy {discrepancy_id} resolved")

    return jsonify({
        'success': True,
        'message': f'Discrepancy {discrepancy_id} resolved'
    })


# ─── Stats ──────────────────────────────────────────────────────────

@api_bp.route('/stats', methods=['GET'])
@api_key_required
def get_stats():
    """Get monitoring statistics."""
    stats = db.get_stats()
    recent = db.get_recent_checks_summary(hours=24)

    return jsonify({
        'success': True,
        'stats': {
            **stats,
            'last_24h': recent
        }
    })
