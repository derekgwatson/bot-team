"""
Authentication service for Scout

Google OAuth integration for web UI.
Based on shared authentication patterns.
"""

import os
import logging
from flask import Flask
from flask_login import LoginManager, UserMixin
from authlib.integrations.flask_client import OAuth

logger = logging.getLogger(__name__)

login_manager = LoginManager()
oauth = OAuth()


class User(UserMixin):
    """User model for Flask-Login"""

    def __init__(self, user_id: str, email: str, name: str = None, picture: str = None):
        self.id = user_id
        self.email = email
        self.name = name or email
        self.picture = picture

    @staticmethod
    def from_google_info(user_info: dict) -> 'User':
        """Create a User from Google OAuth user info"""
        return User(
            user_id=user_info.get('sub'),
            email=user_info.get('email'),
            name=user_info.get('name'),
            picture=user_info.get('picture')
        )


# In-memory user store (users are only stored during session)
_users = {}


@login_manager.user_loader
def load_user(user_id: str) -> User:
    """Load user by ID from in-memory store"""
    return _users.get(user_id)


def store_user(user: User):
    """Store user in memory"""
    _users[user.id] = user


def is_email_allowed(email: str) -> bool:
    """Check if email is in allowed domains"""
    allowed_domains = os.environ.get('ALLOWED_DOMAINS', '').split(',')
    allowed_domains = [d.strip().lower() for d in allowed_domains if d.strip()]

    if not allowed_domains:
        # No domain restrictions
        return True

    domain = email.split('@')[-1].lower()
    return domain in allowed_domains


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
            client_kwargs={
                'scope': 'openid email profile'
            }
        )
        logger.info("Google OAuth configured")
    else:
        logger.warning("Google OAuth not configured - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET required")


def login_required(f):
    """
    Decorator that requires login for a route.
    Uses Flask-Login's login_required internally.
    """
    from flask_login import login_required as flask_login_required
    return flask_login_required(f)
