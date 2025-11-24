"""
Web Routes for Scout

Web UI for viewing monitoring status, issues, and check history.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
import logging
from datetime import datetime, timezone

from database.db import db
from services.checker import checker
from services.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Dashboard showing monitoring status"""
    # Get last check run
    last_run = db.get_last_check_run()

    # Get issue stats
    issue_stats = db.get_issue_stats()

    # Get open issues
    open_issues = db.get_open_issues()

    # Bot status is loaded async via AJAX to speed up page load
    return render_template(
        'index.html',
        last_run=last_run,
        issue_stats=issue_stats,
        open_issues=open_issues
    )


@web_bp.route('/api/bot-status')
@login_required
def get_bot_status_ajax():
    """Get bot connectivity status (for AJAX loading)"""
    try:
        bot_status = checker.get_bot_status()
        return {'status': 'ok', 'bots': bot_status}
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return {'status': 'error', 'error': str(e)}


@web_bp.route('/issues')
@login_required
def issues():
    """View all tracked issues"""
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type')

    if status_filter == 'open':
        all_issues = db.get_open_issues(issue_type=type_filter)
    else:
        all_issues = db.get_all_issues(limit=200)
        if status_filter == 'resolved':
            all_issues = [i for i in all_issues if i['status'] == 'resolved']
        if type_filter:
            all_issues = [i for i in all_issues if i['issue_type'] == type_filter]

    issue_stats = db.get_issue_stats()

    return render_template(
        'issues.html',
        issues=all_issues,
        issue_stats=issue_stats,
        status_filter=status_filter,
        type_filter=type_filter
    )


@web_bp.route('/history')
@login_required
def history():
    """View check run history"""
    limit = request.args.get('limit', 50, type=int)
    check_history = db.get_check_history(limit=limit)

    return render_template(
        'history.html',
        history=check_history
    )


@web_bp.route('/run-checks', methods=['POST'])
@login_required
def run_checks():
    """Trigger a manual check run"""
    try:
        results = checker.run_all_checks()
        flash(
            f"Checks completed: {results['issues_found']} issues found, "
            f"{results['tickets_created']} tickets created",
            'success'
        )
    except Exception as e:
        logger.exception("Error running manual checks")
        flash(f"Error running checks: {str(e)}", 'error')

    return redirect(url_for('web.index'))


@web_bp.route('/resolve-issue/<issue_type>/<issue_key>', methods=['POST'])
@login_required
def resolve_issue(issue_type: str, issue_key: str):
    """Manually resolve an issue"""
    try:
        resolved = db.resolve_issue(issue_type, issue_key)
        if resolved:
            flash(f"Issue resolved: {issue_type}:{issue_key}", 'success')
        else:
            flash(f"Issue not found or already resolved", 'warning')
    except Exception as e:
        logger.exception(f"Error resolving issue {issue_type}:{issue_key}")
        flash(f"Error resolving issue: {str(e)}", 'error')

    return redirect(url_for('web.issues'))


@web_bp.context_processor
def utility_processor():
    """Add utility functions to templates"""
    def format_datetime(dt_str):
        """Format an ISO datetime string for display"""
        if not dt_str:
            return 'Never'
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except (ValueError, AttributeError):
            return dt_str

    def time_ago(dt_str):
        """Get human-readable time ago string"""
        if not dt_str:
            return 'Never'
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            delta = datetime.now(timezone.utc) - dt
            seconds = delta.total_seconds()

            if seconds < 60:
                return 'Just now'
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f'{hours} hour{"s" if hours != 1 else ""} ago'
            else:
                days = int(seconds / 86400)
                return f'{days} day{"s" if days != 1 else ""} ago'
        except (ValueError, AttributeError):
            return dt_str

    return dict(format_datetime=format_datetime, time_ago=time_ago)
