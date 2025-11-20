# Google OAuth Setup for Dorothy

Dorothy uses Google OAuth to ensure only authorized users can access the deployment interface.

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. If prompted, configure the OAuth consent screen:
   - User Type: **External** (or Internal if you have a Google Workspace)
   - App name: **Dorothy Deployment Tool**
   - User support email: your email
   - Developer contact: your email
   - Scopes: No additional scopes needed (just openid, email, profile)
   - Test users: Add your email address
6. Create OAuth Client ID:
   - Application type: **Web application**
   - Name: **Dorothy**
   - Authorized redirect URIs: Add your callback URLs:
     - For local development: `http://localhost:8005/auth/callback`
     - For production: `https://dorothy.watsonblinds.com.au/auth/callback`
7. Click **Create** and save your:
   - **Client ID** (ends with `.apps.googleusercontent.com`)
   - **Client Secret**

## Step 2: Configure Dorothy

1. Copy `.env.example` to `.env`:
   ```bash
   cd dorothy
   cp .env.example .env
   ```

2. Edit `.env` and add your OAuth credentials:
   ```bash
   # Google OAuth for login (REQUIRED)
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret

   # Flask secret key (generate a random one)
   FLASK_SECRET_KEY=your-secret-key-here

   # Allowed email addresses (comma-separated)
   ALLOWED_EMAILS=your@email.com
   ```

3. Generate a secure secret key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Copy the output to `FLASK_SECRET_KEY` in your `.env` file

4. Set your email in `ALLOWED_EMAILS` (only these emails can log in)

## Step 3: Install Dependencies

```bash
cd dorothy
pip install -r requirements.txt
```

The new dependencies are:
- `authlib` - OAuth library
- `flask-login` - Session management

## Step 4: Test Locally

```bash
python app.py
```

Visit `http://localhost:8005` and you should be redirected to Google login.

## Step 5: Deploy to Production

1. Update your `.env` on the server with production values
2. Ensure the OAuth redirect URI includes your production domain
3. Restart Dorothy:
   ```bash
   sudo systemctl restart gunicorn-dorothy
   ```

## Security Notes

- **Never commit `.env` to git** - it contains sensitive credentials
- Only emails listed in `ALLOWED_EMAILS` can access Dorothy
- The OAuth callback must match exactly what's configured in Google Cloud Console
- Use HTTPS in production for secure OAuth flow
- Keep `FLASK_SECRET_KEY` secure and never share it

## Troubleshooting

**Redirect URI mismatch error:**
- Make sure the redirect URI in Google Cloud Console exactly matches your domain
- Check for http vs https
- Check for trailing slashes

**Access Denied:**
- Verify your email is listed in `ALLOWED_EMAILS`
- Check for typos or extra spaces in the email list

**Session issues:**
- Ensure `FLASK_SECRET_KEY` is set and doesn't change between restarts
- Clear browser cookies and try again

**Development with multiple domains:**
- Add both localhost and production URIs to Google Cloud Console
- Dorothy will automatically use the correct one based on the request
