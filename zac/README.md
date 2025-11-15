# Zac - Zendesk User Management

Zac manages Zendesk users through a friendly web interface and REST API. He provides full CRUD operations for Zendesk users, making it easy to create, update, suspend, and manage your Zendesk support team and end users.

## What Zac Does

Zac is your Zendesk user management assistant. Think of him as the HR manager for your Zendesk support portal.

**Key Features:**
- List and search all Zendesk users
- Create new users (end-users, agents, admins)
- Update user information and roles
- Suspend/unsuspend users
- Delete users
- Filter users by role and status
- Web UI for easy user management
- REST API for automation and bot-to-bot communication
- Admin-only access with Google OAuth

## How It Works

```
Web UI / API → Zac → Zendesk API → Zendesk
                ↓
         User Management
    (Create, Read, Update, Delete)
```

**When you create a user:**
1. Zac sends the request to Zendesk API
2. User is created in Zendesk
3. Confirmation returned with user details

**When you suspend a user:**
1. User status updated in Zendesk
2. User can no longer access support portal
3. All tickets and history preserved

## Setup

1. **Install dependencies:**
   ```bash
   cd zac
   pip install -r requirements.txt
   ```

2. **Configure Zendesk credentials:**
   - Copy `.env.example` to `.env`
   - Add your Zendesk subdomain (e.g., 'yourcompany' for yourcompany.zendesk.com)
   - Add your Zendesk admin email
   - Generate a Zendesk API token (Admin > Channels > API)

3. **Configure Google OAuth:**
   - Add your Google OAuth credentials to `.env`
   - Add admin email addresses (comma-separated)

4. **Run Zac:**
   ```bash
   python app.py
   ```

5. **Access Zac:**
   - Web UI: http://localhost:8007
   - API: http://localhost:8007/api
   - Health: http://localhost:8007/health

## Environment Variables

Create a `.env` file with the following:

```bash
# Zendesk Configuration
ZENDESK_SUBDOMAIN=yourcompany
ZENDESK_EMAIL=admin@example.com
ZENDESK_API_TOKEN=your-api-token-here

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Security
SECRET_KEY=your-secret-key-here
BOT_API_KEY=your-bot-api-key

# Access Control
ADMIN_EMAILS=admin1@example.com,admin2@example.com
```

## API Endpoints

All API endpoints require authentication via `X-API-Key` header.

### List Users

```
GET /api/users?role=agent&page=1&per_page=50

Response:
{
  "users": [...],
  "total": 125,
  "page": 1,
  "per_page": 50,
  "total_pages": 3
}
```

**Query Parameters:**
- `role` - Filter by role (end-user, agent, admin)
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 100)

### Get User

```
GET /api/users/{user_id}

Response:
{
  "id": 12345,
  "name": "John Doe",
  "email": "john@example.com",
  "role": "agent",
  "active": true,
  "suspended": false,
  "verified": true,
  "created_at": "2024-01-15T10:30:00Z",
  "last_login_at": "2024-01-20T14:22:00Z"
}
```

### Search Users

```
GET /api/users/search?q=john

Response:
{
  "users": [...]
}
```

### Create User

```
POST /api/users
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "role": "agent",
  "verified": true,
  "phone": "+1 555-1234"
}

Response:
{
  "id": 12345,
  "name": "John Doe",
  "email": "john@example.com",
  "role": "agent",
  "verified": true,
  "active": true
}
```

### Update User

```
PUT /api/users/{user_id}
Content-Type: application/json

{
  "name": "John Smith",
  "role": "admin"
}

Response:
{
  "id": 12345,
  "name": "John Smith",
  "role": "admin",
  ...
}
```

### Suspend User

```
POST /api/users/{user_id}/suspend

Response:
{
  "id": 12345,
  "name": "John Doe",
  "suspended": true
}
```

### Unsuspend User

```
POST /api/users/{user_id}/unsuspend

Response:
{
  "id": 12345,
  "name": "John Doe",
  "suspended": false
}
```

### Delete User

```
DELETE /api/users/{user_id}

Response:
{
  "message": "User 12345 deleted successfully"
}
```

## Web Interface

The web interface provides a user-friendly way to manage Zendesk users:

- **Dashboard** (`/`) - List all users with search and filters
- **Create User** (`/user/create`) - Create new users
- **View User** (`/user/{id}`) - View detailed user information
- **Edit User** (`/user/{id}/edit`) - Edit user details

### Features:
- Search users by name or email
- Filter by role (end-user, agent, admin)
- Pagination for large user lists
- Quick actions (suspend, unsuspend, delete)
- Role badges and status indicators

## User Roles

Zendesk supports three user roles:

- **End User** - Regular support portal users who can submit tickets
- **Agent** - Support staff who can view and respond to tickets
- **Admin** - Full administrative access to Zendesk

## Security

- **Admin-only access**: Only emails in `ADMIN_EMAILS` can access Zac
- **OAuth authentication**: Uses Google OAuth for web login
- **API key authentication**: REST API requires `X-API-Key` header
- **Zendesk API token**: Securely stored in `.env` file
- **robots.txt**: Blocks all search engine crawlers

## Integration with Other Bots

**To call Zac from another bot:**

```python
import requests

# List all agents
response = requests.get(
    'http://localhost:8007/api/users?role=agent',
    headers={'X-API-Key': 'your-bot-api-key'}
)
users = response.json()

# Create a new user
response = requests.post(
    'http://localhost:8007/api/users',
    headers={'X-API-Key': 'your-bot-api-key'},
    json={
        'name': 'Jane Smith',
        'email': 'jane@example.com',
        'role': 'agent'
    }
)
new_user = response.json()
```

## Deployment

See the main [DEPLOYMENT.md](../deployment/DEPLOYMENT.md) guide for production deployment instructions.

**Port:** 8007

## Zendesk API Documentation

For more information about Zendesk's user management capabilities:
- [Zendesk API Documentation](https://developer.zendesk.com/api-reference/)
- [Users API](https://developer.zendesk.com/api-reference/ticketing/users/users/)

## Troubleshooting

**"Zendesk credentials not configured"**
- Make sure `.env` file exists with all required Zendesk credentials
- Check that `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, and `ZENDESK_API_TOKEN` are set

**"Access Denied" on login**
- Ensure your email is in the `ADMIN_EMAILS` list in `.env`
- Check that Google OAuth credentials are correct

**API returns 401 Unauthorized**
- Include `X-API-Key` header with your bot API key
- Verify the API key matches `BOT_API_KEY` in `.env`
