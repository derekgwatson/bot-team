# Claude Reference Guide for Bot-Team

Quick reference for working on this codebase. Read this first!

## Project Overview

Bot-team is a collection of Flask-based microservices ("bots") that handle various business functions for Watson Blinds. Each bot runs on its own port and communicates via REST APIs.

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

## Authentication Patterns

### API Authentication (bot-to-bot)
- Use `@api_key_required` decorator from `shared.auth.bot_api`
- Bots call each other with `X-API-Key` header
- Key stored in `BOT_API_KEY` env var

### Web UI Authentication (Google OAuth)

**How shared OAuth works:**

Google Cloud Console only has **2 authorized redirect URIs**:
- `http://localhost:8008/auth/callback` (development - Chester's port)
- `https://chester.watsonblinds.com.au/auth/callback` (production)

All bots share the same OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` from root `.env`).

In production, nginx routes all bot subdomains through Chester for OAuth:
- User visits `doc.watsonblinds.com.au` → clicks login
- OAuth redirects through `chester.watsonblinds.com.au/auth/callback`
- After auth, user is redirected back to the original bot

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

- SQLite databases in `database/bot.db`
- Use `shared.migrations.MigrationRunner` for schema management
- Migrations in `migrations/001_name.py` with `up(conn)` and `down(conn)` functions

## Key Shared Modules

- `shared/auth/bot_api.py` - `@api_key_required` decorator
- `shared/config/env_loader.py` - Loads shared .env
- `shared/config/organization.yaml` - Company domains for auth
- `shared/config/ports.py` - Port lookup from Chester's config
- `shared/migrations/` - Database migration framework

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

## Testing

- Tests in `/tests/unit/` and `/tests/integration/`
- Run with `pytest tests/` or `pytest -m botname`
- Markers defined in `pytest.ini`

## Bot Communication

Bots discover each other via Chester:
- `GET /api/bots` - List all bots
- Each bot exposes `/health` and `/info` endpoints
- Use `shared/http_client.py` `BotHttpClient` for inter-bot calls

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

1. Copy structure from similar bot (Skye is a good template)
2. Add to Chester's config.yaml with next available port
3. Create config.py loading shared patterns
4. Set up auth following the `/auth/callback` pattern
5. Create database with migrations
6. Add `.env.example`
