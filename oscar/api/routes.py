"""
API Routes for Oscar
REST API for onboarding workflows
"""

from flask import Blueprint, jsonify, request
from database.db import db
from services.orchestrator import orchestrator
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro', methods=['GET'])
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
            'GET /api/onboard/<id>': 'Get onboarding request details',
            'GET /api/onboard': 'List all onboarding requests',
            'POST /api/onboard/<id>/start': 'Start onboarding workflow',
            'GET /api/tasks': 'Get pending manual tasks',
            'POST /api/tasks/<id>/complete': 'Mark manual task as complete'
        }
    })


@api_bp.route('/onboard', methods=['POST'])
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


@api_bp.route('/onboard/<int:request_id>', methods=['GET'])
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
