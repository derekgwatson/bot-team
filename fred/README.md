# 👤 Fred

**Fred manages users in your Google Workspace account.**

Fred is a purpose-built bot that handles user onboarding and offboarding in Google Workspace. He can create new users, archive departing users, and provide a simple interface for managing your organization's accounts.

## What Fred Does

- **List active users** - See all current Google Workspace users with storage usage
- **List archived users** - View users who have been offboarded
- **Create new users** - Add users with email, name, and temporary password
- **Archive users** - Suspend and archive users when they leave (keeps data)
- **Delete users** - Permanently remove users and all their data
- **Storage visibility** - See how much storage each user is consuming
- **API access** - All functionality available via REST API for bot-to-bot communication
- **Web interface** - Simple UI for manual operations

## Setup

### 1. Install Dependencies

```bash
cd fred
pip install -r requirements.txt
```

### 2. Configure Google Workspace

You'll need a Google Cloud service account with domain-wide delegation:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or use existing)
3. Enable the **Admin SDK API**
4. Create a **Service Account**
5. Create and download a **JSON key** for the service account
6. Enable **domain-wide delegation** for the service account
7. In Google Workspace Admin, authorize the service account with these scopes:
   - `https://www.googleapis.com/auth/admin.directory.user`
   - `https://www.googleapis.com/auth/admin.directory.user.readonly`

Save the JSON key as `credentials.json` in the `fred/` directory.

### 3. Update Configuration

Edit `config.yaml`:

```yaml
google_workspace:
  credentials_file: "credentials.json"
  domain: "yourdomain.com"
  admin_email: "admin@yourdomain.com"

server:
  host: "0.0.0.0"
  port: 8001
```

### 4. Run Fred

**Development:**
```bash
python app.py
```

**Production (with gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8001 app:app
```

Fred will be available at:
- Web UI: `http://localhost:8001/`
- API: `http://localhost:8001/api/`
- Health check: `http://localhost:8001/health`

## API Reference

### Introduction

```bash
GET /api/intro
```

Returns Fred's introduction, description, and capabilities. Useful for discovering what Fred can do.

### List Users

```bash
# Get active users
GET /api/users

# Get archived users
GET /api/users?archived=true

# Limit results
GET /api/users?max_results=50
```

### Get User

```bash
GET /api/users/user@example.com
```

### Create User

```bash
POST /api/users
Content-Type: application/json

{
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "TempPassword123!"
}
```

### Archive User

```bash
POST /api/users/user@example.com/archive
```

Suspends and archives the user. Data is retained.

### Delete User

```bash
DELETE /api/users/user@example.com
```

**WARNING:** Permanently deletes the user and all their data. This cannot be undone.

## Web Interface

Visit `http://localhost:8001/` to access Fred's web interface where you can:

- View all active and archived users
- See user details (creation date, last login, status, **storage usage**)
- Add new users with a simple form
- Archive users (keeps data) or permanently delete users

## Security Notes

- **Credentials file** (`credentials.json`) should NEVER be committed to git
- Users are created with `changePasswordAtNextLogin: true` for security
- Archiving a user both suspends and marks them as archived (data is retained)
- **Deleting a user is permanent and cannot be undone** - use with caution
- Fred requires admin-level Google Workspace access

## Bot-to-Bot Communication

Other bots can call Fred's API to manage users as part of automated workflows:

```python
import requests

# Example: Create user when onboarding workflow starts
response = requests.post('http://fred:8001/api/users', json={
    'email': 'newuser@example.com',
    'first_name': 'John',
    'last_name': 'Smith',
    'password': generate_temp_password()
})
```

## File Structure

```
fred/
├── app.py                 # Main Flask application
├── config.py              # Configuration loader
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── api/
│   └── users.py          # REST API endpoints
├── web/
│   ├── routes.py         # Web UI routes
│   └── templates/        # HTML templates
└── services/
    └── google_workspace.py  # Google Workspace API integration
```

## Future Enhancements

- Group management
- User provisioning templates
- Audit logging
- Slack/email notifications
- Batch operations
- User suspension (without archiving)

---

**Fred** - Because managing users should be simple.
