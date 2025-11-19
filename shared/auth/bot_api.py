import os
from functools import wraps
from flask import request, jsonify

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
