"""
Authentication routes for Scout

Google OAuth login/logout routes.
"""

from flask import Blueprint, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user
import logging

from services.auth import oauth, User, store_user, is_email_allowed

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    """Redirect to Google OAuth login"""
    if current_user.is_authenticated:
        return redirect(url_for('web.index'))

    # Check if OAuth is configured
    google = oauth.create_client('google')
    if not google:
        flash('Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.', 'error')
        return redirect(url_for('web.index'))

    redirect_uri = url_for('auth.auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/callback')
def auth_callback():
    """Handle Google OAuth callback"""
    try:
        google = oauth.create_client('google')
        if not google:
            flash('Google OAuth is not configured.', 'error')
            return redirect(url_for('web.index'))

        token = google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            # Fetch user info if not in token
            user_info = google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()

        email = user_info.get('email')

        # Check if email domain is allowed
        if not is_email_allowed(email):
            logger.warning(f"Login denied for email not in allowed domains: {email}")
            flash('Access denied. Your email domain is not authorized.', 'error')
            return redirect(url_for('auth.login'))

        # Create and store user
        user = User.from_google_info(user_info)
        store_user(user)
        login_user(user)

        logger.info(f"User logged in: {email}")
        flash(f'Welcome, {user.name}!', 'success')

        # Redirect to originally requested page or index
        next_page = session.pop('next', None)
        return redirect(next_page or url_for('web.index'))

    except Exception as e:
        logger.exception("Error during OAuth callback")
        flash(f'Authentication error: {str(e)}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    """Log out the current user"""
    if current_user.is_authenticated:
        logger.info(f"User logged out: {current_user.email}")
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
