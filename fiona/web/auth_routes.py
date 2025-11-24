"""
Authentication routes for Fiona
Handles Google OAuth login with staff verification via Peter
"""

from flask import Blueprint, redirect, url_for, session, render_template_string
from flask_login import login_user, logout_user, current_user
from services.auth import oauth, User, is_staff_member
from config import config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login')
def login():
    """Redirect to Google OAuth login"""
    if current_user.is_authenticated:
        return redirect(url_for('web.index'))

    # Get the OAuth redirect URI
    # Use prompt='select_account' to force account selection even if already logged into Google
    redirect_uri = url_for('auth.callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')


@auth_bp.route('/auth/callback')
def callback():
    """Handle OAuth callback from Google"""
    try:
        # Get the OAuth token
        token = oauth.google.authorize_access_token()

        # Get user info from Google
        user_info = token.get('userinfo')

        if not user_info:
            return render_template_string('''
                <html>
                <head><title>Login Failed</title></head>
                <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                    <h1 style="color: #16a085;">Login Failed</h1>
                    <p>Could not retrieve user information from Google.</p>
                    <p><a href="{{ url_for('auth.login') }}" style="color: #16a085;">Try Again</a></p>
                </body>
                </html>
            ''')

        email = user_info.get('email')
        name = user_info.get('name', email)

        # Check if user is staff via Peter
        staff_check = is_staff_member(email)

        if not staff_check.get('approved'):
            # Check if this is a connection error (Peter not running)
            if staff_check.get('error'):
                error = staff_check['error']
                if 'Connection' in error or 'refused' in error or 'Max retries' in error:
                    return render_template_string('''
                        <html>
                        <head><title>Service Unavailable</title></head>
                        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                            <h1 style="color: #e67e22;">Service Temporarily Unavailable</h1>
                            <p>Fiona can't verify your staff status right now because the authentication service (Peter) isn't responding.</p>
                            <p style="margin-top: 20px; color: #666;">Please try again in a few minutes, or contact your administrator if the problem persists.</p>
                            <p style="margin-top: 30px;">
                                <a href="{{ url_for('auth.login') }}" style="color: #16a085; padding: 10px 20px; background: #f0f0f0; border-radius: 5px; text-decoration: none;">Try Again</a>
                            </p>
                        </body>
                        </html>
                    ''')
                else:
                    error_msg = f"Could not verify staff status: {error}"
            else:
                error_msg = "Your email address is not in the staff directory."

            return render_template_string('''
                <html>
                <head><title>Access Denied</title></head>
                <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                    <h1 style="color: #16a085;">Access Denied</h1>
                    <p>{{ error_msg }}</p>
                    <p>Only staff members can access Fiona.</p>
                    <p style="margin-top: 20px; color: #666; font-size: 14px;">
                        Email: {{ email }}
                    </p>
                    <p style="margin-top: 30px;">
                        <a href="{{ url_for('auth.login') }}" style="color: #16a085;">Try a different account</a>
                    </p>
                </body>
                </html>
            ''', email=email, error_msg=error_msg)

        # Use the name from Peter if available (might be more accurate)
        if staff_check.get('name'):
            name = staff_check['name']

        # Create user and log in
        user = User(email, name)
        login_user(user)

        # Store user in session
        session['user'] = {
            'email': email,
            'name': name
        }

        # Redirect to originally requested page or home
        next_url = session.pop('next', None)
        return redirect(next_url or url_for('web.index'))

    except Exception as e:
        return render_template_string('''
            <html>
            <head><title>Login Error</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                <h1 style="color: #16a085;">Login Error</h1>
                <p>An error occurred during login: {{ error }}</p>
                <p><a href="{{ url_for('auth.login') }}" style="color: #16a085;">Try Again</a></p>
            </body>
            </html>
        ''', error=str(e))


@auth_bp.route('/logout')
def logout():
    """Log out the current user"""
    logout_user()
    session.clear()

    return render_template_string('''
        <html>
        <head>
            <title>Logged Out</title>
            <meta http-equiv="refresh" content="2;url={{ url_for('auth.login') }}">
        </head>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
            <h1 style="color: #16a085;">Logged Out</h1>
            <p>You have been successfully logged out.</p>
            <p>Redirecting to login page...</p>
        </body>
        </html>
    ''')
