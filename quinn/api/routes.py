from flask import Blueprint, jsonify, request, session
from functools import wraps
from services.peter_client import peter_client
from services.sync_service import sync_service
from services.google_groups import groups_service
from services import settings
import os

api_bp = Blueprint('api', __name__)

@api_bp.route('/dependencies', methods=['GET'])
def get_dependencies():
    """Get list of bots that Quinn depends on"""
    return jsonify({
        'dependencies': ['peter']
    })

@api_bp.route('/dev-config', methods=['GET'])
def get_dev_config():
    """Get current dev bot configuration (from session)"""
    return jsonify(session.get('dev_bot_config', {}))

@api_bp.route('/dev-config', methods=['POST'])
def update_dev_config():
    """Update dev bot configuration (stores in session)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get existing config or create new
    dev_config = session.get('dev_bot_config', {})

    # Update with new settings
    dev_config.update(data)

    # Store in session
    session['dev_bot_config'] = dev_config

    return jsonify({
        'success': True,
        'config': dev_config
    })

def require_api_key(f):
    """Decorator to require API key for bot-to-bot communication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.environ.get('BOT_API_KEY')

        if not expected_key:
            # If no API key is configured, allow (for initial setup)
            return f(*args, **kwargs)

        if api_key != expected_key:
            return jsonify({'error': 'Invalid or missing API key'}), 401

        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    GET /api/intro

    Returns Quinn's introduction
    """
    return jsonify({
        'name': 'Quinn',
        'greeting': "Hi! I'm Quinn, your all-staff group manager.",
        'description': "I keep the allstaff Google Group in perfect sync with Peter's HR database. I check with Peter to see who should be in the group and automatically add or remove people as needed.",
        'capabilities': [
            'Automatically sync allstaff Google Group with Peter\'s database',
            'Check if staff members are approved for access (for Pam)',
            'Trigger manual sync when needed',
            'Report on sync status and history',
            'REST API for bot-to-bot integration'
        ]
    })

@api_bp.route('/is-approved', methods=['GET'])
@require_api_key
def is_approved():
    """
    GET /api/is-approved?email=xxx
    Header: X-API-Key: <api_key>

    Check if an email address is approved for access
    (Now delegates to Peter instead of using own database)

    Returns:
        JSON with approval status and staff info
    """
    email = request.args.get('email')

    if not email:
        return jsonify({'error': 'email parameter is required'}), 400

    # Check with Peter
    result = peter_client.is_staff_member(email)
    return jsonify(result)


# Sync management endpoints

@api_bp.route('/sync/status', methods=['GET'])
def sync_status():
    """
    GET /api/sync/status

    Get sync service status

    Returns:
        JSON with sync status and last sync info
    """
    status = sync_service.get_status()
    return jsonify(status)


@api_bp.route('/sync/now', methods=['POST'])
def sync_now():
    """
    POST /api/sync/now

    Trigger an immediate sync

    Returns:
        JSON with sync results
    """
    result = sync_service.sync_now()
    return jsonify(result)


@api_bp.route('/group/members', methods=['GET'])
def group_members():
    """
    GET /api/group/members

    Get current Google Group members

    Returns:
        JSON with list of members
    """
    members = groups_service.get_all_members()
    return jsonify({
        'members': members,
        'count': len(members)
    })


@api_bp.route('/sync/preview', methods=['GET'])
def sync_preview():
    """
    GET /api/sync/preview

    Preview what changes would be made by a sync

    Returns:
        JSON with preview of additions and removals
    """
    result = sync_service.preview()
    return jsonify(result)


@api_bp.route('/sync/mode', methods=['GET'])
def get_sync_mode():
    """
    GET /api/sync/mode

    Get current sync mode

    Returns:
        JSON with current mode ('manual' or 'auto')
    """
    return jsonify({
        'mode': settings.get_sync_mode()
    })


@api_bp.route('/sync/mode', methods=['POST'])
def set_sync_mode():
    """
    POST /api/sync/mode

    Set sync mode

    Body:
        mode: 'manual' or 'auto'

    Returns:
        JSON with success status
    """
    data = request.get_json()
    if not data or 'mode' not in data:
        return jsonify({'error': 'mode is required'}), 400

    mode = data['mode']
    if settings.set_sync_mode(mode):
        return jsonify({
            'success': True,
            'mode': mode
        })
    else:
        return jsonify({'error': 'Invalid mode. Must be "manual" or "auto"'}), 400
