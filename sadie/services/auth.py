import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from flask_login import LoginManager, UserMixin, current_user
from authlib.integrations.flask_client import OAuth
from config import config

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

    # Configure OAuth
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    return login_manager

def is_email_allowed(email):
    """Check if email is from an allowed domain (all-staff access)"""
    if not config.allowed_domains:
        # If no allowed domains configured, deny all access
        return False

    # Extract domain from email
    if '@' not in email:
        return False

    email_domain = email.split('@')[1].lower()

    # Check if email domain is in allowed domains
    return email_domain in [domain.lower() for domain in config.allowed_domains]

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def api_key_required(f):
    """Decorator to require API key for API routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in header
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'API key required'}), 401

        if api_key != config.bot_api_key:
            return jsonify({'error': 'Invalid API key'}), 403

        return f(*args, **kwargs)
    return decorated_function
