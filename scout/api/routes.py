"""
API Routes for Scout

REST API for system monitoring and issue tracking.
"""

from flask import Blueprint, jsonify, request
import logging

from database.db import db
from services.checker import checker
from services.scheduler import scheduler
from shared.auth.bot_api import api_key_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Bot Introduction
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """Return Scout's introduction"""
    return jsonify({
        'name': 'Scout',
        'role': 'System Monitoring Bot',
        'description': (
            'I monitor systems for discrepancies and raise tickets via Sadie. '
            'I periodically check Mavis and Fiona for fabric data issues, '
            'track what I\'ve already reported, and avoid creating duplicate tickets.'
        ),
        'capabilities': [
            'Detect fabrics in Mavis without Fiona descriptions',
            'Detect obsolete fabric descriptions in Fiona',
            'Detect incomplete fabric descriptions',
            'Monitor Mavis sync health',
            'Create Zendesk tickets via Sadie for issues',
            'Track reported issues to avoid duplicates',
            'Run checks on a configurable schedule'
        ],
        'endpoints': {
            'POST /api/checks/run': 'Trigger a manual check run',
            'GET /api/checks/status': 'Get scheduler and last run status',
            'GET /api/checks/history': 'Get check run history',
            'GET /api/issues': 'Get tracked issues',
            'GET /api/issues/stats': 'Get issue statistics',
            'POST /api/issues/<type>/<key>/resolve': 'Resolve an issue',
            'GET /api/bots/status': 'Get status of dependent bots'
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# Check Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/checks/run', methods=['POST'])
@api_key_required
def run_checks():
    """
    Trigger a manual check run.

    Returns the check results including issues found and tickets created.
    """
    try:
        logger.info("Manual check run triggered via API")
        results = checker.run_all_checks()
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.exception("Error running checks")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/checks/status', methods=['GET'])
@api_key_required
def get_check_status():
    """Get scheduler status and last check run info"""
    try:
        last_run = db.get_last_check_run()
        scheduler_status = scheduler.get_status()

        return jsonify({
            'scheduler': scheduler_status,
            'last_run': last_run
        })
    except Exception as e:
        logger.exception("Error getting check status")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/checks/history', methods=['GET'])
@api_key_required
def get_check_history():
    """
    Get check run history.

    Query parameters:
        limit (optional): Max results (default 20)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        history = db.get_check_history(limit=limit)

        return jsonify({
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        logger.exception("Error getting check history")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Issue Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/issues', methods=['GET'])
@api_key_required
def get_issues():
    """
    Get tracked issues.

    Query parameters:
        status (optional): Filter by status (open, resolved, all). Default: all
        type (optional): Filter by issue type
        limit (optional): Max results (default 100)
    """
    try:
        status = request.args.get('status', 'all')
        issue_type = request.args.get('type')
        limit = request.args.get('limit', 100, type=int)

        if status == 'open':
            issues = db.get_open_issues(issue_type=issue_type)
        else:
            issues = db.get_all_issues(limit=limit)
            if issue_type:
                issues = [i for i in issues if i['issue_type'] == issue_type]

        return jsonify({
            'issues': issues,
            'count': len(issues)
        })
    except Exception as e:
        logger.exception("Error getting issues")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/issues/stats', methods=['GET'])
@api_key_required
def get_issue_stats():
    """Get issue statistics"""
    try:
        stats = db.get_issue_stats()
        return jsonify(stats)
    except Exception as e:
        logger.exception("Error getting issue stats")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/issues/<issue_type>/<issue_key>/resolve', methods=['POST'])
@api_key_required
def resolve_issue(issue_type: str, issue_key: str):
    """Manually resolve an issue"""
    try:
        resolved = db.resolve_issue(issue_type, issue_key)

        if resolved:
            return jsonify({
                'success': True,
                'message': f'Issue {issue_type}:{issue_key} resolved'
            })
        else:
            return jsonify({
                'error': f'Issue not found or already resolved: {issue_type}:{issue_key}'
            }), 404
    except Exception as e:
        logger.exception(f"Error resolving issue {issue_type}:{issue_key}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Bot Status Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/bots/status', methods=['GET'])
@api_key_required
def get_bots_status():
    """Get connection status for all dependent bots"""
    try:
        status = checker.get_bot_status()
        return jsonify(status)
    except Exception as e:
        logger.exception("Error getting bot status")
        return jsonify({'error': str(e)}), 500
