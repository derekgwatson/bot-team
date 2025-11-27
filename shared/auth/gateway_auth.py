"""
Shared authentication module for bots using Chester's auth gateway.

This module provides a simple way for bots to authenticate users
through Chester's centralized OAuth gateway.

Usage:
    from shared.auth.gateway_auth import GatewayAuth

    auth = GatewayAuth(app, config)

    # In your routes:
    @app.route('/admin')
    @auth.login_required
    def admin():
        user = auth.get_current_user()
        ...

    @app.route('/admin/settings')
    @auth.admin_required
    def admin_settings():
        ...

    # Routes can also use flask_login's current_user:
    from flask_login import current_user
    @app.route('/profile')
    @auth.login_required
    def profile():
        return f"Hello {current_user.email}"

Config options (in config.yaml):
    auth:
      mode: domain           # 'domain', 'admin_only', or 'tiered'
      allowed_domains:       # Optional - defaults to shared/config/organization.yaml
        - example.com
      admin_emails:          # Optional for 'domain', required for 'admin_only'
        - admin@example.com
      chester_url: http://localhost:8008  # Chester's URL for auth gateway

If allowed_domains is not specified, domains are loaded from shared/config/organization.yaml
(the organization-wide domain list). Most bots should NOT specify allowed_domains and just
use the shared organization config.
"""
import os
from functools import wraps
from pathlib import Path
import yaml
from flask import session, redirect, url_for, request, Blueprint, render_template_string
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from shared.auth.tokens import verify_auth_token
from shared.config.ports import get_port


