from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.google_workspace import workspace_service
from services.auth import login_required
from database.db import db
from config import config
import time

web_bp = Blueprint('web', __name__, template_folder='templates')

# How long to hide recently deleted/archived users (in seconds)
# Google API eventual consistency usually resolves within 30 seconds
HIDE_DELETED_DURATION = 60


def _get_pending_count():
    """Get count of pending operations for nav badge"""
    try:
        pending = db.get_pending_operations()
        return len(pending)
    except Exception:
        return 0


def _get_hidden_users():
    """Get list of recently deleted/archived users that should be hidden from lists"""
    hidden = session.get('hidden_users', {})
    now = time.time()
    # Clean up expired entries
    hidden = {email: ts for email, ts in hidden.items() if now - ts < HIDE_DELETED_DURATION}
    session['hidden_users'] = hidden
    return set(hidden.keys())


def _hide_user(email):
    """Mark a user to be hidden from lists temporarily"""
    hidden = session.get('hidden_users', {})
    hidden[email] = time.time()
    session['hidden_users'] = hidden


@web_bp.route('/')
@login_required
def index():
    """Home page showing active users"""
    users = workspace_service.list_users(archived=False)

    if isinstance(users, dict) and 'error' in users:
        error = users['error']
        users = []
    else:
        error = None
        # Filter out recently deleted/archived users (Google API eventual consistency)
        hidden = _get_hidden_users()
        if hidden:
            users = [u for u in users if u.get('email') not in hidden]

    return render_template('index.html', users=users, error=error, archived=False,
                          active_nav='active', pending_count=_get_pending_count())

@web_bp.route('/archived')
@login_required
def archived():
    """Page showing archived users"""
    users = workspace_service.list_users(archived=True)

    if isinstance(users, dict) and 'error' in users:
        error = users['error']
        users = []
    else:
        error = None
        # Filter out recently deleted users (Google API eventual consistency)
        hidden = _get_hidden_users()
        if hidden:
            users = [u for u in users if u.get('email') not in hidden]

    return render_template('index.html', users=users, error=error, archived=True,
                          active_nav='archived', pending_count=_get_pending_count())

@web_bp.route('/users/<email>')
@login_required
def user_detail(email):
    """User detail page"""
    user = workspace_service.get_user(email)

    if isinstance(user, dict) and 'error' in user:
        error = user['error']
        user = None
    else:
        error = None

    return render_template('user_detail.html', user=user, error=error,
                          pending_count=_get_pending_count())

@web_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    """Create new user form"""
    # Get allowed domains from Google Workspace
    allowed_domains = workspace_service.list_domains()
    if isinstance(allowed_domains, dict) and 'error' in allowed_domains:
        allowed_domains = [config.google_domain]  # Fallback

    if request.method == 'POST':
        # Field names obfuscated to prevent password manager detection
        email = request.form.get('f1c')  # Combined email from JS
        first_name = request.form.get('f2a')
        last_name = request.form.get('f2b')
        password = request.form.get('f3a')
        change_password = request.form.get('f3b') == 'on'  # Checkbox for change password at next login
        generate_backup = request.form.get('f4a') == 'on'  # Checkbox for backup codes
        queue_only = request.form.get('queue_only') == '1'  # Hidden field for queue button

        # Validate email domain
        if '@' not in email:
            return render_template('new_user.html', error='Invalid email address',
                                 allowed_domains=allowed_domains, pending_count=_get_pending_count())

        email_domain = email.split('@')[1].lower()
        allowed_domains_lower = [d.lower() for d in allowed_domains]
        if email_domain not in allowed_domains_lower:
            return render_template('new_user.html',
                                 error=f'Email must use one of these domains: {", ".join(allowed_domains)}',
                                 allowed_domains=allowed_domains, pending_count=_get_pending_count())

        # If queue only, save to pending operations
        if queue_only:
            operation_data = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'password': password,
                'change_password_at_next_login': change_password,
                'generate_backup_codes': generate_backup
            }
            operation_id = db.queue_operation(
                operation_type='create_user',
                operation_data=operation_data,
                created_by='web'
            )
            flash(f'User creation queued (Operation #{operation_id}). Go to Pending to execute.', 'success')
            return redirect(url_for('web.pending'))

        # Immediate creation
        result = workspace_service.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            change_password_at_next_login=change_password
        )

        if isinstance(result, dict) and 'error' in result:
            return render_template('new_user.html', error=result['error'],
                                 allowed_domains=allowed_domains, pending_count=_get_pending_count())

        # Generate backup codes if requested
        backup_codes = []
        if generate_backup:
            backup_result = workspace_service.generate_backup_codes(email)
            if backup_result.get('success'):
                backup_codes = backup_result.get('backup_codes', [])

        # Show success page with credentials
        return render_template('user_created.html',
                             email=email,
                             password=password,
                             change_password=change_password,
                             backup_codes=backup_codes,
                             pending_count=_get_pending_count())

    return render_template('new_user.html', allowed_domains=allowed_domains,
                          pending_count=_get_pending_count())

