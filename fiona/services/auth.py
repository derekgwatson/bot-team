"""
Authentication service for Fiona
Uses Google OAuth and verifies staff membership via Peter
Supports admin-only access for editing features
"""

import os
import requests
import logging
from flask import session, render_template_string
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from config import config

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required, admin_required
from shared.auth.email_check import is_admin_user

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
        return {'approved': False, 'email': email, 'error': str(e)}


def is_admin(email: str) -> bool:
    """Check if email is in the admin list"""
    return is_admin_user(email, config.admin_emails or [])


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
                name=user_data['name'],
                admin_emails=config.admin_emails
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
