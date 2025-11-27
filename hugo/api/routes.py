"""
Hugo API routes.

Provides REST API for Buz user management.
"""
import logging
from flask import Blueprint, jsonify, request
from shared.auth.bot_api import api_key_required, api_or_session_auth

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def get_user_service():
    """Lazy import to avoid circular imports."""
    from services.user_service import BuzUserService, run_async
    from config import config
    return BuzUserService(config), run_async


def get_db():
    """Lazy import to avoid circular imports."""
    from database.db import user_db
    return user_db


def get_peter_sync():
    """Lazy import to avoid circular imports."""
    from services.peter_sync import peter_sync
    return peter_sync


@api_bp.route('/users', methods=['GET'])
@api_or_session_auth
def get_users():
    """
    GET /api/users

    List cached users with optional filters.

    Query params:
        org: Filter by org_key
        active: Filter by active status (true/false)
        type: Filter by user_type (employee/customer)
    """
    org_key = request.args.get('org')
    active_param = request.args.get('active')
    user_type = request.args.get('type')

    is_active = None
    if active_param is not None:
        is_active = active_param.lower() == 'true'

    try:
        db = get_db()
        users = db.get_users(org_key=org_key, is_active=is_active, user_type=user_type)

        return jsonify({
            'users': users,
            'count': len(users),
            'filters': {
                'org': org_key,
                'active': is_active,
                'type': user_type
            }
        })
    except Exception as e:
        logger.exception("Error fetching users")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/users/<email>', methods=['GET'])