def _load_organization_domains() -> list:
    """
    Load allowed domains from shared/config/organization.yaml.

    Returns:
        List of domain strings, or empty list if file not found
    """
    try:
        org_config_path = Path(__file__).parent.parent / "config" / "organization.yaml"
        with open(org_config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        return data.get("organization", {}).get("domains", [])
    except Exception:
        return []


class User(UserMixin):
    """User model for flask_login integration"""

    def __init__(self, email, name, picture='', is_admin=False):
        self.id = email
        self.email = email
        self.name = name
        self.picture = picture
        self._is_admin = is_admin

    def is_admin(self):
        """Check if user is an admin"""
        return self._is_admin


class GatewayAuth:
    """
    Authentication handler using Chester's auth gateway.

    Bots redirect users to Chester for OAuth, then receive
    a signed JWT token with the authenticated user info.
    """

    def __init__(self, app, config):
        """
        Initialize gateway authentication

        Args:
            app: Flask app instance
            config: Bot configuration object with auth settings
        """
        self.app = app
        self.config = config

        # Get auth config
        auth_config = getattr(config, 'auth', {}) or {}

        # Auth mode: 'domain', 'admin_only', or 'tiered'
        self.mode = auth_config.get('mode', 'domain')

        # Allowed domains (for domain and tiered modes)
        # Falls back to organization.yaml if not specified in bot config
        self.allowed_domains = auth_config.get('allowed_domains', [])
        if not self.allowed_domains:
            self.allowed_domains = _load_organization_domains()

        # Admin emails (for admin_only and tiered modes)
        self.admin_emails = [e.lower() for e in auth_config.get('admin_emails', [])]

        # Chester URL for auth gateway
        chester_port = get_port('chester')
        default_chester_url = f"http://localhost:{chester_port}"
        self.chester_url = auth_config.get('chester_url', os.environ.get('CHESTER_URL', default_chester_url))

        # Set up Flask session
        if not self.app.config.get('SECRET_KEY'):
            secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')
            self.app.config['SECRET_KEY'] = secret_key

        # Initialize Flask-Login for current_user support
        self.login_manager = LoginManager()
        self.login_manager.init_app(app)
        self.login_manager.login_view = 'gateway_auth.login'

        # Store reference to self for user_loader closure
        gateway_auth = self

        @self.login_manager.user_loader
        def load_user(user_id):
            """Load user from session"""
            if 'user' in session:
                user_data = session['user']
                return User(
                    email=user_data['email'],
                    name=user_data.get('name', ''),
                    picture=user_data.get('picture', ''),
                    is_admin=user_data.get('is_admin', False)
                )
            return None

        # Register auth routes
        self._register_routes()

    def _register_routes(self):
        """Register authentication routes"""
        auth_bp = Blueprint('gateway_auth', __name__)

        @auth_bp.route('/login')
        def login():
            """Redirect to Chester's auth gateway"""
            # Build the return URL for Chester to redirect back to
            callback_url = url_for('gateway_auth.callback', _external=True)
            gateway_url = f"{self.chester_url}/auth/gateway?return_url={callback_url}"
            return redirect(gateway_url)

        @auth_bp.route('/auth/callback')
        def callback():
            """Handle callback from Chester's auth gateway"""
            # Check for error
            error = request.args.get('error')
            if error:
                return render_template_string('''
                    <html>
                    <head><title>Login Failed</title></head>
                    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                        <h1>Login Failed</h1>
                        <p>Authentication failed: {{ error }}</p>
                        <p><a href="{{ url_for('gateway_auth.login') }}">Try Again</a></p>
                    </body>
                    </html>
                ''', error=error)

            # Get and verify token
            token = request.args.get('token')
            if not token:
                return render_template_string('''
                    <html>
                    <head><title>Login Failed</title></head>
                    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                        <h1>Login Failed</h1>
                        <p>No authentication token received.</p>
                        <p><a href="{{ url_for('gateway_auth.login') }}">Try Again</a></p>
                    </body>
                    </html>
                ''')

            user_info = verify_auth_token(token)
            if not user_info:
                return render_template_string('''
                    <html>
                    <head><title>Login Failed</title></head>
                    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                        <h1>Login Failed</h1>
                        <p>Invalid or expired authentication token.</p>
                        <p><a href="{{ url_for('gateway_auth.login') }}">Try Again</a></p>
                    </body>
                    </html>
                ''')

            # Check authorization based on bot's config
            email = user_info['email'].lower()

            if not self._is_authorized(email):
                return render_template_string('''
                    <html>
                    <head><title>Access Denied</title></head>
                    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                        <h1>Access Denied</h1>
                        <p>Your email address ({{ email }}) is not authorized to access this application.</p>
                    </body>
                    </html>
                ''', email=email)

            # Store user in session
            session['user'] = {
                'email': user_info['email'],
                'name': user_info.get('name', ''),
                'picture': user_info.get('picture', ''),
                'is_admin': self._is_admin(email),
            }

            # Create User object and log in with flask_login
            user = User(
                email=user_info['email'],
                name=user_info.get('name', ''),
                picture=user_info.get('picture', ''),
                is_admin=self._is_admin(email)
            )
            login_user(user)

            # Redirect to originally requested page or home
            next_url = session.pop('next_url', '/')
            return redirect(next_url)

        @auth_bp.route('/logout')
        def logout():
            """Log out the current user"""
            logout_user()
            session.clear()
            # Use url_for with _external=True to get correct host behind proxies
            # (same mechanism that works for login redirects)
            callback_url = url_for('gateway_auth.callback', _external=True)
            # Extract root URL: https://bot.example.com/auth/callback -> https://bot.example.com/
            root_url = callback_url.rsplit('/auth/callback', 1)[0] + '/'
            return redirect(root_url)

        self.app.register_blueprint(auth_bp)

    def _is_authorized(self, email: str) -> bool:
        """
        Check if email is authorized based on config mode.

        Args:
            email: User's email address (lowercase)

        Returns:
            True if authorized
        """
        email = email.lower()

        if self.mode == 'admin_only':
            # Only admin emails allowed
            return email in self.admin_emails

        elif self.mode == 'domain':
            # Anyone from allowed domains
            for domain in self.allowed_domains:
                if email.endswith(f'@{domain.lower()}'):
                    return True
            return False

        elif self.mode == 'tiered':
            # Domain users get access, admins get extra features
            for domain in self.allowed_domains:
                if email.endswith(f'@{domain.lower()}'):
                    return True
            # Also allow admin emails even if not from allowed domain
            return email in self.admin_emails

        return False

    def _is_admin(self, email: str) -> bool:
        """
        Check if email is an admin.

        Args:
            email: User's email address (lowercase)

        Returns:
            True if admin
        """
        return email.lower() in self.admin_emails

    def get_current_user(self):
        """Get the currently logged in user (flask_login's current_user)"""
        return current_user if current_user.is_authenticated else None

    def is_authenticated(self) -> bool:
        """Check if there's a logged in user"""
        return current_user.is_authenticated

    def is_admin(self) -> bool:
        """Check if current user is an admin"""
        return current_user.is_authenticated and current_user.is_admin()

    def login_required(self, f):
        """
        Decorator to require login for a route.

        Redirects to login if not authenticated.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                session['next_url'] = request.url
                return redirect(url_for('gateway_auth.login'))
            return f(*args, **kwargs)
        return decorated_function

    def admin_required(self, f):
        """
        Decorator to require admin access for a route.

        Redirects to login if not authenticated.
        Returns 403 if authenticated but not admin.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                session['next_url'] = request.url
                return redirect(url_for('gateway_auth.login'))
            if not current_user.is_admin():
                return render_template_string('''
                    <html>
                    <head><title>Access Denied</title></head>
                    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                        <h1>Access Denied</h1>
                        <p>This page requires administrator privileges.</p>
                    </body>
                    </html>
                '''), 403
            return f(*args, **kwargs)
        return decorated_function
