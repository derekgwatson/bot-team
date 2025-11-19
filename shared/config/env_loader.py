# shared/config/env_loader.py
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]  # points to bot-team/
SHARED_ENV = ROOT_DIR / ".env"

# Load shared env once, without overriding per-bot values
load_dotenv(SHARED_ENV, override=False)
