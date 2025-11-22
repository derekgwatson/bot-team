from flask import Blueprint, redirect, url_for, session, render_template_string, make_response, current_app
from flask_login import login_user, logout_user, current_user
from services.auth import oauth, User, is_email_allowed

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
                    <h1>❌ Login Failed</h1>
                    <p>Could not retrieve user information from Google.</p>
                    <p><a href="{{ url_for('auth.login') }}">Try Again</a></p>
                </body>
                </html>
            ''')

        email = user_info.get('email')
        name = user_info.get('name', email)

        # Check if email is allowed
        if not is_email_allowed(email):
            return render_template_string('''
                <html>
                <head><title>Access Denied</title></head>
                <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                    <h1>🚫 Access Denied</h1>
                    <p>Your email address ({{ email }}) is not authorized to access Peter.</p>
                    <p>Contact the administrator to request access.</p>
                </body>
                </html>
            ''', email=email)

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
                <h1>❌ Login Error</h1>
                <p>An error occurred during login: {{ error }}</p>
                <p><a href="{{ url_for('auth.login') }}">Try Again</a></p>
            </body>
            </html>
        ''', error=str(e))

@auth_bp.route('/logout')
def logout():
    """Log out the current user"""
    # Clear Flask-Login's current user
    logout_user()

    # Clear all session data - this removes the 'user' key that load_user checks
    session.clear()

    # Create the response
    response = make_response(render_template_string('''
        <html>
        <head>
            <title>Logged Out</title>
        </head>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
            <h1>👋 Logged Out</h1>
            <p>You have been successfully logged out.</p>
            <p><a href="{{ url_for('auth.login') }}" style="display: inline-block; margin-top: 20px; padding: 10px 20px; background: #2a5298; color: white; text-decoration: none; border-radius: 5px;">Log In Again</a></p>
        </body>
        </html>
    '''))

    # Explicitly delete the session cookie to ensure logout
    # Use the app's configured session cookie name (defaults to 'session')
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    response.delete_cookie(session_cookie_name)

    return response
