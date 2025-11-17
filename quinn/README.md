# Quinn - All-Staff Google Group Sync Service

Quinn is a simple background service that keeps the all-staff Google Group perfectly synchronized with Peter's HR database.

## What Quinn Does

Quinn has one job: **Keep the all-staff Google Group in sync with Peter's database.**

Every 5 minutes (configurable), Quinn:
1. Asks Peter who should be in the all-staff group
2. Checks the current Google Group membership
3. Adds anyone who should be there but isn't
4. Removes anyone who shouldn't be there

**Peter is the single source of truth** - manage all staff there, and Quinn will automatically sync the Google Group.

## Architecture

```
Peter (HR Database) → Quinn (Sync Service) → Google Groups API
                                                     ↓
                                          allstaff@company.com
```

- **Peter** manages ALL staff (employees + external staff)
- **Quinn** just syncs the Google Group from Peter's data
- **No manual management** needed - everything flows from Peter

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Quinn:**
   - Copy `.env.example` to `.env`
   - Set `PETER_URL` (default: http://localhost:8003)

3. **Add Google service account credentials:**
   - Copy your `credentials.json` to the `quinn/` directory
   - Service account needs domain-wide delegation for Groups API

4. **Configure sync interval:**
   - Edit `config.yaml` to change `sync.interval_seconds` (default: 300 = 5 minutes)

5. **Run Quinn:**
   ```bash
   python app.py
   ```

6. **Access Quinn:**
   - Status page: http://localhost:8006
   - API: http://localhost:8006/api/sync/status
   - Health: http://localhost:8006/health

## API Endpoints

### Sync Management

**Get sync status:**
```
GET /api/sync/status

Response:
{
  "running": true,
  "interval_seconds": 300,
  "last_sync": 1234567890,
  "last_sync_result": {
    "success": true,
    "desired_count": 45,
    "current_count": 45,
    "added": [],
    "removed": [],
    "elapsed_seconds": 2.5
  }
}
```

**Trigger immediate sync:**
```
POST /api/sync/now

Response:
{
  "success": true,
  "desired_count": 45,
  "current_count": 45,
  "added": ["newperson@example.com"],
  "removed": [],
  "elapsed_seconds": 3.2
}
```

### Legacy Endpoints (Deprecated)

These endpoints are deprecated and will be removed. Use Peter's endpoints instead:

- `/api/is-approved` → Use `GET /api/is-approved` on Peter
- `/api/staff` → Use `GET /api/staff` on Peter
- All staff management endpoints → Use Peter's web UI or API

## Integration with Other Bots

**Pam checks with Peter:**
- For access control, Pam calls Peter's `/api/is-approved` endpoint
- Pam no longer checks with Quinn

**To add someone to the all-staff group:**
1. Add them to Peter's database with `include_in_allstaff = 1`
2. Quinn will automatically add them within 5 minutes
3. Or trigger immediate sync: `POST /api/sync/now`

## Configuration

Quinn's configuration is in `config.yaml`:

```yaml
# Peter API configuration (Quinn's source of truth for staff info)
peter_url: "http://peter:8003"

# Sync configuration
sync:
  # How often to sync the allstaff group with Peter's database (in seconds)
  interval_seconds: 300  # 5 minutes
```

## Status Page

Quinn's web interface shows:
- Sync service status (running/stopped)
- Last sync time and results
- How many members were added/removed
- Quick access to API endpoints

No authentication required - it's just a read-only status page.

## What Changed?

Quinn used to manage external staff directly (with its own database and web UI). That functionality has been moved to Peter to create a cleaner architecture:

- **Before:** Quinn managed external staff + synced Google Group
- **After:** Quinn just syncs Google Group from Peter

This makes Peter the single source of truth for ALL staff, simplifying the system.

## Development

### Project Structure

```
quinn/
├── app.py                      # Main Flask application
├── config.py                   # Configuration loader
├── config.yaml                 # Configuration file
├── requirements.txt            # Python dependencies
├── api/
│   └── routes.py               # API endpoints
├── web/
│   └── simple_routes.py        # Simple status page
├── services/
│   ├── sync_service.py         # Background sync service
│   ├── peter_client.py         # Peter API client
│   └── google_groups.py        # Google Groups API client
└── database/
    └── (deprecated - no longer used)
```

### Running Tests

```bash
# From bot-team root directory
pytest tests/unit/test_quinn.py
pytest tests/integration/test_quinn.py
```

## Production Deployment

See `/home/user/bot-team/deployment/DEPLOYMENT.md` for production deployment instructions.

Quinn should be deployed with:
- Systemd service (`quinn.service`)
- Running as `www-data` user
- 2 gunicorn workers
- No nginx needed (internal service)

## Version

Current version: 0.3.0 (Simplified sync-only architecture)
