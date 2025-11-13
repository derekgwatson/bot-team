from flask import Blueprint, jsonify, request
from services.google_workspace import workspace_service

api_bp = Blueprint('api', __name__)

@api_bp.route('/users', methods=['GET'])
def list_users():
    """
    GET /api/users

    Query parameters:
        - archived: true/false (default: false)
        - max_results: int (default: 100)

    Returns list of users
    """
    archived = request.args.get('archived', 'false').lower() == 'true'
    max_results = int(request.args.get('max_results', 100))

    users = workspace_service.list_users(max_results=max_results, archived=archived)

    if isinstance(users, dict) and 'error' in users:
        return jsonify(users), 500

    return jsonify({
        'users': users,
        'count': len(users)
    })

@api_bp.route('/users/<email>', methods=['GET'])
def get_user(email):
    """
    GET /api/users/<email>

    Returns details for a specific user
    """
    user = workspace_service.get_user(email)

    if isinstance(user, dict) and 'error' in user:
        status_code = 404 if user['error'] == 'User not found' else 500
        return jsonify(user), status_code

    return jsonify(user)

@api_bp.route('/users', methods=['POST'])
def create_user():
    """
    POST /api/users

    Body (JSON):
        {
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "TempPassword123!"
        }

    Creates a new user
    """
    data = request.get_json()

    # Validate required fields
    required_fields = ['email', 'first_name', 'last_name', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    result = workspace_service.create_user(
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        password=data['password']
    )

    if isinstance(result, dict) and 'error' in result:
        return jsonify(result), 500

    return jsonify(result), 201

@api_bp.route('/users/<email>/archive', methods=['POST'])
def archive_user(email):
    """
    POST /api/users/<email>/archive

    Archives a user (suspends and marks as archived)
    """
    result = workspace_service.archive_user(email)

    if isinstance(result, dict) and 'error' in result:
        status_code = 404 if result['error'] == 'User not found' else 500
        return jsonify(result), status_code

    return jsonify(result)
