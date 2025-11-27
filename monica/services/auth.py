<<<<<<< HEAD
"""
Authentication compatibility layer.

The actual auth instance is created in app.py using GatewayAuth,
and these values are injected at runtime for backward compatibility
with routes that import from here.
"""
=======
"""Authentication service for Monica."""
import os
from flask import session
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required
from shared.auth.email_check import is_email_allowed_by_list
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo

# These get overwritten at runtime by app.py
auth = None
login_required = None
admin_required = None
get_current_user = None

<<<<<<< HEAD
=======

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

    # Validate ADMIN_EMAILS is configured
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if not admin_emails:
        raise ValueError(
            "Missing ADMIN_EMAILS environment variable.\n"
            "Please set ADMIN_EMAILS with a comma-separated list of authorized email addresses.\n"
            "Example: ADMIN_EMAILS=user1@example.com,user2@example.com"
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
    """Check if email is in the admin list (admin-only access)."""
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if not admin_emails:
        return False
    allowed_list = [e.strip() for e in admin_emails.split(',')]
    return is_email_allowed_by_list(email, allowed_list)
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo
