"""
Hugo API routes.

Provides REST API for Buz user management.
"""
import logging
import threading
import time
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


def _run_sync_in_background(orgs_to_sync: list, sync_ids: dict):
    """
    Run the sync operation in a background thread.

    Args:
        orgs_to_sync: List of org keys to sync
        sync_ids: Dict mapping org_key to sync_log id
    """
    from config import config
    service, run_async = get_user_service()
    db = get_db()

    for org in orgs_to_sync:
        sync_id = sync_ids.get(org)
        start_time = time.time()

        try:
            logger.info(f"Background sync starting for {org}")

            # Scrape users from Buz
            sync_result = run_async(service.scrape_org_users(org))

            # Update database
            db_result = db.bulk_upsert_users(sync_result['users'], org)

            duration = time.time() - start_time

            # Complete the sync record
            db.complete_sync(
                sync_id=sync_id,
                user_count=sync_result['user_count'],
                status='success',
                duration_seconds=duration
            )

            logger.info(f"Background sync completed for {org}: {sync_result['user_count']} users in {duration:.1f}s")

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(f"Background sync failed for {org}")

            db.complete_sync(
                sync_id=sync_id,
                user_count=0,
                status='error',
                error_message=str(e),
                duration_seconds=duration
            )


@api_bp.route('/users/sync', methods=['POST'])
@api_or_session_auth
def sync_users():
    """
    POST /api/users/sync

    Sync users from Buz for one or all orgs.
    Runs in background thread and returns immediately.

    Body (JSON):
        org: Optional org_key (if not specified, syncs all orgs)

    Returns:
        status: 'started'
        sync_ids: Dict of org_key -> sync_log id for tracking
    """
    data = request.get_json() or {}
    org_key = data.get('org')

    try:
        from config import config
        db = get_db()

        orgs_to_sync = [org_key] if org_key else config.available_orgs

        # Check if any syncs are already running
        running = db.get_running_syncs()
        running_orgs = {s['org_key'] for s in running}
        conflicts = set(orgs_to_sync) & running_orgs

        if conflicts:
            return jsonify({
                'error': f"Sync already running for: {', '.join(conflicts)}",
                'running_syncs': running
            }), 409

        # Create sync records for each org
        sync_ids = {}
        for org in orgs_to_sync:
            sync_ids[org] = db.start_sync(org)

        # Start background thread
        thread = threading.Thread(
            target=_run_sync_in_background,
            args=(orgs_to_sync, sync_ids),
            name=f"sync_{'_'.join(orgs_to_sync)}",
            daemon=True
        )
        thread.start()

        logger.info(f"Started background sync for {orgs_to_sync} (sync_ids={sync_ids})")

        return jsonify({
            'status': 'started',
            'orgs': orgs_to_sync,
            'sync_ids': sync_ids,
            'message': 'Sync started in background. Check /api/users/sync/status for progress.'
        })

    except Exception as e:
        logger.exception("Error starting sync")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/users/sync/status', methods=['GET'])
@api_or_session_auth
def users_sync_status():
    """
    GET /api/users/sync/status

    Get status of running syncs and recent sync history.
    """
    try:
        db = get_db()
        running = db.get_running_syncs()
        recent = db.get_sync_history(limit=10)

        return jsonify({
            'running': running,
            'recent': recent
        })

    except Exception as e:
        logger.exception("Error getting sync status")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/users/<email>/activate', methods=['POST'])
@api_or_session_auth
def activate_user(email):
    """
    POST /api/users/<email>/activate

    Activate a user in Buz (queued by default).

    Body (JSON):
        org: Organization key (required)
        immediate: If true, execute immediately (default: false, queue for batch)
    """
    data = request.get_json() or {}
    org_key = data.get('org')
    immediate = data.get('immediate', False)

    if not org_key:
        return jsonify({'error': 'org is required'}), 400

    if immediate:
        return _toggle_user_immediate(email, org_key, activate=True)
    else:
        return _queue_user_change(email, org_key, action='activate')


@api_bp.route('/users/<email>/deactivate', methods=['POST'])
@api_or_session_auth
def deactivate_user(email):
    """
    POST /api/users/<email>/deactivate

    Deactivate a user in Buz (queued by default).

    Body (JSON):
        org: Organization key (required)
        immediate: If true, execute immediately (default: false, queue for batch)
    """
    data = request.get_json() or {}
    org_key = data.get('org')
    immediate = data.get('immediate', False)

    if not org_key:
        return jsonify({'error': 'org is required'}), 400

    if immediate:
        return _toggle_user_immediate(email, org_key, activate=False)
    else:
        return _queue_user_change(email, org_key, action='deactivate')


def _queue_user_change(email: str, org_key: str, action: str):
    """
    Queue a user status change for batch processing.

    Args:
        email: User's email
        org_key: Organization key
        action: 'activate' or 'deactivate'
    """
    try:
        db = get_db()

        # Get user to verify they exist and get user_type
        user = db.get_user_by_email(email, org_key=org_key)

        if not user:
            return jsonify({
                'error': f'User {email} not found in {org_key}. Try syncing first.'
            }), 404

        current_is_active = bool(user['is_active'])
        user_type = user['user_type']

        # Check if already in desired state
        desired_active = (action == 'activate')
        if current_is_active == desired_active:
            state = "active" if desired_active else "inactive"
            return jsonify({
                'success': True,
                'message': f'User is already {state}',
                'no_change': True
            })

        # Queue the change
        requested_by = request.headers.get('X-Performed-By', 'web')
        result = db.queue_change(
            email=email,
            org_key=org_key,
            action=action,
            user_type=user_type,
            requested_by=requested_by
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'queued': result.get('queued', True),
                'message': result.get('message', 'Change queued'),
                'email': email,
                'org': org_key,
                'action': action
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to queue change')
            }), 500

    except Exception as e:
        logger.exception(f"Error queuing change for {email}")
        return jsonify({'error': str(e)}), 500


def _toggle_user_immediate(email: str, org_key: str, activate: bool):
    """
    Execute user status toggle immediately (not queued).

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


# Queue endpoints

@api_bp.route('/queue', methods=['GET'])
@api_or_session_auth
def get_queue():
    """
    GET /api/queue

    Get pending changes in the queue.

    Query params:
        org: Optional org filter
    """
    org_key = request.args.get('org')
    db = get_db()

    changes = db.get_pending_changes(org_key=org_key)
    queue_stats = db.get_queue_stats()

    return jsonify({
        'pending': changes,
        'count': len(changes),
        'stats': queue_stats
    })


@api_bp.route('/queue/process', methods=['POST'])
@api_or_session_auth
def process_queue():
    """
    POST /api/queue/process

    Process all pending changes in the queue.

    Body (JSON):
        org: Optional org_key (if not specified, processes all orgs)

    This endpoint is called by Skye on a schedule.
    """
    data = request.get_json() or {}
    org_filter = data.get('org')

    try:
        from config import config
        service, run_async = get_user_service()
        db = get_db()
        peter_sync = get_peter_sync()

        # Get pending changes grouped by org
        if org_filter:
            changes_by_org = {org_filter: db.get_pending_changes(org_filter)}
        else:
            changes_by_org = db.get_pending_changes_by_org()

        if not any(changes_by_org.values()):
            return jsonify({
                'success': True,
                'message': 'No pending changes to process',
                'processed': 0
            })

        results = []
        total_processed = 0
        total_success = 0
        total_failed = 0

        for org_key, changes in changes_by_org.items():
            if not changes:
                continue

            # Mark as processing
            change_ids = [c['id'] for c in changes]
            db.mark_changes_processing(change_ids)

            try:
                # Build batch for user service
                user_changes = [{
                    'email': c['email'],
                    'is_active': c['action'] != 'activate',  # Current state (opposite of desired)
                    'user_type': c['user_type']
                } for c in changes]

                # Process batch
                batch_results = run_async(service.batch_toggle_users(org_key, user_changes))

                # Update each change based on result
                for change, result in zip(changes, batch_results):
                    success = result.get('success', False)
                    error_msg = result.get('message', '') if not success else ''

                    db.complete_change(change['id'], success, error_msg)

                    if success:
                        total_success += 1

                        # Update local cache
                        new_state = result.get('new_state')
                        if new_state is not None:
                            db.update_user_status(change['email'], org_key, new_state)

                        # Log activity
                        db.log_activity(
                            action=change['action'],
                            email=change['email'],
                            org_key=org_key,
                            old_value=str(not new_state) if new_state is not None else '',
                            new_value=str(new_state) if new_state is not None else '',
                            performed_by=change['requested_by'],
                            success=True
                        )

                        # Sync to Peter
                        all_orgs = db.get_user_orgs(change['email'])
                        peter_sync.sync_user_access(
                            email=change['email'],
                            is_active=new_state,
                            org_key=org_key,
                            all_user_orgs=all_orgs
                        )
                    else:
                        total_failed += 1
                        db.log_activity(
                            action=change['action'],
                            email=change['email'],
                            org_key=org_key,
                            performed_by=change['requested_by'],
                            success=False,
                            error_message=error_msg
                        )

                    total_processed += 1

                results.append({
                    'org': org_key,
                    'processed': len(changes),
                    'success': sum(1 for r in batch_results if r.get('success')),
                    'failed': sum(1 for r in batch_results if not r.get('success'))
                })

            except Exception as e:
                logger.exception(f"Error processing queue for {org_key}")
                # Mark all as failed
                for change in changes:
                    db.complete_change(change['id'], False, str(e))
                    total_failed += 1
                    total_processed += 1

                results.append({
                    'org': org_key,
                    'processed': len(changes),
                    'success': 0,
                    'failed': len(changes),
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'results': results,
            'total_processed': total_processed,
            'total_success': total_success,
            'total_failed': total_failed
        })

    except Exception as e:
        logger.exception("Error processing queue")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/queue/clear', methods=['POST'])
@api_or_session_auth
def clear_queue():
    """
    POST /api/queue/clear

    Clear completed/failed changes older than X days.

    Body (JSON):
        days: Number of days (default 7)
    """
    data = request.get_json() or {}
    days = data.get('days', 7)

    db = get_db()
    deleted = db.clear_completed_changes(older_than_days=days)

    return jsonify({
        'success': True,
        'deleted': deleted
    })


# Auth health endpoints

@api_bp.route('/auth/health', methods=['GET'])
@api_or_session_auth
def get_auth_health():
    """
    GET /api/auth/health

    Get auth health status for all orgs.
    """
    db = get_db()
    health = db.get_auth_health()
    unhealthy = db.get_unhealthy_orgs()

    return jsonify({
        'health': health,
        'unhealthy_count': len(unhealthy),
        'unhealthy': unhealthy
    })


@api_bp.route('/auth/check', methods=['POST'])
@api_or_session_auth
def check_auth():
    """
    POST /api/auth/check

    Run auth health check for one or all orgs.

    Body (JSON):
        org: Optional org_key (if not specified, checks all orgs)

    This endpoint is called by Skye on a schedule.
    """
    data = request.get_json() or {}
    org_key = data.get('org')

    try:
        service, run_async = get_user_service()
        db = get_db()

        if org_key:
            # Check single org
            result = run_async(service.check_auth_health(org_key))
            db.update_auth_health(
                org_key=result['org_key'],
                status=result['status'],
                error_message=result['message'] if result['status'] != 'healthy' else ''
            )
            results = [result]
        else:
            # Check all orgs
            results = run_async(service.check_all_auth_health())
            for result in results:
                db.update_auth_health(
                    org_key=result['org_key'],
                    status=result['status'],
                    error_message=result['message'] if result['status'] != 'healthy' else ''
                )

        healthy_count = sum(1 for r in results if r['status'] == 'healthy')
        unhealthy_count = len(results) - healthy_count

        return jsonify({
            'success': True,
            'results': results,
            'healthy': healthy_count,
            'unhealthy': unhealthy_count
        })

    except Exception as e:
        logger.exception("Error checking auth health")
        return jsonify({'error': str(e)}), 500


# Screenshot endpoints

@api_bp.route('/screenshots', methods=['GET'])
@api_or_session_auth
def list_screenshots():
    """
    GET /api/screenshots

    List available error screenshots.
    """
    from pathlib import Path
    from config import config

    screenshot_dir = Path(config.browser_screenshot_dir)

    if not screenshot_dir.exists():
        return jsonify({'screenshots': [], 'count': 0})

    screenshots = []
    for f in sorted(screenshot_dir.glob('*.png'), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        screenshots.append({
            'name': f.name,
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'url': f'/api/screenshots/{f.name}'
        })

    return jsonify({
        'screenshots': screenshots[:50],  # Limit to 50 most recent
        'count': len(screenshots)
    })


@api_bp.route('/screenshots/<filename>', methods=['GET'])
@api_or_session_auth
def get_screenshot(filename):
    """
    GET /api/screenshots/<filename>

    Serve a screenshot file.
    """
    from flask import send_from_directory
    from pathlib import Path
    from config import config

    screenshot_dir = Path(config.browser_screenshot_dir)

    # Security: ensure filename doesn't contain path traversal
    if '..' in filename or '/' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = screenshot_dir / filename
    if not filepath.exists():
        return jsonify({'error': 'Screenshot not found'}), 404

    return send_from_directory(str(screenshot_dir), filename, mimetype='image/png')


@api_bp.route('/screenshots/<filename>', methods=['DELETE'])
@api_or_session_auth
def delete_screenshot(filename):
    """
    DELETE /api/screenshots/<filename>

    Delete a screenshot file.
    """
    from pathlib import Path
    from config import config

    screenshot_dir = Path(config.browser_screenshot_dir)

    # Security: ensure filename doesn't contain path traversal
    if '..' in filename or '/' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = screenshot_dir / filename
    if not filepath.exists():
        return jsonify({'error': 'Screenshot not found'}), 404

    filepath.unlink()
    return jsonify({'success': True, 'deleted': filename})
