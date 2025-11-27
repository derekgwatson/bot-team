"""API routes for Grant - used by other bots to check permissions."""
from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required
from services.permissions import permission_service

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro')
def intro():
    """Bot introduction endpoint."""
    return jsonify({
        'name': 'Grant',
        'role': 'Centralized Authorization Manager',
        'capabilities': [
            'Check user access to any bot',
            'Grant and revoke permissions',
            'Manage user and admin roles',
            'Audit trail of all permission changes'
        ],
        'endpoints': {
            'GET /api/access': 'Check if user has access to a bot',
            'GET /api/permissions': 'List all permissions (filterable)',
            'POST /api/permissions': 'Grant permission',
            'DELETE /api/permissions': 'Revoke permission',
            'GET /api/users': 'List unique users with permissions',
            'GET /api/bots': 'List registered bots',
            'POST /api/bots/sync': 'Sync bot registry from Chester',
            'GET /api/audit': 'Get audit log',
            'GET /api/stats': 'Get permission statistics'
        }
    })


# ─────────────────────────────────────────────────────────────
# Access Checking (used by GatewayAuth)
# ─────────────────────────────────────────────────────────────

@api_bp.route('/access')
@api_key_required
def check_access():
    """
    Check if a user has access to a bot.

    Query params:
        email: User's email address (required)
        bot: Bot name (required)

    Returns:
        {allowed: bool, role: str|None, is_admin: bool, source: str|None}
    """
    email = request.args.get('email')
    bot = request.args.get('bot')

    if not email:
        return jsonify({'error': 'email parameter is required'}), 400
    if not bot:
        return jsonify({'error': 'bot parameter is required'}), 400

    result = permission_service.check_access(email, bot)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# Permission Management
# ─────────────────────────────────────────────────────────────

@api_bp.route('/permissions')
@api_key_required
def list_permissions():
    """
    List permissions, optionally filtered.

    Query params:
        email: Filter by user email (optional)
        bot: Filter by bot name (optional)

    Returns:
        {permissions: [...]}
    """
    email = request.args.get('email')
    bot = request.args.get('bot')

    if email:
        permissions = permission_service.get_user_permissions(email)
    elif bot:
        permissions = permission_service.get_bot_permissions(bot)
    else:
        permissions = permission_service.get_all_permissions()

    return jsonify({'permissions': permissions})


@api_bp.route('/permissions', methods=['POST'])
@api_key_required
def grant_permission():
    """
    Grant permission for a user on a bot.

    JSON body:
        email: User's email address (required)
        bot: Bot name or '*' for all (required)
        role: 'user' or 'admin' (required)
        granted_by: Email of person granting (required)

    Returns:
        {success: bool, permission: {...}}
    """
    data = request.get_json() or {}

    email = data.get('email')
    bot = data.get('bot')
    role = data.get('role')
    granted_by = data.get('granted_by')

    if not email:
        return jsonify({'error': 'email is required'}), 400
    if not bot:
        return jsonify({'error': 'bot is required'}), 400
    if not role:
        return jsonify({'error': 'role is required'}), 400
    if role not in ('user', 'admin'):
        return jsonify({'error': "role must be 'user' or 'admin'"}), 400
    if not granted_by:
        return jsonify({'error': 'granted_by is required'}), 400

    try:
        permission = permission_service.grant_permission(email, bot, role, granted_by)
        return jsonify({'success': True, 'permission': permission})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/permissions', methods=['DELETE'])
@api_key_required
def revoke_permission():
    """
    Revoke permission for a user on a bot.

    JSON body:
        email: User's email address (required)
        bot: Bot name (required)
        revoked_by: Email of person revoking (required)

    Returns:
        {success: bool, revoked: bool}
    """
    data = request.get_json() or {}

    email = data.get('email')
    bot = data.get('bot')
    revoked_by = data.get('revoked_by')

    if not email:
        return jsonify({'error': 'email is required'}), 400
    if not bot:
        return jsonify({'error': 'bot is required'}), 400
    if not revoked_by:
        return jsonify({'error': 'revoked_by is required'}), 400

    revoked = permission_service.revoke_permission(email, bot, revoked_by)
    return jsonify({'success': True, 'revoked': revoked})


# ─────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────

@api_bp.route('/users')
@api_key_required
def list_users():
    """
    List unique users with permissions.

    Returns:
        {users: [...]}
    """
    users = permission_service.get_unique_users()
    return jsonify({'users': users})


# ─────────────────────────────────────────────────────────────
# Bot Registry
# ─────────────────────────────────────────────────────────────

@api_bp.route('/bots')
@api_key_required
def list_bots():
    """
    List registered bots.

    Returns:
        {bots: [...]}
    """
    bots = permission_service.get_bots()
    return jsonify({'bots': bots})


@api_bp.route('/bots/sync', methods=['POST'])
@api_key_required
def sync_bots():
    """
    Sync bot registry from Chester.

    Returns:
        {success: bool, synced: int, error: str|None}
    """
    result = permission_service.sync_bots_from_chester()
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


# ─────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────

@api_bp.route('/audit')
@api_key_required
def get_audit():
    """
    Get audit log of permission changes.

    Query params:
        email: Filter by user email (optional)
        bot: Filter by bot name (optional)
        limit: Max entries to return (default 100)

    Returns:
        {audit: [...]}
    """
    email = request.args.get('email')
    bot = request.args.get('bot')
    limit = request.args.get('limit', 100, type=int)

    audit = permission_service.get_audit_log(email, bot, limit)
    return jsonify({'audit': audit})


# ─────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────

@api_bp.route('/stats')
@api_key_required
def get_stats():
    """
    Get permission statistics.

    Returns:
        {unique_users: int, bots_with_permissions: int, ...}
    """
    stats = permission_service.get_stats()
    return jsonify(stats)
