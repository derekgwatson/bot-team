# 🎉 Oscar - Staff Onboarding Orchestrator

**Oscar coordinates the entire onboarding process for new staff members.**

Oscar is a purpose-built bot that orchestrates the onboarding workflow by coordinating with multiple other bots in the team. He provides a simple web form for initiating onboarding and automatically handles all the technical setup steps.

## What Oscar Does

Oscar takes a new staff member's information and automatically:

1. **Sends email notification** to HR/Payroll (Ian) with all onboarding details
2. **Creates Google Workspace account** (via Fred) if required
3. **Creates Zendesk account** (via Zac) if required
4. **Registers staff in HR database** (via Peter) for directory and access control
5. **Creates VOIP setup ticket** (via Sadie) for manual PBX configuration
6. **Tracks the entire workflow** with detailed status and activity logging

## Key Features

- **Web-based onboarding form** - Simple interface for submitting new staff details
- **Automated workflow** - Coordinates multiple bots to complete onboarding steps
- **Manual task tracking** - Tracks tasks that require human intervention (e.g., VOIP setup)
- **Activity logging** - Complete audit trail of all onboarding actions
- **Status dashboard** - Real-time view of pending, in-progress, and completed onboardings
- **REST API** - Full API access for automation and integration

## The Onboarding Workflow

```
New Staff Form → Oscar Orchestrates:
  ├─ 1️⃣ Email notification to Ian (HR/Payroll)
  ├─ 2️⃣ Fred creates Google Workspace user
  ├─ 3️⃣ Zac creates Zendesk account (if needed)
  ├─ 4️⃣ Peter registers staff in HR database
  └─ 5️⃣ Sadie creates VOIP setup ticket (if needed)
```

When a VOIP setup is required, Oscar creates a Zendesk ticket with clear instructions. Once you complete the PBX setup and mark the ticket as complete, Oscar marks that step as done.

## Setup

### 1. Install Dependencies

```bash
cd oscar
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Google OAuth (for web authentication)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Admin emails (comma-separated)
ADMIN_EMAILS=admin@watsonblinds.com.au

# Email notifications
NOTIFICATION_EMAIL=ian@watsonblinds.com.au
SMTP_USERNAME=oscar@watsonblinds.com.au
SMTP_PASSWORD=your-smtp-password

# Flask secret key
SECRET_KEY=generate-with-python-secrets-token-hex-32
```

### 3. Verify Bot Dependencies

Oscar requires these bots to be running:
- **Fred** (port 8001) - Google Workspace user management
- **Zac** (port 8007) - Zendesk user management
- **Peter** (port 8003) - HR database
- **Sadie** (port 8010) - Zendesk ticket creation

Update `config.yaml` if your bots run on different URLs.

### 4. Run Oscar

**Development:**
```bash
python app.py
```