@web_bp.route('/users/<email>/archive', methods=['POST'])
@login_required
def archive_user_action(email):
    """Archive user action"""
    result = workspace_service.archive_user(email)

    if isinstance(result, dict) and 'error' in result:
        flash(result['error'], 'error')
    else:
        # Hide user from list temporarily (Google API eventual consistency)
        _hide_user(email)
        flash(f'User {email} archived successfully', 'success')

    return redirect(url_for('web.index'))

@web_bp.route('/users/<email>/delete', methods=['POST'])
@login_required
def delete_user_action(email):
    """Delete user action"""
    result = workspace_service.delete_user(email)

    if isinstance(result, dict) and 'error' in result:
        flash(result['error'], 'error')
    else:
        # Hide user from list temporarily (Google API eventual consistency)
        _hide_user(email)
        flash(f'User {email} deleted successfully', 'success')

    return redirect(url_for('web.index'))


# ─── Pending Operations Routes ────────────────────────────────────────────────

@web_bp.route('/pending')
@login_required
def pending():
    """Page showing pending operations"""
    pending_ops = db.get_operations(status='pending')
    # Also get failed ones (can be retried)
    failed_ops = db.get_operations(status='failed', limit=20)
    # Combine pending and failed for main list
    operations = pending_ops + failed_ops

    # Get recently completed/cancelled for reference
    completed_ops = db.get_operations(status='completed', limit=10)
    cancelled_ops = db.get_operations(status='cancelled', limit=5)
    completed_operations = completed_ops + cancelled_ops

    return render_template('pending.html',
                          operations=operations,
                          completed_operations=completed_operations,
                          active_nav='pending',
                          pending_count=len(pending_ops))

@web_bp.route('/pending/<int:operation_id>')
@login_required
def operation_detail(operation_id):
    """View operation details"""
    operation = db.get_operation(operation_id)

    if not operation:
        flash('Operation not found', 'error')
        return redirect(url_for('web.pending'))

    return render_template('operation_detail.html',
                          operation=operation,
                          active_nav='pending',
                          pending_count=_get_pending_count())

@web_bp.route('/pending/<int:operation_id>/execute', methods=['POST'])
@login_required
def execute_operation(operation_id):
    """Execute a pending operation"""
    operation = db.get_operation(operation_id)

    if not operation:
        flash('Operation not found', 'error')
        return redirect(url_for('web.pending'))

    if operation['status'] not in ['pending', 'failed']:
        flash(f'Cannot execute operation with status: {operation["status"]}', 'error')
        return redirect(url_for('web.pending'))

    # Mark as executing
    db.update_operation_status(operation_id, 'executing', executed_by='web')

    try:
        result = _execute_operation(operation)

        if 'error' in result:
            db.update_operation_status(operation_id, 'failed', error_message=result['error'])
            flash(f'Operation failed: {result["error"]}', 'error')
        else:
            db.update_operation_status(operation_id, 'completed', result_data=result)
            flash(f'Operation completed successfully', 'success')

            # For create_user, redirect to result page to show credentials
            if operation['operation_type'] == 'create_user':
                return redirect(url_for('web.operation_detail', operation_id=operation_id))

    except Exception as e:
        db.update_operation_status(operation_id, 'failed', error_message=str(e))
        flash(f'Operation failed: {str(e)}', 'error')

    return redirect(url_for('web.pending'))

