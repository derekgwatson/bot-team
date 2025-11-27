"""
Hugo web routes.

Provides web UI for Buz user management.
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


def get_db():
    """Lazy import to avoid circular imports."""
    from database.db import user_db
    return user_db


@web_bp.route('/')
@login_required
def index():
    """Dashboard home page."""
    from config import config

    db = get_db()
    stats = db.get_stats()
    queue_stats = db.get_queue_stats()

    # Get last sync for each org
    sync_status = {}
    for org_key in config.available_orgs:
        sync_status[org_key] = db.get_last_sync(org_key)

    return render_template(
        'index.html',
        config=config,
        stats=stats,
        sync_status=sync_status,
        queue_stats=queue_stats
    )


@web_bp.route('/users')
@login_required
def users():
    """User list page."""
    from config import config

    org_key = request.args.get('org')
    active_param = request.args.get('active')
    user_type = request.args.get('type')

    is_active = None
    if active_param is not None:
        is_active = active_param.lower() == 'true'

    db = get_db()
    users_list = db.get_users(org_key=org_key, is_active=is_active, user_type=user_type)

    return render_template(
        'users.html',
        config=config,
        users=users_list,
        filters={
            'org': org_key,
            'active': is_active,
            'type': user_type
        },
        available_orgs=config.available_orgs
    )


@web_bp.route('/users/<email>')
@login_required
def user_detail(email):
    """User detail page."""
    db = get_db()

    # Get user from all orgs
    users = db.get_users()
    user_records = [u for u in users if u['email'] == email]

    if not user_records:
        return render_template('error.html', message=f'User {email} not found'), 404

    # Get activity log for this user
    activity = db.get_activity_log(email=email, limit=20)

    return render_template(
        'user_detail.html',
        email=email,
        user_records=user_records,
        activity=activity
    )


@web_bp.route('/activity')
@login_required
def activity():
    """Activity log page."""
    db = get_db()

    email = request.args.get('email')
    org_key = request.args.get('org')

    activity_log = db.get_activity_log(email=email, org_key=org_key, limit=100)

    return render_template(
        'activity.html',
        activity=activity_log,
        filters={'email': email, 'org': org_key}
    )


@web_bp.route('/sync')
@login_required
def sync():
    """Sync status page."""
    from config import config

    db = get_db()
    history = db.get_sync_history(limit=50)

    # Group by org
    by_org = {}
    for entry in history:
        org = entry['org_key']
        if org not in by_org:
            by_org[org] = []
        by_org[org].append(entry)

    return render_template(
        'sync.html',
        config=config,
        history=history,
        by_org=by_org
    )
