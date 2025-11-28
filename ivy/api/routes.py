"""
API routes for Ivy - Buz Inventory & Pricing Manager.
"""
import logging
import threading
import time
from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required, api_or_session_auth
from shared.playwright.buz import is_lock_available, get_lock_holder_info
from database.db import inventory_db
from services.sync_service import sync_service

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

# How often to check for lock availability when waiting (seconds)
LOCK_POLL_INTERVAL = 60


# =====================
# Background Sync Helpers
# =====================

def _wait_for_lock(sync_id: int, sync_type: str, org_key: str) -> bool:
    """
    Wait for the Buz Playwright lock to become available.

    Polls every LOCK_POLL_INTERVAL seconds until lock is free.
    Updates sync status from 'waiting_for_lock' to 'running' when ready.

    Args:
        sync_id: Sync log ID to update
        sync_type: Type of sync for logging
        org_key: Org key for logging

    Returns:
        True when lock is available
    """
    from database.db import inventory_db
    from shared.playwright.buz import is_lock_available, get_lock_holder_info

    while not is_lock_available():
        holder_info = get_lock_holder_info()
        holder_bot = holder_info.get('bot', 'unknown') if holder_info else 'unknown'
        logger.info(
            f"[{org_key}] {sync_type} sync waiting for lock "
            f"(held by {holder_bot}), checking again in {LOCK_POLL_INTERVAL}s"
        )
        time.sleep(LOCK_POLL_INTERVAL)

    # Lock is available - update status to running
    inventory_db.update_sync_status(sync_id, 'running')
    logger.info(f"[{org_key}] Lock available, {sync_type} sync starting")
    return True


def _run_inventory_sync_background(
    org_key: str,
    sync_id: int,
    include_inactive: bool,
    performed_by: str,
    wait_for_lock: bool = False
):
    """Run inventory sync in background thread."""
    from services.sync_service import sync_service
    from database.db import inventory_db
    start_time = time.time()

    try:
        # If waiting mode, poll until lock is free
        if wait_for_lock:
            _wait_for_lock(sync_id, 'inventory', org_key)

        logger.info(f"Background inventory sync starting for {org_key}")
        result = sync_service._do_inventory_sync(org_key, sync_id, include_inactive, performed_by)
        logger.info(f"Background inventory sync completed for {org_key}: {result}")

    except Exception as e:
        duration = time.time() - start_time
        logger.exception(f"Background inventory sync failed for {org_key}")
        inventory_db.complete_sync(
            sync_id,
            item_count=0,
            status='failed',
            error_message=str(e),
            duration_seconds=duration
        )


def _run_pricing_sync_background(
    org_key: str,
    sync_id: int,
    include_inactive: bool,
    performed_by: str,
    wait_for_lock: bool = False
):
    """Run pricing sync in background thread."""
    from services.sync_service import sync_service
    from database.db import inventory_db
    start_time = time.time()

    try:
        # If waiting mode, poll until lock is free
        if wait_for_lock:
            _wait_for_lock(sync_id, 'pricing', org_key)

        logger.info(f"Background pricing sync starting for {org_key}")
        result = sync_service._do_pricing_sync(org_key, sync_id, include_inactive, performed_by)
        logger.info(f"Background pricing sync completed for {org_key}: {result}")

    except Exception as e:
        duration = time.time() - start_time
        logger.exception(f"Background pricing sync failed for {org_key}")
        inventory_db.complete_sync(
            sync_id,
            item_count=0,
            status='failed',
            error_message=str(e),
            duration_seconds=duration
        )


def _run_all_orgs_sync_background(
    sync_ids: dict,
    include_inactive: bool,
    performed_by: str,
    wait_for_lock: bool = False
):
    """Run sync for all orgs in background thread."""
    from services.sync_service import sync_service
    from database.db import inventory_db
    from shared.playwright.buz import is_lock_available, get_lock_holder_info

    logger.info(f"Background all-orgs sync starting for {list(sync_ids.keys())}")

    for org_key, ids in sync_ids.items():
        # Sync inventory
        if ids.get('inventory'):
            try:
                # Wait for lock if in waiting mode
                if wait_for_lock:
                    _wait_for_lock(ids['inventory'], 'inventory', org_key)
                sync_service._do_inventory_sync(org_key, ids['inventory'], include_inactive, performed_by)
            except Exception as e:
                logger.exception(f"Background inventory sync failed for {org_key}: {e}")

        # Sync pricing
        if ids.get('pricing'):
            try:
                # Wait for lock if in waiting mode
                if wait_for_lock:
                    _wait_for_lock(ids['pricing'], 'pricing', org_key)
                sync_service._do_pricing_sync(org_key, ids['pricing'], include_inactive, performed_by)
            except Exception as e:
                logger.exception(f"Background pricing sync failed for {org_key}: {e}")

    logger.info("Background all-orgs sync completed")


