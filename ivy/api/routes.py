"""
API routes for Ivy - Buz Inventory & Pricing Manager.
"""
from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required, api_or_session_auth
from database.db import inventory_db
from services.sync_service import sync_service

api_bp = Blueprint('api', __name__)


# =====================
# Sync Operations
# =====================

@api_bp.route('/sync/inventory', methods=['POST'])
@api_or_session_auth
def sync_inventory():
    """
    Sync inventory items from Buz for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive items (default: true)
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')

    result = sync_service.sync_inventory(org_key, include_inactive, performed_by)

    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@api_bp.route('/sync/pricing', methods=['POST'])
@api_or_session_auth
def sync_pricing():
    """
    Sync pricing coefficients from Buz for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive pricing (default: true)
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')

    result = sync_service.sync_pricing(org_key, include_inactive, performed_by)

    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@api_bp.route('/sync', methods=['POST'])
@api_or_session_auth
def sync_all():
    """
    Sync both inventory and pricing for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive items/pricing (default: true)
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')

    result = sync_service.sync_all(org_key, include_inactive, performed_by)

    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@api_bp.route('/sync/all-orgs', methods=['POST'])
@api_or_session_auth
def sync_all_orgs():
    """
    Sync all configured organizations.

    Request body:
        include_inactive: Include inactive items/pricing (default: true)
    """
    data = request.get_json() or {}
    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')

    result = sync_service.sync_all_orgs(include_inactive, performed_by)

    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


@api_bp.route('/sync/status', methods=['GET'])
@api_or_session_auth
def sync_status():
    """Get current sync status."""
    org_key = request.args.get('org_key')
    result = sync_service.get_sync_status(org_key)
    return jsonify(result)


@api_bp.route('/sync/history', methods=['GET'])
@api_or_session_auth
def sync_history():
    """Get sync history."""
    org_key = request.args.get('org_key')
    sync_type = request.args.get('sync_type')
    limit = request.args.get('limit', 20, type=int)

    history = inventory_db.get_sync_history(org_key, sync_type, limit)
    return jsonify({'history': history})


# =====================
# Inventory Items
# =====================

@api_bp.route('/items', methods=['GET'])
@api_key_required
def get_items():
    """
    Get inventory items with optional filters.

    Query params:
        org_key: Filter by organization
        group_code: Filter by inventory group
        is_active: Filter by active status (true/false)
        search: Search in code, name, description
        limit: Max results (default 100)
        offset: Pagination offset (default 0)
    """
    org_key = request.args.get('org_key')
    group_code = request.args.get('group_code')
    is_active = request.args.get('is_active')
    search = request.args.get('search')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    # Convert is_active string to boolean
    if is_active is not None:
        is_active = is_active.lower() in ('true', '1', 'yes')

    items = inventory_db.get_inventory_items(
        org_key=org_key,
        group_code=group_code,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'items': items,
        'count': len(items),
        'limit': limit,
        'offset': offset
    })


@api_bp.route('/items/<org_key>/<group_code>/<item_code>', methods=['GET'])
@api_key_required
def get_item(org_key: str, group_code: str, item_code: str):
    """Get a specific inventory item."""
    item = inventory_db.get_inventory_item(org_key, group_code, item_code)

    if not item:
        return jsonify({'error': 'Item not found'}), 404

    return jsonify(item)


@api_bp.route('/items/count', methods=['GET'])
@api_key_required
def get_items_count():
    """Get inventory items count."""
    org_key = request.args.get('org_key')
    is_active = request.args.get('is_active')

    if is_active is not None:
        is_active = is_active.lower() in ('true', '1', 'yes')

    count = inventory_db.get_inventory_item_count(org_key, is_active)
    return jsonify({'count': count})


# =====================
# Inventory Groups
# =====================

@api_bp.route('/items/groups', methods=['GET'])
@api_key_required
def get_inventory_groups():
    """Get inventory groups."""
    org_key = request.args.get('org_key')
    groups = inventory_db.get_inventory_groups(org_key)
    return jsonify({'groups': groups})


# =====================
# Pricing Coefficients
# =====================

@api_bp.route('/pricing', methods=['GET'])
@api_key_required
def get_pricing():
    """
    Get pricing coefficients with optional filters.

    Query params:
        org_key: Filter by organization
        group_code: Filter by pricing group
        is_active: Filter by active status (true/false)
        search: Search in code, name, description
        limit: Max results (default 100)
        offset: Pagination offset (default 0)
    """
    org_key = request.args.get('org_key')
    group_code = request.args.get('group_code')
    is_active = request.args.get('is_active')
    search = request.args.get('search')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    if is_active is not None:
        is_active = is_active.lower() in ('true', '1', 'yes')

    coefficients = inventory_db.get_pricing_coefficients(
        org_key=org_key,
        group_code=group_code,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'coefficients': coefficients,
        'count': len(coefficients),
        'limit': limit,
        'offset': offset
    })


@api_bp.route('/pricing/<org_key>/<group_code>/<coefficient_code>', methods=['GET'])
@api_key_required
def get_coefficient(org_key: str, group_code: str, coefficient_code: str):
    """Get a specific pricing coefficient."""
    coeff = inventory_db.get_pricing_coefficient(org_key, group_code, coefficient_code)

    if not coeff:
        return jsonify({'error': 'Coefficient not found'}), 404

    return jsonify(coeff)


@api_bp.route('/pricing/count', methods=['GET'])
@api_key_required
def get_pricing_count():
    """Get pricing coefficients count."""
    org_key = request.args.get('org_key')
    is_active = request.args.get('is_active')

    if is_active is not None:
        is_active = is_active.lower() in ('true', '1', 'yes')

    count = inventory_db.get_pricing_coefficient_count(org_key, is_active)
    return jsonify({'count': count})


# =====================
# Pricing Groups
# =====================

@api_bp.route('/pricing/groups', methods=['GET'])
@api_key_required
def get_pricing_groups():
    """Get pricing groups."""
    org_key = request.args.get('org_key')
    groups = inventory_db.get_pricing_groups(org_key)
    return jsonify({'groups': groups})


# =====================
# Organizations
# =====================

@api_bp.route('/orgs', methods=['GET'])
@api_key_required
def get_orgs():
    """Get available organizations."""
    from config import config

    orgs = []
    for org_key in config.available_orgs:
        org_config = config.buz_orgs.get(org_key, {})
        orgs.append({
            'org_key': org_key,
            'display_name': org_config.get('display_name', org_key.title()),
            'has_auth': org_key not in config.buz_orgs_missing_auth
        })

    return jsonify({
        'orgs': orgs,
        'missing_auth': list(config.buz_orgs_missing_auth.keys())
    })


# =====================
# Statistics
# =====================

@api_bp.route('/stats', methods=['GET'])
@api_key_required
def get_stats():
    """Get overall statistics."""
    stats = sync_service.get_stats()
    return jsonify(stats)


# =====================
# Activity Log
# =====================

@api_bp.route('/activity', methods=['GET'])
@api_key_required
def get_activity():
    """Get activity log."""
    org_key = request.args.get('org_key')
    entity_type = request.args.get('entity_type')
    limit = request.args.get('limit', 50, type=int)

    log = inventory_db.get_activity_log(org_key, entity_type, limit)
    return jsonify({'activity': log})
