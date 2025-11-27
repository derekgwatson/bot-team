<<<<<<< HEAD
"""
Authentication compatibility layer.

The actual auth instance is created in app.py using GatewayAuth,
and these values are injected at runtime for backward compatibility
with routes that import from here.
"""

# These get overwritten at runtime by app.py
auth = None
login_required = None
admin_required = None
get_current_user = None

=======
"""Authentication service for Skye."""
import os
from flask import session
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from config import config

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required, admin_required
from shared.auth.email_check import is_email_allowed_by_domain

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
            return User(
                email=user_data['email'],
                name=user_data['name'],
                admin_emails=config.admin_emails
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
    """Check if email is allowed to access Skye (company domain only)."""
    return is_email_allowed_by_domain(email, config.allowed_domains)
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo
