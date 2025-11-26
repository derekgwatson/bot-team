"""
Shared authentication module for bot-team.

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
]
