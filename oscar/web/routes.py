"""
Web Routes for Oscar
User interface for onboarding workflows
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.auth import login_required, admin_required
from database.db import db
from services.orchestrator import orchestrator
from config import config
from shared.http_client import BotHttpClient
import logging

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


def _get_bot_client(bot_name: str, timeout: int = 10) -> BotHttpClient:
    """Get a BotHttpClient for the specified bot."""
    bot_url = config.bots.get(bot_name, {}).get('url', f'http://localhost:8000')
    return BotHttpClient(bot_url, timeout=timeout)


def _get_google_domains():
    """Fetch available domains from Fred's API"""
    try:
        client = _get_bot_client('fred')
        response = client.get('/api/domains')
        if response.status_code == 200:
            return response.json().get('domains', [])
    except Exception as e:
        logger.warning(f"Could not fetch domains from Fred: {e}")
    return []  # Return empty list on failure


def _get_zendesk_groups():
    """Fetch available groups from Zac's API"""
    try:
        client = _get_bot_client('zac')
        response = client.get('/api/groups')
        if response.status_code == 200:
            return response.json().get('groups', [])
    except Exception as e:
        logger.warning(f"Could not fetch groups from Zac: {e}")
    return []  # Return empty list on failure


def _get_sadie_groups():
    """Fetch available groups from Sadie's API for ticket assignment"""
    try:
        client = _get_bot_client('sadie')
        response = client.get('/api/groups')
        if response.status_code == 200:
            return response.json().get('groups', [])
    except Exception as e:
        logger.warning(f"Could not fetch groups from Sadie: {e}")
    return []  # Return empty list on failure


@web_bp.route('/')
@login_required
def index():
    """Dashboard with onboarding form and requests"""
    try:
        # Get statistics
        stats = {
            'pending': len(db.get_all_onboarding_requests('pending')),
            'in_progress': len(db.get_all_onboarding_requests('in_progress')),
            'completed': len(db.get_all_onboarding_requests('completed')),
            'failed': len(db.get_all_onboarding_requests('failed'))
        }

        # Get recent requests
        recent_requests = db.get_all_onboarding_requests()[:10]

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


@web_bp.route('/onboard/new')
@login_required
def new_onboard():
    """Show new onboarding form"""
    # Fetch available domains from Fred for work email selection
    google_domains = _get_google_domains()
    # Fetch available groups from Zac for Zendesk agent assignment
    zendesk_groups = _get_zendesk_groups()
    return render_template('onboard_form.html', user=current_user,
                         google_domains=google_domains, zendesk_groups=zendesk_groups)


@web_bp.route('/onboard/submit', methods=['POST'])
@login_required
def submit_onboard():
    """Submit a new onboarding request (prep-and-fire mode: sets up but doesn't execute)"""
    try:
        # Get form data
        data = {
            'full_name': request.form.get('full_name'),
            'preferred_name': request.form.get('preferred_name', ''),
            'position': request.form.get('position'),
            'section': request.form.get('section'),
            'start_date': request.form.get('start_date'),
            'personal_email': request.form.get('personal_email'),
            'phone_mobile': request.form.get('phone_mobile', ''),
            'phone_fixed': request.form.get('phone_fixed', ''),
            'google_access': request.form.get('google_access') == 'on',
            'zendesk_access': request.form.get('zendesk_access') == 'on',
            'voip_access': request.form.get('voip_access') == 'on',
            'wiki_access': request.form.get('wiki_access') == 'on',
            'notes': request.form.get('notes', '')
        }

        # Build work email if Google access is requested
        # Field names obfuscated to prevent password manager detection
        if data['google_access']:
            work_username = request.form.get('wx1', '').strip().lower()
            work_domain = request.form.get('wx2', '')
            if work_username and work_domain:
                data['work_email'] = f"{work_username}@{work_domain}"

        # Get selected Zendesk groups if Zendesk access is requested
        if data['zendesk_access']:
            selected_groups = request.form.getlist('zendesk_groups')
            if selected_groups:
                data['zendesk_groups'] = [int(g) for g in selected_groups]

        # Validate required fields
        required_fields = ['full_name', 'position', 'section', 'start_date', 'personal_email']
        for field in required_fields:
            if not data.get(field):
                flash(f'Missing required field: {field}', 'error')
                return redirect(url_for('web.new_onboard'))

        # Validate work email if Google access requested
        if data['google_access'] and not data.get('work_email'):
            flash('Work email is required when Google access is enabled', 'error')
            return redirect(url_for('web.new_onboard'))

        # Create the onboarding request
        request_id = db.create_onboarding_request(data, created_by=current_user.email)

        # Set up workflow steps (but don't execute them)
        result = orchestrator.setup_workflow(request_id)

        if result.get('success'):
            flash(f'Onboarding request created for {data["full_name"]}. Ready to create accounts when you are!', 'success')
        else:
            flash(f'Onboarding request created but workflow setup failed: {result.get("error")}', 'warning')

        return redirect(url_for('web.view_onboard', request_id=request_id))

    except Exception as e:
        logger.exception("Error submitting onboarding request")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.new_onboard'))


