from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.google_workspace import workspace_service
from services.auth import login_required
from config import config
import time

web_bp = Blueprint('web', __name__, template_folder='templates')

# How long to hide recently deleted/archived users (in seconds)
# Google API eventual consistency usually resolves within 30 seconds
HIDE_DELETED_DURATION = 60


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

    return render_template('index.html', users=users, error=error, archived=False)

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

    return render_template('index.html', users=users, error=error, archived=True)

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

    return render_template('user_detail.html', user=user, error=error)

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

        # Validate email domain
        if '@' not in email:
            return render_template('new_user.html', error='Invalid email address', allowed_domains=allowed_domains)

        email_domain = email.split('@')[1].lower()
        allowed_domains_lower = [d.lower() for d in allowed_domains]
        if email_domain not in allowed_domains_lower:
            return render_template('new_user.html', error=f'Email must use one of these domains: {", ".join(allowed_domains)}', allowed_domains=allowed_domains)

        result = workspace_service.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            change_password_at_next_login=change_password
        )

        if isinstance(result, dict) and 'error' in result:
            return render_template('new_user.html', error=result['error'], allowed_domains=allowed_domains)

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
                             backup_codes=backup_codes)

    return render_template('new_user.html', allowed_domains=allowed_domains)

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
