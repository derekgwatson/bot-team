"""
API Routes for Oscar
REST API for onboarding workflows
"""

from flask import Blueprint, jsonify, request
from database.db import db
from services.orchestrator import orchestrator, get_orchestrator
import logging
from shared.auth.bot_api import api_key_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """Return Oscar's introduction"""
    return jsonify({
        'name': 'Oscar',
        'role': 'Staff Onboarding Orchestrator',
        'description': 'I coordinate the onboarding process for new staff members by working with Fred (Google Workspace), Zac (Zendesk), Peter (HR Database), and Sadie (Zendesk Tickets).',
        'capabilities': [
            'Process onboarding requests',
            'Create Google Workspace accounts',
            'Create Zendesk accounts',
            'Register staff in HR database',
            'Create VOIP setup tickets',
            'Send notifications to HR/Payroll',
            'Track onboarding workflow progress'
        ],
        'endpoints': {
            'POST /api/onboard': 'Submit a new onboarding request',
            'POST /api/onboard/preview': 'Preview onboarding workflow (DRY RUN - no changes made)',
            'GET /api/onboard/<id>': 'Get onboarding request details',
            'GET /api/onboard': 'List all onboarding requests',
            'POST /api/onboard/<id>/start': 'Start onboarding workflow',
            'GET /api/tasks': 'Get pending manual tasks',
            'POST /api/tasks/<id>/complete': 'Mark manual task as complete'
        }
    })


@api_bp.route('/onboard', methods=['POST'])
@api_key_required
def create_onboarding():
    """Create a new onboarding request"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['full_name', 'position', 'section', 'start_date', 'personal_email']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create the request
        created_by = data.get('created_by', 'api')
        request_id = db.create_onboarding_request(data, created_by)

        # Optionally auto-start the workflow
        auto_start = data.get('auto_start', False)
        if auto_start:
            result = orchestrator.start_onboarding(request_id)
            return jsonify({
                'success': True,
                'request_id': request_id,
                'workflow_started': True,
                'workflow_result': result
            }), 201

        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Onboarding request created. Use POST /api/onboard/<id>/start to begin.'
        }), 201

    except Exception as e:
        logger.exception("Error creating onboarding request")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/onboard/preview', methods=['POST'])
@api_key_required
def preview_onboarding():
    """
    Preview what an onboarding workflow would do (DRY RUN).

    This endpoint shows exactly what would happen if you submitted an onboarding
    request, including which bots would be called and what data would be sent.
    No actual changes are made.

    Useful for:
    - Validating data before submission
    - Testing workflow configuration
    - Understanding what Oscar will do
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['full_name', 'position', 'section', 'start_date', 'personal_email']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Get a dry-run orchestrator and preview
        dry_run_orchestrator = get_orchestrator(dry_run=True)
        preview = dry_run_orchestrator.preview_onboarding(data)

        return jsonify(preview)

    except Exception as e:
        logger.exception("Error generating preview")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/onboard/<int:request_id>', methods=['GET'])
