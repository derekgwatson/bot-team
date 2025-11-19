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
    """Check if email is in the allowed admin list"""
    if not config.admin_emails:
        # If no admin emails configured, deny all access
        return False

    return email in config.admin_emails

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

