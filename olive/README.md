# 🫒 Olive - Staff Offboarding Orchestrator

Olive automates the offboarding process for departing staff members by coordinating system access removal across multiple platforms.

## Features

- **Automated Access Removal**: Checks and removes access from all systems
- **Multi-System Integration**: Works with Peter, Google Workspace, Zendesk, Wiki, and Buz
- **Workflow Tracking**: Complete visibility into offboarding progress
- **Secure Access**: Google OAuth with admin-level authorization
- **Email Notifications**: Automatic notifications to HR and IT

## Systems Integrated

- **Peter**: Staff directory and HR database (finish date updates)
- **Google Workspace** (via Fred): Suspend Google accounts
- **Zendesk** (via Zac): Deactivate Zendesk accounts
- **Wiki**: Remove wiki access (stubbed - to be implemented)
- **Buz**: Remove CRM access (stubbed - to be implemented)

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy and configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. Run the application:
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:8012`

## Configuration

Edit `config.yaml` to configure:
- Bot dependencies (Peter, Fred, Zac, etc.)
- Server settings
- Email configuration

Set environment variables in `.env`:
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for OAuth
- `ADMIN_EMAILS` for authorized users (comma-separated)
- `SMTP_USERNAME` and `SMTP_PASSWORD` for email notifications

## Usage

### Web Interface

1. Navigate to `http://localhost:8012`
2. Log in with your Google account (must be an authorized admin)
3. Click "New Offboarding" to start the process
4. Fill in the staff member's details
5. Submit and track progress

### API

```bash
# Create an offboarding request
curl -X POST http://localhost:8012/api/offboard \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith",
    "last_day": "2025-12-31",
    "auto_start": true
  }'

# Get offboarding status
curl http://localhost:8012/api/offboard/1

# Get bot information
curl http://localhost:8012/api/intro
```

## Workflow

When an offboarding request is submitted, Olive:

1. **Sends Notification**: Notifies HR/IT about the offboarding
2. **Checks Peter**: Retrieves staff access information
3. **Disables Google**: Suspends Google Workspace account (if applicable)
4. **Deactivates Zendesk**: Deactivates Zendesk account (if applicable)
5. **Removes Wiki Access**: Removes wiki access (stubbed)
6. **Removes Buz Access**: Removes Buz access (stubbed)
7. **Updates Peter**: Sets finish date and marks staff as finished

## Development Status

**Production Ready:**
- Google Workspace (via Fred)
- Zendesk (via Zac)
- Peter integration

**Stubbed (Coming Soon):**
- Wiki access removal
- Buz access removal

## Security

- Google OAuth authentication
- Admin-level access control
- Session-based authorization
- HTTPS recommended for production

## Related Bots

- **Oscar**: Staff onboarding bot
- **Peter**: Staff directory and HR database
- **Fred**: Google Workspace management
- **Zac**: Zendesk management
