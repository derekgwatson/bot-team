from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user
from services.zendesk import zendesk_service
from services.auth import login_required
from database.db import db
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


def _get_pending_count():
    """Get count of pending operations for nav badge"""
    try:
        pending = db.get_pending_operations()
        return len(pending)
    except Exception:
        return 0


@web_bp.route('/')
@login_required
def index():
    """Main dashboard - list all Zendesk users"""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role')

    try:
        result = zendesk_service.list_users(role=role_filter, page=page, per_page=100)

        return render_template('index.html',
                             users=result['users'],
                             page=result['page'],
                             total_pages=result['total_pages'],
                             total=result['total'],
                             role_filter=role_filter,
                             user=current_user,
                             active_nav='users',
                             pending_count=_get_pending_count())

    except Exception as e:
        return render_template('index.html',
                             error=str(e),
                             users=[],
                             page=1,
                             total_pages=1,
                             total=0,
                             user=current_user,
                             active_nav='users',
                             pending_count=_get_pending_count())

@web_bp.route('/user/<int:user_id>')
@login_required
def view_user(user_id):
    """View detailed information about a specific user"""
    try:
        user = zendesk_service.get_user(user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('web.index'))

        return render_template('user_detail.html', user=user, current_user=current_user,
                             pending_count=_get_pending_count())

    except Exception as e:
        flash(f'Error loading user: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/user/create', methods=['GET', 'POST'])
@login_required
def create_user():
    """Create a new Zendesk agent (restricted to agent role only for security)"""
    # Fetch available groups for selection
    try:
        groups = zendesk_service.list_groups()
    except Exception:
        groups = []

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        # Always create as agent - no role selection in form
        role = 'agent'
        verified = request.form.get('verified') == 'on'
        phone = request.form.get('phone', '')
        selected_groups = request.form.getlist('groups')  # Get selected group IDs
        queue_only = request.form.get('queue_only') == '1'  # Queue for later

        if not name or not email:
            flash('Name and email are required', 'error')
            return render_template('user_create.html', current_user=current_user, groups=groups,
                                 pending_count=_get_pending_count())

        # If queue only, save to pending operations
        if queue_only:
            operation_data = {
                'name': name,
                'email': email,
                'verified': verified,
                'group_ids': [int(gid) for gid in selected_groups] if selected_groups else []
            }
            operation_id = db.queue_operation(
                operation_type='create_user',
                operation_data=operation_data,
                created_by='web'
            )
            flash(f'Agent creation queued (Operation #{operation_id}). Go to Pending to execute.', 'success')
            return redirect(url_for('web.pending'))

        # Immediate creation
        try:
            user = zendesk_service.create_user(
                name=name,
                email=email,
                role=role,
                verified=verified,
                phone=phone if phone else None
            )

            # Add user to selected groups
            if selected_groups:
                try:
                    group_ids = [int(gid) for gid in selected_groups]
                    zendesk_service.set_user_groups(user['id'], group_ids)
                    flash(f'Agent {user["name"]} created and added to {len(group_ids)} group(s)', 'success')
                except Exception as e:
                    flash(f'Agent created but failed to assign groups: {str(e)}', 'warning')
            else:
                flash(f'Agent {user["name"]} created successfully', 'success')

            return redirect(url_for('web.view_user', user_id=user['id']))

        except Exception as e:
            flash(f'Error creating agent: {str(e)}', 'error')
            return render_template('user_create.html', current_user=current_user, groups=groups,
                                 pending_count=_get_pending_count())

    return render_template('user_create.html', current_user=current_user, groups=groups,
                          pending_count=_get_pending_count())

@web_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Edit an existing Zendesk user"""
    try:
        user = zendesk_service.get_user(user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('web.index'))

        if request.method == 'POST':
            updates = {}

            # Collect form fields
            if request.form.get('name'):
                updates['name'] = request.form.get('name')
            if request.form.get('email'):
                updates['email'] = request.form.get('email')
            if request.form.get('role'):
                updates['role'] = request.form.get('role')
            if request.form.get('phone'):
                updates['phone'] = request.form.get('phone')

            # Update verified status
            updates['verified'] = request.form.get('verified') == 'on'

            # Update the user
            updated_user = zendesk_service.update_user(user_id, **updates)
            flash(f'User {updated_user["name"]} updated successfully', 'success')
            return redirect(url_for('web.view_user', user_id=user_id))

        return render_template('user_edit.html', user=user, current_user=current_user,
                             pending_count=_get_pending_count())

    except Exception as e:
        flash(f'Error updating user: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/user/<int:user_id>/suspend', methods=['POST'])
@login_required
def suspend_user(user_id):
    """Suspend a user"""
    try:
        zendesk_service.suspend_user(user_id)
        flash('User suspended successfully', 'success')
    except Exception as e:
        flash(f'Error suspending user: {str(e)}', 'error')

    return redirect(url_for('web.view_user', user_id=user_id))

@web_bp.route('/user/<int:user_id>/unsuspend', methods=['POST'])
@login_required
def unsuspend_user(user_id):
    """Unsuspend a user"""
    try:
        zendesk_service.unsuspend_user(user_id)
        flash('User unsuspended successfully', 'success')
    except Exception as e:
        flash(f'Error unsuspending user: {str(e)}', 'error')

    return redirect(url_for('web.view_user', user_id=user_id))

@web_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user"""
    try:
        zendesk_service.delete_user(user_id)
        flash('User deleted successfully', 'success')
        return redirect(url_for('web.index'))
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
        return redirect(url_for('web.view_user', user_id=user_id))


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

            # For create_user, redirect to the created user
            if operation['operation_type'] == 'create_user' and result.get('user_id'):
                return redirect(url_for('web.view_user', user_id=result['user_id']))

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
        try:
            # Enforce agent role
            user = zendesk_service.create_user(
                name=op_data['name'],
                email=op_data['email'],
                role='agent',
                verified=op_data.get('verified', False)
            )

            # Add to groups if specified
            group_memberships = []
            if op_data.get('group_ids'):
                try:
                    memberships = zendesk_service.set_user_groups(user['id'], op_data['group_ids'])
                    group_memberships = memberships
                except Exception as e:
                    pass  # Group assignment is optional

            return {
                'user': user,
                'user_id': user['id'],
                'email': user['email'],
                'group_memberships': group_memberships
            }
        except Exception as e:
            return {'error': str(e)}

    elif op_type == 'suspend_user':
        try:
            result = zendesk_service.suspend_user(op_data['user_id'])
            return {'suspended': True, 'user_id': op_data['user_id'], 'user': result}
        except Exception as e:
            return {'error': str(e)}

    elif op_type == 'unsuspend_user':
        try:
            result = zendesk_service.unsuspend_user(op_data['user_id'])
            return {'unsuspended': True, 'user_id': op_data['user_id'], 'user': result}
        except Exception as e:
            return {'error': str(e)}

    elif op_type == 'delete_user':
        try:
            zendesk_service.delete_user(op_data['user_id'])
            return {'deleted': True, 'user_id': op_data['user_id']}
        except Exception as e:
            return {'error': str(e)}

    else:
        return {'error': f'Unknown operation type: {op_type}'}
