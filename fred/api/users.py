from flask import Blueprint, jsonify, request
from services.google_workspace import workspace_service
from shared.auth.bot_api import api_key_required
from config import config

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """
    GET /api/intro

    Returns Fred's introduction
    """
    return jsonify({
        'name': 'Fred',
        'greeting': "Hi! I'm Fred, your Google Workspace user management bot.",
        'description': "I handle all the user account stuff for your Google Workspace - creating accounts when people join, archiving them when they leave. Think of me as your friendly neighborhood account manager. I can work through my web interface if you want to do things manually, or you can call my API if you want to automate things. Either way, I've got you covered!",
        'capabilities': [
            'Create new user accounts with temporary passwords',
            'List all active and archived users',
            'Archive users (suspends them but keeps their data)',
            'Permanently delete users (use carefully!)',
            'Provide both web UI and REST API access'
        ]
    })

@api_bp.route('/users', methods=['GET'])
@api_key_required
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
@api_key_required
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

@api_bp.route('/domains', methods=['GET'])
@api_key_required
def list_domains():
    """
    GET /api/domains

    Returns list of domains registered in the Google Workspace account
    """
    domains = workspace_service.list_domains()

    if isinstance(domains, dict) and 'error' in domains:
        return jsonify(domains), 500

    return jsonify({
        'domains': domains,
        'count': len(domains)
    })


@api_bp.route('/users', methods=['POST'])
@api_key_required
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

    # Validate email domain against allowed domains from Google Workspace
    email = data['email']
    if '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    email_domain = email.split('@')[1].lower()
    allowed_domains = workspace_service.list_domains()

    # Fall back to config if API fails
    if isinstance(allowed_domains, dict) and 'error' in allowed_domains:
        allowed_domains = [config.google_domain]

    allowed_domains_lower = [d.lower() for d in allowed_domains]
    if email_domain not in allowed_domains_lower:
        return jsonify({'error': f'Email must use one of these domains: {", ".join(allowed_domains)}'}), 400

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
@api_key_required
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

@api_bp.route('/users/<email>', methods=['DELETE'])
@api_key_required
def delete_user(email):
    """
    DELETE /api/users/<email>

    Permanently deletes a user (cannot be undone)
    """
    result = workspace_service.delete_user(email)

    if isinstance(result, dict) and 'error' in result:
        status_code = 404 if result['error'] == 'User not found' else 500
        return jsonify(result), status_code

    return jsonify(result)
