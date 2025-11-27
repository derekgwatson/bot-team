"""API routes for Doc"""

from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required, api_or_session_auth

from services.sync import sync_service
from services.checkup import checkup_service
from services.test_runner import test_runner
from database.db import db

api_bp = Blueprint('api', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Introduction
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/intro', methods=['GET'])
def intro():
    """Bot introduction - no auth required"""
    return jsonify({
        'name': 'Doc',
        'role': 'Bot Team Health Checker',
        'description': 'I monitor the health of all bots and run test suites to make sure everyone is doing okay.',
        'capabilities': [
            'Health checkups on all bots',
            'Run pytest test suites',
            'Track health metrics over time',
            'Sync bot registry from Chester'
        ],
        'endpoints': {
            'checkup': '/api/checkup - Run health checks',
            'tests': '/api/tests - Run test suites',
            'bots': '/api/bots - View bot registry',
            'vitals': '/api/vitals - View health metrics'
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# Bot Registry
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/bots', methods=['GET'])
@api_key_required
def get_bots():
    """Get all bots in the registry"""
    bots = db.get_all_bots()
    return jsonify({
        'success': True,
        'count': len(bots),
        'bots': bots
    })


@api_bp.route('/bots/<bot_name>', methods=['GET'])
@api_key_required
def get_bot(bot_name):
    """Get a specific bot from the registry"""
    bot = db.get_bot(bot_name)
    if not bot:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found in registry'
        }), 404

    return jsonify({
        'success': True,
        'bot': bot
    })


@api_bp.route('/bots/sync', methods=['POST'])
@api_or_session_auth
def sync_bots():
    """Sync bot registry from Chester (callable from dashboard or other bots)"""
    result = sync_service.sync_from_chester()
    return jsonify(result)


@api_bp.route('/bots/sync/status', methods=['GET'])
@api_key_required
def sync_status():
    """Get sync status"""
    status = sync_service.get_sync_status()
    return jsonify({
        'success': True,
        **status
    })


# ─────────────────────────────────────────────────────────────────────────────
# Health Checkups
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/checkup', methods=['GET', 'POST'])
@api_or_session_auth
def checkup_all():
    """
    Run health checkup on all bots.

    GET: Just run the checkup
    POST: Run checkup (same behavior, for Skye/dashboard compatibility)
    """
    result = checkup_service.check_all_bots()
    return jsonify(result)


@api_bp.route('/checkup/<bot_name>', methods=['GET'])
@api_key_required
def checkup_bot(bot_name):
    """Run health checkup on a specific bot"""
    result = checkup_service.check_bot(bot_name)
    return jsonify({
        'success': True,
        'result': result
    })


@api_bp.route('/checkup/history', methods=['GET'])
@api_key_required
def checkup_history():
    """Get checkup history"""
    bot_name = request.args.get('bot')
    limit = request.args.get('limit', 50, type=int)

    history = db.get_checkup_history(bot_name=bot_name, limit=limit)
    return jsonify({
        'success': True,
        'count': len(history),
        'history': history
    })


@api_bp.route('/status', methods=['GET'])
@api_key_required
def get_status():
    """Get the latest status for all bots (without running new checks)"""
    statuses = checkup_service.get_latest_status()
    healthy = sum(1 for s in statuses if s['status'] == 'healthy')

    return jsonify({
        'success': True,
        'summary': {
            'total': len(statuses),
            'healthy': healthy,
            'unhealthy': len(statuses) - healthy
        },
        'bots': statuses
    })


# ─────────────────────────────────────────────────────────────────────────────
# Vitals (Metrics)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/vitals', methods=['GET'])
@api_key_required
def get_team_vitals():
    """Get vital statistics for the whole team"""
    hours = request.args.get('hours', 24, type=int)
    vitals = checkup_service.get_vitals(hours=hours)
    return jsonify({
        'success': True,
        'vitals': vitals
    })


@api_bp.route('/vitals/<bot_name>', methods=['GET'])
@api_key_required
def get_bot_vitals(bot_name):
    """Get vital statistics for a specific bot"""
    hours = request.args.get('hours', 24, type=int)
    vitals = checkup_service.get_vitals(bot_name=bot_name, hours=hours)
    return jsonify({
        'success': True,
        'vitals': vitals
    })


# ─────────────────────────────────────────────────────────────────────────────
# Test Runner
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/tests/run', methods=['POST'])
@api_or_session_auth
def run_tests():
    """
    Run pytest tests (callable from dashboard or other bots).

    Optional JSON body:
    {
        "marker": "fred",  // pytest marker (optional)
        "timeout": 300     // timeout in seconds (optional, max 600)
    }
    """
    data = request.get_json() or {}
    marker = data.get('marker')
    timeout = data.get('timeout')

    result = test_runner.run_tests(marker=marker, timeout=timeout)
    return jsonify(result)


@api_bp.route('/tests/runs', methods=['GET'])
@api_key_required
def get_test_runs():
    """Get test run history"""
    limit = request.args.get('limit', 20, type=int)
    marker = request.args.get('marker')

    runs = test_runner.get_run_history(limit=limit, marker=marker)
    return jsonify({
        'success': True,
        'count': len(runs),
        'runs': runs
    })


@api_bp.route('/tests/runs/<int:run_id>', methods=['GET'])
@api_key_required
def get_test_run(run_id):
    """Get a specific test run"""
    run = test_runner.get_run(run_id)
    if not run:
        return jsonify({
            'success': False,
            'error': f'Test run {run_id} not found'
        }), 404

    return jsonify({
        'success': True,
        'run': run
    })


@api_bp.route('/tests/latest', methods=['GET'])
@api_key_required
def get_latest_test():
    """Get the most recent test run"""
    marker = request.args.get('marker')
    run = test_runner.get_latest_run(marker=marker)

    if not run:
        return jsonify({
            'success': True,
            'run': None,
            'message': 'No test runs found'
        })

    return jsonify({
        'success': True,
        'run': run
    })


@api_bp.route('/tests/status', methods=['GET'])
@api_key_required
def test_status():
    """Check if tests are currently running"""
    running = db.get_running_test_run()
    return jsonify({
        'success': True,
        'is_running': running is not None,
        'current_run': running
    })


@api_bp.route('/tests/markers', methods=['GET'])
@api_key_required
def get_markers():
    """Get available pytest markers"""
    markers = test_runner.get_available_markers()
    return jsonify({
        'success': True,
        'markers': markers
    })