# =====================
# Sync Operations
# =====================

@api_bp.route('/sync/inventory', methods=['POST'])
@api_or_session_auth
def sync_inventory():
    """
    Start inventory sync in background for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive items (default: true)
        wait_for_lock: If true, wait for lock; if false, fail immediately if busy (default: false)

    Returns immediately with sync_id for status polling.
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')
    wait_for_lock = data.get('wait_for_lock', False)

    # Check for running syncs
    running_syncs = inventory_db.get_running_syncs(org_key)
    if any(s['sync_type'] == 'inventory' for s in running_syncs):
        return jsonify({
            'error': 'Inventory sync already running for this org',
            'running_syncs': running_syncs
        }), 409

    # For manual runs (wait_for_lock=False), check lock availability immediately
    if not wait_for_lock and not is_lock_available():
        holder_info = get_lock_holder_info()
        holder_bot = holder_info.get('bot', 'unknown') if holder_info else 'unknown'
        acquired_at = holder_info.get('acquired_at', 'unknown') if holder_info else 'unknown'
        return jsonify({
            'error': f"Buz is busy (used by '{holder_bot}' since {acquired_at}). Please try again later.",
            'lock_holder': holder_info
        }), 409

    # Determine initial status based on mode
    initial_status = 'waiting_for_lock' if wait_for_lock and not is_lock_available() else 'running'

    # Start sync log record
    sync_id = inventory_db.start_sync(org_key, 'inventory', status=initial_status)

    # Launch background thread
    thread = threading.Thread(
        target=_run_inventory_sync_background,
        args=(org_key, sync_id, include_inactive, performed_by, wait_for_lock),
        name=f"sync_inventory_{org_key}",
        daemon=True
    )
    thread.start()

    status_msg = 'waiting_for_lock' if initial_status == 'waiting_for_lock' else 'started'
    logger.info(f"Started background inventory sync for {org_key} (sync_id={sync_id}, status={status_msg})")

    return jsonify({
        'status': status_msg,
        'org_key': org_key,
        'sync_id': sync_id,
        'sync_type': 'inventory',
        'message': 'Inventory sync started in background. Check /api/sync/status for progress.'
    })


@api_bp.route('/sync/pricing', methods=['POST'])
@api_or_session_auth
def sync_pricing():
    """
    Start pricing sync in background for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive pricing (default: true)
        wait_for_lock: If true, wait for lock; if false, fail immediately if busy (default: false)

    Returns immediately with sync_id for status polling.
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')
    wait_for_lock = data.get('wait_for_lock', False)

    # Check for running syncs
    running_syncs = inventory_db.get_running_syncs(org_key)
    if any(s['sync_type'] == 'pricing' for s in running_syncs):
        return jsonify({
            'error': 'Pricing sync already running for this org',
            'running_syncs': running_syncs
        }), 409

    # For manual runs (wait_for_lock=False), check lock availability immediately
    if not wait_for_lock and not is_lock_available():
        holder_info = get_lock_holder_info()
        holder_bot = holder_info.get('bot', 'unknown') if holder_info else 'unknown'
        acquired_at = holder_info.get('acquired_at', 'unknown') if holder_info else 'unknown'
        return jsonify({
            'error': f"Buz is busy (used by '{holder_bot}' since {acquired_at}). Please try again later.",
            'lock_holder': holder_info
        }), 409

    # Determine initial status based on mode
    initial_status = 'waiting_for_lock' if wait_for_lock and not is_lock_available() else 'running'

    # Start sync log record
    sync_id = inventory_db.start_sync(org_key, 'pricing', status=initial_status)

    # Launch background thread
    thread = threading.Thread(
        target=_run_pricing_sync_background,
        args=(org_key, sync_id, include_inactive, performed_by, wait_for_lock),
        name=f"sync_pricing_{org_key}",
        daemon=True
    )
    thread.start()

    status_msg = 'waiting_for_lock' if initial_status == 'waiting_for_lock' else 'started'
    logger.info(f"Started background pricing sync for {org_key} (sync_id={sync_id}, status={status_msg})")

    return jsonify({
        'status': status_msg,
        'org_key': org_key,
        'sync_id': sync_id,
        'sync_type': 'pricing',
        'message': 'Pricing sync started in background. Check /api/sync/status for progress.'
    })


