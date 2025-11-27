import os
from functools import wraps
from flask import request, jsonify
from flask_login import current_user

BOT_API_KEY = os.getenv("BOT_API_KEY", "")


def api_key_required(view_func):
    """
    Decorator for internal bot-to-bot endpoints.

    - Expects X-API-Key header.
    - 401 if missing.
    - 403 if present but wrong.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        header_key = request.headers.get("X-API-Key")

        if not BOT_API_KEY:
            # Misconfigured service – fail closed so you notice
            return jsonify({"error": "BOT_API_KEY not configured"}), 500

        if not header_key:
            return jsonify({"error": "Missing API key"}), 401

        if header_key != BOT_API_KEY:
            return jsonify({"error": "Invalid API key"}), 403

        return view_func(*args, **kwargs)

    return wrapper


def api_or_session_auth(view_func):
    """
    Decorator that allows either API key auth OR session auth.

    Use this for endpoints that should be accessible both:
    - By other bots via API key (X-API-Key header)
    - By the web UI via session auth (logged in user)

    Returns JSON errors for failed auth.

    Example:
        @app.route('/api/quotes/refresh-pricing', methods=['POST'])
        @api_or_session_auth
        def refresh_pricing():
            # Can be called by other bots OR from the web UI
            ...
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        header_key = request.headers.get("X-API-Key")

        if header_key:
            # API key provided - validate it
            if not BOT_API_KEY:
                return jsonify({"error": "BOT_API_KEY not configured"}), 500
            if header_key != BOT_API_KEY:
                return jsonify({"error": "Invalid API key"}), 403
            return view_func(*args, **kwargs)

        # No API key - check for session auth
        if current_user.is_authenticated:
            return view_func(*args, **kwargs)

        # Neither auth method worked
        return jsonify({"error": "Authentication required"}), 401

    return wrapper
