"""Authentication service for Chester."""
import os
from flask import session
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from config import config

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required
from shared.auth.email_check import is_email_allowed_by_domain
from shared.http_client import BotHttpClient

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
            return User(
                email=user_data['email'],
                name=user_data['name']
            )
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
    """
    Check if email is allowed to access Chester.

    Allows access to:
    1. Anyone from company domains (watsonblinds.com.au, etc.)
    2. External staff approved in Peter's database
    """
    email = email.lower().strip()

    # 1. Check if from company domain
    if is_email_allowed_by_domain(email, config.allowed_domains):
        return True

    # 2. Check if approved in Peter's database (external staff)
    try:
        peter = BotHttpClient(config.peter_api_url, timeout=3)
        response = peter.get('/api/is-approved', params={'email': email})
        if response.status_code == 200:
            data = response.json()
            if data.get('approved'):
                return True
    except Exception as e:
        # If Peter is down, log error but don't crash
        print(f"Warning: Could not reach Peter to check approval: {e}")
        # Fall through to deny access

    return False
