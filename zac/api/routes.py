from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required
from services.zendesk import zendesk_service
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/users', methods=['GET'])
@api_key_required
def list_users():
    """
    List all Zendesk users with optional filtering

    Query Parameters:
        role: Filter by role (end-user, agent, admin)
        page: Page number (default: 1)
        per_page: Results per page (default: 100)

    Returns:
        JSON object with users list and pagination info
    """
    try:
        role = request.args.get('role')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))

        result = zendesk_service.list_users(role=role, page=page, per_page=per_page)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@api_key_required
def get_user(user_id):
    """
    Get a specific user by ID

    Args:
        user_id: Zendesk user ID

    Returns:
        JSON object with user details
    """
    try:
        user = zendesk_service.get_user(user_id)
        if user:
            return jsonify(user), 200
        else:
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/search', methods=['GET'])
@api_key_required
def search_users():
    """
    Search for users by name or email

    Query Parameters:
        q: Search query string

    Returns:
        JSON array of matching users
    """
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'error': 'Search query required'}), 400

        users = zendesk_service.search_users(query)
        return jsonify({'users': users}), 200

    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users', methods=['POST'])
@api_key_required
def create_user():
    """
    Create a new Zendesk user

    Request Body:
        name: User's full name (required)
        email: User's email address (required)
        role: User role (default: end-user)
        verified: Email verified status (default: false)
        phone: Phone number (optional)
        organization_id: Organization ID (optional)

    Returns:
        JSON object with created user details
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        name = data.get('name')
        email = data.get('email')

        if not name or not email:
            return jsonify({'error': 'name and email are required'}), 400

        role = data.get('role', 'end-user')
        verified = data.get('verified', False)

        # Extract additional properties
        additional_props = {
            k: v for k, v in data.items()
            if k not in ['name', 'email', 'role', 'verified']
        }

        user = zendesk_service.create_user(
            name=name,
            email=email,
            role=role,
            verified=verified,
            **additional_props
        )

        return jsonify(user), 201

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>', methods=['PUT', 'PATCH'])
@api_key_required
def update_user(user_id):
    """
    Update a user's properties

    Args:
        user_id: Zendesk user ID

    Request Body:
        Any user properties to update (name, email, role, phone, etc.)

    Returns:
        JSON object with updated user details
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        user = zendesk_service.update_user(user_id, **data)
        return jsonify(user), 200

    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@api_key_required
def suspend_user(user_id):
    """
    Suspend a user

    Args:
        user_id: Zendesk user ID

    Returns:
        JSON object with updated user details
    """
    try:
        user = zendesk_service.suspend_user(user_id)
        return jsonify(user), 200

    except Exception as e:
        logger.error(f"Error suspending user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>/unsuspend', methods=['POST'])
@api_key_required
def unsuspend_user(user_id):
    """
    Unsuspend a user

    Args:
        user_id: Zendesk user ID

    Returns:
        JSON object with updated user details
    """
    try:
        user = zendesk_service.unsuspend_user(user_id)
        return jsonify(user), 200

    except Exception as e:
        logger.error(f"Error unsuspending user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>', methods=['DELETE'])
@api_key_required
def delete_user(user_id):
    """
    Delete a user

    Args:
        user_id: Zendesk user ID

    Returns:
        Success message
    """
    try:
        zendesk_service.delete_user(user_id)
        return jsonify({'message': f'User {user_id} deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
