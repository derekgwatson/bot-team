"""Authentication service for Doc."""
import os
from functools import wraps
from flask import session, redirect, url_for, request
from flask_login import LoginManager, UserMixin, current_user
from authlib.integrations.flask_client import OAuth
from config import config


class User(UserMixin):
    """User model for Flask-Login."""

    def __init__(self, email, name):
        self.id = email
        self.email = email
        self.name = name
        self._is_admin = None

    @property
    def is_admin(self):
        """Check if user is an admin."""
        if self._is_admin is None:
            self._is_admin = self.email.lower() in [e.lower() for e in config.admin_emails]
        return self._is_admin


# Initialize OAuth
oauth = OAuth()


def init_auth(app):
    """Initialize authentication for the Flask app."""

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        if 'user' in session:
            user_data = session['user']
            return User(user_data['email'], user_data['name'])
        return None

    # Get OAuth credentials
    client_id = os.getenv('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET') or os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

    if not client_id or not client_secret:
        raise ValueError(
            "Missing Google OAuth credentials. Please set:\n"
            "  GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET\n"
            "in your .env file"
        )

    # Configure OAuth
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    return login_manager


def is_email_allowed(email):
    """Check if email is allowed to access Doc (must be from allowed domain)."""
    email = email.lower().strip()

    for domain in config.allowed_domains:
        if email.endswith(f'@{domain}'):
            return True

    return False


def is_admin(email):
    """Check if email is an admin."""
    if not config.admin_emails:
        return False
    return email.lower() in [e.lower() for e in config.admin_emails]


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_admin:
            return "Access denied. Admin privileges required.", 403
        return f(*args, **kwargs)
    return decorated_function