@api_bp.route('/sync', methods=['POST'])
@api_or_session_auth
def sync_all():
    """
    Start both inventory and pricing sync for an organization.

    Request body:
        org_key: Organization to sync
        include_inactive: Include inactive items/pricing (default: true)
        wait_for_lock: If true, wait for lock; if false, fail immediately if busy (default: false)

    Returns immediately with sync_ids for status polling.
    """
    data = request.get_json() or {}
    org_key = data.get('org_key')

    if not org_key:
        return jsonify({'error': 'org_key is required'}), 400

    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')
    wait_for_lock = data.get('wait_for_lock', False)

    # Check for running syncs
    running_syncs = inventory_db.get_running_syncs(org_key)
    running_types = {s['sync_type'] for s in running_syncs}
    if running_types:
        return jsonify({
            'error': f"Sync already running for: {', '.join(running_types)}",
            'running_syncs': running_syncs
        }), 409

    # For manual runs (wait_for_lock=False), check lock availability immediately
    if not wait_for_lock and not is_lock_available():
        holder_info = get_lock_holder_info()
        holder_bot = holder_info.get('bot', 'unknown') if holder_info else 'unknown'
        acquired_at = holder_info.get('acquired_at', 'unknown') if holder_info else 'unknown'
        return jsonify({
            'error': f"Buz is busy (used by '{holder_bot}' since {acquired_at}). Please try again later.",
            'lock_holder': holder_info
        }), 409

    # Determine initial status based on mode
    initial_status = 'waiting_for_lock' if wait_for_lock and not is_lock_available() else 'running'

    # Start sync log records
    inventory_sync_id = inventory_db.start_sync(org_key, 'inventory', status=initial_status)
    pricing_sync_id = inventory_db.start_sync(org_key, 'pricing', status=initial_status)

    sync_ids = {
        org_key: {
            'inventory': inventory_sync_id,
            'pricing': pricing_sync_id
        }
    }

    # Launch background thread
    thread = threading.Thread(
        target=_run_all_orgs_sync_background,
        args=(sync_ids, include_inactive, performed_by, wait_for_lock),
        name=f"sync_all_{org_key}",
        daemon=True
    )
    thread.start()

    status_msg = 'waiting_for_lock' if initial_status == 'waiting_for_lock' else 'started'
    logger.info(f"Started background full sync for {org_key} (status={status_msg})")

    return jsonify({
        'status': status_msg,
        'org_key': org_key,
        'sync_ids': {
            'inventory': inventory_sync_id,
            'pricing': pricing_sync_id
        },
        'message': 'Full sync started in background. Check /api/sync/status for progress.'
    })


@api_bp.route('/sync/all-orgs', methods=['POST'])
@api_or_session_auth
def sync_all_orgs():
    """
    Start sync for all configured organizations in background.

    Request body:
        include_inactive: Include inactive items/pricing (default: true)
        wait_for_lock: If true, wait for lock; if false, fail immediately if busy (default: false)

    Returns immediately with sync_ids for status polling.
    """
    from config import config

    data = request.get_json() or {}
    include_inactive = data.get('include_inactive', True)
    performed_by = data.get('performed_by', 'api')
    wait_for_lock = data.get('wait_for_lock', False)

    # Check for any running syncs across all orgs
    all_running = inventory_db.get_running_syncs()
    if all_running:
        running_orgs = {s['org_key'] for s in all_running}
        return jsonify({
            'error': f"Syncs already running for: {', '.join(running_orgs)}",
            'running_syncs': all_running
        }), 409

    # For manual runs (wait_for_lock=False), check lock availability immediately
    if not wait_for_lock and not is_lock_available():
        holder_info = get_lock_holder_info()
        holder_bot = holder_info.get('bot', 'unknown') if holder_info else 'unknown'
        acquired_at = holder_info.get('acquired_at', 'unknown') if holder_info else 'unknown'
        return jsonify({
            'error': f"Buz is busy (used by '{holder_bot}' since {acquired_at}). Please try again later.",
            'lock_holder': holder_info
        }), 409

    # Determine initial status based on mode
    initial_status = 'waiting_for_lock' if wait_for_lock and not is_lock_available() else 'running'

    # Create sync records for each org
    sync_ids = {}
    for org_key in config.available_orgs:
        sync_ids[org_key] = {
            'inventory': inventory_db.start_sync(org_key, 'inventory', status=initial_status),
            'pricing': inventory_db.start_sync(org_key, 'pricing', status=initial_status)
        }

    # Launch background thread
    thread = threading.Thread(
        target=_run_all_orgs_sync_background,
        args=(sync_ids, include_inactive, performed_by, wait_for_lock),
        name="sync_all_orgs",
        daemon=True
    )
    thread.start()

    status_msg = 'waiting_for_lock' if initial_status == 'waiting_for_lock' else 'started'
    logger.info(f"Started background sync for all orgs: {list(sync_ids.keys())} (status={status_msg})")

    return jsonify({
        'status': status_msg,
        'orgs': list(sync_ids.keys()),
        'sync_ids': sync_ids,
        'message': 'All-orgs sync started in background. Check /api/sync/status for progress.'
    })


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
