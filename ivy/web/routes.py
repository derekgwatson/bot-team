"""
Web routes for Ivy - Buz Inventory & Pricing Manager.
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from services.auth import login_required
from database.db import inventory_db
from services.sync_service import sync_service
from config import config
from shared.playwright.buz import BuzOrgs

web_bp = Blueprint('web', __name__)


@web_bp.context_processor
def utility_processor():
    """Add utility functions to Jinja templates."""

    def time_ago(dt_str):
        """Get human-readable relative time string."""
        if not dt_str:
            return 'Never'
        try:
            if isinstance(dt_str, str):
                # SQLite format: "2024-01-15 10:30:00"
                if 'T' not in dt_str and ' ' in dt_str:
                    dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                dt = dt_str

            delta = datetime.now(timezone.utc) - dt
            seconds = delta.total_seconds()

            if seconds < 60:
                return 'Just now'
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f'{minutes} min{"s" if minutes != 1 else ""} ago'
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f'{hours} hour{"s" if hours != 1 else ""} ago'
            elif seconds < 604800:  # 7 days
                days = int(seconds / 86400)
                return f'{days} day{"s" if days != 1 else ""} ago'
            else:
                return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError, TypeError):
            return str(dt_str)[:16] if dt_str else 'Never'

    def format_number(n):
        """Format number with commas."""
        try:
            return f'{int(n):,}'
        except (ValueError, TypeError):
            return str(n)

    return dict(time_ago=time_ago, format_number=format_number)


@web_bp.route('/')
@login_required
def index():
    """Dashboard with overview statistics."""
    stats = sync_service.get_stats()
    sync_status = sync_service.get_sync_status()

    # Get last sync for each org
    last_syncs = {}
    for org_key in config.available_orgs:
        last_inventory = inventory_db.get_last_sync(org_key, 'inventory')
        last_pricing = inventory_db.get_last_sync(org_key, 'pricing')
        last_syncs[org_key] = {
            'inventory': last_inventory,
            'pricing': last_pricing
        }

    return render_template(
        'index.html',
        stats=stats,
        sync_status=sync_status,
        last_syncs=last_syncs,
        config=config,
        BuzOrgs=BuzOrgs
    )


@web_bp.route('/items')
@login_required
def items():
    """List inventory items."""
    org_key = request.args.get('org_key')
    group_code = request.args.get('group_code')
    is_active = request.args.get('is_active')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Convert is_active
    is_active_bool = None
    if is_active == 'true':
        is_active_bool = True
    elif is_active == 'false':
        is_active_bool = False

    offset = (page - 1) * per_page

    items = inventory_db.get_inventory_items(
        org_key=org_key,
        group_code=group_code,
        is_active=is_active_bool,
        search=search if search else None,
        limit=per_page,
        offset=offset
    )

    total = inventory_db.get_inventory_item_count(org_key, is_active_bool)
    total_pages = (total + per_page - 1) // per_page

    # Get inventory groups for filter dropdown
    groups = inventory_db.get_inventory_groups(org_key)

    return render_template(
        'items.html',
        items=items,
        groups=groups,
        org_key=org_key,
        group_code=group_code,
        is_active=is_active,
        search=search,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        config=config,
        BuzOrgs=BuzOrgs
    )


@web_bp.route('/pricing')
@login_required
def pricing():
    """List pricing coefficients."""
    org_key = request.args.get('org_key')
    group_code = request.args.get('group_code')
    is_active = request.args.get('is_active')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Convert is_active
    is_active_bool = None
    if is_active == 'true':
        is_active_bool = True
    elif is_active == 'false':
        is_active_bool = False

    offset = (page - 1) * per_page

    coefficients = inventory_db.get_pricing_coefficients(
        org_key=org_key,
        group_code=group_code,
        is_active=is_active_bool,
        search=search if search else None,
        limit=per_page,
        offset=offset
    )

    total = inventory_db.get_pricing_coefficient_count(org_key, is_active_bool)
    total_pages = (total + per_page - 1) // per_page

    # Get pricing groups for filter dropdown
    groups = inventory_db.get_pricing_groups(org_key)

    return render_template(
        'pricing.html',
        coefficients=coefficients,
        groups=groups,
        org_key=org_key,
        group_code=group_code,
        is_active=is_active,
        search=search,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        config=config,
        BuzOrgs=BuzOrgs
    )


@web_bp.route('/sync')
@login_required
def sync_page():
    """Sync management page."""
    history = inventory_db.get_sync_history(limit=50)
    sync_status = sync_service.get_sync_status()

    return render_template(
        'sync.html',
        history=history,
        sync_status=sync_status,
        config=config,
        BuzOrgs=BuzOrgs
    )


@web_bp.route('/sync/trigger/<org_key>/<sync_type>', methods=['POST'])
@login_required
def trigger_sync(org_key: str, sync_type: str):
    """Trigger a sync operation."""
    from services.auth import get_current_user

    user = get_current_user()
    performed_by = user.email if user else 'web'

    if sync_type == 'inventory':
        result = sync_service.sync_inventory(org_key, True, performed_by)
    elif sync_type == 'pricing':
        result = sync_service.sync_pricing(org_key, True, performed_by)
    elif sync_type == 'all':
        result = sync_service.sync_all(org_key, True, performed_by)
    else:
        flash(f'Unknown sync type: {sync_type}', 'error')
        return redirect(url_for('web.sync_page'))

    if result['success']:
        flash(f'Sync completed successfully for {org_key}', 'success')
    else:
        flash(f'Sync failed: {result.get("error", "Unknown error")}', 'error')

    return redirect(url_for('web.sync_page'))


@web_bp.route('/activity')
@login_required
def activity():
    """Activity log page."""
    org_key = request.args.get('org_key')
    entity_type = request.args.get('entity_type')

    log = inventory_db.get_activity_log(org_key, entity_type, 100)

    return render_template(
        'activity.html',
        log=log,
        org_key=org_key,
        entity_type=entity_type,
        config=config,
        BuzOrgs=BuzOrgs
    )