@web_bp.route('/onboard/<int:request_id>')
@login_required
def view_onboard(request_id):
    """View onboarding request details"""
    try:
        request_data = db.get_onboarding_request(request_id)
        if not request_data:
            flash('Onboarding request not found', 'error')
            return redirect(url_for('web.index'))

        # Get workflow steps
        steps = db.get_workflow_steps(request_id)

        # Get activity log
        activity = db.get_activity_log(request_id)

        # Parse backup codes from JSON if present
        backup_codes = []
        if request_data.get('google_backup_codes'):
            try:
                backup_codes = json.loads(request_data['google_backup_codes'])
            except (json.JSONDecodeError, TypeError):
                pass

        return render_template('onboard_detail.html',
                             request=request_data,
                             steps=steps,
                             activity=activity,
                             backup_codes=backup_codes,
                             user=current_user)

    except Exception as e:
        logger.exception(f"Error viewing onboarding request {request_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/onboard/<int:request_id>/execute/<step_name>', methods=['POST'])
@login_required
def execute_step(request_id, step_name):
    """Execute a single workflow step"""
    try:
        result = orchestrator.execute_single_step(request_id, step_name)

        if result.get('success'):
            flash(f'Step "{step_name.replace("_", " ").title()}" completed successfully!', 'success')
        else:
            flash(f'Step failed: {result.get("error")}', 'error')

        return redirect(url_for('web.view_onboard', request_id=request_id))

    except Exception as e:
        logger.exception(f"Error executing step {step_name} for request {request_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.view_onboard', request_id=request_id))


@web_bp.route('/onboard/<int:request_id>/execute-all', methods=['POST'])
@login_required
def execute_all_steps(request_id):
    """Execute all pending workflow steps"""
    try:
        result = orchestrator.execute_all_pending(request_id)

        if result.get('success'):
            flash('All steps completed successfully!', 'success')
        else:
            completed = sum(1 for s in result.get('steps', []) if s.get('success'))
            total = len(result.get('steps', []))
            flash(f'Completed {completed}/{total} steps. Some steps failed.', 'warning')

        return redirect(url_for('web.view_onboard', request_id=request_id))

    except Exception as e:
        logger.exception(f"Error executing all steps for request {request_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.view_onboard', request_id=request_id))


@web_bp.route('/onboard/<int:request_id>/start', methods=['POST'])
@login_required
def start_onboard(request_id):
    """Start the onboarding workflow (legacy: execute all steps)"""
    return execute_all_steps(request_id)


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
            "SELECT onboarding_request_id FROM workflow_steps WHERE id = ?",
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
                   WHERE onboarding_request_id = ? AND status NOT IN ('completed', 'skipped')""",
                (request_id,)
            ).fetchone()[0]

            if remaining_steps == 0:
                db.update_onboarding_status(request_id, 'completed')

        flash('Manual task marked as complete!', 'success')
        return redirect(url_for('web.manual_tasks'))

    except Exception as e:
        logger.exception(f"Error completing manual task {task_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.manual_tasks'))


@web_bp.route('/requests')
@login_required
def all_requests():
    """View all onboarding requests"""
    try:
        status_filter = request.args.get('status')
        requests = db.get_all_onboarding_requests(status_filter)

        return render_template('all_requests.html',
                             requests=requests,
                             status_filter=status_filter,
                             user=current_user)

    except Exception as e:
        logger.exception("Error viewing all requests")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/settings')
@login_required
def settings():
    """View and edit Oscar settings"""
    try:
        all_settings = db.get_all_settings()
        # Fetch Zendesk groups from Sadie for the dropdown
        zendesk_groups = _get_sadie_groups()

        return render_template('settings.html',
                             settings=all_settings,
                             zendesk_groups=zendesk_groups,
                             user=current_user)

    except Exception as e:
        logger.exception("Error viewing settings")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/settings/save', methods=['POST'])
@login_required
def save_settings():
    """Save Oscar settings"""
    try:
        # Get form data
        settings_to_update = {
            'hr_notification_email': request.form.get('hr_notification_email', '').strip(),
            'hr_notification_name': request.form.get('hr_notification_name', '').strip(),
            'voip_ticket_group_id': request.form.get('voip_ticket_group_id', '').strip(),
            'voip_ticket_group_name': request.form.get('voip_ticket_group_name', '').strip(),
        }

        db.update_settings(settings_to_update, updated_by=current_user.email)

        flash('Settings saved successfully!', 'success')
        return redirect(url_for('web.settings'))

    except Exception as e:
        logger.exception("Error saving settings")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.settings'))
