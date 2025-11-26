"""
Authentication service for Mavis
Uses Google OAuth and verifies staff membership via Peter
"""

import os
import requests
import logging
from flask import session
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from config import config
from shared.http_client import BotHttpClient

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required

logger = logging.getLogger(__name__)

# Initialize OAuth
oauth = OAuth()


def get_peter_url():
    """Get Peter's URL based on environment"""
    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        return 'http://localhost:8003'
    return 'https://peter.watsonblinds.com.au'


def is_staff_member(email):
    """
    Check if email belongs to an active staff member via Peter API

    Returns:
        dict with 'approved' (bool), 'name' (str if approved), 'email' (str)
    """
    try:
        peter = BotHttpClient(get_peter_url(), timeout=10)
        response = peter.get('/api/is-approved', params={'email': email})

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Peter API returned status {response.status_code}: {response.text}")
            return {'approved': False, 'email': email}

    except requests.RequestException as e:
        logger.error(f"Failed to check staff status with Peter: {e}")
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
            return User(
                email=user_data['email'],
                name=user_data['name']
            )
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
        client_kwargs={'scope': 'openid email profile'}
    )

    return login_manager
