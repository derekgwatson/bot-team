# Claude Reference Guide for Bot-Team

Quick reference for working on this codebase. Read this first!

## Project Overview

Bot-team is a collection of Flask-based microservices ("bots") that handle various business functions for Watson Blinds. Each bot runs on its own port and communicates via REST APIs.

### Design Philosophy: Do One Thing Well

**CRITICAL**: Each bot follows the Unix philosophy - do one thing and do it well.

When adding new functionality, ALWAYS ask:
- Does this belong in this bot's core purpose?
- Is this causing scope creep?
- Would a new bot be better suited for this?

If a bot starts doing too much, **nip it in the bud immediately**. Split functionality into a new bot rather than letting one bot become a monolith. It's better to have 20 focused bots than 5 bloated ones.

## Bot Registry (Chester's config.yaml) - SINGLE SOURCE OF TRUTH

**CRITICAL**: `/chester/config.yaml` is the ONE AND ONLY place where bot ports are defined!

- NEVER hardcode ports anywhere else in the codebase
- Bots discover ports dynamically via Chester's API or `shared/config/ports.py`
- When adding a new bot: add entry to `bot_team:` section with name, port, description, capabilities
- Port range: 8001-8030 (check config.yaml for next available)

## Dependencies

**IMPORTANT**: The bot team uses a **single shared virtual environment** and one root `requirements.txt` file.

- All dependencies go in `/bot-team/requirements.txt`
- Do NOT create per-bot `requirements.txt` files
- When adding a new bot that needs a new package, add it to the root file with a comment indicating which bot uses it

## Standard Bot Structure

```
bot-name/
├── app.py              # Flask entry point
├── config.py           # Config loader (uses shared patterns)
├── config.yaml         # Bot-specific settings
├── .env.example        # Environment variables template
├── api/
│   ├── __init__.py
│   └── routes.py       # API endpoints (use @api_key_required)
├── services/
│   ├── __init__.py
│   ├── auth.py         # OAuth setup (if web UI)
│   └── *.py            # Business logic
├── web/
│   ├── __init__.py
│   ├── routes.py       # Web UI routes (use @login_required or @admin_required)
│   ├── auth_routes.py  # OAuth routes (if web UI)
│   └── templates/
├── database/
│   ├── __init__.py
│   └── db.py           # SQLite with migrations
└── migrations/
    └── 001_*.py        # Database migrations
```

### app.py Initialization Pattern

Every bot's app.py MUST start with sys.path setup to access shared modules:

```python
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Now safe to import from shared/
from flask import Flask
from config import config
```

### Required Endpoints (/health and /info)

Every bot MUST expose these endpoints at the root level:

```python
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version
    })

@app.route('/info')
def info():
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': '🩺',  # Each bot has a unique emoji
        'endpoints': {
            'web': {'GET /': 'Dashboard'},
            'api': {'GET /api/bots': 'List bots'},
            'system': {'GET /health': 'Health check'}
        }
    })
```

## Authentication Patterns

### IMPORTANT: All Bots Require OAuth

**POLICY**: Every bot MUST require Google OAuth login for ALL web routes. No bot should be accessible to people outside the organization.

- **Customer-facing routes** (like Juno's `/track/<code>`) are the ONLY exception
- All admin/dashboard/management routes MUST use `@login_required`
- Use `allowed_domains` from `shared/config/organization.yaml` to restrict to company staff

When creating a new bot with a web UI:
1. Add `services/auth.py` compatibility layer (copy from any existing bot)
2. Initialize `GatewayAuth` in `app.py` (handles /login, /auth/callback, /logout automatically)
3. Apply `@login_required` to ALL web routes
4. Add `auth: mode: grant` to config.yaml (or `domain` for standalone auth)
5. Add `allowed_domains` property to config.py (loads from organization.yaml)

### API Authentication (bot-to-bot)
- Use `@api_key_required` decorator from `shared.auth.bot_api`
- Bots call each other with `X-API-Key` header
- Key stored in `BOT_API_KEY` env var

**Current limitation**: All bots share a single `BOT_API_KEY`. This works well for internal bot-to-bot communication, but if an external service needs API access, they would receive the same key that grants access to all bots.

**Future enhancement**: Support per-service API keys via `EXTERNAL_API_KEYS` environment variable. This would allow:
- Issuing unique keys to external services
- Revoking individual keys without affecting other services
- Tracking which service made each request
- Format: `EXTERNAL_API_KEYS=service1:key1,service2:key2`

Until this is implemented, be cautious about sharing `BOT_API_KEY` with external services.

### Dashboard Calling API Endpoints

When a bot's web UI needs to call its own API endpoints (e.g., a "Sync" button that calls `/api/sync`), use `@api_or_session_auth` from `shared.auth.bot_api`:

```python
from shared.auth.bot_api import api_or_session_auth

@api_bp.route('/bots/sync', methods=['POST'])
@api_or_session_auth
def sync_bots():
    """Callable from dashboard (session) or other bots (API key)"""
    result = sync_service.sync_from_chester()
    return jsonify(result)
```

This decorator allows either:
- **API key** (`X-API-Key` header) - for bot-to-bot calls from Skye, etc.
- **Session auth** - for calls from the bot's own web UI (user is logged in)

Use this instead of `@api_key_required` when the endpoint will be called from dashboard buttons/AJAX.

### Web UI Authentication (GatewayAuth - Centralized OAuth)

**How GatewayAuth works:**

All bots use Chester as a centralized OAuth gateway. When a user tries to access a protected route:
1. Bot redirects user to Chester's `/auth/gateway?return_to=<bot_url>`
2. Chester handles Google OAuth (login page, callback, etc.)
3. Chester creates a signed JWT with user info and redirects back to the bot
4. Bot validates the JWT and creates a session

**Benefits:**
- Only Chester needs Google Cloud Console redirect URIs configured
- Adding new bots requires NO changes to Google Cloud Console
- Centralized auth logic - fixes/updates apply to all bots automatically
- Simpler bot code - just use GatewayAuth, no OAuth complexity per bot

**Google Cloud Console setup (Chester only):**
- `http://localhost:8008/auth/callback` (development)
- `https://chester.watsonblinds.com.au/auth/callback` (production)

### GatewayAuth Setup for New Bots

**Step 1: Add `auth` property to config.py:**

```python
@property
def auth(self):
    """Auth config for GatewayAuth."""
    return {
        'mode': 'grant',  # Options: 'grant', 'domain', 'admin_only', or 'tiered'
        'allowed_domains': self.allowed_domains,
        'admin_emails': self.admin_emails,
    }
```

**Auth modes:**
- `'grant'` - **Recommended** - Use Grant bot for centralized authorization (falls back to domain check if Grant unavailable)
- `'domain'` - Anyone from allowed_domains can access (standalone auth)
- `'admin_only'` - Only emails in admin_emails can access
- `'tiered'` - Domain users get access, admin_emails get extra admin features

**Step 2: Initialize GatewayAuth in app.py:**

```python
from shared.auth import GatewayAuth

# After creating Flask app and setting secret_key...
auth = GatewayAuth(app, config)

# Store auth instance in services.auth for backward compatibility with routes
import botname.services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user
```

**Step 3: Create services/auth.py stub:**

```python
"""
Authentication compatibility layer for BotName.

Auth is handled by GatewayAuth in app.py, which injects the actual
decorators into this module at runtime for backward compatibility
with routes that import from here.
"""

# These get set at runtime by app.py via GatewayAuth
auth = None
login_required = None
admin_required = None
get_current_user = None
```

**Step 4: Use decorators in routes:**

```python
from services.auth import login_required, admin_required

@web_bp.route('/')
@login_required
def index():
    return render_template('index.html')
```

### Allowed Domains

**IMPORTANT**: Allowed domains are centralized in `shared/config/organization.yaml`.

- GatewayAuth automatically loads domains from organization.yaml when `auth.allowed_domains` is not specified
- Do NOT duplicate domains in each bot's config.yaml
- Only override `allowed_domains` in a bot's config if it has special requirements (rare)

### Key auth files to copy from:
- `skye/app.py` - GatewayAuth initialization pattern
- `skye/services/auth.py` - Stub pattern
- `skye/config.py` - Config with `auth` property

### Chester's Direct OAuth (Exception)

Chester is the ONLY bot that uses direct Google OAuth (via `init_auth()`), because it IS the auth gateway. All other bots use GatewayAuth which delegates to Chester.

## Configuration Patterns

### config.py must:
1. Import shared env loader: `from shared.config.env_loader import SHARED_ENV  # noqa: F401`
2. Load bot's config.yaml
3. Load admin_emails from `{BOT}_ADMIN_EMAILS` env var OR `admin.emails` in config.yaml (optional when using Grant mode)
4. Load allowed_domains from `shared/config/organization.yaml`
5. Ensure admin_emails defaults to `[]` not `None` (use `or []` since YAML returns None for empty/commented lists)

### Environment variables:
- Shared vars in `/bot-team/.env` (loaded by all bots via `shared/config/env_loader.py`)
- Bot-specific vars in `/bot-name/.env`
- Always provide `.env.example`

**IMPORTANT**: Bot `.env.example` files should only contain bot-specific variables!
Do NOT include shared variables like:
- `BOT_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `CHESTER_API_URL`

These are already in `/bot-team/.env` and loaded automatically. Just add a comment pointing to the root .env:
```
# Bot-specific environment variables
# Shared variables (BOT_API_KEY, GOOGLE_CLIENT_ID, etc.) are in /bot-team/.env
```

## Database Patterns

**CRITICAL**: All bots MUST use the shared migration framework!

- SQLite databases in `database/bot.db`
- Use `shared.migrations.MigrationRunner` for schema management
- Migrations in `migrations/001_name.py` with `up(conn)` and `down(conn)` functions
- **Migrations run automatically on bot startup** - just restart the bot in prod to apply DB changes
- Never manually modify database schema - always create a migration file

Example migration file (`migrations/002_add_status_column.py`):
```python
def up(conn):
    conn.execute("ALTER TABLE bots ADD COLUMN status TEXT DEFAULT 'unknown'")

def down(conn):
    # SQLite doesn't support DROP COLUMN easily, so often left empty
    pass
```

## Key Shared Modules

- `shared/auth/` - Authentication module (see below)
- `shared/error_handlers.py` - Standard 404/500 error handlers
- `shared/http_client.py` - BotHttpClient for bot-to-bot calls
- `shared/config/env_loader.py` - Loads shared .env
- `shared/config/organization.yaml` - Company domains for auth
- `shared/config/ports.py` - Port lookup from Chester's config
- `shared/migrations/` - Database migration framework

### Shared Error Handlers (`shared/error_handlers.py`)

All bots use standardized error handlers for consistent API responses. The module provides a `register_error_handlers()` function that registers 404 and 500 handlers.

**Usage in app.py:**

```python
import logging
from shared.error_handlers import register_error_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ... register blueprints ...

# Register error handlers (after blueprint registration)
register_error_handlers(app, logger)
```

**What it provides:**

- **404 handler**: Returns `{'error': 'Not found'}` with status 404
- **500 handler**: Logs the error with `exc_info=True` and returns `{'error': 'Internal server error'}` with status 500

**IMPORTANT**: Always pass a logger to ensure 500 errors are logged with full tracebacks.

### Shared Auth Module (`shared/auth/`)

The shared auth module eliminates code duplication across bots. Import from `shared.auth`:

```python
from shared.auth import User, login_required, admin_required
from shared.auth import is_email_allowed, is_email_allowed_by_domain, is_email_allowed_by_list
from shared.auth import api_key_required, api_or_session_auth
```

**Components:**

- `User` - Flask-Login compatible user class with optional `is_admin` and `picture` support
- `login_required` - Decorator for routes requiring authentication
- `admin_required` - Decorator for admin-only routes (checks `user.is_admin`)
- `is_email_allowed_by_domain(email, domains)` - Check email against allowed domains
- `is_email_allowed_by_list(email, allowed_list)` - Check email against specific list
- `is_email_allowed(email, domains, admin_emails)` - Combined check
- `api_key_required` - Decorator for API routes requiring `X-API-Key` header
- `api_or_session_auth` - Decorator allowing either API key or logged-in session

**User class with admin support:**

```python
# In user_loader callback
user = User(
    email=user_data['email'],
    name=user_data['name'],
    admin_emails=config.admin_emails  # Enables is_admin property
)
```

## Common Gotchas

1. **GatewayAuth for all bots except Chester** - All bots use GatewayAuth which delegates OAuth to Chester. Only Chester has direct Google OAuth. See "GatewayAuth Setup for New Bots" section.

2. **Always use `prompt='select_account'`** in OAuth redirect to force account selection.

3. **Blueprint registration** - Auth blueprint at root level:
   ```python
   app.register_blueprint(auth_bp)  # No url_prefix
   ```

4. **ProxyFix required** for production (nginx):
   ```python
   from werkzeug.middleware.proxy_fix import ProxyFix
   app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
   ```

5. **New bots need**: Entry in Chester's config.yaml, proper port assignment

6. **Don't duplicate shared env vars** - Bot `.env.example` should NOT include `BOT_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc. These are in the root `.env`.

7. **Never hardcode ports** - Ports are ONLY defined in Chester's `config.yaml`. Use `shared/config/ports.py` or query Chester's API to get ports dynamically.

8. **Gunicorn: 1 worker only** - In production, all bots run with a single Gunicorn worker (`--workers 1`). This avoids concurrency issues with SQLite and shared state. The bot team doesn't have enough traffic to need multiple workers.

9. **Always use migrations** - Never create database tables manually or outside the migration framework. Use `shared.migrations.MigrationRunner`. Migrations run automatically on startup, so prod DB changes just need a bot restart.

10. **Always use BotHttpClient for bot-to-bot calls** - Never use raw `requests.get/post()` when calling other bots. Use `shared.http_client.BotHttpClient` which automatically adds the `X-API-Key` header. Raw requests will fail authentication.

11. **Always read files before writing** - When using Claude Code to edit files, ALWAYS read the file first before attempting to write or edit it. The Write and Edit tools will fail if the file hasn't been read in the current session. This applies even if you've seen the file contents in a previous message.

## Testing

**IMPORTANT**: Test coverage is critical for maintaining a healthy codebase.

- Tests in `/tests/unit/` and `/tests/integration/`
- Run with `pytest tests/` or `pytest -m botname`
- Markers defined in `pytest.ini`

### Test Requirements

1. **All tests must pass** - Before committing, run `pytest tests/` to ensure nothing is broken
2. **New functionality needs tests** - Every new feature, endpoint, or service method should have corresponding tests
3. **Bug fixes need tests** - When fixing a bug, add a test that would have caught it
4. **Review existing tests** - When modifying a bot, check its test coverage and add missing tests

### What to Test

- **API endpoints**: Test both success and error cases, authentication requirements
- **Service methods**: Test business logic, edge cases, error handling
- **Database operations**: Use `tmp_path` fixture for isolated test databases
- **Authentication**: Test that protected routes require auth, admin routes require admin

### Running Tests

```bash
# Run all tests
pytest tests/

# Run tests for a specific bot
pytest -m hugo

# Run with verbose output
pytest -v tests/

# Run specific test file
pytest tests/unit/test_hugo_service.py
```

### Test Setup (conftest.py)

Environment variables MUST be set BEFORE importing bot modules:

```python
import os
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'  # Skip .env validation
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'

# NOW safe to import bot modules
from mybot.services.database import Database
```

Use `tmp_path` fixture for isolated test databases:

```python
def test_something(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    # Test with isolated DB
```

## Bot Communication

Bots discover each other via Chester:
- `GET /api/bots` - List all bots
- Each bot exposes `/health` and `/info` endpoints

### BotHttpClient (for inter-bot calls)

**CRITICAL**: Always use `BotHttpClient` for bot-to-bot API calls. Never use raw `requests`.

`BotHttpClient` automatically:
- Adds `X-API-Key` header for authentication
- Handles URL joining (no double slashes)
- Provides sensible timeout defaults

```python
from shared.http_client import BotHttpClient

# Create client for a specific bot
client = BotHttpClient("http://localhost:8008", timeout=30)

# Available methods (all add X-API-Key automatically)
response = client.get("/api/bots")
response = client.get("/api/staff", params={'name': 'John'})
response = client.post("/api/users", json={'email': 'test@example.com'})
response = client.patch(f"/api/users/{user_id}", json={'suspended': True})
response = client.put("/api/config", json={'setting': 'value'})
response = client.delete(f"/api/users/{user_id}")
```

**Pattern for orchestrator services:**

```python
from shared.http_client import BotHttpClient

class OrchestrationService:
    def _get_bot_client(self, bot_name: str, timeout: int = 30) -> BotHttpClient:
        """Get a BotHttpClient for the specified bot."""
        return BotHttpClient(self._get_bot_url(bot_name), timeout=timeout)

    def call_fred(self, email: str):
        fred = self._get_bot_client('fred')
        response = fred.post('/api/users', json={'email': email})
        return response.json()
```

**Why not raw requests?** Using `requests.get()` directly will fail authentication because the `X-API-Key` header won't be included.

## Service Layer Pattern

Services should use consistent logging and error handling:

```python
import logging
logger = logging.getLogger(__name__)

class SyncService:
    def sync_bots(self) -> dict:
        logger.info("Starting sync...")

        try:
            # Do work
            logger.info(f"Synced {count} bots")
            return {'success': True, 'bots_synced': count}

        except requests.exceptions.ConnectionError:
            error = "Could not connect to Chester"
            logger.warning(error)
            return {'success': False, 'error': error}

        except Exception as e:
            logger.exception(f"Sync failed: {e}")
            return {'success': False, 'error': str(e)}
```

Key patterns:
- Return dicts with `success` boolean and `error` message on failure
- Use `logger.warning()` for recoverable issues (connection failures)
- Use `logger.exception()` for unexpected errors (includes traceback)

## Timestamp Display Patterns

**IMPORTANT**: Use relative times ("2 hours ago") for all timestamps in the UI unless there's a specific reason to show an absolute time.

### Relative Times (Default)

For activity logs, sync history, last updated times, etc., use the `time_ago()` context processor pattern:

```python
# In web/routes.py
from datetime import datetime, timezone

@web_bp.context_processor
def utility_processor():
    """Add utility functions to Jinja templates."""

    def time_ago(dt_str):
        """Get human-readable relative time string."""
        if not dt_str:
            return 'Never'
        try:
            if isinstance(dt_str, str):
                # SQLite format: "2024-01-15 10:30:00"
                if 'T' not in dt_str and ' ' in dt_str:
                    dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                dt = dt_str

            delta = datetime.now(timezone.utc) - dt
            seconds = delta.total_seconds()

            if seconds < 60:
                return 'Just now'
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f'{minutes} min{"s" if minutes != 1 else ""} ago'
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f'{hours} hour{"s" if hours != 1 else ""} ago'
            elif seconds < 604800:  # 7 days
                days = int(seconds / 86400)
                return f'{days} day{"s" if days != 1 else ""} ago'
            else:
                return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError, TypeError):
            return str(dt_str)[:16] if dt_str else 'Never'

    return dict(time_ago=time_ago)
```

**Usage in templates:**

```html
<!-- Show relative time with full timestamp on hover -->
<td class="text-muted" title="{{ entry.performed_at }}" style="white-space: nowrap; cursor: help;">
    {{ time_ago(entry.performed_at) }}
</td>
```

### When to Use Absolute Times

Use absolute times only when:
- Scheduling future events (job schedules, appointments)
- Legal/audit requirements need exact timestamps
- User explicitly requests "show full date"

When showing absolute times, **always use local time** (convert from UTC on the client side if needed).

### Reference Implementation

See `hugo/web/routes.py` for the full `time_ago()` implementation and `hugo/web/templates/sync.html` for template usage.

## UI/UX Patterns

### No JavaScript Popups

**CRITICAL**: Never use JavaScript `alert()`, `confirm()`, or `prompt()` dialogs.

Instead, always use:
- **Flash messages** for notifications (success, error, info)
- **Inline divs** for confirmation dialogs or forms
- **HTML error pages** for error states (see `shared/error_handlers.py`)

Flash message example:
```python
from flask import flash
flash('Job queued successfully', 'success')  # Types: success, error, info, warning
```

For confirmations, use a form with a submit button, not `confirm()`:
```html
<!-- Good: Inline form -->
<form method="post" action="/delete/123">
    <p>Are you sure you want to delete this item?</p>
    <button type="submit" class="btn btn-danger">Delete</button>
    <a href="/cancel" class="btn">Cancel</a>
</form>

<!-- Bad: JavaScript confirm -->
<button onclick="if(confirm('Delete?')) ...">Delete</button>
```

### Error Display

Use `shared/error_handlers.py` which provides:
- JSON responses for API requests (detects `X-API-Key` header or `Accept: application/json`)
- Clean HTML error pages for browser requests (div-based, no popups)
- Handlers for: 400, 401, 403, 404, 405, 408, 429, 500, 502, 503, 504

## Bot-Specific Notes

For the full list of bots and their ports, see `/chester/config.yaml`. Here are important notes for key bots:

### Chester - The Concierge
- **Single source of truth** for all bot metadata (ports, descriptions, capabilities)
- All bots discover each other through Chester's `/api/bots` endpoint
- `config.yaml` contains the `bot_team:` registry - this is where ports live
- If you need a bot's port, query Chester or use `shared/config/ports.py`

### Skye - Task Scheduler
- Runs scheduled jobs for the entire bot team
- Good template for new bots with web UI and auth

**How Skye jobs work:**

Jobs are stored in Skye's SQLite database and managed via its web UI or API. However, you can define **job templates** in `skye/config.yaml` under `job_templates:` - these are automatically seeded to the database on first startup.

```yaml
# skye/config.yaml
job_templates:
  hugo_sync:
    name: "Hugo Buz User Sync"
    description: "Sync user data from Buz to Hugo's cache"
    target_bot: "hugo"
    endpoint: "/api/users/sync"
    method: "POST"
    schedule:
      type: "cron"
      hour: "6"
      minute: "0"
```

**Key points:**
- Templates are seeded on Skye startup (idempotent - skips if job already exists)
- After seeding, jobs are managed in the database (edits via UI persist)
- To add a new scheduled job: add it to `job_templates` in config.yaml, restart Skye
- Jobs call bot APIs using `BotHttpClient` with automatic `X-API-Key` auth
- Target bot endpoints should use `@api_or_session_auth` to allow both Skye calls and dashboard buttons

### Doc - Bot Health Checker
- **Designed to be standalone** - must work even when other bots are down
- Has its own SQLite database with a local copy of the bot registry
- Skye runs a sync job to keep Doc's registry updated from Chester
- Does NOT hardcode ports - uses its local DB (synced from Chester)
- Uses Grant mode for authorization (access managed via Grant's UI)
- Runs health checks and test suites against other bots

### Dorothy - Deployment Orchestrator
- Deploys bots to production via SSH
- Uses templates from `/dorothy/templates/` for nginx and gunicorn configs
- `nginx.conf.template` - HTTP base config (certbot adds SSL)
- `gunicorn.service.template` - systemd service (already has `--workers 1`)

### Peter - Staff Directory
- Central HR database for staff information
- Other bots query Peter for employee data

### Fred & Iris - Google Workspace
- Fred: User provisioning and management
- Iris: Reporting and analytics
- Both require Google Workspace API credentials

### Oscar & Olive - Staff Lifecycle
- Oscar: Onboarding new staff
- Olive: Offboarding departing staff
- Orchestrate actions across multiple bots

### Zac & Sadie - Zendesk
- Zac: User management in Zendesk
- Sadie: Ticket management
- Both require Zendesk API credentials

### Grant - Centralized Authorization Manager
- **Single source of truth** for bot access permissions
- Replaces per-bot `{BOT}_ADMIN_EMAILS` environment variables
- Stores who can access which bots and with what role (user/admin)
- Web UI for managing permissions across all bots
- API for bots to check permissions at login via `auth: mode: grant`
- Audit trail of all permission changes
- **Superadmins** (set via `GRANT_SUPERADMINS` env var) always have admin access to all bots
- Falls back to domain-based auth if Grant is unavailable

**Using Grant mode:**
1. Set `auth: mode: grant` in your bot's config.yaml
2. Mark `{BOT}_ADMIN_EMAILS` as optional in `.env.example` (comment it out, add "optional" to description)
3. Grant checks permissions via `/api/access?email=x&bot=y`
4. Permissions are cached for 5 minutes to reduce API calls

**Important:** When using Grant mode, the `{BOT}_ADMIN_EMAILS` env var becomes optional because Grant handles authorization centrally. The env validator reads `.env.example` and requires any uncommented variable unless "optional" appears in its description.

## Quick Start for New Bot

1. **Pick a human name** - All bots are named like team members (Fred, Iris, Chester, Skye, Doc, etc.). No generic names like "tracker" or "journey".
2. Copy structure from similar bot (Skye is a good template)
3. Add to Chester's config.yaml with next available port
4. Create config.py loading shared patterns
5. **Set up OAuth** - REQUIRED!
   - Copy `services/auth.py` compatibility layer from any existing bot
   - Initialize `GatewayAuth(app, config)` in app.py
   - Add `auth: mode: grant` to config.yaml (preferred - uses centralized authorization via Grant)
6. **Apply `@login_required`** to ALL web routes (except customer-facing public pages)
7. **Register error handlers** - Add `register_error_handlers(app, logger)` after blueprint registration
8. Create database with migrations (if needed)
9. Add `.env.example` - mark `{BOT}_ADMIN_EMAILS` as optional if using Grant mode
10. **Write tests** - Create `tests/unit/test_<botname>_*.py` with tests for services, API endpoints, and database operations. Run `pytest tests/` to ensure all tests pass.

**Note:** No Google Cloud Console changes needed! GatewayAuth uses Chester for OAuth, so only Chester's redirect URIs need to be configured.
