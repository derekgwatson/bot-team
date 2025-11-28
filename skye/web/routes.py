"""Web routes for Skye - job management UI."""
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.database import db
from services.scheduler import scheduler_service
from services.auth import login_required, admin_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Dashboard - overview of all scheduled jobs."""
    jobs = db.get_all_jobs()

    # Add next run times
    for job in jobs:
        job['next_run_time'] = scheduler_service.get_next_run_time(job['job_id'])

    stats = db.get_stats()
    stats['scheduler_running'] = scheduler_service.is_running()

    # Show latest success/failure per job for cleaner dashboard
    recent_executions = db.get_latest_per_job()
    failed_executions = db.get_failed_executions(since_hours=24)

    return render_template(
        'index.html',
        config=config,
        jobs=jobs,
        stats=stats,
        recent_executions=recent_executions,
        failed_executions=failed_executions,
        current_user=current_user
    )


@web_bp.route('/jobs')
@login_required
def jobs_list():
    """List all jobs."""
    jobs = db.get_all_jobs()

    for job in jobs:
        job['next_run_time'] = scheduler_service.get_next_run_time(job['job_id'])

    return render_template(
        'jobs.html',
        config=config,
        jobs=jobs,
        current_user=current_user
    )


@web_bp.route('/jobs/<job_id>')
@login_required
def job_detail(job_id):
    """View job details and history."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    job['next_run_time'] = scheduler_service.get_next_run_time(job_id)
    job['schedule_config_parsed'] = json.loads(job['schedule_config'])

    history = db.get_job_history(job_id, limit=50)

    return render_template(
        'job_detail.html',
        config=config,
        job=job,
        history=history,
        current_user=current_user
    )


@web_bp.route('/jobs/new')
@admin_required
def new_job():
    """Form to create a new job."""
    return render_template(
        'admin/new_job.html',
        config=config,
        templates=config.job_templates,
        current_user=current_user
    )


@web_bp.route('/jobs/create', methods=['POST'])
@admin_required
def create_job():
    """Create a new job from form."""
    job_id = request.form.get('job_id', '').strip()
    name = request.form.get('name', '').strip()
    target_bot = request.form.get('target_bot', '').strip()
    endpoint = request.form.get('endpoint', '').strip()
    method = request.form.get('method', 'POST')
    schedule_type = request.form.get('schedule_type', 'cron')
    description = request.form.get('description', '').strip()

    # Build schedule config from form
    if schedule_type == 'cron':
        schedule_config = {
            'hour': request.form.get('cron_hour', '*'),
            'minute': request.form.get('cron_minute', '0'),
            'day_of_week': request.form.get('cron_dow') or None,
            'day': request.form.get('cron_day') or None,
        }
        # Remove None values
        schedule_config = {k: v for k, v in schedule_config.items() if v is not None}
    else:
        schedule_config = {
            'hours': int(request.form.get('interval_hours', 0) or 0),
            'minutes': int(request.form.get('interval_minutes', 0) or 0),
        }

    try:
        scheduler_service.add_job(
            job_id=job_id,
            name=name,
            target_bot=target_bot,
            endpoint=endpoint,
            method=method,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            description=description,
            enabled=True,
            created_by=current_user.email
        )
        flash(f'Job "{name}" created successfully', 'success')
        return redirect(url_for('web.job_detail', job_id=job_id))

    except Exception as e:
        flash(f'Error creating job: {e}', 'error')
        return redirect(url_for('web.new_job'))


@web_bp.route('/jobs/<job_id>/edit')
@admin_required
def edit_job(job_id):
    """Form to edit a job."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    job['schedule_config_parsed'] = json.loads(job['schedule_config'])

    return render_template(
        'admin/edit_job.html',
        config=config,
        job=job,
        current_user=current_user
    )


@web_bp.route('/jobs/<job_id>/update', methods=['POST'])
@admin_required
def update_job(job_id):
    """Update a job from form."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    name = request.form.get('name', '').strip()
    target_bot = request.form.get('target_bot', '').strip()
    endpoint = request.form.get('endpoint', '').strip()
    method = request.form.get('method', 'POST')
    schedule_type = request.form.get('schedule_type', 'cron')
    description = request.form.get('description', '').strip()
    quiet = request.form.get('quiet') == '1'

    # Build schedule config from form
    if schedule_type == 'cron':
        schedule_config = {
            'hour': request.form.get('cron_hour', '*'),
            'minute': request.form.get('cron_minute', '0'),
            'day_of_week': request.form.get('cron_dow') or None,
            'day': request.form.get('cron_day') or None,
        }
        schedule_config = {k: v for k, v in schedule_config.items() if v is not None}
    else:
        schedule_config = {
            'hours': int(request.form.get('interval_hours', 0) or 0),
            'minutes': int(request.form.get('interval_minutes', 0) or 0),
        }

    try:
        scheduler_service.update_job(
            job_id,
            name=name,
            target_bot=target_bot,
            endpoint=endpoint,
            method=method,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            description=description,
            quiet=quiet
        )
        flash(f'Job "{name}" updated successfully', 'success')
        return redirect(url_for('web.job_detail', job_id=job_id))

    except Exception as e:
        flash(f'Error updating job: {e}', 'error')
        return redirect(url_for('web.edit_job', job_id=job_id))


@web_bp.route('/jobs/<job_id>/toggle', methods=['POST'])
@admin_required
def toggle_job(job_id):
    """Enable or disable a job."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    if job['enabled']:
        scheduler_service.disable_job(job_id)
        flash(f'Job "{job["name"]}" disabled', 'info')
    else:
        scheduler_service.enable_job(job_id)
        flash(f'Job "{job["name"]}" enabled', 'success')

    return redirect(request.referrer or url_for('web.jobs_list'))


@web_bp.route('/jobs/<job_id>/run', methods=['POST'])
@admin_required
def run_job(job_id):
    """Manually trigger a job."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    result = scheduler_service.run_job_now(job_id)

    if result.get('queued'):
        flash(f'Job "{job["name"]}" queued - check history for results', 'info')
    elif result.get('success'):
        flash(f'Job "{job["name"]}" executed successfully', 'success')
    else:
        flash(f'Job "{job["name"]}" failed: {result.get("error", "Unknown error")}', 'error')

    return redirect(url_for('web.job_detail', job_id=job_id))


@web_bp.route('/jobs/<job_id>/delete', methods=['POST'])
@admin_required
def delete_job(job_id):
    """Delete a job."""
    job = db.get_job(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('web.jobs_list'))

    scheduler_service.remove_job(job_id)
    flash(f'Job "{job["name"]}" deleted', 'info')

    return redirect(url_for('web.jobs_list'))


@web_bp.route('/history')
@login_required
def execution_history():
    """View execution history."""
    # View modes: 'summary' (latest per job) or 'all' (full history)
    view = request.args.get('view', 'summary')

    if view == 'all':
        executions = db.get_recent_executions(limit=200)
    else:
        executions = db.get_latest_per_job()

    return render_template(
        'history.html',
        config=config,
        executions=executions,
        view=view,
        current_user=current_user
    )


@web_bp.route('/failures')
@login_required
def failures():
    """View recent failures."""
    hours = request.args.get('hours', 24, type=int)
    failures = db.get_failed_executions(since_hours=hours)

    return render_template(
        'failures.html',
        config=config,
        failures=failures,
        hours=hours,
        current_user=current_user
    )
