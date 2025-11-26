"""
Shared authentication module for bot-team.

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
]
