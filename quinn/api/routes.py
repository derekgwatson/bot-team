from flask import Blueprint, jsonify, request
from functools import wraps
from database.db import db
from services.google_groups import groups_service
import os

api_bp = Blueprint('api', __name__)

def require_api_key(f):
    """Decorator to require API key for bot-to-bot communication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.environ.get('BOT_API_KEY')

        if not expected_key:
            # If no API key is configured, allow (for initial setup)
            return f(*args, **kwargs)

        if api_key != expected_key:
            return jsonify({'error': 'Invalid or missing API key'}), 401

        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    GET /api/intro

    Returns Quinn's introduction
    """
    return jsonify({
        'name': 'Quinn',
        'greeting': "Hi! I'm Quinn, your external staff access manager.",
        'description': "I manage access for staff who don't have company email addresses. I keep track of approved external staff and manage the allstaff Google Group membership.",
        'capabilities': [
            'Check if external emails are approved for access',
            'Manage external staff registry',
            'Automatically add/remove members from allstaff Google Group',
            'Provide access control for other bots',
            'Track when staff were added and by whom'
        ]
    })

@api_bp.route('/is-approved', methods=['GET'])
@require_api_key
def is_approved():
    """
    GET /api/is-approved?email=xxx
    Header: X-API-Key: <api_key>

    Check if an email address is approved

    Returns:
        JSON with approval status and staff info
    """
    email = request.args.get('email')

    if not email:
        return jsonify({'error': 'email parameter is required'}), 400

    result = db.is_approved(email)
    return jsonify(result)

@api_bp.route('/staff', methods=['GET'])
def get_staff():
    """
    GET /api/staff?status=active

    Get all external staff members

    Query params:
        status: Filter by status (active, inactive, or omit for all)

    Returns:
        JSON list of staff members
    """
    status = request.args.get('status')
    staff = db.get_all_staff(status=status)

    return jsonify({
        'staff': staff,
        'count': len(staff)
    })

@api_bp.route('/staff', methods=['POST'])
def add_staff():
    """
    POST /api/staff

    Add a new external staff member

    Body (JSON):
        {
            "name": "John Doe",
            "email": "john@personal.com",
            "phone": "0412 345 678",
            "role": "Contractor",
            "notes": "Works in warehouse"
        }

    Returns:
        JSON with success status
    """
    data = request.get_json()

    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'name and email are required'}), 400

    added_by = request.headers.get('X-User-Email', 'unknown')

    result = db.add_staff(
        name=data['name'],
        email=data['email'],
        phone=data.get('phone', ''),
        role=data.get('role', ''),
        added_by=added_by,
        notes=data.get('notes', '')
    )

    if 'error' in result:
        return jsonify(result), 400

    # Add to Google Group
    group_result = groups_service.add_member(data['email'])

    return jsonify({
        **result,
        'group_membership': group_result
    }), 201

@api_bp.route('/staff/<int:staff_id>', methods=['GET'])
def get_staff_by_id(staff_id):
    """
    GET /api/staff/<id>

    Get a specific staff member

    Returns:
        JSON with staff member details
    """
    staff = db.get_staff_by_id(staff_id)

    if not staff:
        return jsonify({'error': 'Staff member not found'}), 404

    return jsonify(staff)

@api_bp.route('/staff/<int:staff_id>', methods=['PUT'])
def update_staff(staff_id):
    """
    PUT /api/staff/<id>

    Update a staff member

    Body (JSON):
        {
            "name": "New Name",
            "status": "inactive",
            ...
        }

    Returns:
        JSON with success status
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    # Get old status to check if it changed
    old_staff = db.get_staff_by_id(staff_id)
    if not old_staff:
        return jsonify({'error': 'Staff member not found'}), 404

    result = db.update_staff(
        staff_id=staff_id,
        name=data.get('name'),
        email=data.get('email'),
        phone=data.get('phone'),
        role=data.get('role'),
        status=data.get('status'),
        notes=data.get('notes')
    )

    if 'error' in result:
        return jsonify(result), 400

    # Handle Google Group membership if status changed
    new_status = data.get('status')
    if new_status and new_status != old_staff['status']:
        email = data.get('email', old_staff['email'])

        if new_status == 'active':
            group_result = groups_service.add_member(email)
        else:
            group_result = groups_service.remove_member(email)

        result['group_membership'] = group_result

    return jsonify(result)

@api_bp.route('/staff/<int:staff_id>', methods=['DELETE'])
def delete_staff(staff_id):
    """
    DELETE /api/staff/<id>

    Delete (deactivate) a staff member

    Returns:
        JSON with success status
    """
    # Get staff email before deactivating
    staff = db.get_staff_by_id(staff_id)
    if not staff:
        return jsonify({'error': 'Staff member not found'}), 404

    result = db.delete_staff(staff_id)

    if 'error' in result:
        return jsonify(result), 400

    # Remove from Google Group
    group_result = groups_service.remove_member(staff['email'])

    return jsonify({
        **result,
        'group_membership': group_result
    })
