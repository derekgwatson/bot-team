from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.google_workspace import workspace_service

web_bp = Blueprint('web', __name__, template_folder='templates')

@web_bp.route('/')
def index():
    """Home page showing active users"""
    users = workspace_service.list_users(archived=False)

    if isinstance(users, dict) and 'error' in users:
        error = users['error']
        users = []
    else:
        error = None

    return render_template('index.html', users=users, error=error, archived=False)

@web_bp.route('/archived')
def archived():
    """Page showing archived users"""
    users = workspace_service.list_users(archived=True)

    if isinstance(users, dict) and 'error' in users:
        error = users['error']
        users = []
    else:
        error = None

    return render_template('index.html', users=users, error=error, archived=True)

@web_bp.route('/users/<email>')
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
def new_user():
    """Create new user form"""
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')

        result = workspace_service.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )

        if isinstance(result, dict) and 'error' in result:
            return render_template('new_user.html', error=result['error'])

        return redirect(url_for('web.index'))

    return render_template('new_user.html')

@web_bp.route('/users/<email>/archive', methods=['POST'])
def archive_user_action(email):
    """Archive user action"""
    result = workspace_service.archive_user(email)

    if isinstance(result, dict) and 'error' in result:
        # In a real app, you'd want flash messages
        pass

    return redirect(url_for('web.index'))
