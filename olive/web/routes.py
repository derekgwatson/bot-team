"""
Web Routes for Olive
User interface for offboarding workflows
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.auth import login_required, admin_required
from database.db import db
from services.orchestrator import orchestrator
import logging

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Dashboard with offboarding form and requests"""
    try:
        # Get statistics
        stats = {
            'pending': len(db.get_all_offboarding_requests('pending')),
            'in_progress': len(db.get_all_offboarding_requests('in_progress')),
            'completed': len(db.get_all_offboarding_requests('completed')),
            'failed': len(db.get_all_offboarding_requests('failed'))
        }

        # Get recent requests
        recent_requests = db.get_all_offboarding_requests()[:10]

        # Get pending manual tasks
        manual_tasks = db.get_pending_manual_tasks()

        return render_template('index.html',
                             stats=stats,
                             recent_requests=recent_requests,
                             manual_tasks=manual_tasks,
                             user=current_user)

    except Exception as e:
        logger.exception("Error loading dashboard")
        return f"Error loading dashboard: {str(e)}", 500


@web_bp.route('/offboard/new')
@login_required
def new_offboard():
    """Show new offboarding form"""
    return render_template('offboard_form.html', user=current_user)


@web_bp.route('/offboard/submit', methods=['POST'])
@login_required
def submit_offboard():
    """Submit a new offboarding request"""
    try:
        # Get form data
        data = {
            'full_name': request.form.get('full_name'),
            'position': request.form.get('position', ''),
            'section': request.form.get('section', ''),
            'last_day': request.form.get('last_day'),
            'personal_email': request.form.get('personal_email', ''),
            'phone_mobile': request.form.get('phone_mobile', ''),
            'notes': request.form.get('notes', '')
        }

        # Validate required fields
        required_fields = ['full_name', 'last_day']
        for field in required_fields:
            if not data.get(field):
                flash(f'Missing required field: {field}', 'error')
                return redirect(url_for('web.new_offboard'))

        # Create the offboarding request
        request_id = db.create_offboarding_request(data, created_by=current_user.email)

        # Auto-start the workflow
        result = orchestrator.start_offboarding(request_id)

        if result.get('success'):
            flash(f'Offboarding request created and workflow started for {data["full_name"]}!', 'success')
        else:
            flash(f'Offboarding request created but workflow failed: {result.get("error")}', 'warning')

        return redirect(url_for('web.view_offboard', request_id=request_id))

    except Exception as e:
        logger.exception("Error submitting offboarding request")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.new_offboard'))


@web_bp.route('/offboard/<int:request_id>')
@login_required
def view_offboard(request_id):
    """View offboarding request details"""
    try:
        request_data = db.get_offboarding_request(request_id)
        if not request_data:
            flash('Offboarding request not found', 'error')
            return redirect(url_for('web.index'))

        # Get workflow steps
        steps = db.get_workflow_steps(request_id)

        # Get activity log
        activity = db.get_activity_log(request_id)

        return render_template('offboard_detail.html',
                             request=request_data,
                             steps=steps,
                             activity=activity,
                             user=current_user)

    except Exception as e:
        logger.exception(f"Error viewing offboarding request {request_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/offboard/<int:request_id>/start', methods=['POST'])
@login_required
def start_offboard(request_id):
    """Start the offboarding workflow"""
    try:
        result = orchestrator.start_offboarding(request_id)

        if result.get('success'):
            flash('Offboarding workflow started successfully!', 'success')
        else:
            flash(f'Workflow failed: {result.get("error")}', 'error')

        return redirect(url_for('web.view_offboard', request_id=request_id))

    except Exception as e:
        logger.exception(f"Error starting offboarding workflow {request_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.view_offboard', request_id=request_id))


@web_bp.route('/tasks')
@login_required
def manual_tasks():
    """View all pending manual tasks"""
    try:
        tasks = db.get_pending_manual_tasks()

        return render_template('manual_tasks.html',
                             tasks=tasks,
                             user=current_user)

    except Exception as e:
        logger.exception("Error viewing manual tasks")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/tasks/<int:task_id>/complete', methods=['POST'])
@login_required
def complete_task(task_id):
    """Mark a manual task as complete"""
    try:
        notes = request.form.get('notes', '')

        # Update the workflow step
        db.update_workflow_step(
            task_id,
            'completed',
            success=True,
            result_data={'completion_notes': notes, 'completed_by': current_user.email}
        )

        # Log the activity
        steps = db.get_connection().execute(
            "SELECT offboarding_request_id FROM workflow_steps WHERE id = ?",
            (task_id,)
        ).fetchone()

        if steps:
            request_id = steps[0]
            db.log_activity(
                request_id,
                'manual_task_completed',
                f'Manual task #{task_id} marked as complete by {current_user.email}',
                created_by=current_user.email,
                metadata={'task_id': task_id, 'notes': notes}
            )

            # Check if all steps are complete
            remaining_steps = db.get_connection().execute(
                """SELECT COUNT(*) FROM workflow_steps
                   WHERE offboarding_request_id = ? AND status NOT IN ('completed', 'skipped')""",
                (request_id,)
            ).fetchone()[0]

            if remaining_steps == 0:
                db.update_offboarding_status(request_id, 'completed')

        flash('Manual task marked as complete!', 'success')
        return redirect(url_for('web.manual_tasks'))

    except Exception as e:
        logger.exception(f"Error completing manual task {task_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.manual_tasks'))


@web_bp.route('/requests')
@login_required
def all_requests():
    """View all offboarding requests"""
    try:
        status_filter = request.args.get('status')
        requests = db.get_all_offboarding_requests(status_filter)

        return render_template('all_requests.html',
                             requests=requests,
                             status_filter=status_filter,
                             user=current_user)

    except Exception as e:
        logger.exception("Error viewing all requests")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))
