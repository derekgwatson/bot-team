"""Web routes for Liam."""
import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, request

from config import config
from services.auth import login_required
from database.db import leads_db

logger = logging.getLogger(__name__)

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

    return dict(time_ago=time_ago)


@web_bp.route('/')
@login_required
def index():
    """Dashboard showing verification status and stats."""
    # Get stats
    stats = leads_db.get_stats()

    # Build org list with last check info
    orgs = []
    for org_key in config.available_orgs:
        org_config = config.get_org_config(org_key)
        last_verification = leads_db.get_latest_verification(org_key)

        orgs.append({
            'key': org_key,
            'code': org_config['code'],
            'display_name': org_config['display_name'],
            'is_primary': org_config.get('is_primary', False),
            'last_check_at': last_verification['verified_at'] if last_verification else None,
            'last_status': last_verification['status'] if last_verification else None
        })

    # Build missing orgs list
    missing_orgs = []
    for org_key, info in config.missing_credentials.items():
        missing_orgs.append({
            'key': org_key,
            'code': info['code'],
            'display_name': info['display_name'],
            'missing_vars': info['missing']
        })

    return render_template(
        'index.html',
        config=config,
        stats=stats,
        orgs=orgs,
        missing_orgs=missing_orgs
    )


@web_bp.route('/history')
@login_required
def history():
    """Verification history page."""
    selected_org = request.args.get('org', '')

    history = leads_db.get_verification_history(
        org_key=selected_org if selected_org else None,
        limit=100
    )

    return render_template(
        'history.html',
        config=config,
        history=history,
        org_keys=config.available_orgs,
        selected_org=selected_org
    )
