# Bot Team Authentication

Shared Google OAuth authentication for all bot-team bots.

## Features

- **Google OAuth 2.0** - Secure authentication via Google accounts
- **Domain-based access** - Auto-grant access to users from specific email domains (for Pam)
- **Whitelist access** - Restrict access to specific email addresses (for admin tools)
- **Session management** - Secure Flask sessions
- **Beautiful login pages** - Customizable per-bot

## Setup Google OAuth

1. **Go to Google Cloud Console**: https://console.cloud.google.com/

2. **Create a new project** (or select existing):
   - Project name: "Bot Team" (or similar)

3. **Enable Google+ API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API"
   - Click "Enable"

4. **Configure OAuth Consent Screen**:
   - Go to "APIs & Services" > "OAuth consent screen"
   - Choose "Internal" (for workspace users only) or "External"
   - Fill in:
     - App name: "Bot Team"
     - User support email: your@watsonblinds.com.au
     - Developer contact: your@watsonblinds.com.au
   - Save and continue through the scopes/test users screens

5. **Create OAuth 2.0 Credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth Client ID"
   - Application type: "Web application"
   - Name: "Bot Team Web Client"
   - Authorized redirect URIs:
     ```
     http://localhost:8001/auth/callback  (Fred)
     http://localhost:8002/auth/callback  (Iris)
     http://localhost:8003/auth/callback  (Peter)
     http://localhost:8004/auth/callback  (Pam)
     https://pam.watsonblinds.com.au/auth/callback
     https://fred.watsonblinds.com.au/auth/callback
     https://peter.watsonblinds.com.au/auth/callback
     https://iris.watsonblinds.com.au/auth/callback
     ```
   - Click "Create"
   - **Save the Client ID and Client Secret**

6. **Add credentials to each bot**:

   Edit each bot's `config.yaml`:

   ```yaml
   auth:
     oauth_client_id: "YOUR_GOOGLE_CLIENT_ID_HERE"
     oauth_client_secret: "YOUR_GOOGLE_CLIENT_SECRET_HERE"
   ```

## Configuration

### Pam (Domain-based access)
Anyone with an email from allowed domains can access:

```yaml
auth:
  oauth_client_id: "..."
  oauth_client_secret: "..."
  allowed_domains:
    - "watsonblinds.com.au"
```

### Admin Tools (Whitelist access)
Only specific emails can access:

```yaml
auth:
  oauth_client_id: "..."
  oauth_client_secret: "..."
  admin_emails:
    - "derek@watsonblinds.com.au"
```

## Usage in Bots

See `pam/app.py` for a complete example.

```python
from shared.auth.google_oauth import GoogleAuth

app = Flask(__name__)
auth = GoogleAuth(app, config)

# Add auth routes
@app.route('/login')
def login():
    return render_template('auth/login.html', ...)

@app.route('/auth/login')
def auth_login():
    return auth.login_route()

@app.route('/auth/callback')
def auth_callback():
    return auth.callback_route()

@app.route('/auth/logout')
def auth_logout():
    return auth.logout_route()

# Protect routes with @require_auth decorator
```

## Security Notes

- OAuth Client Secret should be kept secure
- Consider using environment variables for production
- HTTPS is required for production OAuth (works with localhost for dev)
- Session keys are auto-generated - set `FLASK_SECRET_KEY` env var for production
