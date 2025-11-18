"""
API Routes for Olive
REST API for offboarding workflows
"""

from flask import Blueprint, jsonify, request
from database.db import db
from services.orchestrator import orchestrator
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro', methods=['GET'])
def intro():
    """Return Olive's introduction"""
    return jsonify({
        'name': 'Olive',
        'role': 'Staff Offboarding Orchestrator',
        'description': 'I coordinate the offboarding process for departing staff members by removing system access from Google Workspace, Zendesk, Wiki, and Buz CRM, and updating Peter with finish dates.',
        'capabilities': [
            'Process offboarding requests',
            'Check staff access in Peter',
            'Suspend Google Workspace accounts',
            'Deactivate Zendesk accounts',
            'Remove Wiki access',
            'Remove Buz CRM access',
            'Update Peter with finish dates',
            'Send notifications to HR/IT',
            'Track offboarding workflow progress'
        ],
        'endpoints': {
            'POST /api/offboard': 'Submit a new offboarding request',
            'GET /api/offboard/<id>': 'Get offboarding request details',
            'GET /api/offboard': 'List all offboarding requests',
            'POST /api/offboard/<id>/start': 'Start offboarding workflow',
            'GET /api/tasks': 'Get pending manual tasks',
            'POST /api/tasks/<id>/complete': 'Mark manual task as complete'
        }
    })


@api_bp.route('/offboard', methods=['POST'])
def create_offboarding():
    """Create a new offboarding request"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['full_name', 'last_day']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Create the request
        created_by = data.get('created_by', 'api')
        request_id = db.create_offboarding_request(data, created_by)

        # Optionally auto-start the workflow
        auto_start = data.get('auto_start', False)
        if auto_start:
            result = orchestrator.start_offboarding(request_id)
            return jsonify({
                'success': True,
                'request_id': request_id,
                'workflow_started': True,
                'workflow_result': result
            }), 201

        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Offboarding request created. Use POST /api/offboard/<id>/start to begin.'
        }), 201

    except Exception as e:
        logger.exception("Error creating offboarding request")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/offboard/<int:request_id>', methods=['GET'])
def get_offboarding(request_id):
    """Get offboarding request details"""
    try:
        request_data = db.get_offboarding_request(request_id)
        if not request_data:
            return jsonify({'error': 'Offboarding request not found'}), 404

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
        logger.exception(f"Error getting offboarding request {request_id}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/offboard', methods=['GET'])
def list_offboarding():
    """List all offboarding requests"""
    try:
        status = request.args.get('status')
        requests = db.get_all_offboarding_requests(status)

        return jsonify({
            'requests': requests,
            'count': len(requests)
        })

    except Exception as e:
        logger.exception("Error listing offboarding requests")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/offboard/<int:request_id>/start', methods=['POST'])
def start_offboarding(request_id):
    """Start the offboarding workflow for a request"""
    try:
        request_data = db.get_offboarding_request(request_id)
        if not request_data:
            return jsonify({'error': 'Offboarding request not found'}), 404

        if request_data['status'] != 'pending':
            return jsonify({
                'error': f"Cannot start workflow. Request status is '{request_data['status']}'"
            }), 400

        # Start the workflow
        result = orchestrator.start_offboarding(request_id)

        return jsonify(result)

    except Exception as e:
        logger.exception(f"Error starting offboarding workflow {request_id}")
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
            "SELECT offboarding_request_id FROM workflow_steps WHERE id = ?",
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
                   WHERE offboarding_request_id = ? AND status NOT IN ('completed', 'skipped')""",
                (request_id,)
            ).fetchone()[0]

            if remaining_steps == 0:
                db.update_offboarding_status(request_id, 'completed')

        return jsonify({
            'success': True,
            'message': 'Manual task marked as complete'
        })

    except Exception as e:
        logger.exception(f"Error completing manual task {task_id}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get offboarding statistics"""
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
            "SELECT status, COUNT(*) FROM offboarding_requests GROUP BY status"
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
def get_dependencies():
    """Get list of bots that Olive depends on"""
    return jsonify({
        'dependencies': ['peter', 'fred', 'zac', 'sadie']
    })


@api_bp.route('/dev-config', methods=['GET'])
def get_dev_config():
    """Get current dev bot configuration (from session)"""
    from flask import session
    return jsonify(session.get('dev_bot_config', {}))


@api_bp.route('/dev-config', methods=['POST'])
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
