"""
JWT token handling for auth gateway
Uses BOT_API_KEY as the shared secret for signing tokens
"""
import os
import time
from typing import Optional, Dict, Any


def get_secret_key() -> str:
    """Get the secret key for JWT signing"""
    key = os.environ.get('BOT_API_KEY')
    if not key:
        raise ValueError("BOT_API_KEY environment variable must be set for auth tokens")
    return key


def create_auth_token(user_info: Dict[str, Any], expires_in: int = 300) -> str:
    """
    Create a signed JWT token with user info

    Args:
        user_info: Dict with 'email' and 'name'
        expires_in: Token expiry in seconds (default 5 minutes - short since it's one-time use)

    Returns:
        Signed JWT token string
    """
    import jwt

    payload = {
        'email': user_info['email'],
        'name': user_info.get('name', ''),
        'picture': user_info.get('picture', ''),
        'exp': int(time.time()) + expires_in,
        'iat': int(time.time()),
    }

    return jwt.encode(payload, get_secret_key(), algorithm='HS256')


def verify_auth_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a JWT token and extract user info

    Args:
        token: JWT token string

    Returns:
        Dict with user info if valid, None if invalid/expired
    """
    import jwt

    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=['HS256'])
        return {
            'email': payload['email'],
            'name': payload.get('name', ''),
            'picture': payload.get('picture', ''),
        }
    except jwt.ExpiredSignatureError:
        print("Auth token expired")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid auth token: {e}")
        return None
