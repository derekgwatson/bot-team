from flask import Blueprint, jsonify, request
from database.db import db
from services.zendesk import zendesk_service
from shared.auth.bot_api import api_key_required
import logging

logger = logging.getLogger(__name__)

operations_bp = Blueprint('operations', __name__)


@operations_bp.route('/operations', methods=['GET'])
@api_key_required
def list_operations():
    """
    GET /api/operations

    Query parameters:
        - status: Filter by status (pending, completed, failed, cancelled)
        - type: Filter by operation type (create_user, suspend_user, unsuspend_user, delete_user)
        - limit: Max results (default: 100)

    Returns list of operations
    """
    status = request.args.get('status')
    operation_type = request.args.get('type')
    limit = int(request.args.get('limit', 100))

    operations = db.get_operations(status=status, operation_type=operation_type, limit=limit)

    return jsonify({
        'operations': operations,
        'count': len(operations)
    })


@operations_bp.route('/operations/<int:operation_id>', methods=['GET'])
@api_key_required
def get_operation(operation_id):
    """
    GET /api/operations/<id>

    Returns details for a specific operation
    """
    operation = db.get_operation(operation_id)

    if not operation:
        return jsonify({'error': 'Operation not found'}), 404

    return jsonify(operation)


@operations_bp.route('/operations', methods=['POST'])
@api_key_required
def queue_operation():
    """
    POST /api/operations

    Body (JSON):
        {
            "operation_type": "create_user",  # create_user, suspend_user, unsuspend_user, delete_user
            "data": {
                # For create_user:
                "name": "John Doe",
                "email": "john@example.com",
                "verified": false,
                "group_ids": [123, 456]  # Optional

                # For suspend_user/unsuspend_user/delete_user:
                "user_id": 12345
            },
            "external_reference": "optional-ref-id"  # Optional, for Oscar integration
        }

    Queues an operation for later execution
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    operation_type = data.get('operation_type')
    operation_data = data.get('data', {})
    external_ref = data.get('external_reference')

    # Validate operation type
    valid_types = ['create_user', 'suspend_user', 'unsuspend_user', 'delete_user']
    if operation_type not in valid_types:
        return jsonify({'error': f'Invalid operation_type. Must be one of: {", ".join(valid_types)}'}), 400

    # Validate based on operation type
    if operation_type == 'create_user':
        if 'name' not in operation_data or 'email' not in operation_data:
            return jsonify({'error': 'Missing required fields in data: name, email'}), 400

    elif operation_type in ['suspend_user', 'unsuspend_user', 'delete_user']:
        if 'user_id' not in operation_data:
            return jsonify({'error': 'Missing required field in data: user_id'}), 400

    # Queue the operation
    operation_id = db.queue_operation(
        operation_type=operation_type,
        operation_data=operation_data,
        created_by=request.headers.get('X-Requesting-Bot', 'api'),
        external_reference=external_ref
    )

    operation = db.get_operation(operation_id)

    return jsonify({
        'message': 'Operation queued successfully',
        'operation': operation
    }), 201


@operations_bp.route('/operations/<int:operation_id>/execute', methods=['POST'])
@api_key_required
def execute_operation(operation_id):
    """
    POST /api/operations/<id>/execute

    Executes a pending operation
    """
    operation = db.get_operation(operation_id)

    if not operation:
        return jsonify({'error': 'Operation not found'}), 404

    if operation['status'] != 'pending':
        return jsonify({
            'error': f'Operation cannot be executed - current status: {operation["status"]}'
        }), 400

    # Mark as executing
    db.update_operation_status(
        operation_id,
        'executing',
        executed_by=request.headers.get('X-Requesting-Bot', 'api')
    )

    operation_type = operation['operation_type']
    op_data = operation['operation_data']

    try:
        if operation_type == 'create_user':
            result = _execute_create_user(op_data)
        elif operation_type == 'suspend_user':
            result = _execute_suspend_user(op_data)
        elif operation_type == 'unsuspend_user':
            result = _execute_unsuspend_user(op_data)
        elif operation_type == 'delete_user':
            result = _execute_delete_user(op_data)
        else:
            raise ValueError(f'Unknown operation type: {operation_type}')

        # Check for errors in result
        if isinstance(result, dict) and 'error' in result:
            db.update_operation_status(
                operation_id,
                'failed',
                error_message=result['error']
            )
            return jsonify({
                'success': False,
                'error': result['error'],
                'operation': db.get_operation(operation_id)
            }), 500

        # Success
        db.update_operation_status(
            operation_id,
            'completed',
            result_data=result
        )

        return jsonify({
            'success': True,
            'result': result,
            'operation': db.get_operation(operation_id)
        })

    except Exception as e:
        logger.error(f"Error executing operation {operation_id}: {str(e)}")
        db.update_operation_status(
            operation_id,
            'failed',
            error_message=str(e)
        )
        return jsonify({
            'success': False,
            'error': str(e),
            'operation': db.get_operation(operation_id)
        }), 500


@operations_bp.route('/operations/<int:operation_id>', methods=['DELETE'])
@api_key_required
def cancel_operation(operation_id):
    """
    DELETE /api/operations/<id>

    Cancels a pending operation
    """
    operation = db.get_operation(operation_id)

    if not operation:
        return jsonify({'error': 'Operation not found'}), 404

    if operation['status'] not in ['pending']:
        return jsonify({
            'error': f'Only pending operations can be cancelled - current status: {operation["status"]}'
        }), 400

    db.cancel_operation(
        operation_id,
        cancelled_by=request.headers.get('X-Requesting-Bot', 'api')
    )

    return jsonify({
        'message': 'Operation cancelled',
        'operation': db.get_operation(operation_id)
    })


@operations_bp.route('/operations/by-reference/<reference>', methods=['GET'])
@api_key_required
def get_operations_by_reference(reference):
    """
    GET /api/operations/by-reference/<reference>

    Get all operations for an external reference (e.g., Oscar request ID)
    """
    operations = db.get_operations_by_external_ref(reference)

    return jsonify({
        'external_reference': reference,
        'operations': operations,
        'count': len(operations)
    })


# Helper functions to execute operations

def _execute_create_user(op_data: dict) -> dict:
    """Execute a create_user operation"""
    try:
        # Enforce agent role for security
        result = zendesk_service.create_user(
            name=op_data['name'],
            email=op_data['email'],
            role='agent',  # Always agent
            verified=op_data.get('verified', False)
        )

        # Add to groups if specified
        group_memberships = []
        if op_data.get('group_ids'):
            try:
                memberships = zendesk_service.set_user_groups(result['id'], op_data['group_ids'])
                group_memberships = memberships
            except Exception as e:
                logger.warning(f"Failed to set groups: {str(e)}")

        return {
            'user': result,
            'user_id': result['id'],
            'email': result['email'],
            'group_memberships': group_memberships
        }
    except Exception as e:
        return {'error': str(e)}


def _execute_suspend_user(op_data: dict) -> dict:
    """Execute a suspend_user operation"""
    try:
        result = zendesk_service.suspend_user(op_data['user_id'])
        return {
            'suspended': True,
            'user_id': op_data['user_id'],
            'user': result
        }
    except Exception as e:
        return {'error': str(e)}


def _execute_unsuspend_user(op_data: dict) -> dict:
    """Execute an unsuspend_user operation"""
    try:
        result = zendesk_service.unsuspend_user(op_data['user_id'])
        return {
            'unsuspended': True,
            'user_id': op_data['user_id'],
            'user': result
        }
    except Exception as e:
        return {'error': str(e)}


def _execute_delete_user(op_data: dict) -> dict:
    """Execute a delete_user operation"""
    try:
        zendesk_service.delete_user(op_data['user_id'])
        return {
            'deleted': True,
            'user_id': op_data['user_id']
        }
    except Exception as e:
        return {'error': str(e)}
