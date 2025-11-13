# 🔍 Iris

**Iris provides reporting and analytics for your Google Workspace.**

Iris is a purpose-built bot that tracks storage usage, monitors trends, and provides insights into how your Google Workspace is being used. She's great at answering questions like "Who's using the most storage?" or "How much Gmail vs Drive space are we using?"

## What Iris Does

- **Storage analytics** - Track Gmail, Drive, and total storage per user
- **Usage trends** - View historical data and identify patterns
- **High usage alerts** - See who's using the most space at a glance
- **Organization metrics** - Total storage, average per user, distribution
- **API access** - All functionality available via REST API for bot-to-bot communication
- **Web dashboard** - Visual interface for exploring usage data

## Setup

### 1. Install Dependencies

```bash
cd iris
pip install -r requirements.txt
```

### 2. Configure Google Workspace

You'll need a Google Cloud service account with domain-wide delegation:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Use the same project as Fred (or create new)
3. Enable the **Admin SDK API** (if not already enabled)
4. Use the same service account as Fred
5. In Google Workspace Admin, add these additional scopes for the service account:
   - `https://www.googleapis.com/auth/admin.reports.usage.readonly`
   - `https://www.googleapis.com/auth/admin.reports.audit.readonly`

You can use the **same credentials.json file as Fred** - just copy it to the `iris/` directory.

### 3. Update Configuration

Edit `config.yaml`:

```yaml
google_workspace:
  credentials_file: "credentials.json"
  domain: "yourdomain.com"
  admin_email: "admin@yourdomain.com"

server:
  host: "0.0.0.0"
  port: 8002

bots:
  fred:
    url: "http://localhost:8001"
    description: "User management bot"
```

### 4. Run Iris

**Development:**
```bash
python app.py
```

**Production (with gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8002 app:app
```

Iris will be available at:
- Web UI: `http://localhost:8002/`
- API: `http://localhost:8002/api/`
- Health check: `http://localhost:8002/health`

## API Reference

### Introduction

```bash
GET /api/intro
```

Returns Iris's introduction, description, and capabilities.

### Get All Usage

```bash
# Get usage for all users (yesterday's data)
GET /api/usage

# Get usage for a specific date
GET /api/usage?date=2024-01-15

# Get usage for specific user
GET /api/usage?email=user@example.com
```

### Get User Usage

```bash
GET /api/usage/user@example.com

# With specific date
GET /api/usage/user@example.com?date=2024-01-15
```

**Response example:**
```json
{
  "email": "user@example.com",
  "date": "2024-01-15",
  "gmail_used_gb": 2.45,
  "drive_used_gb": 8.32,
  "total_used_gb": 10.77,
  "total_quota_gb": 30.0,
  "gmail_used_mb": 2510,
  "drive_used_mb": 8520,
  "total_used_mb": 11030
}
```

## Web Interface

Visit `http://localhost:8002/` to access Iris's web dashboard where you can:

- View organization-wide storage statistics
- See all users sorted by storage usage
- Drill down into individual user details
- Compare Gmail vs Drive usage
- Identify users with high storage consumption

## Important Notes

- **Data delay**: Google Reports API typically has a 1-2 day delay. You won't see today's data immediately.
- **Credentials**: You can use the same `credentials.json` as Fred - just make sure the Reports API scopes are authorized.
- **Date format**: All dates must be in YYYY-MM-DD format.
- **Read-only**: Iris only reads reports data - she doesn't modify anything.

## Bot-to-Bot Communication

Other bots can call Iris's API to get storage information:

```python
import requests

# Example: Check storage before creating a new user
response = requests.get('http://iris:8002/api/usage')
usage_data = response.json()

# Find users over 50GB
heavy_users = [u for u in usage_data['usage'] if u['total_used_gb'] > 50]

# Combine with Fred to archive heavy users
for user in heavy_users:
    requests.post(f'http://fred:8001/api/users/{user["email"]}/archive')
```

## Working with Fred

Iris and Fred work great together:

- **Fred** answers: "Who has access?"
- **Iris** answers: "What are they using?"

Example workflow:
1. Ask Iris for users over 20GB
2. Ask Fred if they've logged in recently
3. Archive inactive heavy users through Fred

## File Structure

```
iris/
├── app.py                 # Main Flask application
├── config.py              # Configuration loader
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── api/
│   └── reports.py        # REST API endpoints
├── web/
│   ├── routes.py         # Web UI routes
│   └── templates/        # HTML templates
└── services/
    └── google_reports.py  # Google Reports API integration
```

## Troubleshooting

**"No usage data available"**
- Usage data has a 1-2 day delay
- Try requesting data from 2-3 days ago: `?date=2024-01-13`
- Verify Reports API is enabled
- Check that scopes are authorized in Workspace Admin

**"API error: 403"**
- Make sure domain-wide delegation includes Reports API scopes
- Verify admin_email has super admin permissions

---

**Iris** - Because insights drive better decisions.
