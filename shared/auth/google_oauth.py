"""
Shared Google OAuth authentication for bot-team
"""
from flask import session, redirect, url_for, request
from functools import wraps
from authlib.integrations.flask_client import OAuth
import os


class GoogleAuth:
    """
    Google OAuth authentication handler
    """

    def __init__(self, app, config):
        """
        Initialize Google OAuth

        Args:
            app: Flask app instance
            config: Bot configuration object with oauth settings
        """
        self.app = app
        self.config = config

        # Set up Flask session
        self.app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

        # Initialize OAuth
        self.oauth = OAuth(app)
        self.google = self.oauth.register(
            name='google',
            client_id=config.oauth_client_id,
            client_secret=config.oauth_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    def login_route(self):
        """OAuth login route"""
        redirect_uri = url_for('auth_callback', _external=True)
        return self.google.authorize_redirect(redirect_uri)

    def callback_route(self):
        """OAuth callback route"""
        try:
            token = self.google.authorize_access_token()
            user_info = token.get('userinfo')

            if user_info:
                session['user'] = {
                    'email': user_info['email'],
                    'name': user_info.get('name', ''),
                    'picture': user_info.get('picture', '')
                }

                # Check authorization based on bot's policy
                if not self._is_authorized(user_info['email']):
                    session.clear()
                    return redirect(url_for('access_denied'))

                return redirect(url_for('index'))

            return redirect(url_for('login'))

        except Exception as e:
            print(f"OAuth error: {e}")
            return redirect(url_for('login'))

    def logout_route(self):
        """Logout route"""
        session.clear()
        return redirect(url_for('login'))

    def _is_authorized(self, email):
        """
        Check if user is authorized based on bot's policy

        Args:
            email: User's email address

        Returns:
            Boolean indicating if user is authorized
        """
        # Check for domain-based access (for Pam)
        if hasattr(self.config, 'allowed_domains'):
            for domain in self.config.allowed_domains:
                if email.lower().endswith(f'@{domain}'):
                    return True

        # Check for whitelist access (for admin tools)
        if hasattr(self.config, 'admin_emails'):
            if email.lower() in [e.lower() for e in self.config.admin_emails]:
                return True

        return False

    def require_auth(self, f):
        """
        Decorator to require authentication for a route
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    def get_current_user(self):
        """Get currently logged in user"""
        return session.get('user')
