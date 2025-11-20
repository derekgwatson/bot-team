# Environment Configuration

This directory contains shared configuration utilities for the bot team.

## Environment Validation

The `env_validator.py` module automatically validates environment variables on startup to ensure all required variables are properly configured.

### How It Works

1. **Automatic Validation**: When any bot starts up, the `env_loader.py` automatically validates environment variables
2. **Smart Filtering**: Only checks variables relevant to the specific bot (e.g., Zac requires Zendesk variables, Sally doesn't)
3. **Clear Error Messages**: Provides detailed, actionable error messages if variables are missing or misconfigured

### What Gets Validated

The validator reads `.env.example` files and:
- Checks that required variables are set
- Filters variables by bot (using "Used by:" comments in `.env.example`)
- Warns about placeholder values (e.g., "your-api-key-here")
- Provides helpful setup instructions

### Disabling Validation

To skip validation (e.g., for testing or CI):

```bash
export SKIP_ENV_VALIDATION=1
python app.py
```

### Manual Validation

You can also validate environment variables manually:

```bash
# Validate a specific bot
python3 -m shared.config.env_validator zac

# Validate only shared environment
python3 -m shared.config.env_validator

# Strict mode (treat warnings as errors)
python3 -m shared.config.env_validator zac --strict
```

### Example Error Output

```
============================================================
❌ Environment Variable Validation Failed
============================================================

ERRORS:

❌ Missing required variable: BOT_API_KEY
   Source: shared .env (bot-team/.env)
   Description: Shared API key for internal bot communication
   Example: BOT_API_KEY=your-secret-bot-api-key-here

============================================================

How to fix:
1. Check your .env files exist:
   - /path/to/bot/.env
   - /path/to/bot-team/.env

2. Copy from .env.example if needed:
   cp /path/to/bot/.env.example /path/to/bot/.env
   cp /path/to/bot-team/.env.example /path/to/bot-team/.env

3. Fill in all required values with your actual credentials

============================================================
```

### Formatting .env.example Files

The validator parses comments in `.env.example` files:

```bash
# ── Section Name (BotA, BotB) ──────────
# Description of this variable
# Used by: BotA, BotB, BotC
VARIABLE_NAME=example-value

# Optional: Description
# NOTE: This is optional
OPTIONAL_VAR=value
```

- **Section headers** with bot names in parentheses: `(Fred, Iris)`
- **Used by** comments: `Used by: Peter, Chester, Pam`
- **Optional markers**: `Optional:`, `NOTE:`, `Only required if`