@api_key_required
def get_onboarding(request_id):
    """Get onboarding request details"""
    try:
        request_data = db.get_onboarding_request(request_id)
        if not request_data:
            return jsonify({'error': 'Onboarding request not found'}), 404

        # Get workflow steps
        steps = db.get_workflow_steps(request_id)

        # Get activity log
        activity = db.get_activity_log(request_id)

        return jsonify({
            'request': request_data,
            'steps': steps,
            'activity': activity
        })

    except Exception as e:
        logger.exception(f"Error getting onboarding request {request_id}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/onboard', methods=['GET'])
@api_key_required
def list_onboarding():
    """List all onboarding requests"""
    try:
        status = request.args.get('status')
        requests = db.get_all_onboarding_requests(status)

        return jsonify({
            'requests': requests,
            'count': len(requests)
        })

    except Exception as e:
        logger.exception("Error listing onboarding requests")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/onboard/<int:request_id>/start', methods=['POST'])
@api_key_required
def start_onboarding(request_id):
    """Start the onboarding workflow for a request"""
    try:
        request_data = db.get_onboarding_request(request_id)
        if not request_data:
            return jsonify({'error': 'Onboarding request not found'}), 404

        if request_data['status'] != 'pending':
            return jsonify({
                'error': f"Cannot start workflow. Request status is '{request_data['status']}'"
            }), 400

        # Start the workflow
        result = orchestrator.start_onboarding(request_id)

        return jsonify(result)

    except Exception as e:
        logger.exception(f"Error starting onboarding workflow {request_id}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks', methods=['GET'])
@api_key_required
def get_manual_tasks():
    """Get all pending manual tasks"""
    try:
        tasks = db.get_pending_manual_tasks()

        return jsonify({
            'tasks': tasks,
            'count': len(tasks)
        })

    except Exception as e:
        logger.exception("Error getting manual tasks")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks/<int:task_id>/complete', methods=['POST'])
@api_key_required
def complete_manual_task(task_id):
    """Mark a manual task as complete"""
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')

        # Update the workflow step
        db.update_workflow_step(
            task_id,
            'completed',
            success=True,
            result_data={'completion_notes': notes}
        )

        # Get the step to find the request_id
        steps = db.get_connection().execute(
            "SELECT onboarding_request_id FROM workflow_steps WHERE id = ?",
            (task_id,)
        ).fetchone()

        if steps:
            request_id = steps[0]
            db.log_activity(
                request_id,
                'manual_task_completed',
                f'Manual task #{task_id} marked as complete',
                created_by=data.get('completed_by', 'api'),
                metadata={'task_id': task_id, 'notes': notes}
            )

            # Check if all steps are complete, and update request status if so
            remaining_steps = db.get_connection().execute(
                """SELECT COUNT(*) FROM workflow_steps
                   WHERE onboarding_request_id = ? AND status NOT IN ('completed', 'skipped')""",
                (request_id,)
            ).fetchone()[0]

            if remaining_steps == 0:
                db.update_onboarding_status(request_id, 'completed')

        return jsonify({
            'success': True,
            'message': 'Manual task marked as complete'
        })

    except Exception as e:
        logger.exception(f"Error completing manual task {task_id}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats', methods=['GET'])
@api_key_required
def get_stats():
    """Get onboarding statistics"""
    try:
        conn = db.get_connection()

        # Get counts by status
        stats = {
            'total': 0,
            'by_status': {},
            'pending_manual_tasks': 0
        }

        # Count requests by status
        cursor = conn.execute(
            "SELECT status, COUNT(*) FROM onboarding_requests GROUP BY status"
        )
        for row in cursor:
            stats['by_status'][row[0]] = row[1]
            stats['total'] += row[1]

        # Count pending manual tasks
        cursor = conn.execute(
            """SELECT COUNT(*) FROM workflow_steps
               WHERE requires_manual_action = 1 AND status IN ('pending', 'in_progress')"""
        )
        stats['pending_manual_tasks'] = cursor.fetchone()[0]

        conn.close()

        return jsonify(stats)

    except Exception as e:
        logger.exception("Error getting stats")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dependencies', methods=['GET'])
@api_key_required
def get_dependencies():
    """Get list of bots that Oscar depends on"""
    return jsonify({
        'dependencies': ['fred', 'zac', 'peter', 'sadie']
    })


@api_bp.route('/dev-config', methods=['GET'])
@api_key_required
def get_dev_config():
    """Get current dev bot configuration (from session)"""
    from flask import session
    return jsonify(session.get('dev_bot_config', {}))


@api_bp.route('/dev-config', methods=['POST'])
@api_key_required
def update_dev_config():
    """Update dev bot configuration (stores in session)"""
    from flask import session

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get existing config or create new
    dev_config = session.get('dev_bot_config', {})

    # Update with new settings
    dev_config.update(data)

    # Store in session
    session['dev_bot_config'] = dev_config

    return jsonify({
        'success': True,
        'config': dev_config
    })


@api_bp.route('/check-pending-tickets', methods=['POST'])
@api_key_required
def check_pending_tickets():
    """
    Check status of pending VOIP tickets and update workflow steps accordingly.

    This endpoint is designed to be called periodically by Skye (the scheduler).
    It queries Sadie for the status of each pending VOIP ticket and marks
    the workflow step as complete if the ticket has been solved.

    Returns:
        JSON object with results of the check
    """
    from config import config
    from shared.http_client import BotHttpClient

    try:
        # Get all in-progress VOIP steps with ticket IDs
        pending_steps = db.get_pending_voip_steps()

        if not pending_steps:
            return jsonify({
                'success': True,
                'message': 'No pending VOIP tickets to check',
                'checked': 0,
                'completed': 0
            })

        results = {
            'success': True,
            'checked': len(pending_steps),
            'completed': 0,
            'still_pending': 0,
            'errors': 0,
            'details': []
        }

        # Get Sadie client
        sadie_url = config.bots.get('sadie', {}).get('url', 'http://localhost:8005')
        sadie_client = BotHttpClient(sadie_url, timeout=10)

        for step in pending_steps:
            ticket_id = step.get('zendesk_ticket_id')
            step_id = step.get('id')
            request_id = step.get('request_id')
            full_name = step.get('full_name', 'Unknown')

            if not ticket_id:
                continue

            try:
                # Query Sadie for ticket status
                response = sadie_client.get(f'/api/tickets/{ticket_id}')

                if response.status_code == 200:
                    # Sadie returns ticket data directly, not wrapped in {"ticket": ...}
                    ticket_data = response.json()
                    ticket_status = ticket_data.get('status', '')

                    if ticket_status in ['solved', 'closed']:
                        # Ticket is complete - mark the step as completed
                        db.update_workflow_step(
                            step_id,
                            'completed',
                            success=True,
                            result_data={
                                'ticket_status': ticket_status,
                                'auto_completed': True,
                                'completed_by': 'Oscar (auto-check)'
                            }
                        )

                        db.log_activity(
                            request_id,
                            'voip_ticket_auto_completed',
                            f'VOIP ticket #{ticket_id} was {ticket_status} - step auto-completed',
                            created_by='oscar_scheduler'
                        )

                        # Check if all steps are now complete
                        remaining = db.get_connection().execute(
                            """SELECT COUNT(*) FROM workflow_steps
                               WHERE onboarding_request_id = ? AND status NOT IN ('completed', 'skipped')""",
                            (request_id,)
                        ).fetchone()[0]

                        if remaining == 0:
                            db.update_onboarding_status(request_id, 'completed')

                        results['completed'] += 1
                        results['details'].append({
                            'ticket_id': ticket_id,
                            'full_name': full_name,
                            'status': 'completed',
                            'ticket_status': ticket_status
                        })
                    else:
                        results['still_pending'] += 1
                        results['details'].append({
                            'ticket_id': ticket_id,
                            'full_name': full_name,
                            'status': 'still_pending',
                            'ticket_status': ticket_status
                        })
                else:
                    results['errors'] += 1
                    results['details'].append({
                        'ticket_id': ticket_id,
                        'full_name': full_name,
                        'status': 'error',
                        'error': f'Sadie returned {response.status_code}'
                    })

            except Exception as e:
                logger.warning(f"Error checking ticket {ticket_id}: {e}")
                results['errors'] += 1
                results['details'].append({
                    'ticket_id': ticket_id,
                    'full_name': full_name,
                    'status': 'error',
                    'error': str(e)
                })

        return jsonify(results)

    except Exception as e:
        logger.exception("Error checking pending tickets")
        return jsonify({'error': str(e)}), 500
