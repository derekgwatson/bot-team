"""Session-based API endpoints for atomic browser operations."""
import logging
from flask import Blueprint, request, jsonify
from shared.auth.bot_api import api_key_required
from config import config
from services.session_manager import get_session_manager

logger = logging.getLogger(__name__)

sessions_bp = Blueprint('sessions', __name__)


@sessions_bp.route('/start', methods=['POST'])
@api_key_required
def start_session():
    """
    Start a new browser session.

    Request body:
        {
            "org": "designer_drapes"
        }

    Returns:
        {
            "session_id": "uuid-here",
            "org": "designer_drapes",
            "created_at": "2025-01-20T14:30:22",
            "timeout_minutes": 30
        }
    """
    data = request.get_json()

    if not data or 'org' not in data:
        available_orgs = ', '.join(config.buz_orgs.keys())
        return jsonify({
            'error': f'Missing required field: org. Available orgs: {available_orgs}'
        }), 400

    org = data['org']

    try:
        session_manager = get_session_manager()
        session = session_manager.create_session(org)

        return jsonify({
            'session_id': session.session_id,
            'org': session.org_name,
            'created_at': session.created_at.isoformat(),
            'timeout_minutes': session_manager.session_timeout_minutes
        }), 201

    except ValueError as e:
        logger.error(f"Failed to create session for org {org}: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Unexpected error creating session for org {org}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>', methods=['DELETE'])
@api_key_required
def close_session(session_id: str):
    """
    Close a browser session.

    Returns:
        {
            "session_id": "uuid-here",
            "status": "closed"
        }
    """
    try:
        session_manager = get_session_manager()
        success = session_manager.close_session(session_id)

        if success:
            return jsonify({
                'session_id': session_id,
                'status': 'closed'
            }), 200
        else:
            return jsonify({
                'error': f'Session not found: {session_id}'
            }), 404

    except Exception as e:
        logger.exception(f"Error closing session {session_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>', methods=['GET'])
@api_key_required
def get_session_info(session_id: str):
    """
    Get information about a session.

    Returns:
        {
            "session_id": "uuid-here",
            "org": "designer_drapes",
            "created_at": "2025-01-20T14:30:22",
            "last_activity": "2025-01-20T14:35:10",
            "current_quote_id": "12345",
            "current_order_pk_id": "9b7b351a-..."
        }
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        return jsonify({
            'session_id': session.session_id,
            'org': session.org_name,
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'current_quote_id': session.current_quote_id,
            'current_order_pk_id': session.current_order_pk_id
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    except Exception as e:
        logger.exception(f"Error getting session info {session_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>/navigate/quote', methods=['POST'])
@api_key_required
def navigate_to_quote(session_id: str):
    """
    Navigate to a specific quote using Quick Lookup.

    Request body:
        {
            "quote_id": "12345"
        }

    Returns:
        {
            "quote_id": "12345",
            "order_pk_id": "9b7b351a-...",
            "current_url": "https://go.buzmanager.com/Sales/Summary?orderId=..."
        }
    """
    data = request.get_json()

    if not data or 'quote_id' not in data:
        return jsonify({'error': 'Missing required field: quote_id'}), 400

    quote_id = data['quote_id']

    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        # Navigate to quote
        order_pk_id = session.quote_page.navigate_to_quote(quote_id)

        # Store in session state
        session.current_quote_id = quote_id
        session.current_order_pk_id = order_pk_id

        return jsonify({
            'quote_id': quote_id,
            'order_pk_id': order_pk_id,
            'current_url': session.browser_manager.page.url
        }), 200

    except ValueError as e:
        logger.error(f"Navigation failed for session {session_id}, quote {quote_id}: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Unexpected error navigating to quote {quote_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>/quote/total', methods=['GET'])
@api_key_required
def get_quote_total(session_id: str):
    """
    Get the total price from the current quote summary page.

    Must be on a Sales/Summary page when calling this.

    Returns:
        {
            "total_price": 1234.56,
            "quote_id": "12345"  # if known
        }
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        # Verify we're on a summary page
        current_url = session.browser_manager.page.url
        if 'Sales/Summary' not in current_url:
            return jsonify({
                'error': 'Not on a quote summary page. Navigate to a quote first.',
                'current_url': current_url
            }), 400

        # Get total price
        total_price = session.quote_page.get_total_price()

        return jsonify({
            'total_price': total_price,
            'quote_id': session.current_quote_id
        }), 200

    except ValueError as e:
        logger.error(f"Failed to get total for session {session_id}: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Unexpected error getting total for session {session_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>/bulk-edit/open', methods=['POST'])
@api_key_required
def open_bulk_edit(session_id: str):
    """
    Open bulk edit page for the current quote.

    Request body (optional):
        {
            "order_pk_id": "9b7b351a-..."  # optional - uses current if not provided
        }

    Returns:
        {
            "status": "bulk_edit_opened",
            "order_pk_id": "9b7b351a-...",
            "current_url": "https://go.buzmanager.com/Sales/BulkEditOrder?orderPkId=..."
        }
    """
    data = request.get_json() or {}

    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        # Get order_pk_id from request or session state
        order_pk_id = data.get('order_pk_id') or session.current_order_pk_id

        if not order_pk_id:
            return jsonify({
                'error': 'No order_pk_id available. Navigate to a quote first or provide order_pk_id.'
            }), 400

        # Open bulk edit
        session.quote_page.open_bulk_edit(order_pk_id)

        return jsonify({
            'status': 'bulk_edit_opened',
            'order_pk_id': order_pk_id,
            'current_url': session.browser_manager.page.url
        }), 200

    except ValueError as e:
        logger.error(f"Failed to open bulk edit for session {session_id}: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Unexpected error opening bulk edit for session {session_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/<session_id>/bulk-edit/save', methods=['POST'])
@api_key_required
def save_bulk_edit(session_id: str):
    """
    Click Save button on bulk edit page.

    Must be on BulkEditOrder page when calling this.

    Returns:
        {
            "status": "saved",
            "current_url": "..."
        }
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        # Verify we're on bulk edit page
        current_url = session.browser_manager.page.url
        if 'BulkEditOrder' not in current_url:
            return jsonify({
                'error': 'Not on bulk edit page. Call /bulk-edit/open first.',
                'current_url': current_url
            }), 400

        # Save
        session.quote_page.save_bulk_edit()

        return jsonify({
            'status': 'saved',
            'current_url': session.browser_manager.page.url
        }), 200

    except ValueError as e:
        logger.error(f"Failed to save bulk edit for session {session_id}: {e}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Unexpected error saving bulk edit for session {session_id}")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/active', methods=['GET'])
@api_key_required
def list_active_sessions():
    """
    List all active sessions.

    Returns:
        {
            "session_count": 3,
            "sessions": [
                {
                    "session_id": "uuid-1",
                    "org": "designer_drapes",
                    "created_at": "...",
                    "last_activity": "..."
                },
                ...
            ]
        }
    """
    try:
        session_manager = get_session_manager()

        sessions_info = []
        with session_manager.lock:
            for session_id, session in session_manager.sessions.items():
                sessions_info.append({
                    'session_id': session.session_id,
                    'org': session.org_name,
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat()
                })

        return jsonify({
            'session_count': len(sessions_info),
            'sessions': sessions_info
        }), 200

    except Exception as e:
        logger.exception("Error listing active sessions")
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@sessions_bp.route('/health', methods=['GET'])
def sessions_health():
    """Health check for sessions API."""
    try:
        session_manager = get_session_manager()
        return jsonify({
            'status': 'healthy',
            'service': 'sessions',
            'active_sessions': session_manager.get_session_count(),
            'timeout_minutes': session_manager.session_timeout_minutes
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
