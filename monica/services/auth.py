import os
from functools import wraps
from flask import session, redirect, url_for, request
from flask_login import LoginManager, UserMixin, current_user
from authlib.integrations.flask_client import OAuth

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, email, name):
        self.id = email
        self.email = email
        self.name = name

# Initialize OAuth
oauth = OAuth()

def init_auth(app):
    """Initialize authentication for the Flask app"""

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        # Load user from session
        if 'user' in session:
            user_data = session['user']
            return User(user_data['email'], user_data['name'])
        return None

    # Get OAuth credentials with backward compatibility
    # Support both new (GOOGLE_CLIENT_ID) and old (GOOGLE_OAUTH_CLIENT_ID) variable names
    client_id = os.getenv('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET') or os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

    if not client_id or not client_secret:
        raise ValueError(
            "Missing Google OAuth credentials. Please set either:\n"
            "  GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (new format)\n"
            "  or GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET (old format)\n"
            "in your .env file"
        )

    # Validate ADMIN_EMAILS is configured
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if not admin_emails:
        raise ValueError(
            "Missing ADMIN_EMAILS environment variable.\n"
            "Please set ADMIN_EMAILS with a comma-separated list of authorized email addresses.\n"
            "Example: ADMIN_EMAILS=user1@example.com,user2@example.com"
        )

    # Configure OAuth
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    return login_manager

def is_email_allowed(email):
    """Check if email is in the allowed list"""
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if not admin_emails:
        # If no admin emails configured, deny all access
        return False

    allowed_list = [e.strip() for e in admin_emails.split(',')]
    return email in allowed_list

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
