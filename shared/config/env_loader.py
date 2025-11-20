# shared/config/env_loader.py
from pathlib import Path
from dotenv import load_dotenv
import os
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]  # points to bot-team/
SHARED_ENV = ROOT_DIR / ".env"

# Load shared env once, without overriding per-bot values
load_dotenv(SHARED_ENV, override=False)

# Validate environment variables on import
# This ensures validation happens early in the startup process
# Set SKIP_ENV_VALIDATION=1 to disable (useful for testing/CI)
if not os.environ.get('SKIP_ENV_VALIDATION'):
    try:
        # Determine which bot is loading this by inspecting the call stack
        import inspect
        bot_name = None

        # Look through the call stack to find which bot's config.py is importing us
        for frame_info in inspect.stack():
            frame_path = Path(frame_info.filename).resolve()
            try:
                # Check if this file is inside a bot directory
                relative = frame_path.relative_to(ROOT_DIR)
                parts = relative.parts

                # Skip if we're in shared or if it's the env_loader itself
                if len(parts) > 0 and parts[0] not in ['shared', 'venv', '.venv']:
                    potential_bot = parts[0]
                    # Verify it's actually a bot directory (has config.py and .env.example)
                    bot_dir = ROOT_DIR / potential_bot
                    if (bot_dir / 'config.py').exists():
                        bot_name = potential_bot
                        break
            except (ValueError, IndexError):
                continue

        # Load bot-specific .env file before validation
        # This ensures validation can check bot-specific variables
        if bot_name:
            bot_env = ROOT_DIR / bot_name / '.env'
            if bot_env.exists():
                load_dotenv(bot_env, override=False)

        # Import validator here to avoid circular imports
        from shared.config.env_validator import validate_env

        # Run validation (non-strict to allow warnings)
        validate_env(bot_name=bot_name, strict=False)

    except Exception as e:
        # If it's an EnvValidationError, show it and exit
        if type(e).__name__ == 'EnvValidationError':
            print(str(e), file=sys.stderr)
            sys.exit(1)
        # For other errors during validation, warn but don't block startup
        print(f"⚠️  Warning: Could not validate environment: {e}", file=sys.stderr)
