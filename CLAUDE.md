# Claude Reference Guide for Bot-Team

Quick reference for working on this codebase. Read this first!

## Project Overview

Bot-team is a collection of Flask-based microservices ("bots") that handle various business functions for Watson Blinds. Each bot runs on its own port and communicates via REST APIs.

## Bot Registry (Chester's config.yaml)

The single source of truth for all bots is `/chester/config.yaml`. When adding a new bot:
1. Add entry to `bot_team:` section with name, port, description, capabilities
2. Port range: 8001-8030 (check for next available)

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
**IMPORTANT**: Only Chester's callback URL is registered in Google Cloud Console!

All bots must use the same OAuth callback path: `/auth/callback`

```python
# In auth_routes.py - THIS IS CRITICAL
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
- Shared vars in `/bot-team/.env` (loaded by all bots)
- Bot-specific vars in `/bot-name/.env`
- Always provide `.env.example`

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

## Testing

- Tests in `/tests/unit/` and `/tests/integration/`
- Run with `pytest tests/` or `pytest -m botname`
- Markers defined in `pytest.ini`

## Bot Communication

Bots discover each other via Chester:
- `GET /api/bots` - List all bots
- Each bot exposes `/health` and `/info` endpoints
- Use `shared/http_client.py` `BotHttpClient` for inter-bot calls

## Current Bots (Port Assignment)

| Port | Bot | Purpose |
|------|-----|---------|
| 8001 | Fred | Google Workspace User Management |
| 8002 | Iris | Google Workspace Reporting |
| 8003 | Peter | Staff Directory (HR Database) |
| 8004 | Sally | SSH Command Executor |
| 8005 | Dorothy | Deployment Orchestrator |
| 8006 | Quinn | External Staff Access |
| 8007 | Zac | Zendesk User Management |
| 8008 | Chester | Bot Team Concierge |
| 8009 | Pam | Phone Directory Web UI |
| 8010 | Sadie | Zendesk Ticket Manager |
| 8011 | Oscar | Staff Onboarding |
| 8012 | Olive | Staff Offboarding |
| 8013 | Rita | Staff Access Requests |
| 8014 | Banji | Buz Browser Automation |
| 8015 | Monica | ChromeOS Monitoring |
| 8016 | Mabel | Email Service |
| 8017 | Mavis | Unleashed Data Integration |
| 8018 | Fiona | Fabric Descriptions |
| 8019 | Scout | System Monitoring |
| 8020 | Skye | Task Scheduler |
| 8021 | Travis | Field Staff Location |
| 8022 | Juno | Customer Tracking |
| 8023 | Nigel | (Reserved) |
| 8024 | Doc | Bot Health Checker |

## Quick Start for New Bot

1. Copy structure from similar bot (Skye is a good template)
2. Add to Chester's config.yaml with next available port
3. Create config.py loading shared patterns
4. Set up auth following the `/auth/callback` pattern
5. Create database with migrations
6. Add `.env.example`
