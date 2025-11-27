"""
Shared authentication module for bot-team.

<<<<<<< HEAD
This module provides centralized authentication through Chester's gateway.

Usage:
    # For bots using Chester's auth gateway:
    from shared.auth import GatewayAuth
    auth = GatewayAuth(app, config)

    # For token operations (used by Chester internally):
    from shared.auth.tokens import create_auth_token, verify_auth_token
"""
from shared.auth.gateway_auth import GatewayAuth
from shared.auth.tokens import create_auth_token, verify_auth_token

__all__ = [
    'GatewayAuth',
    'create_auth_token',
    'verify_auth_token',
=======
This module provides common authentication components used across bots:
- User class for Flask-Login
- Decorators (login_required, admin_required)
- Email authorization checks
- API key authentication (bot-to-bot)
"""

# User class
from shared.auth.user import User

# Decorators
from shared.auth.decorators import login_required, admin_required

# Email checks
from shared.auth.email_check import (
    is_email_allowed,
    is_email_allowed_by_domain,
    is_email_allowed_by_list,
    is_admin_user,
)

# API authentication (existing)
from shared.auth.bot_api import api_key_required, api_or_session_auth

__all__ = [
    # User
    'User',
    # Decorators
    'login_required',
    'admin_required',
    # Email checks
    'is_email_allowed',
    'is_email_allowed_by_domain',
    'is_email_allowed_by_list',
    'is_admin_user',
    # API auth
    'api_key_required',
    'api_or_session_auth',
>>>>>>> claude/bot-health-checker-0177PC3W9xfEUfnoYhkY3Foo
]
