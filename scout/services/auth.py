"""
Authentication compatibility layer.

The actual auth instance is created in app.py using GatewayAuth,
and these values are injected at runtime for backward compatibility
with routes that import from here.
"""

<<<<<<< HEAD
# These get overwritten at runtime by app.py
auth = None
login_required = None
admin_required = None
get_current_user = None

=======
import os
import logging
from flask import Flask, session, redirect, url_for, request
from flask_login import LoginManager, current_user
from authlib.integrations.flask_client import OAuth

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required
from shared.auth.email_check import is_email_allowed_by_domain

logger = logging.getLogger(__name__)

login_manager = LoginManager()
oauth = OAuth()


@login_manager.user_loader
def load_user(user_id: str) -> User:
    """Load user from session"""
    if 'user' in session:
        user_data = session['user']
        return User(
            email=user_data['email'],
            name=user_data.get('name'),
            picture=user_data.get('picture')
        )
    return None


def store_user(user: User):
    """Store user in session for persistence across requests"""
    session['user'] = {
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'picture': user.picture
    }


def is_email_allowed(email: str) -> bool:
    """Check if email is in allowed domains"""
    allowed_domains = os.environ.get('ALLOWED_DOMAINS', '').split(',')
    allowed_domains = [d.strip().lower() for d in allowed_domains if d.strip()]

    if not allowed_domains:
        # No domain restrictions
        return True

    return is_email_allowed_by_domain(email, allowed_domains)


def init_auth(app: Flask):
    """Initialize authentication for the Flask app"""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    oauth.init_app(app)

    # Register Google OAuth
    google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
    google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

    if google_client_id and google_client_secret:
        oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        logger.info("Google OAuth configured")
    else:
        logger.warning("Google OAuth not configured - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET required")
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo
