# 📱 Peter - HR & Phone Directory Manager

**Peter is your organization's central HR system, managing ALL staff information.**

Peter has evolved from a simple phone directory to a complete HR management system. He now:
- **Manages ALL staff** (employees + external/contract staff)
- **Handles access requests** from people without company Google accounts
- **Provides phone directory** for internal use (Pam displays this publicly)
- **Syncs with Quinn** to keep the all-staff Google Group up-to-date
- **Provides access control** for other bots (Pam checks with Peter for authorization)

## 🆕 New Features (v2.0)

### Access Request System
External staff (contractors, people without company emails) can request access via Peter's API:
- `POST /api/access-requests` - Submit access request (public endpoint)
- `GET /api/access-requests` - View pending requests (admin)
- `POST /api/access-requests/<id>/approve` - Approve and auto-create staff entry
- `POST /api/access-requests/<id>/deny` - Deny request

### Staff Database (SQLite)
Peter now uses a local SQLite database instead of Google Sheets:
- All staff information stored in `database/staff.db`
- Supports migrations for schema changes
- Flags like `include_in_allstaff`, `show_on_phone_list` control visibility
- Tracks work email and personal email separately

### Integration Endpoints
- `GET /api/staff/allstaff-members` - Quinn calls this to sync Google Group
- `GET /api/is-approved?email=...` - Pam calls this for access control
- `GET /api/staff` - Get all staff (not just phone list)

---

## Original Features (Phone Directory)

# 📱 Peter

**Peter manages your organization's phone directory.**

Peter is a purpose-built bot that syncs with your Google Sheets phone list to provide easy access to contact information. He makes it simple to find someone's extension, mobile number, or email - and he's perfect for bot-to-bot integration when other bots need contact info.

## What Peter Does

- **Browse directory** - View all contacts organized by department/section
- **Search contacts** - Find people by name, extension, or phone number
- **Add contacts** - Add new people to the directory
- **Update contacts** - Modify existing contact information
- **Delete contacts** - Remove people from the directory
- **API access** - All functionality available via REST API for bot-to-bot communication
- **Web interface** - Clean UI for browsing and managing contacts

## Setup

### 1. Install Dependencies

```bash
cd peter
pip install -r requirements.txt
```

### 2. Configure Google Sheets Access

Peter uses the Google Sheets API to access your phone directory.

1. Use the **same credentials.json as Fred and Iris**
2. Copy `credentials.json` to the `peter/` directory
3. Get the service account email from the credentials file
4. **Share your Google Sheet** with the service account email (give it Editor access)

### 3. Update Configuration

Edit `config.yaml`:

```yaml
google_sheets:
  credentials_file: "credentials.json"
  spreadsheet_id: "YOUR_SPREADSHEET_ID"  # From the Sheet URL
  sheet_name: "Phone List"  # Name of the tab

server:
  host: "0.0.0.0"
  port: 8003
```

**To get the Spreadsheet ID:**
From the URL `https://docs.google.com/spreadsheets/d/ABC123.../edit`
The ID is `ABC123...`

### 4. Run Peter

**Development:**
```bash
python app.py
```

**Production (with gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8003 app:app
```

Peter will be available at:
- Web UI: `http://localhost:8003/`
- API: `http://localhost:8003/api/`
- Health check: `http://localhost:8003/health`

## Sheet Structure

Peter expects your Google Sheet to have this structure:

| Extension | Name | Fixed Line | Mobile | Email |
|-----------|------|------------|--------|-------|
| 1234 | John Doe | 02 1234 5678 | 0412 345 678 | john@example.com |

**Section Headers:**
- Section names should be in ALL CAPS in the Name column
- Can optionally include main phone: `SALES - 02 1234 0000`
- Section headers span columns B-E
- Leave Extension column empty for section headers

## API Reference

### Introduction

```bash
GET /api/intro
```

Returns Peter's introduction, description, and capabilities.

### List All Contacts

```bash
GET /api/contacts
```

Returns all contacts from the phone directory.

**Response example:**
```json
{
  "contacts": [
    {
      "row": 5,
      "extension": "1234",
      "name": "John Doe",
      "fixed_line": "02 1234 5678",
      "mobile": "0412 345 678",
      "email": "john@example.com",
      "section": "SALES"
    }
  ],
  "count": 1
}
```

### Search Contacts

```bash
GET /api/contacts/search?q=john

# Search by extension
GET /api/contacts/search?q=1234

# Search by phone
GET /api/contacts/search?q=0412
```

### Add Contact

```bash
POST /api/contacts
Content-Type: application/json

{
  "section": "SALES",
  "extension": "1234",
  "name": "John Doe",
  "fixed_line": "02 1234 5678",
  "mobile": "0412 345 678",
  "email": "john@example.com"
}
```

### Update Contact

```bash
PUT /api/contacts/5
Content-Type: application/json

{
  "mobile": "0499 123 456"
}
```

Only include fields you want to update.

### Delete Contact

```bash
DELETE /api/contacts/5
```

Deletes the contact at row 5.

## Web Interface

Visit `http://localhost:8003/` to access Peter's web interface where you can:

- Browse the entire phone directory organized by section
- Search for contacts by any field
- Add new contacts with a simple form
- Delete contacts with one click
- Click phone numbers to initiate calls (on mobile)
- Click emails to send messages

## Bot-to-Bot Communication

Other bots can call Peter's API to get contact information:

```python
import requests

# Example: Find someone's mobile number
response = requests.get('http://peter:8003/api/contacts/search?q=john')
contacts = response.json()['results']

if contacts:
    mobile = contacts[0]['mobile']
    print(f"John's mobile: {mobile}")

# Example: Add contact during onboarding
requests.post('http://peter:8003/api/contacts', json={
    'section': 'ADMIN',
    'name': 'New Employee',
    'mobile': '0412 345 678',
    'email': 'new@example.com'
})
```

## Working with Fred

Peter and Fred work great together for onboarding:

```
Onboarding workflow:
1. Fred creates Google Workspace user
2. Peter adds them to phone directory
3. Notification bot sends welcome message
```

## File Structure

```
peter/
├── app.py                    # Main Flask application
├── config.py                 # Configuration loader
├── config.yaml               # Configuration file
├── requirements.txt          # Python dependencies
├── api/
│   └── contacts.py          # REST API endpoints
├── web/
│   ├── routes.py            # Web UI routes
│   └── templates/           # HTML templates
└── services/
    └── google_sheets.py     # Google Sheets API integration
```

## Important Notes

- **Sheet Access**: The service account must have Editor access to the Google Sheet
- **Row Numbers**: Row numbers in the API correspond to actual sheet rows
- **Sections**: Section names must match exactly (case-sensitive)
- **Real-time**: Changes sync immediately with the Google Sheet
- **No Caching**: Peter always reads fresh data from the sheet

## Troubleshooting

**"Google Sheets service not initialized"**
- Make sure `credentials.json` is in the peter directory
- Verify the file path in `config.yaml`

**"API error: 403"**
- The service account doesn't have access to the sheet
- Share the sheet with the service account email (give Editor access)

**"Section not found"**
- Section names are case-sensitive
- Make sure the section header exists in the sheet (ALL CAPS)

---

**Peter** - Because everyone needs a good contact.
