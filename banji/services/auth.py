"""
Authentication compatibility layer.

The actual auth instance is created in app.py using GatewayAuth,
and these values are injected at runtime for backward compatibility
with routes that import from here.
"""

# These get overwritten at runtime by app.py
auth = None
login_required = None
admin_required = None
get_current_user = None