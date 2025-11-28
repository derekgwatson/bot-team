"""API routes for Paige - DokuWiki user management endpoints."""
from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required, api_or_session_auth
from services.dokuwiki_service import DokuWikiService
from services.sync_service import SyncService
from config import config
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize the DokuWiki service
wiki_service = DokuWikiService(
    dokuwiki_path=config.dokuwiki_path,
    default_groups=config.default_groups
)

# Initialize the sync service
sync_service = SyncService(wiki_service)


@api_bp.route('/users', methods=['GET'])
@api_or_session_auth
def list_users():
    """
    List all DokuWiki users.

    Returns:
        JSON with list of users
    """
    users = wiki_service.get_all_users()
    return jsonify({
        'users': [u.to_dict() for u in users],
        'count': len(users)
    })


@api_bp.route('/users/<login>', methods=['GET'])
@api_or_session_auth
def get_user(login: str):
    """
    Get a specific user by login.

    Args:
        login: Username to look up

    Returns:
        JSON with user data or 404
    """
    user = wiki_service.get_user(login)
    if not user:
        return jsonify({'error': f'User not found: {login}'}), 404

    return jsonify({'user': user.to_dict()})


@api_bp.route('/users', methods=['POST'])
@api_key_required
def create_user():
    """
    Create a new DokuWiki user.

    Expected JSON body:
        {
            "login": "firstname.lastname",
            "name": "Full Name",
            "email": "email@example.com",
            "groups": ["user", "google"]  // optional, defaults to config
        }

    Returns:
        JSON with created user or error
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing JSON body'}), 400

    # Validate required fields
    required = ['login', 'name', 'email']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    result = wiki_service.add_user(
        login=data['login'],
        name=data['name'],
        email=data['email'],
        groups=data.get('groups')  # None means use defaults
    )

    if result['success']:
        logger.info(f"Created wiki user: {data['login']} ({data['email']})")
        return jsonify(result), 201
    else:
        logger.warning(f"Failed to create wiki user: {result.get('error')}")
        return jsonify(result), 400


@api_bp.route('/users/<login>', methods=['DELETE'])
@api_key_required
def delete_user(login: str):
    """
    Delete a DokuWiki user.

    Args:
        login: Username to delete

    Returns:
        JSON with success status
    """
    result = wiki_service.remove_user(login)

    if result['success']:
        logger.info(f"Deleted wiki user: {login}")
        return jsonify(result)
    else:
        logger.warning(f"Failed to delete wiki user {login}: {result.get('error')}")
        status_code = 404 if 'not found' in result.get('error', '').lower() else 400
        return jsonify(result), status_code


@api_bp.route('/users/<login>/exists', methods=['GET'])
@api_key_required
def check_user_exists(login: str):
    """
    Check if a user exists.

    Args:
        login: Username to check

    Returns:
        JSON with exists boolean
    """
    exists = wiki_service.user_exists(login)
    return jsonify({
        'login': login,
        'exists': exists
    })


@api_bp.route('/status', methods=['GET'])
@api_or_session_auth
def get_status():
    """
    Get DokuWiki service status.

    Returns:
        JSON with service health information
    """
    health = wiki_service.get_health_status()
    return jsonify(health)


@api_bp.route('/sync', methods=['POST'])
@api_key_required
def sync_users():
    """
    Sync wiki users with Peter staff directory.

    Peter is authoritative - users are added/removed based on Peter's data.
    Admin users in the wiki are never removed (safety measure).

    Returns:
        JSON with sync results (added, removed, errors)
    """
    logger.info("Starting wiki user sync with Peter")
    result = sync_service.sync()

    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500


@api_bp.route('/sync/preview', methods=['GET'])
@api_or_session_auth
def preview_sync():
    """
    Preview what a sync would do without making changes.

    Returns:
        JSON showing what would be added/removed
    """
    result = sync_service.preview()
    return jsonify(result)
