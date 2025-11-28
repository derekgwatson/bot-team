"""
Hugo web routes.

Provides web UI for Buz user management.
"""
import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.context_processor
def utility_processor():
    """Add utility functions to Jinja templates."""

    def time_ago(dt_str):
        """Get human-readable relative time string."""
        if not dt_str:
            return 'Never'
        try:
            # Handle various timestamp formats
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
                # For older dates, show the date
                return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError, TypeError):
            return str(dt_str)[:16] if dt_str else 'Never'

    return dict(time_ago=time_ago)


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
    unhealthy_orgs = db.get_unhealthy_orgs()
    auth_health = db.get_auth_health()

    # Get last sync for each org
    sync_status = {}
    for org_key in config.available_orgs:
        sync_status[org_key] = db.get_last_sync(org_key)

    return render_template(
        'index.html',
        config=config,
        stats=stats,
        sync_status=sync_status,
        queue_stats=queue_stats,
        unhealthy_orgs=unhealthy_orgs,
        auth_health=auth_health
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

    # Consolidate users by email - group multiple org entries together
    consolidated = {}
    for user in users_list:
        email = user['email']
        if email not in consolidated:
            consolidated[email] = {
                'email': email,
                'full_name': user['full_name'],
                'user_type': user['user_type'],
                'orgs': [],
                'last_session': user['last_session'] or '',
                'is_active_anywhere': False
            }

        # Track org membership with status
        consolidated[email]['orgs'].append({
            'org_key': user['org_key'],
            'is_active': user['is_active'],
            'user_group': user['user_group']
        })

        # Track if active anywhere
        if user['is_active']:
            consolidated[email]['is_active_anywhere'] = True

        # Keep the most recent last_session
        if user['last_session']:
            current = consolidated[email]['last_session']
            if not current or user['last_session'] > current:
                consolidated[email]['last_session'] = user['last_session']

    # Convert to sorted list
    consolidated_list = sorted(
        consolidated.values(),
        key=lambda u: (u['full_name'] or u['email']).lower()
    )

    return render_template(
        'users.html',
        config=config,
        users=consolidated_list,
        raw_user_count=len(users_list),
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
    from config import config

    db = get_db()

    # Get user from all orgs
    users = db.get_users()
    user_records = [u for u in users if u['email'] == email]

    if not user_records:
        return render_template('error.html', message=f'User {email} not found'), 404

    # Get the display name (most common or first non-empty)
    full_name = next((u['full_name'] for u in user_records if u['full_name']), None)

    # Get activity log for this user
    activity = db.get_activity_log(email=email, limit=20)

    return render_template(
        'user_detail.html',
        config=config,
        email=email,
        full_name=full_name,
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
    running = db.get_running_syncs()

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
        by_org=by_org,
        running=running
    )


@web_bp.route('/screenshots')
@login_required
def screenshots():
    """Screenshot viewer page."""
    from pathlib import Path
    from config import config
    from datetime import datetime

    screenshot_dir = Path(config.browser_screenshot_dir)

    screenshot_list = []
    if screenshot_dir.exists():
        for f in sorted(screenshot_dir.glob('*.png'), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
            stat = f.stat()
            screenshot_list.append({
                'name': f.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'url': f'/api/screenshots/{f.name}'
            })

    return render_template(
        'screenshots.html',
        config=config,
        screenshots=screenshot_list
    )
