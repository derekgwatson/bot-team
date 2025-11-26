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

When creating a new bot:
1. Add `services/auth.py` (copy from any existing bot)
2. Add `web/auth_routes.py` with `/login`, `/auth/callback`, `/logout`
3. Apply `@login_required` to ALL web routes
4. Add `allowed_domains` property to config.py (loads from organization.yaml)

### API Authentication (bot-to-bot)
- Use `@api_key_required` decorator from `shared.auth.bot_api`
- Bots call each other with `X-API-Key` header
- Key stored in `BOT_API_KEY` env var

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

### Web UI Authentication (Google OAuth)

**How shared OAuth works:**

Google Cloud Console needs **2 authorized redirect URIs per bot**:
- `http://localhost:<port>/auth/callback` (development)
- `https://<bot>.watsonblinds.com.au/auth/callback` (production)

For example, Doc (port 8023) needs:
- `http://localhost:8023/auth/callback`
- `https://doc.watsonblinds.com.au/auth/callback`

All bots share the same OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` from root `.env`).

**CRITICAL**: Every bot must use the path `/auth/callback` (not `/callback`):

```python
# In auth_routes.py - THIS PATH IS CRITICAL
@auth_bp.route('/auth/callback')  # NOT just '/callback'!
def callback():
    ...
```

Auth pattern (follow Skye as template):
1. `services/auth.py` - OAuth setup, User class, decorators
2. `web/auth_routes.py` - /login, /auth/callback, /logout routes
3. Config loads `admin_emails` from env or config.yaml
4. Config loads `allowed_domains` from `shared/config/organization.yaml`

### Key auth files to copy from:
- `skye/services/auth.py` - Clean auth service pattern
- `skye/web/auth_routes.py` - OAuth routes
- `skye/config.py` - Loading admin_emails and allowed_domains

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
- `shared/http_client.py` - BotHttpClient for bot-to-bot calls
- `shared/config/env_loader.py` - Loads shared .env
- `shared/config/organization.yaml` - Company domains for auth
- `shared/config/ports.py` - Port lookup from Chester's config
- `shared/migrations/` - Database migration framework

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

**Usage in auth.py:**

```python
from shared.auth import User
from shared.auth.decorators import login_required, admin_required
from shared.auth.email_check import is_email_allowed_by_domain

def is_email_allowed(email):
    """Bot-specific wrapper using shared function"""
    return is_email_allowed_by_domain(email, config.allowed_domains)
```

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

1. **OAuth callback must be `/auth/callback`** - Not `/callback`! All bots share Chester's registered redirect URI.

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
4. Create config.py loading shared patterns (include `allowed_domains` from organization.yaml)
5. **Set up OAuth** - REQUIRED! Copy `services/auth.py` and `web/auth_routes.py` from any existing bot
6. **Apply `@login_required`** to ALL web routes (except customer-facing public pages)
7. Create database with migrations
8. Add `.env.example`