@web_bp.route('/pending/<int:operation_id>/cancel', methods=['POST'])
@login_required
def cancel_operation(operation_id):
    """Cancel a pending operation"""
    operation = db.get_operation(operation_id)

    if not operation:
        flash('Operation not found', 'error')
        return redirect(url_for('web.pending'))

    if operation['status'] != 'pending':
        flash(f'Cannot cancel operation with status: {operation["status"]}', 'error')
        return redirect(url_for('web.pending'))

    db.cancel_operation(operation_id, cancelled_by='web')
    flash('Operation cancelled', 'success')

    return redirect(url_for('web.pending'))

@web_bp.route('/pending/<int:operation_id>/retry', methods=['POST'])
@login_required
def retry_operation(operation_id):
    """Retry a failed operation"""
    operation = db.get_operation(operation_id)

    if not operation:
        flash('Operation not found', 'error')
        return redirect(url_for('web.pending'))

    if operation['status'] != 'failed':
        flash(f'Cannot retry operation with status: {operation["status"]}', 'error')
        return redirect(url_for('web.pending'))

    # Reset to pending and execute
    db.update_operation_status(operation_id, 'pending')
    return execute_operation(operation_id)

@web_bp.route('/pending/execute-all', methods=['POST'])
@login_required
def execute_all_pending():
    """Execute all pending operations"""
    pending_ops = db.get_pending_operations()

    if not pending_ops:
        flash('No pending operations to execute', 'info')
        return redirect(url_for('web.pending'))

    success_count = 0
    fail_count = 0

    for operation in pending_ops:
        db.update_operation_status(operation['id'], 'executing', executed_by='web')

        try:
            result = _execute_operation(operation)

            if 'error' in result:
                db.update_operation_status(operation['id'], 'failed', error_message=result['error'])
                fail_count += 1
            else:
                db.update_operation_status(operation['id'], 'completed', result_data=result)
                success_count += 1

        except Exception as e:
            db.update_operation_status(operation['id'], 'failed', error_message=str(e))
            fail_count += 1

    if fail_count > 0:
        flash(f'Executed {success_count} operations, {fail_count} failed', 'warning')
    else:
        flash(f'Successfully executed {success_count} operations', 'success')

    return redirect(url_for('web.pending'))


def _execute_operation(operation: dict) -> dict:
    """Execute a single operation and return result"""
    op_type = operation['operation_type']
    op_data = operation['operation_data']

    if op_type == 'create_user':
        result = workspace_service.create_user(
            email=op_data['email'],
            first_name=op_data['first_name'],
            last_name=op_data['last_name'],
            password=op_data['password'],
            change_password_at_next_login=op_data.get('change_password_at_next_login', True)
        )

        if isinstance(result, dict) and 'error' in result:
            return result

        # Generate backup codes if requested
        backup_codes = []
        if op_data.get('generate_backup_codes'):
            backup_result = workspace_service.generate_backup_codes(op_data['email'])
            if backup_result.get('success'):
                backup_codes = backup_result.get('backup_codes', [])

        return {
            'user': result,
            'email': op_data['email'],
            'password': op_data['password'],
            'backup_codes': backup_codes
        }

    elif op_type == 'archive_user':
        result = workspace_service.archive_user(op_data['email'])

        if isinstance(result, dict) and 'error' in result:
            return result

        _hide_user(op_data['email'])
        return {'archived': True, 'email': op_data['email']}

    elif op_type == 'delete_user':
        result = workspace_service.delete_user(op_data['email'])

        if isinstance(result, dict) and 'error' in result:
            return result

        _hide_user(op_data['email'])
        return {'deleted': True, 'email': op_data['email']}

    else:
        return {'error': f'Unknown operation type: {op_type}'}
