from flask import Blueprint, redirect, url_for, session, render_template_string, request
from flask_login import login_user, logout_user, current_user
from urllib.parse import urlparse, urlencode
from services.auth import oauth, User, is_email_allowed
from shared.auth.tokens import create_auth_token

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


@auth_bp.route('/auth/gateway')
def gateway():
    """
    Auth gateway for other bots.

    Other bots redirect here instead of handling OAuth themselves.
    Chester handles OAuth, then redirects back to the requesting bot with a signed token.

    Query params:
        return_url: URL to redirect back to after auth (required)

    Example:
        /auth/gateway?return_url=http://localhost:8023/auth/callback

    After successful auth, redirects to:
        http://localhost:8023/auth/callback?token=<JWT>
    """
    return_url = request.args.get('return_url')

    if not return_url:
        return render_template_string('''
            <html>
            <head><title>Auth Gateway Error</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                <h1>Auth Gateway Error</h1>
                <p>Missing return_url parameter.</p>
            </body>
            </html>
        '''), 400

    # Validate return_url is a valid URL
    parsed = urlparse(return_url)
    if not parsed.scheme or not parsed.netloc:
        return render_template_string('''
            <html>
            <head><title>Auth Gateway Error</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                <h1>Auth Gateway Error</h1>
                <p>Invalid return_url parameter.</p>
            </body>
            </html>
        '''), 400

    # Store return_url and mark as gateway flow
    session['gateway_return_url'] = return_url
    session['is_gateway_flow'] = True

    # Redirect to Google OAuth
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
                    <h1>Login Failed</h1>
                    <p>Could not retrieve user information from Google.</p>
                    <p><a href="{{ url_for('auth.login') }}">Try Again</a></p>
                </body>
                </html>
            ''')

        email = user_info.get('email')
        name = user_info.get('name', email)
        picture = user_info.get('picture', '')

        # Check if this is a gateway flow (auth on behalf of another bot)
        is_gateway = session.pop('is_gateway_flow', False)
        gateway_return_url = session.pop('gateway_return_url', None)

        if is_gateway and gateway_return_url:
            # Gateway flow: don't check Chester's authorization rules,
            # let the receiving bot handle its own authorization.
            # Just issue a token with the authenticated user info.

            auth_token = create_auth_token({
                'email': email,
                'name': name,
                'picture': picture,
            })

            # Redirect back to the requesting bot with the token
            separator = '&' if '?' in gateway_return_url else '?'
            return redirect(f"{gateway_return_url}{separator}token={auth_token}")

        # Normal Chester login flow - check if email is allowed
        if not is_email_allowed(email):
            return render_template_string('''
                <html>
                <head><title>Access Denied</title></head>
                <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                    <h1>Access Denied</h1>
                    <p>Your email address ({{ email }}) is not authorized to access Chester.</p>
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
        # Check if this was a gateway flow to provide better error message
        is_gateway = session.pop('is_gateway_flow', False)
        gateway_return_url = session.pop('gateway_return_url', None)

        if is_gateway and gateway_return_url:
            # Redirect back to the bot with an error
            separator = '&' if '?' in gateway_return_url else '?'
            return redirect(f"{gateway_return_url}{separator}error=auth_failed")

        return render_template_string('''
            <html>
            <head><title>Login Error</title></head>
            <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; text-align: center;">
                <h1>Login Error</h1>
                <p>An error occurred during login: {{ error }}</p>
                <p><a href="{{ url_for('auth.login') }}">Try Again</a></p>
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
            <h1>Logged Out</h1>
            <p>You have been successfully logged out.</p>
            <p>Redirecting to login page...</p>
        </body>
        </html>
    ''')