**Production (with gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8011 app:app
```

Oscar will be available at:
- Web UI: `http://localhost:8011/`
- API: `http://localhost:8011/api/`
- Health check: `http://localhost:8011/health`

## Using Oscar

### Web Interface

1. **Visit** `http://localhost:8011/`
2. **Log in** with your admin Google account
3. **Click "New Onboarding"** to access the form
4. **Fill in** the staff member's details and system access requirements
5. **Submit** - Oscar automatically starts the workflow
6. **Monitor** progress on the dashboard
7. **Complete manual tasks** (like VOIP setup) when prompted

### Dashboard Features

- **Statistics** - See pending, in-progress, completed, and failed onboardings
- **Recent requests** - Quick view of recent onboarding activity
- **Manual tasks alert** - Get notified when action is required
- **Detailed view** - Click any request to see full workflow progress

### Manual Tasks

When Oscar creates a VOIP setup ticket (or any manual task):

1. **View the task** in the "Manual Tasks" section
2. **Follow the instructions** provided in the task
3. **Complete the work** (e.g., create VOIP user in PBX)
4. **Mark as complete** in Oscar's interface
5. Oscar updates the onboarding status automatically

## API Reference

### Onboarding Endpoints

**Create onboarding request:**
```bash
POST /api/onboard
Content-Type: application/json

{
  "full_name": "John Doe",
  "position": "Sales Manager",
  "section": "Sales",
  "start_date": "2024-01-15",
  "personal_email": "john@example.com",
  "phone_mobile": "0412 345 678",
  "google_access": true,
  "zendesk_access": true,
  "voip_access": true,
  "auto_start": true
}
```

**Get onboarding details:**
```bash
GET /api/onboard/<id>
```

**List all onboarding requests:**
```bash
GET /api/onboard?status=pending
```

**Start onboarding workflow:**
```bash
POST /api/onboard/<id>/start
```

**Get pending manual tasks:**
```bash
GET /api/tasks
```

**Complete manual task:**
```bash
POST /api/tasks/<id>/complete
Content-Type: application/json

{
  "notes": "VOIP extension 1234 created",
  "completed_by": "admin@example.com"
}
```

**Get statistics:**
```bash
GET /api/stats
```

## Database

Oscar uses SQLite to track onboarding workflows:

- **Location:** `database/oscar.db`
- **Schema:** `database/schema.sql`
- **Tables:**
  - `onboarding_requests` - Staff onboarding requests
  - `workflow_steps` - Individual workflow steps
  - `activity_log` - Complete audit trail

The database is automatically created when Oscar starts.

## Workflow Steps

Oscar's workflow includes these steps (conditionally executed based on requirements):

1. **notify_ian** - Email notification to HR/Payroll *(always)*
2. **create_google_user** - Create Google Workspace account *(if google_access)*
3. **create_zendesk_user** - Create Zendesk account *(if zendesk_access)*
4. **register_peter** - Register in HR database *(always)*
5. **voip_ticket** - Create VOIP setup ticket *(if voip_access)* **[Manual]**

Critical steps (notify_ian, create_google_user, register_peter) will stop the workflow if they fail. Non-critical steps (create_zendesk_user, voip_ticket) will log the error but allow the workflow to continue.

## Bot-to-Bot Communication

Oscar calls these bot endpoints:

**Fred (Google Workspace):**
```python
POST http://localhost:8001/api/users
{
  "email": "john.doe@watsonblinds.com.au",
  "first_name": "John",
  "last_name": "Doe",
  "recovery_email": "john@example.com"
}
```

**Zac (Zendesk):**
```python
POST http://localhost:8007/api/users
{
  "name": "John Doe",
  "email": "john.doe@watsonblinds.com.au",
  "role": "agent"
}
```

**Peter (HR Database):**
```python
POST http://localhost:8003/api/staff
{
  "name": "John Doe",
  "position": "Sales Manager",
  "section": "Sales",
  "work_email": "john.doe@watsonblinds.com.au",
  "personal_email": "john@example.com",
  "phone_mobile": "0412 345 678",
  "google_access": true,
  "zendesk_access": true,
  "voip_access": true,
  "status": "active"
}
```

**Sadie (Zendesk Tickets):**
```python
POST http://localhost:8010/api/tickets
{
  "subject": "VOIP Setup Required: John Doe",
  "description": "Instructions for PBX setup...",
  "priority": "normal",
  "type": "task"
}
```

## File Structure

```
oscar/
├── app.py                          # Main Flask application
├── config.py                       # Configuration loader
├── config.yaml                     # Configuration file
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── api/
│   └── routes.py                  # REST API endpoints
├── web/
│   ├── routes.py                  # Web UI routes
│   ├── auth_routes.py             # Authentication routes
│   └── templates/                 # HTML templates
│       ├── base.html             # Base template
│       ├── index.html            # Dashboard
│       ├── onboard_form.html     # Onboarding form
│       ├── onboard_detail.html   # Request details
│       ├── manual_tasks.html     # Manual tasks list
│       └── all_requests.html     # All requests list
├── services/
│   ├── auth.py                    # Authentication service
│   ├── email_service.py           # Email notifications
│   └── orchestrator.py            # Workflow orchestration
└── database/
    ├── schema.sql                 # Database schema
    └── db.py                      # Database operations
```

## Security & Access Control

- **Authentication:** Google OAuth (organization accounts only)
- **Authorization:** Only admin users (configured in ADMIN_EMAILS) can access
- **Session management:** Secure Flask sessions
- **API access:** Consider adding API authentication for production

## Error Handling

Oscar includes comprehensive error handling:

- **Failed steps** are logged with error messages
- **Non-critical failures** don't stop the workflow
- **Critical failures** halt the workflow and update status to "failed"
- **Activity log** captures all events for troubleshooting
- **Email notifications** still sent even if other steps fail

## Future Enhancements

Potential additions:
- Email/SMS notifications to the new staff member
- Integration with building access systems
- Automated equipment ordering workflow
- Slack/Teams notifications for HR team
- Offboarding workflow (separate bot following Unix philosophy)

## Troubleshooting

**"Bot not responding" errors:**
- Verify Fred, Zac, Peter, and Sadie are running
- Check bot URLs in `config.yaml`
- Review logs for connection errors

**Email notifications not sending:**
- Verify SMTP credentials in `.env`
- Check SMTP_USERNAME and SMTP_PASSWORD
- Test with a simple Python SMTP script first

**Database errors:**
- Database is auto-created on first run
- Delete `database/oscar.db` to reset (loses all data)
- Schema updates require migration (see `database/schema.sql`)

**Access denied:**
- Ensure your email is in ADMIN_EMAILS environment variable
- Check Google OAuth credentials are correct
- Try logging out and back in

---

**Oscar** - Because onboarding should be a celebration, not a chore! 🎉
