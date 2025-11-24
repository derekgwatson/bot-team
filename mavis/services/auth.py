"""
Authentication service for Mavis
Uses Google OAuth and verifies staff membership via Peter
"""

import os
import requests
from functools import wraps
from flask import session, redirect, url_for, request
from flask_login import LoginManager, UserMixin, current_user
from authlib.integrations.flask_client import OAuth
from config import config
import logging

logger = logging.getLogger(__name__)

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, email, name):
        self.id = email
        self.email = email
        self.name = name


# Initialize OAuth
oauth = OAuth()


def get_peter_url():
    """Get Peter's URL based on environment"""
    # In dev mode, use localhost
    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        return 'http://localhost:8003'
    # In production, use the production URL
    return 'https://peter.watsonblinds.com.au'


def is_staff_member(email):
    """
    Check if email belongs to an active staff member via Peter API

    Returns:
        dict with 'approved' (bool), 'name' (str if approved), 'email' (str)
    """
    try:
        peter_url = get_peter_url()
        response = requests.get(
            f'{peter_url}/api/is-approved',
            params={'email': email},
            headers={'X-API-Key': config.bot_api_key},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Peter API returned status {response.status_code}: {response.text}")
            return {'approved': False, 'email': email}

    except requests.RequestException as e:
        logger.error(f"Failed to check staff status with Peter: {e}")
        # In case of error, deny access for security
        return {'approved': False, 'email': email, 'error': str(e)}


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

    # Get OAuth credentials
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

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
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    return login_manager


def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
