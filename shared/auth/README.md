# Shared Auth Module

This module provides centralized authentication through Chester's OAuth gateway.

## How It Works

1. **Chester** handles all OAuth with Google
2. **Other bots** redirect users to Chester for authentication
3. Chester issues a **JWT token** with the authenticated user info
4. The token is passed back to the requesting bot
5. Each bot validates the token and handles its own **authorization**

## Benefits

- **Single Google redirect URI**: Only Chester needs to be configured in Google Console
- **Simpler setup**: New bots don't need OAuth credentials
- **Centralized auth**: One place to handle Google OAuth
- **Flexible authorization**: Each bot controls its own access rules

## Migrating a Bot to Use Gateway Auth

### 1. Add auth config to config.yaml

```yaml
auth:
  # Mode options:
  #   - admin_only: Only users in admin_emails can access
  #   - domain: Any user from allowed_domains can access
  #   - tiered: Domain users can access, admins get extra features
  mode: admin_only  # or 'domain' or 'tiered'

  # For admin_only and tiered modes:
  admin_emails:
    - admin@example.com

  # For domain and tiered modes:
  allowed_domains:
    - example.com
```

### 2. Load auth config in config.py

```python
class Config:
    def __init__(self):
        # ... existing config loading ...

        # Add this line:
        self.auth = data.get("auth", {}) or {}
```

### 3. Update app.py

Replace the old auth setup:

```python
# OLD:
from services.auth import init_auth
from web.auth_routes import auth_bp
init_auth(app)
app.register_blueprint(auth_bp, url_prefix='/')

# NEW:
from shared.auth import GatewayAuth

# Initialize authentication via Chester's gateway
auth = GatewayAuth(app, config)

# Store auth instance for routes that import from services.auth
import services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user
```

### 4. Update services/auth.py

Replace with a thin compatibility layer:

```python
"""
Authentication compatibility layer.
Values are injected at runtime by app.py
"""
auth = None
login_required = None
admin_required = None
get_current_user = None
```

### 5. Update templates

Change logout links:

```html
<!-- OLD: -->
<a href="{{ url_for('auth.logout') }}">Logout</a>

<!-- NEW: -->
<a href="{{ url_for('gateway_auth.logout') }}">Logout</a>
```

### 6. Delete old auth_routes.py

The GatewayAuth class registers its own `/login`, `/auth/callback`, and `/logout` routes.

## Using flask_login's current_user

Routes can continue to use `current_user` from flask_login:

```python
from flask_login import current_user

@web_bp.route('/profile')
@login_required
def profile():
    return f"Hello {current_user.email}"
```

The User object has these properties:
- `email` - User's email address
- `name` - User's display name
- `picture` - User's profile picture URL
- `is_admin` - Whether user is in admin_emails list (property)

## Auth Modes

### admin_only
Only users whose email is in `admin_emails` can access. Good for IT tools.

### domain
Any user with an email from `allowed_domains` can access. Good for company-wide tools.

### tiered
Domain users get basic access, admins (in `admin_emails`) get extra features.
Use `current_user.is_admin` to check for admin features.
