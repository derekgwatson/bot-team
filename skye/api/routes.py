"""API routes for Skye - job management endpoints."""
import os
from flask import Blueprint, jsonify, request
from services.database import db
from services.scheduler import scheduler_service
from config import config

api_bp = Blueprint('api', __name__)


def require_api_key(f):
    """Decorator to require API key for bot-to-bot calls."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = config.bot_api_key

        if not expected_key:
            # No API key configured, allow request
            return f(*args, **kwargs)

        if api_key != expected_key:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(*args, **kwargs)

    return decorated_function


# ─────────────────────────────────────────────────────────────────────────────
# Job CRUD Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/jobs', methods=['GET'])
@require_api_key
def list_jobs():
    """List all scheduled jobs."""
    include_disabled = request.args.get('include_disabled', 'true').lower() == 'true'
    jobs = db.get_all_jobs(include_disabled=include_disabled)

    # Add next run time from scheduler
    for job in jobs:
        job['next_run_time'] = scheduler_service.get_next_run_time(job['job_id'])

    return jsonify({
        'jobs': jobs,
        'count': len(jobs)
    })


@api_bp.route('/jobs/<job_id>', methods=['GET'])
@require_api_key
def get_job(job_id):
    """Get a specific job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    job['next_run_time'] = scheduler_service.get_next_run_time(job_id)
    job['history'] = db.get_job_history(job_id, limit=10)

    return jsonify(job)


@api_bp.route('/jobs', methods=['POST'])
@require_api_key
def create_job():
    """Create a new scheduled job."""
    data = request.get_json()

    required = ['job_id', 'name', 'target_bot', 'endpoint']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    try:
        scheduler_service.add_job(
            job_id=data['job_id'],
            name=data['name'],
            target_bot=data['target_bot'],
            endpoint=data['endpoint'],
            method=data.get('method', 'POST'),
            schedule_type=data.get('schedule_type', 'cron'),
            schedule_config=data.get('schedule_config', {}),
            description=data.get('description'),
            enabled=data.get('enabled', True),
            created_by=data.get('created_by')
        )

        job = db.get_job(data['job_id'])
        return jsonify(job), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/jobs/<job_id>', methods=['PUT'])
@require_api_key
def update_job(job_id):
    """Update a scheduled job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    data = request.get_json()

    try:
        scheduler_service.update_job(job_id, **data)
        updated_job = db.get_job(job_id)
        return jsonify(updated_job)

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/jobs/<job_id>', methods=['DELETE'])
@require_api_key
def delete_job(job_id):
    """Delete a scheduled job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    scheduler_service.remove_job(job_id)
    return jsonify({'success': True, 'deleted': job_id})


# ─────────────────────────────────────────────────────────────────────────────
# Job Control Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/jobs/<job_id>/enable', methods=['POST'])
@require_api_key
def enable_job(job_id):
    """Enable a job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    scheduler_service.enable_job(job_id)
    return jsonify({'success': True, 'job_id': job_id, 'enabled': True})


@api_bp.route('/jobs/<job_id>/disable', methods=['POST'])
@require_api_key
def disable_job(job_id):
    """Disable a job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    scheduler_service.disable_job(job_id)
    return jsonify({'success': True, 'job_id': job_id, 'enabled': False})


@api_bp.route('/jobs/<job_id>/run', methods=['POST'])
@require_api_key
def run_job(job_id):
    """Manually trigger a job to run immediately."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    result = scheduler_service.run_job_now(job_id)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# History & Stats Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/jobs/<job_id>/history', methods=['GET'])
@require_api_key
def get_job_history(job_id):
    """Get execution history for a job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    limit = request.args.get('limit', 50, type=int)
    history = db.get_job_history(job_id, limit=limit)

    return jsonify({
        'job_id': job_id,
        'history': history,
        'count': len(history)
    })


@api_bp.route('/executions', methods=['GET'])
@require_api_key
def get_recent_executions():
    """Get recent executions across all jobs."""
    limit = request.args.get('limit', 100, type=int)
    executions = db.get_recent_executions(limit=limit)

    return jsonify({
        'executions': executions,
        'count': len(executions)
    })


@api_bp.route('/executions/failed', methods=['GET'])
@require_api_key
def get_failed_executions():
    """Get failed executions."""
    hours = request.args.get('hours', 24, type=int)
    failures = db.get_failed_executions(since_hours=hours)

    return jsonify({
        'failures': failures,
        'count': len(failures),
        'hours': hours
    })


@api_bp.route('/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get scheduler statistics."""
    stats = db.get_stats()
    stats['scheduler_running'] = scheduler_service.is_running()
    stats['scheduled_jobs'] = scheduler_service.get_scheduled_jobs()

    return jsonify(stats)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler Control Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/scheduler/status', methods=['GET'])
@require_api_key
def scheduler_status():
    """Get scheduler status."""
    return jsonify({
        'running': scheduler_service.is_running(),
        'scheduled_jobs': scheduler_service.get_scheduled_jobs(),
        'timezone': config.scheduler_timezone
    })


@api_bp.route('/scheduler/start', methods=['POST'])
@require_api_key
def start_scheduler():
    """Start the scheduler."""
    if scheduler_service.is_running():
        return jsonify({'success': True, 'message': 'Scheduler already running'})

    scheduler_service.start()
    return jsonify({'success': True, 'message': 'Scheduler started'})


@api_bp.route('/scheduler/stop', methods=['POST'])
@require_api_key
def stop_scheduler():
    """Stop the scheduler."""
    if not scheduler_service.is_running():
        return jsonify({'success': True, 'message': 'Scheduler already stopped'})

    scheduler_service.stop()
    return jsonify({'success': True, 'message': 'Scheduler stopped'})


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/cleanup', methods=['POST'])
@require_api_key
def cleanup_executions():
    """Clean up old execution records."""
    days = request.args.get('days', 30, type=int)
    deleted = db.cleanup_old_executions(keep_days=days)

    return jsonify({
        'success': True,
        'deleted': deleted,
        'kept_days': days
    })
