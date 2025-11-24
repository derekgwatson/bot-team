"""
Settings service for Quinn
Stores sync mode and managers list in a JSON file
"""
import json
import os
from threading import Lock

# Settings file path (in quinn directory)
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')

# Default settings
DEFAULT_SETTINGS = {
    'sync_mode': 'manual',  # 'manual' or 'auto'
    'managers': []  # List of manager emails (Watson addresses allowed to send to allstaff)
}

# Thread-safe lock for file operations
_lock = Lock()


def _load_settings():
    """Load settings from JSON file"""
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Merge with defaults to handle missing keys
            settings = DEFAULT_SETTINGS.copy()
            settings.update(data)
            return settings
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()


def _save_settings(settings):
    """Save settings to JSON file"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)


def get_sync_mode():
    """Get current sync mode ('manual' or 'auto')"""
    with _lock:
        settings = _load_settings()
        return settings.get('sync_mode', 'manual')


def set_sync_mode(mode):
    """
    Set sync mode

    Args:
        mode: 'manual' or 'auto'

    Returns:
        True if successful, False if invalid mode
    """
    if mode not in ('manual', 'auto'):
        return False

    with _lock:
        settings = _load_settings()
        settings['sync_mode'] = mode
        _save_settings(settings)
        return True


def get_managers():
    """Get list of manager emails"""
    with _lock:
        settings = _load_settings()
        return settings.get('managers', [])


def add_manager(email):
    """
    Add a manager email

    Args:
        email: Email address to add

    Returns:
        True if added, False if already exists
    """
    email = email.lower().strip()
    with _lock:
        settings = _load_settings()
        managers = settings.get('managers', [])

        if email in [m.lower() for m in managers]:
            return False

        managers.append(email)
        settings['managers'] = managers
        _save_settings(settings)
        return True


def remove_manager(email):
    """
    Remove a manager email

    Args:
        email: Email address to remove

    Returns:
        True if removed, False if not found
    """
    email = email.lower().strip()
    with _lock:
        settings = _load_settings()
        managers = settings.get('managers', [])

        # Find and remove (case-insensitive)
        for i, m in enumerate(managers):
            if m.lower() == email:
                managers.pop(i)
                settings['managers'] = managers
                _save_settings(settings)
                return True

        return False


def is_manager(email):
    """Check if email is a manager"""
    email = email.lower().strip()
    managers = get_managers()
    return email in [m.lower() for m in managers]
