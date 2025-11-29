"""Quote-related API endpoints for Banji."""
from flask import Blueprint, request, jsonify
from shared.auth.bot_api import api_or_session_auth
from services.browser import BrowserManager
from services.quotes import LoginPage, QuotePage
from database import db as job_db
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


@quotes_bp.route('/batch-refresh-pricing-async', methods=['POST'])
@api_or_session_auth
def batch_refresh_pricing_async():
    """
    Queue a batch pricing refresh job for async processing.

    Unlike the sync endpoint, this returns immediately with a job ID.
    The job runs in the background and can take as long as needed.
    Poll /jobs/{job_id} to check status and get results.

    Request body:
        {
            "quote_ids": ["12345", "12346", "12347"],
            "org": "canberra"
        }

    Returns:
        {
            "success": true,
            "job_id": "abc123-...",
            "message": "Job queued for 3 quotes"
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

    # Validate org exists
    try:
        config.get_org_config(org)
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

    # Create job
    job_id = job_db.create_job(
        job_type='batch_refresh_pricing',
        org=org,
        payload={
            'quote_ids': quote_ids,
            'headless': headless
        }
    )

    logger.info(f"Created async job {job_id} for batch refresh of {len(quote_ids)} quotes (org: {org})")

    return jsonify({
        'success': True,
        'job_id': job_id,
        'message': f'Job queued for {len(quote_ids)} quotes',
        'status_url': f'/api/quotes/jobs/{job_id}'
    }), 202  # 202 Accepted


@quotes_bp.route('/jobs/<job_id>', methods=['GET'])
@api_or_session_auth
def get_job_status(job_id):
    """
    Get status and results for a job.

    Returns:
        {
            "success": true,
            "job": {
                "id": "abc123-...",
                "job_type": "batch_refresh_pricing",
                "org": "canberra",
                "status": "processing",  // pending, processing, completed, failed
                "progress_current": 5,
                "progress_total": 32,
                "progress_message": "Processing quote 5/32: 12345",
                "created_at": "2025-01-15 10:30:00",
                "started_at": "2025-01-15 10:30:02",
                "completed_at": null,
                "result": null,  // populated when completed
                "error": null    // populated when failed
            }
        }
    """
    job = job_db.get_job(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': f'Job {job_id} not found'
        }), 404

    return jsonify({
        'success': True,
        'job': job
    })


@quotes_bp.route('/jobs', methods=['GET'])
@api_or_session_auth
def list_jobs():
    """
    List recent jobs with optional filters.

    Query params:
        status: Filter by status (pending, processing, completed, failed)
        org: Filter by organization
        limit: Max results (default 50)

    Returns:
        {
            "success": true,
            "jobs": [...]
        }
    """
    status = request.args.get('status')
    org = request.args.get('org')
    limit = request.args.get('limit', 50, type=int)

    jobs = job_db.get_jobs(status=status, org=org, limit=limit)

    return jsonify({
        'success': True,
        'count': len(jobs),
        'jobs': jobs
    })


@quotes_bp.route('/health', methods=['GET'])
def quotes_health():
    """Health check for quotes API."""
    return jsonify({
        'status': 'healthy',
        'service': 'quotes',
        'browser_mode': 'headless' if config.browser_headless else 'headed'
    }), 200