@api_or_session_auth
def get_user(email):
    """
    GET /api/users/<email>

    Get a specific user by email.

    Query params:
        org: Optional org filter
    """
    org_key = request.args.get('org')

    try:
        db = get_db()
        user = db.get_user_by_email(email, org_key=org_key)

        if not user:
            return jsonify({'error': f'User {email} not found'}), 404

        # Also get all orgs for this user
        orgs = db.get_user_orgs(email)

        return jsonify({
            'user': user,
            'all_orgs': orgs
        })
    except Exception as e:
        logger.exception(f"Error fetching user {email}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/users/sync', methods=['POST'])
@api_or_session_auth
def sync_users():
    """
    POST /api/users/sync

    Sync users from Buz for one or all orgs.

    Body (JSON):
        org: Optional org_key (if not specified, syncs all orgs)
    """
    data = request.get_json() or {}
    org_key = data.get('org')

    try:
        from config import config
        service, run_async = get_user_service()
        db = get_db()

        orgs_to_sync = [org_key] if org_key else config.available_orgs

        results = []
        for org in orgs_to_sync:
            try:
                # Scrape users from Buz
                sync_result = run_async(service.scrape_org_users(org))

                # Update database
                db_result = db.bulk_upsert_users(sync_result['users'], org)

                # Log the sync
                db.log_sync(
                    org_key=org,
                    user_count=sync_result['user_count'],
                    status='success',
                    duration_seconds=sync_result['duration_seconds']
                )

                results.append({
                    'org': org,
                    'success': True,
                    'user_count': sync_result['user_count'],
                    'created': db_result['created'],
                    'updated': db_result['updated'],
                    'duration': sync_result['duration_seconds']
                })

            except Exception as e:
                logger.exception(f"Error syncing {org}")
                db.log_sync(
                    org_key=org,
                    user_count=0,
                    status='error',
                    error_message=str(e)
                )
                results.append({
                    'org': org,
                    'success': False,
                    'error': str(e)
                })

        return jsonify({
            'results': results,
            'total_orgs': len(results),
            'successful': sum(1 for r in results if r['success'])
        })

    except Exception as e:
        logger.exception("Error in sync")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/users/<email>/activate', methods=['POST'])
@api_or_session_auth
def activate_user(email):
    """
    POST /api/users/<email>/activate

    Activate a user in Buz.

    Body (JSON):
        org: Organization key (required)
    """
    data = request.get_json() or {}
    org_key = data.get('org')

    if not org_key:
        return jsonify({'error': 'org is required'}), 400

    return _toggle_user(email, org_key, activate=True)


@api_bp.route('/users/<email>/deactivate', methods=['POST'])
@api_or_session_auth
def deactivate_user(email):
    """
    POST /api/users/<email>/deactivate

    Deactivate a user in Buz.

    Body (JSON):
        org: Organization key (required)
    """
    data = request.get_json() or {}
    org_key = data.get('org')

    if not org_key:
        return jsonify({'error': 'org is required'}), 400

    return _toggle_user(email, org_key, activate=False)


def _toggle_user(email: str, org_key: str, activate: bool):
    """
    Internal helper to toggle user status.

    Args:
        email: User's email
        org_key: Organization key
        activate: True to activate, False to deactivate
    """
    try:
        service, run_async = get_user_service()
        db = get_db()
        peter_sync = get_peter_sync()

        # Get current user state from cache
        user = db.get_user_by_email(email, org_key=org_key)

        if not user:
            return jsonify({
                'error': f'User {email} not found in {org_key}. Try syncing first.'
            }), 404

        current_is_active = bool(user['is_active'])
        user_type = user['user_type']

        # Check if already in desired state
        if current_is_active == activate:
            state = "active" if activate else "inactive"
            return jsonify({
                'success': True,
                'message': f'User is already {state}',
                'no_change': True
            })

        # Toggle in Buz
        result = run_async(service.toggle_user_status(
            org_key=org_key,
            email=email,
            current_is_active=current_is_active,
            user_type=user_type
        ))

        if result['success']:
            # Update local cache
            db.update_user_status(email, org_key, result['new_state'])

            # Log the activity
            db.log_activity(
                action='activate' if activate else 'deactivate',
                email=email,
                org_key=org_key,
                old_value=str(current_is_active),
                new_value=str(result['new_state']),
                performed_by=request.headers.get('X-Performed-By', 'api')
            )

            # Sync to Peter
            all_orgs = db.get_user_orgs(email)
            peter_result = peter_sync.sync_user_access(
                email=email,
                is_active=result['new_state'],
                org_key=org_key,
                all_user_orgs=all_orgs
            )

            return jsonify({
                'success': True,
                'email': email,
                'org': org_key,
                'new_state': 'active' if result['new_state'] else 'inactive',
                'peter_sync': peter_result
            })

        else:
            # Log failed attempt
            db.log_activity(
                action='activate' if activate else 'deactivate',
                email=email,
                org_key=org_key,
                old_value=str(current_is_active),
                new_value='',
                performed_by=request.headers.get('X-Performed-By', 'api'),
                success=False,
                error_message=result['message']
            )

            return jsonify({
                'success': False,
                'error': result['message']
            }), 500

    except Exception as e:
        logger.exception(f"Error toggling user {email}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/orgs', methods=['GET'])
@api_or_session_auth
def get_orgs():
    """
    GET /api/orgs

    List available organizations.
    """
    from config import config

    orgs = []
    for org_key in config.available_orgs:
        org_config = config.buz_orgs[org_key]
        orgs.append({
            'key': org_key,
            'name': org_config['display_name'],
            'has_customers': org_config.get('has_customers', False)
        })

    # Also include orgs missing auth
    for org_key in config.buz_orgs_missing_auth.keys():
        orgs.append({
            'key': org_key,
            'name': org_key.title(),
            'missing_auth': True
        })

    return jsonify({
        'orgs': orgs,
        'configured_count': len(config.available_orgs),
        'missing_auth_count': len(config.buz_orgs_missing_auth)
    })


@api_bp.route('/sync/status', methods=['GET'])
@api_or_session_auth
def sync_status():
    """
    GET /api/sync/status

    Get sync status for all orgs.
    """
    from config import config
    db = get_db()

    status = []
    for org_key in config.available_orgs:
        last_sync = db.get_last_sync(org_key)
        status.append({
            'org': org_key,
            'last_sync': last_sync
        })

    return jsonify({
        'status': status
    })


@api_bp.route('/sync/history', methods=['GET'])
@api_or_session_auth
def sync_history():
    """
    GET /api/sync/history

    Get sync history.

    Query params:
        org: Optional org filter
        limit: Max records (default 20)
    """
    org_key = request.args.get('org')
    limit = int(request.args.get('limit', 20))

    db = get_db()
    history = db.get_sync_history(org_key=org_key, limit=limit)

    return jsonify({
        'history': history,
        'count': len(history)
    })


@api_bp.route('/activity', methods=['GET'])
@api_or_session_auth
def activity_log():
    """
    GET /api/activity

    Get activity log.

    Query params:
        email: Filter by user email
        org: Filter by org
        limit: Max records (default 50)
    """
    email = request.args.get('email')
    org_key = request.args.get('org')
    limit = int(request.args.get('limit', 50))

    db = get_db()
    log = db.get_activity_log(email=email, org_key=org_key, limit=limit)

    return jsonify({
        'activity': log,
        'count': len(log)
    })


@api_bp.route('/stats', methods=['GET'])
@api_or_session_auth
def stats():
    """
    GET /api/stats

    Get user statistics.
    """
    db = get_db()
    stats = db.get_stats()

    return jsonify(stats)
