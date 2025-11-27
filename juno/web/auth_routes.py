"""Authentication routes for Juno."""
from flask import Blueprint, redirect, url_for, session, request
from flask_login import login_user, logout_user, current_user
from juno.config import config
from juno.services.auth import oauth, User, is_email_allowed

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    """Initiate Google OAuth login."""
    if current_user.is_authenticated:
        return redirect(url_for('web.admin_index'))

    # Get the callback URL
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')


@auth_bp.route('/auth/callback')
def callback():
    """Handle Google OAuth callback."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            return '''
                <h1>Authentication Failed</h1>
                <p>Could not get user information from Google.</p>
                <a href="/">Try Again</a>
            ''', 401

        email = user_info.get('email', '').lower()
        name = user_info.get('name', email)

        # Check if email is allowed
        if not is_email_allowed(email):
            return f'''
                <html>
                <head><title>Access Denied - Juno</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>Access Denied</h1>
                    <p>Sorry, <strong>{email}</strong> is not authorized to access Juno admin.</p>
                    <p>Only Watson Blinds staff can access the admin area.</p>
                    <a href="{url_for('auth.login')}" style="color: #16a085;">Try with a different account</a>
                </body>
                </html>
            ''', 403

        # Create user and log in
        user = User(email=email, name=name, admin_emails=config.admin_emails)
        session['user'] = {'email': email, 'name': name}
        login_user(user)

        # Redirect to original destination or admin
        next_url = request.args.get('next') or url_for('web.admin_index')
        return redirect(next_url)

    except Exception as e:
        return f'''
            <h1>Authentication Error</h1>
            <p>An error occurred during authentication: {str(e)}</p>
            <a href="/">Try Again</a>
        ''', 500


@auth_bp.route('/logout')
def logout():
    """Log out the current user."""
    session.pop('user', None)
    logout_user()
    return redirect(url_for('web.index'))
