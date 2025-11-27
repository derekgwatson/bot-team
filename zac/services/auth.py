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
"""Authentication service for Zac."""
from flask import session
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from config import config

# Import from shared auth module
from shared.auth import User
from shared.auth.decorators import login_required
from shared.auth.email_check import is_email_allowed_by_list

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

    # Configure OAuth
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    return login_manager


def is_email_allowed(email):
    """Check if email is in the admin list (admin-only access)."""
    return is_email_allowed_by_list(email, config.admin_emails)
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo
