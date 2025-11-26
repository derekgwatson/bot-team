"""
Shared authentication decorators for Flask routes.
"""
from functools import wraps
from flask import redirect, url_for, request
from flask_login import current_user


def login_required(f):
    """
    Decorator to require login for a route.

    Redirects to auth.login with next parameter if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin login for a route.

    Checks both authentication and admin status.
    Returns 403 if authenticated but not admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not getattr(current_user, 'is_admin', False):
            return "Access denied. Admin privileges required.", 403
        return f(*args, **kwargs)
    return decorated_function
