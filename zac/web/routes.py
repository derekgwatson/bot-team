from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user
from services.zendesk import zendesk_service
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')

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
                             user=current_user)

    except Exception as e:
        return render_template('index.html',
                             error=str(e),
                             users=[],
                             page=1,
                             total_pages=1,
                             total=0,
                             user=current_user)

@web_bp.route('/user/<int:user_id>')
@login_required
def view_user(user_id):
    """View detailed information about a specific user"""
    try:
        user = zendesk_service.get_user(user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('web.index'))

        return render_template('user_detail.html', user=user, current_user=current_user)

    except Exception as e:
        flash(f'Error loading user: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/user/create', methods=['GET', 'POST'])
@login_required
def create_user():
    """Create a new Zendesk user"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            role = request.form.get('role', 'end-user')
            verified = request.form.get('verified') == 'on'
            phone = request.form.get('phone', '')

            if not name or not email:
                flash('Name and email are required', 'error')
                return render_template('user_create.html', current_user=current_user)

            user = zendesk_service.create_user(
                name=name,
                email=email,
                role=role,
                verified=verified,
                phone=phone if phone else None
            )

            flash(f'User {user["name"]} created successfully', 'success')
            return redirect(url_for('web.view_user', user_id=user['id']))

        except Exception as e:
            flash(f'Error creating user: {str(e)}', 'error')
            return render_template('user_create.html', current_user=current_user)

    return render_template('user_create.html', current_user=current_user)

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

        return render_template('user_edit.html', user=user, current_user=current_user)

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
