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
1. Add `auth` property to config.py (see GatewayAuth section below)
2. Add `web/auth_routes.py` with `/login`, `/auth/callback`, `/logout`
3. Initialize GatewayAuth in `app.py` (see GatewayAuth section below)
4. Apply `@login_required` to ALL web routes
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
        'mode': 'domain',  # Options: 'domain', 'admin_only', or 'tiered'
        'allowed_domains': self.allowed_domains,
        'admin_emails': self.admin_emails,
    }
```

**Auth modes:**
- `'domain'` - Anyone from allowed_domains can access
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

### Key auth files to copy from:
- `skye/app.py` - GatewayAuth initialization pattern
- `skye/services/auth.py` - Stub pattern
- `skye/config.py` - Config with `auth` property
- `skye/web/auth_routes.py` - OAuth routes (handles Chester callbacks)

### Chester's Direct OAuth (Exception)

Chester is the ONLY bot that uses direct Google OAuth (via `init_auth()`), because it IS the auth gateway. All other bots use GatewayAuth which delegates to Chester.

## Configuration Patterns

### config.py must:
1. Import shared env loader: `from shared.config.env_loader import SHARED_ENV  # noqa: F401`
2. Load bot's config.yaml
3. Load admin_emails from `{BOT}_ADMIN_EMAILS` env var OR `admin.emails` in config.yaml
4. Load allowed_domains from `shared/config/organization.yaml`

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

- Tests in `/tests/unit/` and `/tests/integration/`
- Run with `pytest tests/` or `pytest -m botname`
- Markers defined in `pytest.ini`

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

## Bot-Specific Notes

For the full list of bots and their ports, see `/chester/config.yaml`. Here are important notes for key bots:

### Chester - The Concierge
- **Single source of truth** for all bot metadata (ports, descriptions, capabilities)
- All bots discover each other through Chester's `/api/bots` endpoint
- `config.yaml` contains the `bot_team:` registry - this is where ports live
- If you need a bot's port, query Chester or use `shared/config/ports.py`

### Skye - Task Scheduler
- Runs scheduled jobs for the entire bot team
- Has a sync job that updates Doc's local bot registry from Chester
- Good template for new bots with web UI and auth

### Doc - Bot Health Checker
- **Designed to be standalone** - must work even when other bots are down
- Has its own SQLite database with a local copy of the bot registry
- Skye runs a sync job to keep Doc's registry updated from Chester
- Does NOT hardcode ports - uses its local DB (synced from Chester)
- Admin-only access (uses `DOC_ADMIN_EMAILS` env var)
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

## Quick Start for New Bot

1. **Pick a human name** - All bots are named like team members (Fred, Iris, Chester, Skye, Doc, etc.). No generic names like "tracker" or "journey".
2. Copy structure from similar bot (Skye is a good template)
3. Add to Chester's config.yaml with next available port
4. Create config.py loading shared patterns (include `allowed_domains`, `admin_emails`, and `auth` property)
5. **Set up GatewayAuth** - REQUIRED! See "GatewayAuth Setup for New Bots" section. Copy from Skye:
   - `app.py` - GatewayAuth initialization
   - `services/auth.py` - Stub file (decorators injected at runtime)
   - `web/auth_routes.py` - Handles Chester auth callbacks
6. **Apply `@login_required`** to ALL web routes (except customer-facing public pages)
7. **Register error handlers** - Add `register_error_handlers(app, logger)` after blueprint registration
8. Create database with migrations (if needed)
9. Add `.env.example`

**Note:** No Google Cloud Console changes needed! GatewayAuth uses Chester for OAuth, so only Chester's redirect URIs need to be configured.
