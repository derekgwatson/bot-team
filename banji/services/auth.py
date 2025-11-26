"""
Authentication compatibility layer.

The actual auth instance is created in app.py using GatewayAuth,
and these values are injected at runtime for backward compatibility
with routes that import from here.
"""
import os
from functools import wraps
from flask import request, jsonify
from flask_login import current_user

# These get overwritten at runtime by app.py
auth = None
login_required = None
admin_required = None
get_current_user = None


def api_or_session_auth(f):
    """
    Decorator that allows either API key auth OR session auth.

    Use this for endpoints that should be accessible both:
    - By other bots via API key (X-API-Key header)
    - By the web UI via session auth (logged in user)
    """
    BOT_API_KEY = os.getenv("BOT_API_KEY", "")

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key first
        header_key = request.headers.get("X-API-Key")

        if header_key:
            # API key provided - validate it
            if not BOT_API_KEY:
                return jsonify({"error": "BOT_API_KEY not configured"}), 500
            if header_key != BOT_API_KEY:
                return jsonify({"error": "Invalid API key"}), 401
            # API key valid - proceed
            return f(*args, **kwargs)

        # No API key - check session auth
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        # Neither auth method worked
        return jsonify({"error": "Authentication required"}), 401

    return decorated_function