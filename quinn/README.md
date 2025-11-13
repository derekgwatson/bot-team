# Quinn - External Staff Access Manager

Quinn manages access for external staff who don't have company email addresses. He maintains a registry of approved external staff and automatically manages Google Groups membership.

## What Quinn Does

Quinn is the gatekeeper for external staff access. Think of him as HR for people who don't have company email accounts.

**Key Features:**
- Maintains external staff registry in SQLite database
- Provides API for other bots to check if someone is approved
- Automatically manages allstaff@watsonblinds.com.au Google Group
- Web UI for adding/editing external staff
- Admin-only access (whitelist-based)
- Tracks who added each person and when

## How It Works

```
External Staff → Quinn (Registry) → Pam, other bots
                      ↓
              Google Groups API
                      ↓
           allstaff@watsonblinds.com.au
```

**When you add someone to Quinn:**
1. They're saved to the database
2. Automatically added to allstaff Google Group
3. Other bots can check their approval status
4. They can now access Pam and other tools

**When you deactivate someone:**
1. Status changed to "inactive" in database
2. Automatically removed from allstaff Google Group
3. They lose access to all bot tools

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Quinn:**
   - Copy `.env.example` to `.env`
   - Add your Google OAuth credentials
   - Update `config.yaml` with your admin email and allstaff group address

3. **Add service account credentials:**
   - Copy your `credentials.json` to the `quinn/` directory
   - Service account needs domain-wide delegation for Groups API

4. **Run Quinn:**
   ```bash
   python app.py
   ```

5. **Access Quinn:**
   - Web UI: http://localhost:8005
   - API: http://localhost:8005/api/intro
   - Health: http://localhost:8005/health

## API Endpoints

### For Other Bots

**Check if email is approved:**
```
GET /api/is-approved?email=john@personal.com

Response:
{
  "approved": true,
  "name": "John Doe",
  "email": "john@personal.com",
  "role": "Contractor"
}
```

**Get all external staff:**
```
GET /api/staff?status=active

Response:
{
  "staff": [...],
  "count": 5
}
```

### Admin Operations

**Add staff member:**
```
POST /api/staff
{
  "name": "John Doe",
  "email": "john@personal.com",
  "phone": "0412 345 678",
  "role": "Contractor",
  "notes": "Works in warehouse"
}
```

**Update staff member:**
```
PUT /api/staff/1
{
  "status": "inactive"
}
```

## Integration with Other Bots

**Pam automatically checks with Quinn:**
- User tries to log in with Google
- If email is not in allowed domains, Pam asks Quinn
- If Quinn says they're approved, access granted
- If not approved, access denied

**To integrate Quinn with your bot:**
```python
# In your bot's config.yaml
auth:
  quinn_api_url: "http://localhost:8005"

# The shared auth module will automatically check Quinn
```

## Database Schema

```sql
external_staff:
  - id (primary key)
  - name
  - email (unique)
  - phone
  - role
  - status (active/inactive)
  - added_date
  - added_by
  - modified_date
  - notes
```

Database is stored at: `database/external_staff.db`

## Security

- **Admin-only access**: Only emails in `config.yaml` admin_emails list can access Quinn
- **OAuth authentication**: Uses Google OAuth for login
- **Database**: SQLite file - should be backed up regularly
- **Google Groups**: Automatic sync keeps group membership accurate

## Backup

The SQLite database is a single file at `database/external_staff.db`.

To backup:
```bash
cp database/external_staff.db database/external_staff_backup_$(date +%Y%m%d).db
```

Consider setting up automated backups of this file.
